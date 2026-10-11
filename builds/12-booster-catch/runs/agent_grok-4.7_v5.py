import math

mem = {"phase": 0}

def pilot(tel):
    if tel["tower_health"] == "FAULT":
        return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": True}

    h = tel["altitude_m"]
    v = tel["vertical_speed_ms"]
    dist = tel["distance_to_tower_m"]
    vs = tel["sideways_speed_ms"]
    m = tel["mass_kg"]
    speed = max(0.0, -v)
    g = 9.81

    fins = 0.0
    if tel["engines_running"] == 0 and speed > 40:
        fins = max(-1.0, min(1.0, 0.008 * dist + 0.25 * vs))

    # plan 3 engines at ~0.9 for the braking burn, targeting a stop at h_target
    h_target = 40.0
    n_plan = 3
    thr_plan = 0.9
    a_brake = n_plan * 2.75e6 * thr_plan / m - g
    stop_from = max(0.0, h - h_target)
    # speed we can kill over stop_from
    # start when speed^2 / (2 a) >= stop_from, plus coast during light
    coast = speed * 1.5 + 0.5 * g * 2.25
    need = speed * speed / (2 * max(a_brake, 1.0))
    engines = 0
    throttle = thr_plan
    if tel["engines_commanded"] > 0 or tel["engines_running"] > 0 or need + coast > stop_from:
        engines = 3

    if tel["engines_running"] >= 1:
        n = tel["engines_running"]
        # desired speed profile: at altitude h, want speed such that we arrive at h_target with ~0
        # v_des^2 = 2*a*(h - h_target) but a depends on throttle. Closed loop:
        # if above target, brake so predicted stop altitude is h_target
        if h > h_target + 5 and speed > 2:
            a_need = speed * speed / (2 * max(h - h_target, 1.0))
            T_need = (a_need + g) * m
            throttle = max(0.4, min(1.0, T_need / (n * 2.75e6)))
            engines = 3
        elif speed < 2 and h > 8:
            # stopped above pad: cut engines, fall, relight for short burn
            engines = 0
            throttle = 0.4
        else:
            # final approach: min throttle, accept a bit of climb risk if late
            engines = 3
            # if rising, cut
            if v > 1.5 and h > 3:
                engines = 0
            else:
                # throttle to null speed near 0
                if h > 1:
                    a_need = speed * speed / (2 * max(h, 0.3))
                    T_need = (a_need + g) * m
                    throttle = max(0.4, min(1.0, T_need / (n * 2.75e6)))
                else:
                    throttle = 0.4

    tilt_cmd = max(-12.0, min(12.0, 0.1 * dist + 0.7 * vs))
    return {"engines": int(engines), "throttle": float(throttle), "tilt": float(tilt_cmd), "fins": float(fins), "abort": False}
