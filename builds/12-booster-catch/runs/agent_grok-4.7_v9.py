import math

def pilot(tel):
    if tel.get("tower_health") == "FAULT":
        return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": True}

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
    if n_run == 0 and speed > 60:
        fins = max(-1.0, min(1.0, 0.005 * dist + 0.2 * vs))

    # Ignite only inside the realistic burn window (~2 km), on a 0.6-throttle curve.
    a_plan = 3 * 2.75e6 * 0.6 / m - g
    coast = speed * 1.5 + 0.5 * g * 2.25
    need = speed * speed / (2.0 * max(a_plan, 0.5))
    want = (h < 3000) and (need + coast + 20.0 > h)
    engines = 3 if (want or n_run > 0 or n_cmd > 0) else 0
    throttle = 0.6

    if n_run >= 1:
        n = n_run
        if h > 0.4:
            a_need = speed * speed / (2.0 * h)
            throttle = (a_need + g) * m / (n * 2.75e6)
            throttle = max(0.4, min(1.0, throttle))
        else:
            throttle = 0.4
        engines = 3
        # engine-out: if we commanded 3 and fewer are burning, or we are saturating
        # high with lots of speed left, call up the middle ring
        if n < n_cmd or (throttle > 0.95 and speed > 40 and h > 100):
            engines = 13

    lim = 7.0 if h < 50 else 12.0
    tilt_cmd = max(-lim, min(lim, 0.1 * dist + 0.6 * vs))

    return {"engines": int(engines), "throttle": float(throttle), "tilt": float(tilt_cmd), "fins": float(fins), "abort": False}
