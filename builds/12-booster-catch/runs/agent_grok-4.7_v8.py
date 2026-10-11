import math

def pilot(tel):
    if tel.get("tower_health") == "FAULT":
        return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": False, "abort": True}

    h = float(tel["altitude_m"])
    v = float(tel["vertical_speed_ms"])
    dist = float(tel["distance_to_tower_m"])
    vs = float(tel["sideways_speed_ms"])
    m = max(1.0, float(tel["mass_kg"]))
    g = 9.81
    speed = max(0.0, -v)
    n_run = int(tel["engines_running"])
    n_cmd = int(tel["engines_commanded"])

    fins = 0.0
    if n_run == 0 and speed > 50:
        fins = max(-1.0, min(1.0, 0.006 * dist + 0.22 * vs))

    # single continuous burn, target zero speed at h=0
    # start on the 0.55-throttle suicide curve so we have throttle margin both ways
    a_plan = 3 * 2.75e6 * 0.55 / m - g
    coast = speed * 1.5 + 0.5 * g * 2.25
    need = speed * speed / (2.0 * max(a_plan, 0.5))
    engines = 3 if (n_run > 0 or n_cmd > 0 or need + coast + 15 > h) else 0
    throttle = 0.55

    if n_run >= 1 and h > 0.3 and speed + max(v, 0) > 0.2:
        n = n_run
        a_need = (speed * speed) / (2.0 * max(h, 0.3))
        # tiny bias: slightly more decel so we arrive a touch slow, not fast
        a_need = a_need * 1.0 + 0.15
        throttle = (a_need + g) * m / (n * 2.75e6)
        throttle = max(0.4, min(1.0, throttle))
        engines = 3
    elif n_run >= 1:
        throttle = 0.4
        engines = 3

    # if throttle is pinned at 0.4 and we will reverse well above the pad, we started too early
    if n_run >= 1 and h > 30:
        a_min = n_run * 2.75e6 * 0.4 / m - g
        stop_h = h - speed * speed / (2.0 * max(a_min, 0.5))
        if stop_h > 40 and throttle <= 0.41:
            # too early — but cutting now costs 1.5s. Only cut if the coast+relight still works.
            pass

    lim = 6.0 if h < 40 else 12.0
    tilt_cmd = max(-lim, min(lim, 0.12 * dist + 0.7 * vs))

    return {"engines": int(engines), "throttle": float(throttle), "tilt": float(tilt_cmd), "fins": float(fins), "abort": False}
