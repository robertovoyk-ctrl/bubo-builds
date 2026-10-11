import math

G = 9.81
T_ENG = 2.75e6
MDOT = 849.0
V_TGT = -1.7

mem = {}


def _clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _mass_fuel(tel):
    m = float(tel["mass_kg"])
    f = max(0.0, float(tel["fuel_kg"]))
    mode = mem.get("mass_mode")
    if mode is None:
        if f > 5000.0 and m < 215000.0:
            mode = "dry"
        elif m > f + 170000.0:
            mode = "total"
        elif m > 230000.0:
            mode = "total"
        else:
            mode = "dry"
        mem["mass_mode"] = mode
    if mode == "dry":
        return m + f, f
    return max(m, 1000.0), f


def _sim(h, v, mass, fuel, n, delay, thr, k, dt=0.04, tmax=48.0):
    n = int(n)
    thr = float(_clamp(thr, 0.4, 1.0))
    dry = max(mass - max(fuel, 0.0), 50000.0)
    fuel = max(0.0, fuel)
    mass = dry + fuel
    t = 0.0
    steps = 0
    lim = int(tmax / dt) + 3
    while steps < lim:
        steps += 1
        burning = (t + 1e-9 >= delay) and n > 0 and fuel > 0.5
        a_drag = -k * v * abs(v)
        if burning:
            a = n * T_ENG * thr / mass - G + a_drag
            mdot = n * MDOT * thr
        else:
            a = -G + a_drag
            mdot = 0.0
        v2 = v + a * dt
        h2 = h + 0.5 * (v + v2) * dt
        fuel = max(0.0, fuel - mdot * dt)
        mass = dry + fuel
        t2 = t + dt
        if burning and v < 0.0 <= v2 and h > 0.4:
            frac = (0.0 - v) / (v2 - v) if v2 != v else 1.0
            frac = _clamp(frac, 0.0, 1.0)
            h_stop = h + 0.5 * (v + 0.0) * (dt * frac)
            return {"climbed": True, "apex": h_stop, "impact_v": 0.0, "t": t + dt * frac, "fuel": fuel}
        if h > 0.0 >= h2:
            denom = h - h2
            frac = h / denom if denom != 0.0 else 1.0
            frac = _clamp(frac, 0.0, 1.0)
            v_imp = v + (v2 - v) * frac
            return {"climbed": False, "apex": 0.0, "impact_v": v_imp, "t": t + dt * frac, "fuel": fuel}
        if h2 > h + 8.0 and v2 > 2.0:
            return {"climbed": True, "apex": h2, "impact_v": v2, "t": t2, "fuel": fuel}
        h, v, t = h2, v2, t2
        if h < 80.0:
            dt = min(dt, 0.025)
    if h > 0.0 and v >= 0.0:
        return {"climbed": True, "apex": h, "impact_v": v, "t": t, "fuel": fuel}
    return {"climbed": False, "apex": 0.0, "impact_v": v if h <= 0.0 else -80.0, "t": t, "fuel": fuel}


def _solve(h, v, mass, fuel, n, delay, k):
    dt = 0.02 if h < 60.0 else (0.035 if h < 500.0 else 0.055)
    if h > 1500.0:
        dt = 0.07
    res_lo = _sim(h, v, mass, fuel, n, delay, 0.4, k, dt)
    if res_lo["climbed"] and res_lo["apex"] > 2.5:
        return "early", 0.4, res_lo
    if (not res_lo["climbed"]) and res_lo["impact_v"] > -0.45:
        return "early", 0.4, res_lo
    res_hi = _sim(h, v, mass, fuel, n, delay, 1.0, k, dt)
    if (not res_hi["climbed"]) and res_hi["impact_v"] < -3.05:
        return "late", 1.0, res_hi
    lo, hi = 0.4, 1.0
    best_thr, best = 0.7, res_hi
    for _ in range(8):
        mid = 0.5 * (lo + hi)
        res = _sim(h, v, mass, fuel, n, delay, mid, k, dt)
        too_much = res["climbed"] or res["impact_v"] > V_TGT
        if too_much:
            hi = mid
        else:
            lo = mid
            best_thr, best = mid, res
    res_b = _sim(h, v, mass, fuel, n, delay, hi, k, dt)
    if res_b["climbed"] and res_b["apex"] > 3.0:
        return "good", max(0.4, hi - 0.04), best
    return "good", hi, res_b


