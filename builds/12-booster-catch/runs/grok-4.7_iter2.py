import math

G = 9.81
T_ENG = 2.75e6
MDOT = 849.0
H_SCALE = 8500.0
V_TGT = -1.75
DRY = 200000.0

mem = {}


def _clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _drag_a(v, h, mass, k):
    if mass <= 1.0 or k <= 0.0:
        return 0.0
    return -(k / mass) * math.exp(-max(h, 0.0) / H_SCALE) * v * abs(v)


def _mass_fuel(tel):
    m = float(tel["mass_kg"])
    f = max(0.0, float(tel["fuel_kg"]))
    dry_if_total = m - f
    if abs(dry_if_total - DRY) <= abs(m - DRY):
        return max(m, 1000.0), f
    return max(m + f, 1000.0), f


def _coast(h, v, mass, k, horizon, dt=0.05):
    t = 0.0
    while t < horizon - 1e-9 and h > 0.0:
        step = min(dt, horizon - t)
        a = -G + _drag_a(v, h, mass, k)
        v2 = v + a * step
        h = h + 0.5 * (v + v2) * step
        v = v2
        t += step
    return h, v


def _ratio(h, v, mass, k, delay, n):
    hh, vv = _coast(h, v, mass, k, delay)
    if hh <= 1.0:
        return 9.0, hh, vv, 40.0
    a_req = (vv * vv - V_TGT * V_TGT) / (2.0 * hh)
    ad = max(0.0, _drag_a(vv, hh, mass, k))
    a_need = a_req - 0.20 * ad
    a_max = n * T_ENG / max(mass, 1.0) - G
    if a_max < 0.6:
        return 9.0, hh, vv, a_need
    return a_need / a_max, hh, vv, a_need


def _sim(h, v, mass, fuel, n, throttle, delay, k, dt=0.05, max_t=42.0):
    n = int(max(0, n))
    throttle = float(_clamp(throttle, 0.0, 1.0))
    dry = mass - fuel
    if dry < 80000.0 or dry > 600000.0:
        dry = DRY
    if mass < dry:
        mass = dry + max(fuel, 0.0)
    t = 0.0
    steps = 0
    limit = int(max_t / dt) + 2
    while steps < limit:
        steps += 1
        if h <= 0.0:
            return {"impact_v": v, "rev_h": None, "climbed": False, "t": t, "fuel": fuel}
        lit = (t >= delay - 1e-9) and n > 0 and fuel > 1.0
        if lit:
            thrust = n * T_ENG * throttle
            mdot = n * MDOT * throttle
        else:
            thrust = 0.0
            mdot = 0.0
        a = -G + thrust / max(mass, 1.0) + _drag_a(v, h, mass, k)
        v2 = v + a * dt
        h2 = h + 0.5 * (v + v2) * dt
        mass = max(dry, mass - mdot * dt)
        fuel = max(0.0, fuel - mdot * dt)
        t += dt
        if lit and v < 0.0 <= v2 and h2 > 1.2:
            frac = (0.0 - v) / (v2 - v) if v2 != v else 1.0
            rh = h + (h2 - h) * max(0.0, min(1.0, frac))
            return {"impact_v": 0.0, "rev_h": rh, "climbed": True, "t": t - dt * (1.0 - frac), "fuel": fuel}
        if h > 0.0 >= h2:
            denom = h - h2
            frac = h / denom if denom != 0.0 else 1.0
            frac = _clamp(frac, 0.0, 1.0)
            iv = v + (v2 - v) * frac
            return {"impact_v": iv, "rev_h": None, "climbed": False, "t": t - dt * (1.0 - frac), "fuel": fuel}
        h, v = h2, v2
    if h > 0.0 and v < 0.0:
        return {"impact_v": -280.0, "rev_h": None, "climbed": False, "t": t, "fuel": fuel}
    return {"impact_v": v, "rev_h": h, "climbed": h > 2.0 and v >= 0.0, "t": t, "fuel": fuel}


