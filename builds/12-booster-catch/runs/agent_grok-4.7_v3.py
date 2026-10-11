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

    # lateral guidance with fins (engines off, fast)
    # positive fins push toward negative distance, so sign(fins) = sign(dist) to reduce positive dist
    fins = 0.0
    if tel["engines_running"] == 0 and speed > 40:
        # predict and damp: want vs = -k * dist
        vs_des = -0.15 * dist
        fins = max(-1.0, min(1.0, 0.4 * (vs - vs_des)))
        # if far, just full
        if abs(dist) > 30:
            fins = max(-1.0, min(1.0, 0.02 * dist + 0.15 * vs))

    # suicide burn
    Tmax = 3 * 2.75e6
    a_full = Tmax / m - 9.81
    stop = speed * speed / (2 * max(a_full, 1))
    # light delay 1.5s coast
    coast = speed * 1.5 + 0.5 * 9.81 * 2.25
    engines = 0
    throttle = 0.6
    if tel["engines_commanded"] > 0 or tel["engines_running"] > 0 or h < stop + coast + 30:
        engines = 3

    if tel["engines_running"] >= 1:
        n = tel["engines_running"]
        if h > 2 and speed > 0.5:
            a_need = speed * speed / (2 * max(h, 0.5))
            # add a little bias to arrive slightly early (softer) — actually bias up so we don't hit fast
            a_need *= 1.04
            T_need = (a_need + 9.81) * m
            throttle = T_need / (n * 2.75e6)
            throttle = max(0.4, min(1.0, throttle))
        else:
            throttle = 0.4
        engines = n if n >= 3 else 3

    tilt_cmd = max(-12, min(12, 0.08 * dist + 0.5 * vs))

    return {"engines": engines, "throttle": float(throttle), "tilt": float(tilt_cmd), "fins": float(fins), "abort": False}
