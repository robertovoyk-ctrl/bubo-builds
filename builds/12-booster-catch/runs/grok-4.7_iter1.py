import math

G = 9.81
T_ENG = 2.75e6
MDOT = 849.0
H_SCALE = 8500.0
TARGET_V = -1.7
DRY_NOM = 200000.0

mem = {}


def _clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _total_mass(tel):
    m = float(tel["mass_kg"])
    f = max(0.0, float(tel["fuel_kg"]))
    if abs((m - f) - DRY_NOM) <= abs(m - DRY_NOM):
        return max(m, 1000.0), f
    return max(m + f, 1000.0), f


def _drag_acc(v, h, mass, k):
    if k <= 0.0 or mass <= 1.0:
        return 0.0
    return -(k / mass) * math.exp(-max(h, 0.0) / H_SCALE) * v * abs(v)


def _simulate(h, v, mass, fuel, n_eng, throttle, delay, k, dt):
    dry = mass - fuel
    if dry < 5000.0:
        dry = DRY_NOM
        if mass < dry:
            mass = dry + fuel
    t = 0.0
    max_steps = int(75.0 / dt) + 2
    for _ in range(max_steps):
        if h <= 0.0:
            return v, t, False
        lit = (t >= delay) and n_eng > 0 and fuel > 0.5
        if lit:
            thrust = n_eng * T_ENG * throttle
            mdot = n_eng * MDOT * throttle
        else:
            thrust = 0.0
            mdot = 0.0
        a = -G + thrust / mass + _drag_acc(v, h, mass, k)
        v2 = v + a * dt
        h2 = h + (v + v2) * 0.5 * dt
        mass -= mdot * dt
        fuel -= mdot * dt
        if fuel < 0.0 or mass < dry:
            fuel = 0.0
            mass = max(mass, dry)
        t += dt
        if lit and v < 0.6 and v2 >= 0.0 and h2 > 0.8:
            return 10000.0 + h2, t, True
        if h > 0.0 >= h2:
            denom = h - h2
            frac = h / denom if denom != 0.0 else 1.0
            frac = _clamp(frac, 0.0, 1.0)
            return v + (v2 - v) * frac, t - dt * (1.0 - frac), False
        h, v = h2, v2
    if h > 0.0 and v < 0.0:
        return -400.0, t, False
    return v, t, h > 2.0


def _solve(h, v, mass, fuel, n_eng, delay, k, mode):
    if h > 1800.0:
        dt = 0.12
    elif h > 180.0:
        dt = 0.08
    else:
        dt = 0.045
    vg_lo, tg_lo, high_lo = _simulate(h, v, mass, fuel, n_eng, 0.4, delay, k, dt)
    vg_hi, tg_hi, high_hi = _simulate(h, v, mass, fuel, n_eng, 1.0, delay, k, dt)
    if high_lo:
        return 0.4, "early", vg_lo, tg_lo
    if (not high_hi) and vg_hi < -3.02:
        return 1.0, "late", vg_hi, tg_hi
    lo, hi = 0.4, 1.0
    for _ in range(8):
        mid = 0.5 * (lo + hi)
        vg, tg, high = _simulate(h, v, mass, fuel, n_eng, mid, delay, k, dt)
        if high or vg > TARGET_V:
            hi = mid
        else:
            lo = mid
    f_star = lo
    if (not high_lo) and vg_lo > TARGET_V:
        f_star = 0.4
        vg_s, tg_s = vg_lo, tg_lo
        high_s = False
    else:
        vg_s, tg_s, high_s = _simulate(h, v, mass, fuel, n_eng, f_star, delay, k, dt)
    if high_s:
        return 0.4, "early", vg_s, tg_s
    status = "ok"
    if mode == "ignite":
        if f_star >= 0.60 or vg_lo <= -2.35:
            status = "light"
        else:
            status = "early"
    return f_star, status, vg_s, tg_s


