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

    # Grid fins steer only while engines are off and we are still fast.
    # Positive fins push toward negative distance, so the sign matches dist.
    fins = 0.0
    if n_run == 0 and speed > 50:
        t_go = max(4.0, h / max(speed, 1.0))
        vs_des = -dist / t_go
        fins = 0.5 * (vs - vs_des)
        if abs(dist) > 15:
            fins = math.copysign(1.0, dist)
            if dist * vs < 0 and abs(vs) > abs(vs_des):
                fins = 0.5 * (vs - vs_des)
        fins = max(-1.0, min(1.0, fins))

    # One continuous burn. Ignite on the suicide curve of 3 engines at
    # mid throttle, aimed at zero vertical speed exactly at the catch point,
    # so the min-throttle floor never stops us in mid-air.
    a_plan = 3 * 2.75e6 * 0.6 / m - g
    coast = speed * 1.5 + 0.5 * g * 2.25
    need = speed * speed / (2.0 * max(a_plan, 0.5))
    want = (h < 2800) and (need + coast + 10.0 > h)
    engines = 3 if (want or n_run > 0 or n_cmd > 0) else 0
    throttle = 0.6

    if n_run >= 1:
        n = n_run
        if h > 0.5:
            a_need = speed * speed / (2.0 * h)
            throttle = max(0.4, min(1.0, (a_need + g) * m / (n * 2.75e6)))
        else:
            throttle = 0.4
        # engine out, or 3 engines saturated with speed still to kill: light the ring
        engines = 13 if (n < 3 or (throttle > 0.97 and speed > 50)) else 3

    lim = 6.0 if h < 60 else 10.0
    t_go = max(2.0, h / max(speed, 5.0))
    vs_des = -dist / t_go
    tilt_cmd = max(-lim, min(lim, 0.8 * (vs - vs_des)))

    return {"engines": int(engines), "throttle": float(throttle), "tilt": float(tilt_cmd), "fins": float(fins), "abort": False}