def _solve(h, v, mass, fuel, n, delay, k):
    dt = 0.025 if h < 90.0 else (0.04 if h < 500.0 else 0.06)
    r_full = _sim(h, v, mass, fuel, n, 1.0, delay, k, dt)
    if r_full["climbed"] and (r_full["rev_h"] or 0.0) > 220.0:
        return 0.4, "early", r_full
    if (not r_full["climbed"]) and r_full["impact_v"] < -3.4:
        return 1.0, "late", r_full
    r_min = _sim(h, v, mass, fuel, n, 0.4, delay, k, dt)
    if r_min["climbed"] and (r_min["rev_h"] or 0.0) > 18.0 and r_full["climbed"] and (r_full["rev_h"] or 0.0) > 40.0:
        return 0.4, "early", r_full
    lo, hi = 0.4, 1.0
    best_f, best_r = 1.0, r_full
    for _ in range(7):
        mid = 0.5 * (lo + hi)
        r = _sim(h, v, mass, fuel, n, mid, delay, k, dt)
        too_much = r["climbed"] or r["impact_v"] > V_TGT
        if too_much:
            hi = mid
        else:
            lo = mid
            best_f, best_r = mid, r
    if best_r["climbed"] or best_r["t"] > 16.0:
        if r_full["climbed"] and (r_full["rev_h"] or 0.0) > 30.0:
            return 0.4, "early", r_full
    if (not best_r["climbed"]) and best_r["impact_v"] < -3.6 and best_f > 0.92:
        return 1.0, "late", best_r
    return best_f, "ok", best_r