def _ff_tgo(h, v):
    disc = v * v + 2.0 * G * max(h, 0.0)
    if disc <= 0.0:
        return 20.0
    t = (v + math.sqrt(disc)) / G
    if t < 0.4:
        t = 0.4
    return t * 1.3


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

    if mem.get("t_prev") is not None and (
        t < mem["t_prev"] - 0.02 or h > mem.get("h_prev", h) + 800.0
    ):
        mem.clear()

    mass, fuel = _total_mass(tel)

    def _remember():
        mem["t_prev"] = t
        mem["h_prev"] = h
        mem["v_prev"] = v
        mem["vs_prev"] = vs
        mem["run_prev"] = running
        mem["thr_prev"] = thr_now
        mem["tilt_prev"] = tilt_now
        mem["mass_prev"] = mass

    if tower != "OK":
        away = -15.0 if dist >= 0.0 else 15.0
        fins = -1.0 if dist >= 0.0 else 1.0
        eng = 0
        thr = 0.4
        if h < 5000.0 and fuel > 1500.0 and h > -50.0:
            eng = 13 if (h < 900.0 and fuel > 8000.0 and abs(v) > 40.0) else 3
            thr = 1.0
        _remember()
        mem["fins_prev"] = fins
        return {
            "engines": int(eng),
            "throttle": float(thr),
            "tilt": float(away),
            "fins": float(fins),
            "abort": True,
        }

    if h <= 0.0:
        _remember()
        mem["fins_prev"] = 0.0
        return {
            "engines": 0,
            "throttle": 0.4,
            "tilt": 0.0,
            "fins": 0.0,
            "abort": False,
        }

    dt = 0.1
    if mem.get("t_prev") is not None:
        raw_dt = t - mem["t_prev"]
        if 0.01 < raw_dt < 0.6:
            dt = raw_dt
            a_obs = (v - mem["v_prev"]) / dt
            a_side = (vs - mem["vs_prev"]) / dt
            thrust_v = 0.0
            if running > 0:
                thrust_v = (
                    running
                    * T_ENG
                    * thr_now
                    * math.cos(math.radians(_clamp(tilt_now, -20.0, 20.0)))
                )
            a_drag = a_obs + G - thrust_v / mass
            mem["a_drag"] = a_drag
            if abs(v) > 30.0:
                denom = math.exp(-max(h, 0.0) / H_SCALE) * (-v * abs(v))
                if abs(denom) > 1.0:
                    k_s = a_drag * mass / denom
                    prev_k = mem.get("c_k", k_s)
                    n = mem.get("c_n", 0)
                    ok = 0.0 <= k_s <= 450.0
                    if ok and n >= 8:
                        if k_s > prev_k * 3.5 + 8.0 or k_s < prev_k * 0.28 - 1.0:
                            ok = False
                    if ok:
                        blend = min(n, 12)
                        mem["c_k"] = (prev_k * blend + k_s) / (blend + 1.0)
                        mem["c_n"] = n + 1
            prev_run = mem.get("run_prev", 0)
            if prev_run > 0:
                Tp = prev_run * T_ENG * mem.get("thr_prev", thr_now)
                expected = -(Tp / max(mem.get("mass_prev", mass), 1.0)) * math.sin(
                    math.radians(mem.get("tilt_prev", 0.0))
                )
                resid = a_side - expected
                mem["wind_a"] = 0.72 * mem.get("wind_a", 0.0) + 0.28 * _clamp(resid, -5.0, 5.0)
            elif abs(mem.get("fins_prev", 0.0)) < 0.2 and abs(mem.get("v_prev", v)) > 45.0:
                resid = a_side
                mem["wind_a"] = 0.86 * mem.get("wind_a", 0.0) + 0.14 * _clamp(resid, -4.0, 4.0)

    if mem.get("c_n", 0) >= 3:
        k = mem.get("c_k", 30.0)
    else:
        k = mem.get("c_k", 28.0) if mem.get("c_n", 0) > 0 else 28.0

    if "phase" not in mem:
        mem["phase"] = "coast"
        mem["n_cmd"] = 0
        mem["thr"] = 0.55
        mem["spool_t"] = t
        mem["wind_a"] = mem.get("wind_a", 0.0)
        mem["lat_i"] = 0.0

    phase = mem["phase"]
    n_cmd = int(mem.get("n_cmd", 0))
    f_cmd = 0.4
    t_go = _ff_tgo(h, v)
    blocked = t < mem.get("relight_block", -1.0)

    if phase == "coast":
        if blocked or (mem.get("c_n", 0) < 3 and h > 450.0):
            n_cmd = 0
            f_cmd = 0.4
        else:
            skip = False
            if h > 1600.0:
                a_min = 3 * T_ENG * 0.4 / mass - G + max(_drag_acc(v, h, mass, k), 0.0) * 0.45
                a_min = max(a_min, 2.2)
                if h > (v * v) / (2.0 * a_min) + 1600.0:
                    skip = True
            if skip:
                n_cmd = 0
                f_cmd = 0.4
            else:
                f3, st3, vg3, tg3 = _solve(h, v, mass, fuel, 3, 1.5, k, "ignite")
                if tg3 and tg3 > 0.2:
                    t_go = tg3
                if st3 == "light":
                    phase = "spool"
                    n_cmd = 3
                    f_cmd = f3
                    mem["spool_t"] = t
                elif st3 == "late" and fuel > 4500.0:
                    f13, st13, vg13, tg13 = _solve(h, v, mass, fuel, 13, 1.5, k, "ignite")
                    if tg13 and tg13 > 0.2:
                        t_go = tg13
                    phase = "spool"
                    n_cmd = 13
                    mem["spool_t"] = t
                    if st13 == "late":
                        f_cmd = 1.0
                    elif st13 == "early":
                        f_cmd = 0.42
                    else:
                        f_cmd = f13
                else:
                    n_cmd = 0
                    f_cmd = 0.4
    else:
        elapsed = t - mem.get("spool_t", t)
        if running > 0:
            phase = "burn"
            delay = 0.0
        else:
            delay = max(0.0, 1.5 - elapsed)
            if elapsed > 3.0 and running == 0:
                phase = "coast"
                n_cmd = 0
                delay = 1.5

        if phase != "coast" and n_cmd >= 13:
            if running >= 3:
                _, st3, _, tg3 = _solve(h, v, mass, fuel, 3, 0.0, k, "control")
                if tg3 and tg3 > 0.2:
                    t_go = tg3
                if st3 != "late":
                    n_cmd = 3
            else:
                _, st3, _, _ = _solve(h, v, mass, fuel, 3, delay, k, "ignite")
                if st3 == "light":
                    n_cmd = 3
                elif st3 == "early":
                    phase = "coast"
                    n_cmd = 0

        if phase != "coast" and n_cmd > 0:
            if running > 0:
                n_solve = n_cmd if n_cmd <= running else running
                if n_solve <= 0:
                    n_solve = running if running > 0 else n_cmd
                dly = 0.0
            else:
                n_solve = n_cmd
                dly = delay
            f_s, st_s, vg_s, tg_s = _solve(
                h, v, mass, fuel, max(n_solve, 1), dly, k, "control"
            )
            f_cmd = f_s
            if tg_s and tg_s > 0.2:
                t_go = tg_s
            if running == 0 and st_s == "early" and elapsed < 1.2:
                phase = "coast"
                n_cmd = 0
                f_cmd = 0.4
            if running > 0 and st_s == "early" and h > 115.0 and vg_s > 10045.0:
                phase = "coast"
                n_cmd = 0
                f_cmd = 0.4
                mem["relight_block"] = t + 0.55
            if running > 0 and st_s == "late" and n_cmd < 13 and fuel > 5000.0:
                n_cmd = 13
                f_cmd = 1.0

    if phase == "coast":
        thr = 0.4
        n_out = 0
    else:
        n_thr = running if running > 0 else n_cmd
        if running > 0 and n_thr > 0 and 0.0 < h < 320.0:
            a_meas = mem.get("a_drag", 0.0)
            a_model = _drag_acc(v, h, mass, k)
            if mem.get("c_n", 0) >= 3:
                a_use = 0.55 * a_meas + 0.45 * a_model
            else:
                a_use = a_model
            h_eff = max(h, 0.65)
            a_need = (v * v - TARGET_V * TARGET_V) / (2.0 * h_eff)
            cos_t = max(0.72, math.cos(math.radians(tilt_now)))
            tmax = n_thr * T_ENG * cos_t
            f_react = _clamp((a_need + G - a_use) * mass / tmax, 0.4, 1.0)
            if h < 16.0:
                w = 0.72
            elif h < 70.0:
                w = 0.4
            else:
                w = 0.18
            f_cmd = (1.0 - w) * f_cmd + w * f_react
        if running > 0 and h < 22.0 and v < -4.2:
            f_cmd = max(f_cmd, 1.0 if v < -7.5 else 0.9)
        alpha = 0.18 if h < 28.0 else 0.34
        thr = (1.0 - alpha) * f_cmd + alpha * mem.get("thr", f_cmd)
        thr = _clamp(thr, 0.4, 1.0)
        n_out = n_cmd if n_cmd in (3, 13) else (13 if n_cmd > 3 else 3)

    # Lateral guidance
    prev_tgo = mem.get("t_go", t_go)
    if prev_tgo > 0.0:
        t_go = 0.65 * prev_tgo + 0.35 * t_go
    t_go_use = max(t_go, 1.15)
    if h < 500.0:
        mem["lat_i"] = _clamp(mem.get("lat_i", 0.0) + dist * dt, -50.0, 50.0)
    else:
        mem["lat_i"] *= 0.98

    wind_a = mem.get("wind_a", 0.0)
    v_lim = 26.0 if h > 140.0 else (9.0 if h > 45.0 else 4.0)
    if abs(dist) > 16.0 or (abs(vs) > 5.5 and abs(dist) > 7.0):
        a_max = 2.75
        sign_d = 1.0 if dist >= 0.0 else -1.0
        closing = -vs * sign_d
        stop_d = (closing * closing) / (2.0 * a_max) if closing > 0.0 else 0.0
        if closing > 0.4 and stop_d >= abs(dist) * 0.72:
            a_act = math.copysign(a_max, dist)
        else:
            a_act = -math.copysign(a_max, dist if dist != 0.0 else vs)
        a_act -= wind_a
    else:
        v_des = _clamp(-1.45 * dist / t_go_use, -v_lim, v_lim)
        if h < 28.0:
            v_des = _clamp(-dist / max(t_go_use, 1.4), -2.2, 2.2)
        tau = 0.78 if h < 160.0 else 1.15
        a_act = (v_des - vs) / tau - 0.055 * dist - 0.01 * mem.get("lat_i", 0.0) - wind_a

    if running == 0 and v < -18.0:
        auth = 3.0 if abs(v) > 85.0 else max(0.35, 3.0 * abs(v) / 85.0)
        fins = _clamp(-a_act / auth, -1.0, 1.0)
    else:
        fins = 0.0

    n_tilt = running if running > 0 else (n_out if n_out > 0 else 3)
    a_avail = max(n_tilt, 1) * T_ENG * (thr if n_out > 0 or running > 0 else 0.6) / mass
    sin_lim = math.sin(math.radians(15.0))
    sin_t = _clamp(-a_act / max(a_avail, 0.5), -sin_lim, sin_lim)
    tilt = math.degrees(math.asin(sin_t))

    if h < 75.0:
        if abs(dist) < 3.2 and abs(vs) < 1.15:
            lim = _clamp(0.4 + max(0.0, h - 5.0) * 0.28, 0.4, 7.0)
        elif h < 12.0:
            lim = 8.0
        elif h < 30.0:
            lim = 10.0
        else:
            lim = 13.0
        tilt = _clamp(tilt, -lim, lim)
    if n_out == 0 and running == 0:
        tilt = _clamp(tilt, -10.0, 10.0)

    mem["phase"] = phase
    mem["n_cmd"] = n_cmd if phase != "coast" else 0
    mem["thr"] = thr
    mem["t_go"] = t_go
    mem["fins_prev"] = fins
    _remember()

    return {
        "engines": int(0 if phase == "coast" else n_out),
        "throttle": float(_clamp(thr, 0.4, 1.0)),
        "tilt": float(_clamp(tilt, -15.0, 15.0)),
        "fins": float(_clamp(fins, -1.0, 1.0)),
        "abort": False,
    }
