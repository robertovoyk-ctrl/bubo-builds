import math

_mem = {}

def pilot(tel):
    g = 9.81
    T_one = 2.75e6
    m = max(float(tel["mass_kg"]), 1.0)
    h = float(tel["altitude_m"])
    x = float(tel["distance_to_tower_m"])
    vx = float(tel["sideways_speed_ms"])
    tilt_now = float(tel["tilt_deg"])
    n_run = int(tel["engines_running"])
    n_cmd = int(tel["engines_commanded"])
    wind = float(tel["wind_ms"])
    t = float(tel["t"])
    vy_raw = float(tel["vertical_speed_ms"])

    if tel["tower_health"] != "OK":
        _mem.clear()
        return {"engines": 0, "throttle": 0.4, "tilt": 0.0, "fins": 0.0, "abort": True}

    prev_t = _mem.get("t", t - 0.1)
    dt = t - prev_t
    if dt <= 1e-4 or dt > 0.5:
        dt = 0.1
    prev_h = _mem.get("h", h)
    prev_vy_raw = _mem.get("vy_raw", vy_raw)

    if "vsign" not in _mem:
        if h < prev_h - 0.2:
            _mem["vsign"] = -1.0 if vy_raw > 0.5 else 1.0
        elif vy_raw < -30.0:
            _mem["vsign"] = 1.0
        elif vy_raw > 30.0:
            _mem["vsign"] = -1.0
        else:
            _mem["vsign"] = 1.0
    vy = vy_raw * _mem["vsign"]

    if n_run == 0:
        a_meas = (vy - prev_vy_raw * _mem["vsign"]) / dt
        if abs(a_meas) < 40.0:
            a_c = _mem.get("a_coast", -g)
            _mem["a_coast"] = 0.75 * a_c + 0.25 * a_meas
    a_coast = _mem.get("a_coast", -g)
    if a_coast > -1.0:
        a_coast = -1.0
    if a_coast < -g - 2.0:
        a_coast = -g

    _mem["t"] = t
    _mem["h"] = h
    _mem["vy_raw"] = vy_raw

    v_down = max(0.0, -vy)
    t_go = h / max(v_down, 25.0)
    vx_des = -x / max(t_go, 2.5)
    vx_des = max(-35.0, min(35.0, vx_des))
    # positive fins / tilt accelerate toward -x
    ax_des = (vx_des - vx) / 2.2 - 0.15 * wind
    fins = max(-1.0, min(1.0, -ax_des / 3.0))

    def net_accel(n, th):
        return n * T_one * th / m - g

    a_full3 = max(net_accel(3, 1.0), 1.0)
    a_min3 = max(net_accel(3, 0.4), 0.5)
    v_tgt = 0.6

    delay = 0.0
    if n_run == 0:
        delay = 0.4 if n_cmd > 0 else 1.5
    h_pred = h + vy * delay + 0.5 * a_coast * delay * delay
    vy_pred = vy + a_coast * delay
    if h_pred < 1.0:
        h_pred = max(h, 1.0)
        vy_pred = vy
    vd_p = max(0.0, -vy_pred)
    a_need_p = (vd_p * vd_p - v_tgt * v_tgt) / (2.0 * max(h_pred, 1.0))

    vd_now = v_down
    a_need = (vd_now * vd_now - v_tgt * v_tgt) / (2.0 * max(h, 0.8))

    spool_n = _mem.get("spool_n", 0)
    if n_run == 0 and spool_n > 0:
        engines = spool_n
    else:
        engines = 0

    too_early = n_run >= 3 and h > 120.0 and a_need < 0.50 * a_min3 and vd_now > 8.0
    climbing = vy > 1.5 and h > 30.0 and n_run > 0

    if too_early or climbing:
        engines = 0
        _mem["spool_n"] = 0
    elif n_run >= 13:
        engines = 3 if a_need < 0.90 * a_full3 else 13
    elif n_run >= 3:
        engines = 13 if a_need > 1.05 * a_full3 else 3
    else:
        if a_need_p > 0.98 * a_full3 or a_need > 0.90 * a_full3:
            engines = 13
        elif a_need_p > 0.72 * a_full3 or a_need > 0.62 * a_full3:
            engines = 3
        elif spool_n > 0:
            engines = spool_n
        else:
            engines = 0
        if engines > 0:
            _mem["spool_n"] = engines
        if n_run > 0:
            _mem["spool_n"] = 0

    if engines == 0:
        _mem["spool_n"] = 0
        throttle = 0.4
        tilt_cmd = max(-8.0, min(8.0, -math.degrees(ax_des / 25.0)))
    else:
        n_th = n_run if n_run > 0 else engines
        c = math.cos(math.radians(max(-15.0, min(15.0, tilt_now))))
        c = max(c, 0.6)
        T_need = (a_need + g) * m / c
        throttle = T_need / (n_th * T_one)
        throttle = max(0.4, min(1.0, throttle))
        if h < 12.0 and vd_now > 4.0:
            throttle = 1.0
        if h < 8.0 and vy > 0.4:
            throttle = 0.4
        Tm = max(n_th * throttle * T_one / m, 8.0)
        s = max(-0.30, min(0.30, -ax_des / Tm))
        tilt_cmd = math.degrees(math.asin(s))
        if h < 80.0:
            tilt_cmd *= max(0.2, h / 80.0)
        tilt_cmd = max(-15.0, min(15.0, tilt_cmd))

    if h < 20.0:
        fins *= 0.3

    return {
        "engines": int(engines),
        "throttle": float(throttle),
        "tilt": float(tilt_cmd),
        "fins": float(fins),
        "abort": False,
    }