def _algebraic(h, v, mass, n, k, tilt_deg):
    h_use = max(h, 0.45)
    a_req = (v * v - V_TGT * V_TGT) / (2.0 * h_use)
    a_drag_up = k * v * v
    cos_t = max(0.72, math.cos(math.radians(tilt_deg)))
    n = max(int(n), 1)
    thr = (a_req + G - a_drag_up) * mass / (n * T_ENG * cos_t)
    return _clamp(thr, 0.4, 1.0), a_req


def pilot(tel):
    t = float(tel["t"])
    h = float(tel["altitude_m"])
    x = float(tel["distance_to_tower_m"])
    v = float(tel["vertical_speed_ms"])
    vx = float(tel["sideways_speed_ms"])
    tilt_now = float(tel["tilt_deg"])
    running = int(tel["engines_running"])
    tower = tel["tower_health"]
    wind = float(tel["wind_ms"])
    mass, fuel = _mass_fuel(tel)

    if mem.get("t") is not None and (t < mem["t"] - 0.05 or h > mem.get("h", h) + 2000.0):
        mem.clear()
        mass, fuel = _mass_fuel(tel)

    dt = 0.1
    if mem.get("t") is not None:
        raw = t - mem["t"]
        if 0.02 < raw < 0.5:
            dt = raw

    k = mem.get("k", 9.81 / (300.0 * 300.0))
    if mem.get("t") is not None and abs(v) > 25.0:
        a_obs = (v - mem["v"]) / dt
        thrust_up = 0.0
        if running > 0:
            thr_tel = float(tel["throttle"])
            thrust_up = running * T_ENG * thr_tel * math.cos(math.radians(_clamp(tilt_now, -20.0, 20.0)))
        a_drag_up = a_obs + G - thrust_up / max(mass, 1.0)
        if a_drag_up > -1.5:
            ks = a_drag_up / (v * v)
            if 0.0 <= ks <= 0.0025:
                n_k = mem.get("kn", 0)
                alpha = 0.22 if n_k < 8 else 0.08
                if running > 0:
                    alpha = 0.12
                k = (1.0 - alpha) * k + alpha * ks
                mem["k"] = k
                mem["kn"] = n_k + 1
        if running == 0 and abs(mem.get("fins", 0.0)) < 0.12:
            a_lat = (vx - mem["vx"]) / dt
            mem["wind_a"] = 0.82 * mem.get("wind_a", 0.0) + 0.18 * _clamp(a_lat, -6.0, 6.0)
            mem["wind_n"] = mem.get("wind_n", 0) + 1
        elif running > 0 and abs(tilt_now) < 1.2:
            a_lat = (vx - mem["vx"]) / dt
            mem["wind_a"] = 0.9 * mem.get("wind_a", 0.0) + 0.1 * _clamp(a_lat, -6.0, 6.0)

    k = _clamp(mem.get("k", k), 0.0, 0.0025)
    wind_a = mem.get("wind_a", 0.0)
    if mem.get("wind_n", 0) < 6:
        wind_a = 0.65 * wind_a + 0.35 * (k * abs(v) * wind)

    if tower != "OK":
        sign = 1.0 if x >= 0.0 else -1.0
        if abs(x) < 0.5:
            sign = 1.0
        mem["t"] = t
        mem["h"] = h
        mem["v"] = v
        mem["vx"] = vx
        mem["phase"] = "abort"
        return {
            "engines": 3,
            "throttle": 0.85,
            "tilt": float(-14.0 * sign),
            "fins": float(_clamp(-sign, -1.0, 1.0)),
            "abort": True,
        }

    if h <= 0.0 or fuel < 20.0 and running == 0 and h < 5.0:
        mem["t"] = t
        mem["h"] = h
        mem["v"] = v
        mem["vx"] = vx
        return {"engines": 0, "throttle": 0.4, "tilt": 0.0, "fins": 0.0, "abort": False}

    committed = bool(mem.get("committed", False))
    info = {"t": max(1.0, h / max(15.0, -v)), "impact_v": v, "climbed": False, "apex": 0.0}

    speed_factor = (min(v, -1.0) / -300.0) ** 2
    gate = 4200.0 * speed_factor + 700.0

    n_cmd = 0
    thr = 0.4
    status = "coast"

    if not committed:
        if t < mem.get("cooldown", -1.0):
            status = "coast"
        elif h > gate or v > -8.0:
            status = "coast"
        elif mem.get("kn", 0) < 4 and h > 1800.0:
            status = "coast"
        else:
            status, thr, info = _solve(h, v, mass, fuel, 3, 1.5, k)
            if status == "late":
                st13, thr13, info13 = _solve(h, v, mass, fuel, 13, 1.5, k)
                committed = True
                mem["committed"] = True
                mem["spool_t"] = t
                mem["thr_bias"] = 0.0
                if st13 == "good" or st13 == "late":
                    mem["n_plan"] = 13
                    thr = 1.0 if st13 == "late" else thr13
                    info = info13
                else:
                    mem["n_plan"] = 3
                    thr = 1.0
                status = "late"
            elif status == "good" and thr >= 0.50:
                committed = True
                mem["committed"] = True
                mem["spool_t"] = t
                mem["n_plan"] = 3
                mem["thr_bias"] = 0.0
            else:
                status = "coast"
                thr = 0.4
                committed = False
                mem["committed"] = False
    if committed:
        n_plan = int(mem.get("n_plan", 3))
        if running <= 0:
            elapsed = t - mem.get("spool_t", t)
            delay_left = max(0.0, 1.5 - elapsed)
            n_sol = 13 if n_plan >= 13 else 3
            status, thr_s, info = _solve(h, v, mass, fuel, n_sol, delay_left, k)
            if status == "early" and info.get("apex", 0.0) > 60.0 and elapsed < 0.35 and h > 80.0:
                st_rel, _, _ = _solve(h, v, mass, fuel, 3, 1.5, k)
                if st_rel != "late":
                    mem["committed"] = False
                    mem["cooldown"] = t + 0.35
                    mem["spool_t"] = None
                    committed = False
                    n_cmd = 0
                    thr = 0.4
                    status = "coast"
            if committed:
                if elapsed > 1.85 and running <= 0:
                    mem["n_plan"] = 13
                    mem["spool_t"] = t
                    n_plan = 13
                n_cmd = 13 if n_plan >= 13 else 3
                if status == "late":
                    thr = 1.0
                    if n_cmd < 13 and elapsed < 0.2:
                        n_cmd = 13
                        mem["n_plan"] = 13
                elif status == "early":
                    thr = 0.4
                else:
                    thr = thr_s
                if n_cmd >= 13:
                    thr = min(thr, 0.55)
        else:
            if running < 3:
                mem["force13"] = True
            use_13 = bool(mem.get("force13", False)) and running < 3
            if running >= 3 and not use_13:
                status, thr_s, info = _solve(h, v, mass, fuel, 3, 0.0, k)
                if status == "late":
                    if fuel > 1800.0 and h > 25.0:
                        mem["force13"] = True
                        use_13 = True
                    else:
                        n_cmd = 3
                        thr = 1.0
                elif status == "early":
                    n_cmd = 3
                    thr = 0.4
                    if info.get("apex", 0.0) > 18.0 and h > 55.0:
                        st_rel, _, irel = _solve(h, v, mass, fuel, 3, 1.5, k)
                        if st_rel != "late":
                            mem["committed"] = False
                            mem["force13"] = False
                            mem["cooldown"] = t + 0.3
                            mem["spool_t"] = None
                            mem["thr_bias"] = 0.0
                            committed = False
                            n_cmd = 0
                            thr = 0.4
                            status = "coast"
                else:
                    n_cmd = 3
                    thr = thr_s
            if committed and (use_13 or (running >= 3 and mem.get("force13") and status == "late")):
                n_eff = running if running > 0 else 13
                if n_eff >= 8:
                    n_eff = min(n_eff, 13)
                status, thr_s, info = _solve(h, v, mass, fuel, max(n_eff, 1), 0.0, k)
                n_cmd = 13
                if status == "early":
                    if running >= 3:
                        mem["force13"] = False
                        n_cmd = 3
                        thr = 0.4
                    else:
                        thr = 0.4
                elif status == "late":
                    thr = 1.0
                else:
                    thr = thr_s
                if running >= 3 and status != "late":
                    st3, thr3, inf3 = _solve(h, v, mass, fuel, 3, 0.0, k)
                    if st3 == "good" and thr3 >= 0.42:
                        mem["force13"] = False
                        n_cmd = 3
                        thr = thr3
                        info = inf3
                        status = st3
            if committed and running > 0 and n_cmd == 0:
                n_cmd = 3 if running <= 3 else 13
                thr = 1.0 if v < -8.0 else 0.55

        if committed and running > 0 and n_cmd > 0:
            n_alg = 3 if n_cmd <= 3 else max(running, 1)
            thr_alg, a_req = _algebraic(h, v, mass, n_alg, k, tilt_now)
            if status == "late":
                thr = 1.0
            elif status == "early":
                thr = 0.4
            else:
                thr = 0.62 * thr + 0.38 * thr_alg
            if mem.get("t") is not None and running > 0:
                a_meas = (v - mem["v"]) / dt
                thr_applied = float(tel["throttle"])
                if abs(thr_applied - mem.get("thr", thr_applied)) < 0.18:
                    a_exp = (
                        running * T_ENG * thr_applied * math.cos(math.radians(tilt_now)) / max(mass, 1.0)
                        - G
                        + k * v * v
                    )
                    err = a_exp - a_meas
                    mem["thr_bias"] = _clamp(0.88 * mem.get("thr_bias", 0.0) + 0.03 * err, -0.22, 0.28)
            thr = _clamp(thr + mem.get("thr_bias", 0.0), 0.4, 1.0)
            if h < 18.0 and v < -6.0:
                thr = max(thr, 0.72 if h > 8.0 else 0.85)
            if h < 8.0 and -3.2 < v < -0.4 and abs(x) < 8.0:
                thr = min(thr, 0.62)
    else:
        n_cmd = 0
        thr = 0.4

    if fuel < 40.0:
        n_cmd = 0
        thr = 0.4

    t_go = info.get("t", h / max(12.0, -v))
    if not committed:
        t_go = max(2.5, 0.62 * h / max(20.0, -v) + 1.5)
    t_go = max(0.7, t_go)
    mem["t_go"] = 0.65 * mem.get("t_go", t_go) + 0.35 * t_go
    t_go = mem["t_go"]

    if abs(x) > 12.0 and running == 0 and h > 50.0:
        v_lim = 22.0 if h > 250.0 else 8.0
        closing = vx * x
        if closing >= 0.0 or abs(vx) < v_lim:
            a_ctrl = -math.copysign(2.65, x if x != 0.0 else 1.0) - wind_a
        else:
            a_ctrl = math.copysign(1.8, x) - wind_a
    else:
        v_des = _clamp(-1.45 * x / max(t_go, 1.0), -14.0, 14.0)
        if h < 45.0:
            v_des = _clamp(-1.1 * x / max(t_go, 1.3), -3.0, 3.0)
        if h < 16.0:
            v_des = _clamp(-0.85 * x / max(t_go, 1.4), -1.6, 1.6)
        tau = 0.65 if h > 80.0 else 0.85
        a_ctrl = (v_des - vx) / tau - 0.04 * x - wind_a
    a_ctrl = _clamp(a_ctrl, -4.0, 4.0)

    if running == 0 and v < -18.0 and n_cmd == 0:
        auth = 3.0 * min(1.0, (abs(v) / 75.0) ** 2)
        auth = max(auth, 0.35)
        fins = _clamp(-a_ctrl / auth, -1.0, 1.0)
    else:
        fins = 0.0

    n_tilt = running if running > 0 else (n_cmd if n_cmd > 0 else 0)
    if n_tilt > 0 and (running > 0 or committed):
        a_avail = max(n_tilt, 1) * T_ENG * max(thr, 0.4) / max(mass, 1.0)
        lim_deg = 9.0 if h > 40.0 else (6.0 if h > 14.0 else 4.0)
        if abs(x) > 4.0 or abs(vx) > 1.5:
            lim_deg = max(lim_deg, 7.0)
        if h < 10.0 and abs(x) < 3.5 and abs(vx) < 1.3:
            lim_deg = min(lim_deg, 3.5)
        lim = math.sin(math.radians(lim_deg))
        s = _clamp(-a_ctrl / max(a_avail, 1.0), -lim, lim)
        tilt = math.degrees(math.asin(_clamp(s, -0.30, 0.30)))
    else:
        tilt = _clamp(-0.7 * a_ctrl, -8.0, 8.0)

    if h < 12.0 and abs(x) < 2.5 and abs(vx) < 1.0:
        tilt *= max(0.0, h / 12.0)

    prev = mem.get("thr", thr)
    if n_cmd > 0 and running > 0 and status != "late":
        slew = 0.22 if h < 40.0 else 0.12
        thr = prev + _clamp(thr - prev, -slew, slew)
    thr = _clamp(thr, 0.4, 1.0)

    if n_cmd >= 8:
        n_cmd = 13
    elif n_cmd >= 1:
        n_cmd = 3
    else:
        n_cmd = 0

    mem["t"] = t
    mem["h"] = h
    mem["v"] = v
    mem["vx"] = vx
    mem["fins"] = fins
    mem["thr"] = thr
    mem["k"] = k
    mem["committed"] = committed

    return {
        "engines": int(n_cmd),
        "throttle": float(thr),
        "tilt": float(_clamp(tilt, -15.0, 15.0)),
        "fins": float(_clamp(fins, -1.0, 1.0)),
        "abort": False,
    }
