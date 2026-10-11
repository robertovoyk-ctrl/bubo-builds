import math

def pilot(tel):
    if tel["tower_health"] == "FAULT":
        return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": True}

    h = float(tel["altitude_m"])
    v = float(tel["vertical_speed_ms"])
    dist = float(tel["distance_to_tower_m"])
    vs = float(tel["sideways_speed_ms"])
    m = float(tel["mass_kg"])
    speed = max(0.0, -v)
    g = 9.81
    n_run = int(tel["engines_running"])
    n_cmd = int(tel["engines_commanded"])

    # ---- lateral: fins while coasting ----
    fins = 0.0
    if n_run == 0 and speed > 30:
        # accel authority ~ 3 m/s^2. PD
        fins = 0.012 * dist + 0.35 * vs
        fins = max(-1.0, min(1.0, fins))

    # ---- vertical guidance ----
    # Brake with 3 engines targeting a hover-impossible stop around 25 m,
    # then drop and do a short min-throttle landing burn.
    h_stop = 25.0
    thr_plan = 0.85
    a_brake = 3 * 2.75e6 * thr_plan / m - g
    coast = speed * 1.55 + 0.5 * g * 1.55 * 1.55
    need = speed * speed / (2.0 * max(a_brake, 1.0))
    engines = 0
    throttle = thr_plan

    lit = n_cmd > 0 or n_run > 0
    if lit or (need + coast > max(0.0, h - h_stop) and h < 4000):
        engines = 3

    if n_run >= 1:
        n = n_run
        if h > h_stop + 8 and speed > 3:
            a_need = (speed * speed) / (2.0 * max(h - h_stop, 1.0))
            throttle = (a_need + g) * m / (n * 2.75e6)
            throttle = max(0.45, min(1.0, throttle))
            engines = 3
        elif v > -1.0 and h > 12:
            # nearly stopped high: shut down and fall
            engines = 0
            throttle = 0.4
        else:
            # landing burn. min throttle net accel is large, so time it.
            # 3 eng min: T=3*2.75e6*0.4, a = T/m - g
            a_min = n * 2.75e6 * 0.4 / m - g
            # if not yet lit for landing, the caller above may have engines 0
            # suicide: start when speed^2/(2 a_min) ~= h, accounting we are already lit or not
            a_use = max(a_min, 1.0)
            dist_stop = speed * speed / (2.0 * a_use)
            if h > 4 and dist_stop < h - 2 and speed < 25:
                # too early, would stop in air
                engines = 0
                throttle = 0.4
            else:
                engines = 3
                if h > 0.5 and speed > 0.3:
                    a_need = speed * speed / (2.0 * max(h, 0.3))
                    throttle = (a_need + g) * m / (n * 2.75e6)
                    throttle = max(0.4, min(1.0, throttle))
                else:
                    throttle = 0.4
                if v > 0.8:
                    engines = 0

    # if we commanded shutdown, don't immediately relight (1.5 s penalty) unless suicide says so
    if n_run == 0 and engines == 3 and h > 15 and speed < 30:
        a_min = 3 * 2.75e6 * 0.4 / max(m, 1) - g
        # during 1.5 s we fall further
        spd2 = speed + g * 1.5
        fall = speed * 1.5 + 0.5 * g * 2.25
        dist_stop = spd2 * spd2 / (2.0 * max(a_min, 1.0))
        if dist_stop + 1.0 < h - fall:
            engines = 0

    # tilt: positive tilt pushes toward -distance
    # stronger when high so we arrive on the tower; ease off near the pad
    k_p = 0.25 if h > 80 else 0.15
    k_d = 1.2 if h > 80 else 0.8
    tilt_cmd = k_p * dist + k_d * vs
    # don't tilt hard if it would add too much vertical loss when fast? keep moderate
    tilt_cmd = max(-12.0, min(12.0, tilt_cmd))
    if n_run == 0:
        tilt_cmd = 0.0

    return {
        "engines": int(engines),
        "throttle": float(throttle),
        "tilt": float(tilt_cmd),
        "fins": float(fins),
        "abort": False,
    }