def pilot(tel):
    t = float(tel["t"])
    h = float(tel["altitude_m"])
    dist = float(tel["distance_to_tower_m"])
    v = float(tel["vertical_speed_ms"])
    vs = float(tel["sideways_speed_ms"])
    tilt_now = float(tel["tilt_deg"])
    running = int(tel["engines_running"])
    thr_now = float(tel["throttle"])
    tower = tel["tower_health"]
    mass, fuel = _mass_fuel(tel)

    if mem.get("t") is not None and (t < mem["t"] - 0.05 or h > mem.get("h", h) + 1500.0):
        mem.clear()

    dt = 0.1
    if mem.get("t") is not None:
        raw = t - mem["t"]
        if 0.02 < raw < 0.5:
            dt = raw

    k = mem.get("k", 70.0)
    if mem.get("t") is not None and dt > 0.0 and abs(v) > 35.0:
        a_obs = (v - mem["v"]) / dt
        thrust_v = 0.0
        if running > 0:
            thrust_v = running * T_ENG * thr_now * math.cos(math.radians(_clamp(tilt_now, -20.0, 20.0)))
        a_drag = a_obs + G - thrust_v / max(mass, 1.0)
        denom = math.exp(-max(h, 0.0) / H_SCALE) * v * v
        if denom > 80.0:
            ks = a_drag * mass / denom
            if 0.0 <= ks <= 650.0:
                n = mem.get("kn", 0)
                prev = mem.get("k", ks)
                if n < 4 or abs(ks - prev) < max(50.0, 0.55 * prev + 12.0):
                    blend = min(n, 18)
                    k = (prev * blend + ks) / (blend + 1.0)
                    mem["k"] = k
                    mem["kn"] = n + 1
                else:
                    k = prev
        if running > 0:
            mem["ad"] = 0.65 * mem.get("ad", a_drag) + 0.35 * _clamp(a_drag, -5.0, 80.0)
        elif abs(mem.get("fins", 0.0)) < 0.25:
            a_side = (vs - mem["vs"]) / dt
            mem["wind_a"] = 0.86 * mem.get("wind_a", 0.0) + 0.14 * _clamp(a_side, -4.5, 4.5)
        if running > 0:
            a_side = (vs - mem["vs"]) / dt
            expected = -(running * T_ENG * thr_now / max(mass, 1.0)) * math.sin(math.radians(mem.get("tilt", tilt_now)))
            resid = a_side - expected
            mem["wind_a"] = 0.75 * mem.get("wind_a", 0.0) + 0.25 * _clamp(resid, -5.0, 5.0)

    k = _clamp(mem.get("k", k), 0.0, 600.0)
    wind_a = mem.get("wind_a", 0.0)

    if "phase" not in mem:
        mem["phase"] = "coast"
        mem["n_cmd"] = 0
        mem["f"] = 0.7
        mem["spool_t"] = t
        mem["coast_until"] = -1.0
        mem["wind_a"] = 0.0
        mem["lat_i"] = 0.0

    if tower != "OK":
        sign = 1.0 if dist >= 0.0 else -1.0
        if abs(dist) < 0.8:
            sign = 1.0
        eng = 0
        thr = 0.4
        if fuel > 1500.0 and h > 20.0 and h < 6000.0:
            eng = 3 if fuel < 8000.0 or h > 800.0 else 13
            thr = 1.0
        mem["t"] = t
        mem["h"] = h
        mem["v"] = v
        mem["vs"] = vs
        mem["tilt"] = -15.0 * sign
        mem["fins"] = -sign
        mem["phase"] = "abort"
        return {
            "engines": int(eng),
            "throttle": float(thr),
            "tilt": float(-15.0 * sign),
            "fins": float(_clamp(-sign, -1.0, 1.0)),
            "abort": True,
        }

    if h <= 0.0:
        mem["t"] = t
        mem["h"] = h
        mem["v"] = v
        mem["vs"] = vs
        return {"engines": 0, "throttle": 0.4, "tilt": 0.0, "fins": 0.0, "abort": False}

    phase = mem["phase"]
    if phase == "abort":
        phase = "coast"
    n_cmd = int(mem.get("n_cmd", 0))
    if running > 0 and phase == "coast":
        phase = "burn"
        n_cmd = 13 if running > 3 else 3

    if phase == "spool" and running > 0:
        phase = "burn"
    if phase == "burn" and running == 0 and n_cmd == 0:
        phase = "coast"

    delay = 0.0
    if running <= 0:
        if phase == "spool":
            delay = max(0.0, 1.5 - (t - mem.get("spool_t", t)))
        else:
            delay = 1.5

    r3, h2, v2, a_need = _ratio(h, v, mass, k, delay, 3)
    r13, _, _, _ = _ratio(h, v, mass, k, delay, 13)

    # Absolute "still way too high for a suicide burn" gate (the previous failure mode).
    too_high = False
    if running <= 0 and h > 500.0:
        v_est = min(v, -1.0)
        h_suicide = (v_est * v_est) / (2.0 * 16.0) + max(-v_est, 0.0) * 1.5 + 280.0
        if h > h_suicide and r3 < 0.72:
            too_high = True
    if running <= 0 and r3 < 0.36 and h > 80.0:
        too_high = True

    f_cmd = mem.get("f", 0.75)

    if phase == "coast":
        n_cmd = 0
        f_cmd = 0.55
        if (not too_high) and t >= mem.get("coast_until", -1.0) and fuel > 400.0:
            if r3 > 1.12:
                phase = "spool"
                n_cmd = 13
                mem["spool_t"] = t
                f_cmd = 1.0 if r13 > 0.55 else _clamp(0.45 + 0.5 * r13, 0.4, 1.0)
            elif r3 >= 0.50:
                f_s, tag, rs = _solve(h, v, mass, fuel, 3, delay, k)
                if tag == "late":
                    if r13 >= 0.38 or r3 > 1.35:
                        phase = "spool"
                        n_cmd = 13
                        mem["spool_t"] = t
                        f_cmd = 1.0 if r13 > 0.7 else 0.55
                    else:
                        phase = "spool"
                        n_cmd = 3
                        mem["spool_t"] = t
                        f_cmd = 1.0
                elif tag == "ok" and rs["t"] < 15.5 and f_s >= 0.48:
                    if not (rs["climbed"] and (rs["rev_h"] or 0.0) > 25.0):
                        phase = "spool"
                        n_cmd = 3
                        mem["spool_t"] = t
                        f_cmd = f_s
                elif tag == "ok" and r3 > 0.85:
                    phase = "spool"
                    n_cmd = 3
                    mem["spool_t"] = t
                    f_cmd = max(f_s, 0.7)
    elif phase == "spool":
        if running <= 0 and r3 < 0.24 and (t - mem.get("spool_t", t)) < 0.45 and h > 120.0:
            phase = "coast"
            n_cmd = 0
            f_cmd = 0.5
            mem["coast_until"] = t + 0.25
        else:
            n_sol = n_cmd if n_cmd in (3, 13) else 3
            f_s, tag, rs = _solve(h, v, mass, fuel, n_sol, delay, k)
            if tag == "late" and n_cmd < 13 and fuel > 4000.0:
                n_cmd = 13
                f_cmd = 1.0
            elif tag == "early":
                f_cmd = 0.42
            else:
                f_cmd = f_s
            if running <= 0 and (t - mem.get("spool_t", t)) > 2.1:
                n_cmd = 13 if n_cmd == 3 else 3
                mem["spool_t"] = t
                phase = "spool"
    else:
        phase = "burn"
        n_phys = running if running > 0 else (n_cmd if n_cmd > 0 else 3)
        f_s, tag, rs = _solve(h, v, mass, fuel, max(n_phys, 1), 0.0, k)
        # kinematic throttle from measured drag
        cos_t = max(0.72, math.cos(math.radians(tilt_now)))
        a_req = (v * v - V_TGT * V_TGT) / (2.0 * max(h, 0.45))
        if mem.get("burn_t") is None:
            mem["burn_t"] = t
        if (t - mem.get("burn_t", t)) > 0.25 and "ad" in mem:
            ad_up = mem["ad"]
        else:
            ad_up = max(0.0, _drag_a(v, h, mass, k))
        f_kin = (a_req + G - ad_up) * mass / (max(n_phys, 1) * T_ENG * cos_t)
        f_kin = _clamp(f_kin, 0.4, 1.0)
        if tag == "late":
            f_cmd = 1.0
            if n_cmd < 13 and fuel > 2500.0 and h > 18.0:
                n_cmd = 13
        elif tag == "early":
            f_cmd = 0.4
            rev = rs["rev_h"] or 0.0
            if rev > 32.0 and h > 48.0 and running > 0:
                # min throttle still climbs — cut and relight if a later burn can save us
                rel_r = _sim(h, v, mass, fuel, 3, 1.0, 1.5, k, 0.05)
                safe = rel_r["climbed"] or rel_r["impact_v"] > -7.5
                if safe:
                    phase = "coast"
                    n_cmd = 0
                    f_cmd = 0.4
                    mem["coast_until"] = t + 0.35
                    mem["burn_t"] = None
                else:
                    f_cmd = 0.4
        else:
            w = 0.55 if h > 60.0 else 0.35
            f_cmd = w * f_s + (1.0 - w) * f_kin
            if rs["impact_v"] < -2.6 and not rs["climbed"]:
                f_cmd = max(f_cmd, f_s)
            if rs["climbed"] and (rs["rev_h"] or 0.0) > 6.0:
                f_cmd = min(f_cmd, max(0.4, f_s - 0.05))
        # engine-out / shortfall: 3 not enough
        if running > 0 and n_cmd <= 3 and tag == "late" and fuel > 3000.0:
            n_cmd = 13
            f_cmd = 1.0
        if n_cmd >= 13 and running >= 3 and r3 < 0.92 and h > 25.0:
            f3, tag3, r3s = _solve(h, v, mass, fuel, min(running, 3), 0.0, k)
            if tag3 == "ok":
                n_cmd = 3
            elif tag3 == "early" and (r3s["rev_h"] or 0.0) > 25.0 and h > 70.0:
                rel_r = _sim(h, v, mass, fuel, 3, 1.0, 1.5, k, 0.05)
                if rel_r["climbed"] or rel_r["impact_v"] > -6.0:
                    phase = "coast"
                    n_cmd = 0
                    f_cmd = 0.4
                    mem["coast_until"] = t + 0.3
                    mem["burn_t"] = None
        if running > 0 and v > 0.8 and h > 18.0:
            phase = "coast"
            n_cmd = 0
            f_cmd = 0.4
            mem["coast_until"] = t + 0.4
            mem["burn_t"] = None
        if phase == "burn":
            # slew limit except when saturating to save the landing
            prev_f = mem.get("f", f_cmd)
            slew = 0.28 if h < 35.0 else 0.14
            if tag == "late":
                slew = 0.45
            f_cmd = _clamp(f_cmd, prev_f - slew, prev_f + slew)

    if phase == "coast":
        n_out = 0
        f_out = 0.4
    else:
        n_out = 13 if n_cmd > 3 else 3
        f_out = _clamp(f_cmd, 0.4, 1.0)
        if fuel < 30.0:
            n_out = 0
            f_out = 0.4

    # Lateral: fins while falling unpowered, tilt always (pre-slew before light).
    disc = v * v + 2.0 * max(2.5, G - max(_drag_a(v, h, mass, k), 0.0) * 0.45) * max(h, 0.0)
    t_go = (v + math.sqrt(disc)) / max(2.5, G * 0.5) if False else 0.0
    g_eff = max(1.8, G - 0.45 * max(_drag_a(v, h, mass, k), 0.0))
    disc = v * v + 2.0 * g_eff * max(h, 0.0)
    t_go = (v + math.sqrt(max(0.0, disc))) / g_eff
    if t_go < 0.6:
        t_go = 0.6
    prev_tgo = mem.get("t_go", t_go)
    t_go = 0.62 * prev_tgo + 0.38 * t_go
    if h < 400.0:
        mem["lat_i"] = _clamp(mem.get("lat_i", 0.0) + dist * dt, -40.0, 40.0)
    else:
        mem["lat_i"] = mem.get("lat_i", 0.0) * 0.99

    v_lim = 28.0 if h > 180.0 else (10.0 if h > 50.0 else 3.2)
    if h < 30.0:
        v_lim = min(v_lim, 1.3 + 0.06 * h)
    if abs(dist) > 18.0 or (abs(vs) > 5.0 and abs(dist) > 8.0):
        a_max = 2.7
        sign_d = 1.0 if dist >= 0.0 else -1.0
        closing = -vs * sign_d
        stop_d = (closing * closing) / (2.0 * a_max) if closing > 0.4 else 0.0
        if closing > 0.35 and stop_d >= abs(dist) * 0.70:
            a_act = math.copysign(a_max, dist if dist != 0.0 else 1.0)
        else:
            a_act = -math.copysign(a_max, dist if dist != 0.0 else vs)
        a_act -= wind_a
    else:
        v_des = _clamp(-1.55 * dist / max(t_go, 1.05), -v_lim, v_lim)
        if h < 32.0:
            v_des = _clamp(-dist / max(t_go, 1.3), -2.0, 2.0)
        tau = 0.72 if h < 160.0 else 1.05
        a_act = (v_des - vs) / tau - 0.06 * dist - 0.012 * mem.get("lat_i", 0.0) - wind_a
        if abs(dist) > 2.5 and h < 220.0:
            a_act += -0.07 * dist

    if running == 0 and v < -16.0:
        spd = abs(v)
        auth = 3.0 if spd > 90.0 else max(0.30, 3.0 * spd / 90.0)
        fins = _clamp(-a_act / auth, -1.0, 1.0)
    else:
        fins = 0.0

    n_tilt = running if running > 0 else (n_out if n_out > 0 else 3)
    thr_for_tilt = f_out if n_out > 0 or running > 0 else 0.65
    a_avail = max(n_tilt, 1) * T_ENG * max(thr_for_tilt, 0.4) / max(mass, 1.0)
    if h > 70.0:
        tilt_lim = 12.0
    elif h > 20.0:
        tilt_lim = 8.0
    else:
        tilt_lim = 5.5
    if abs(dist) > 3.5 or abs(vs) > 1.4:
        tilt_lim = max(tilt_lim, 7.5 if h > 8.0 else 6.0)
    if f_out > 0.96 and h < 80.0 and v < -8.0:
        tilt_lim = min(tilt_lim, 4.5)
    if h < 12.0 and abs(dist) < 4.5 and abs(vs) < 1.6:
        tilt_lim = min(tilt_lim, 4.0 + 0.25 * h)
    sin_lim = math.sin(math.radians(min(15.0, tilt_lim)))
    sin_t = _clamp(-a_act / max(a_avail, 0.8), -sin_lim, sin_lim)
    tilt = math.degrees(math.asin(sin_t))
    tilt = _clamp(tilt, -tilt_lim, tilt_lim)
    if n_out == 0 and running == 0:
        tilt = _clamp(tilt, -12.0, 12.0)

    mem["phase"] = phase
    mem["n_cmd"] = n_cmd if phase != "coast" else 0
    mem["f"] = f_out
    mem["t_go"] = t_go
    mem["t"] = t
    mem["h"] = h
    mem["v"] = v
    mem["vs"] = vs
    mem["tilt"] = tilt
    mem["fins"] = fins
    mem["k"] = k

    return {
        "engines": int(n_out),
        "throttle": float(_clamp(f_out, 0.4, 1.0)),
        "tilt": float(_clamp(tilt, -15.0, 15.0)),
        "fins": float(_clamp(fins, -1.0, 1.0)),
        "abort": False,
    }
