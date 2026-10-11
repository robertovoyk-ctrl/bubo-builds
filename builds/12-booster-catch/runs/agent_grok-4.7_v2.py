import math

def pilot(tel):
    if tel["tower_health"] == "FAULT":
        return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": True}

    h = tel["altitude_m"]
    v = tel["vertical_speed_ms"]  # negative falling
    dist = tel["distance_to_tower_m"]
    vs = tel["sideways_speed_ms"]
    tilt = tel["tilt_deg"]

    # fins: positive pushes toward negative distance
    # want to drive dist toward 0. If dist > 0, want negative sideways accel -> positive fins
    fins = 0.0
    if tel["engines_running"] == 0:
        # PD toward tower
        fins = max(-1.0, min(1.0, 0.004 * dist + 0.08 * vs))

    # suicide burn estimate with 3 engines
    # target net accel
    m = tel["mass_kg"]
    # start lighting when h is less than v^2/(2*a) plus margin for light delay
    T = 3 * 2.75e6 * 0.85
    a_net = T / m - 9.81
    # distance to stop
    speed = -v
    stop_dist = speed * speed / (2 * max(a_net, 1.0))
    # during 1.5s light, fall further ~ speed*1.5 + 0.5*9.81*2.25
    light_fall = speed * 1.5 + 0.5 * 9.81 * 2.25

    engines = 0
    throttle = 0.4
    if h < stop_dist + light_fall + 80:
        engines = 3
        throttle = 0.85

    if tel["engines_running"] >= 3:
        # closed loop throttle: want a such that v^2 = 2*a*h, a = v^2/(2h)
        if h > 5:
            a_need = (speed * speed) / (2 * h)
            # a_need = T/(m) - g => T = (a_need+g)*m
            T_need = (a_need + 9.81) * m
            throttle = T_need / (3 * 2.75e6)
            throttle = max(0.4, min(1.0, throttle))
        else:
            throttle = 0.4
        engines = 3

    # tilt to correct lateral: positive tilt pushes toward negative distance
    # want dist -> 0. If dist > 0, want push negative -> positive tilt
    tilt_cmd = max(-15, min(15, 0.05 * dist + 0.4 * vs))

    return {"engines": engines, "throttle": throttle, "tilt": tilt_cmd, "fins": fins, "abort": False}
