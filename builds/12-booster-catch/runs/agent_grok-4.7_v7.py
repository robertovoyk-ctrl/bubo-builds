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

    # fins only useful engines-off and fast
    fins = 0.0
    if n_run == 0 and speed > 40:
        fins = max(-1.0, min(1.0, 0.01 * dist + 0.3 * vs))

    # ignition: 3 engines, plan to kill speed by ~15 m using ~0.7 throttle
    # so the last segment is a short min-throttle burn we can time.
    h_ref = 18.0
    a_plan = 3 * 2.75e6 * 0.72 / m - g
    coast = speed * 1.6 + 0.5 * g * 2.56
    need = speed * speed / (2.0 * max(a_plan, 1.0))
    start = need + coast > max(0.0, h - h_ref) and h < 4500

    engines = 3 if (start or n_run > 0 or int(tel["engines_commanded"]) > 0) else 0
    throttle = 0.72

    if n_run >= 1:
        n = n_run
        T1 = n * 2.75e6
        # Above the reference band, track a speed profile that zeros at h_ref.
        if h > h_ref + 2 and speed > 1.5:
            a_need = speed * speed / (2.0 * (h - h_ref))
            # slight extra so we don't arrive hot
            a_need *= 1.02
            throttle = max(0.4, min(1.0, (a_need + g) * m / T1))
            engines = 3
        else:
            # Final segment. Min-throttle cannot hover.
            # Stay at min throttle; if we are about to reverse with altitude left, accept it
            # only if reversing would still be within 3 m/s at h=0 — otherwise we started early.
            a_min = 0.4 * T1 / m - g
            # predicted speed at h=0 if we hold min throttle (v is negative)
            # v_f^2 = v^2 - 2*a_min*h, sign: we are decelerating a fall
            vf2 = speed * speed - 2.0 * a_min * max(h, 0.0)
            if vf2 > 0:
                # still falling at pad: too late, go harder
                a_need = speed * speed / (2.0 * max(h, 0.4))
                throttle = max(0.4, min(1.0, (a_need + g) * m / T1))
            else:
                # will stop before pad. How much climb after stop?
                # stop altitude = h - speed^2/(2 a_min). Then we climb until we cut.
                throttle = 0.4
            engines = 3
            # if already climbing and above 2 m, shut down — we overshot the timing
            if v > 0.5 and h > 2.0:
                engines = 0
                throttle = 0.4

    # tilt guidance. positive tilt -> acceleration toward -dist
    # limit tilt when very low so we don't miss the angle gate
    lim = 8.0 if h < 30 else 12.0
    tilt_cmd = 0.18 * dist + 0.9 * vs
    tilt_cmd = max(-lim, min(lim, tilt_cmd))
    if n_run == 0:
        tilt_cmd = max(-lim, min(lim, 0.05 * dist))

    return {"engines": int(engines), "throttle": float(throttle), "tilt": float(tilt_cmd), "fins": float(fins), "abort": False}
