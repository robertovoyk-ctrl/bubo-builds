# Classic autopilot: the "how a normal flight computer does it" baseline.
# Vertical: suicide-burn guidance. Even 3 engines at minimum throttle push harder than gravity, so it cannot hover:
#   timing is everything. Sideways: grid fins steer the fall toward the tower, then the engines lean to null the rest.
import math
from sim import G, T_ENG, IGN_DELAY

def autopilot(tel, decide_every=1.0, vf=0.8):
    z, vz, x, vx = tel['altitude_m'], tel['vertical_speed_ms'], tel['distance_to_tower_m'], tel['sideways_speed_ms']
    m = tel['mass_kg']
    if tel['tower_health'] != 'OK':
        return {'abort': True}
    cmd = {}
    t_left = max(1.5, z / max(abs(vz), 1.0))
    if tel['engines_running'] == 0:
        vx_des = max(-40.0, min(40.0, -x / (0.8 * t_left + 2.0)))
        cmd['fins'] = max(-1.0, min(1.0, 0.5 * (vx - vx_des)))
        cmd['tilt'] = 0.0
    else:
        t_go = max(1.5, 2 * z / max(abs(vz), 1.0))                    # braking: time left ~ 2z/|v|
        a_side = 3 * x / t_go ** 2 + 2.5 * vx / t_go                 # arrive at x=0 with vx=0
        a_thr = max(1.0, tel['engines_running'] * T_ENG * tel['throttle'] / m)
        cmd['tilt'] = max(-12.0, min(12.0, math.degrees(math.asin(max(-0.2, min(0.2, a_side / a_thr))))))
    if vz > -0.2:                                                     # going up: cut
        cmd['engines'] = 0
        return cmd
    a_des = (vz * vz - vf * vf) / (2 * max(z, 0.3))                   # constant decel that arrives at vf
    big = tel['engines_running'] if tel['engines_commanded'] == 13 and tel['engines_running'] > 3 else 13   # engines that actually lit
    thr3, thr13 = (a_des + G) * m / (3 * T_ENG), (a_des + G) * m / (big * T_ENG)
    lead = abs(vz) * (decide_every + (IGN_DELAY if tel['engines_running'] == 0 else 0.0))
    if tel['engines_commanded'] == 0:
        # light 13 when the decel needed (including the time it takes to light) reaches ~half of what 13 can give
        a_need = (vz * vz) / (2 * max(z - lead, 1.0))
        if (a_need + G) * m / (13 * T_ENG) >= 0.5 or (abs(vz) < 60 and (a_need + G) * m / (3 * T_ENG) >= 0.7):
            e = 13 if abs(vz) >= 60 else 3
            cmd.update(engines=e, throttle=min(1.0, max(0.4, (a_need + G) * m / (e * T_ENG))))
        return cmd
    if thr3 <= 0.95:
        cmd.update(engines=3, throttle=min(1.0, max(0.4, thr3)))
        if thr3 < 0.4 and z > 60: cmd['engines'] = 0                # too slow for this height: coast, relight later
    else:
        cmd.update(engines=13, throttle=min(1.0, max(0.4, thr13)))
    return cmd
