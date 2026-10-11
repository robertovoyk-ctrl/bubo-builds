import math

def pilot(tel):
    if tel["tower_health"] == "FAULT":
        return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": True}

    h = tel["altitude_m"]
    v = tel["vertical_speed_ms"]
    dist = tel["distance_to_tower_m"]
    vs = tel["sideways_speed_ms"]
    m = tel["mass_kg"]
    speed = max(0.0, -v)

    fins = 0.0
    if tel["engines_running"] == 0 and speed > 50:
        # bang-bang lateral with damping
        fins = max(-1.0, min(1.0, 0.01 * dist + 0.2 * vs))

    g = 9.81
    n_plan = 3
    Tmax = n_plan * 2.75e6
    a_full = Tmax / m - g
    stop = speed * speed / (2 * max(a_full, 1))
    coast = speed * 1.6 + 0.5 * g * 2.56
    engines = 0
    throttle = 0.7
    if tel["engines_commanded"] > 0 or tel["engines_running"] > 0 or h < stop + coast + 40:
        engines = 3

    if tel["engines_running"] >= 1:
        n = tel["engines_running"]
        if h > 1.0 and speed > 1.0:
            a_need = speed * speed / (2.0 * h) * 1.25 + 1.5
            T_need = (a_need + g) * m
            throttle = max(0.4, min(1.0, T_need / (n * 2.75e6)))
        else:
            # final: if very slow and low, cut? can't relight fast. hold min
            throttle = 0.4
        engines = 3

    # lateral with tilt during burn
    tilt_cmd = max(-12.0, min(12.0, 0.12 * dist + 0.8 * vs))

    return {"engines": engines, "throttle": float(throttle), "tilt": float(tilt_cmd), "fins": float(fins), "abort": False}
