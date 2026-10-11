# Booster catch, simplified: the last ~7 km of a Super Heavy style return, down to the tower arms.
# 2D (x = sideways distance from the tower, z = height above the catch point). Not SpaceX's model; numbers are public ballparks.
#
# Each decision step (default 1 s) a pilot sees telemetry and returns a command:
#   engines: 0, 3 or 13      throttle: 0.4..1.0      tilt: -15..15 deg (thrust/body lean, + pushes toward -x)
#   fins: -1..1 (grid fins, sideways push while falling fast)      abort: true -> divert to the sea
# Real-time mode: a command computed from the telemetry at time t only takes effect at t + latency.
import math, random

G = 9.81
DRY = 200_000.0                 # kg
FUEL0 = 45_000.0                # kg left for the landing
T_ENG = 2.75e6                  # N per engine, sea level
MDOT = T_ENG / (330 * G)        # kg/s per engine at full throttle
AREA, CD = 64.0, 1.0            # m^2 cross-section, tail-first drag
IGN_DELAY = 1.5                 # s from command to thrust
TILT_RATE = 10.0                # deg/s the body + gimbal can lean
FIN_ACC = 3.0                   # m/s^2 max sideways push from grid fins at high speed
CATCH = dict(x=6.0, vz=3.0, vx=2.0, tilt=10.0)   # limits at the arms (same spirit as public sims)

def rho(z): return 1.225 * math.exp(-max(z, 0) / 8500.0)

class Booster:
    def __init__(self, seed=0, scenario='nominal'):
        r = random.Random(seed)
        self.t = 0.0
        self.x, self.z = r.uniform(250, 450), 7000.0
        self.vx, self.vz = r.uniform(-8, -2), -300.0
        self.tilt = 0.0
        self.fuel = FUEL0
        self.wind = r.uniform(-6, 6)                 # m/s steady wind
        self.gust_seed = r.random() * 100
        self.engines_cmd, self.engines_on, self.ign_t = 0, 0, None
        self.throttle, self.tilt_cmd, self.fins = 0.4, 0.0, 0.0
        self.dead_engines = 0
        self.tower_ok = True
        self.scenario = scenario
        self.fault_t = r.uniform(8, 16) if scenario == 'tower_fault' else None
        self.engine_fault = scenario == 'engine_out'
        self.aborted = False
        self.done, self.result = False, None

    def telemetry(self):
        return dict(t=round(self.t, 1), altitude_m=round(self.z, 1), distance_to_tower_m=round(self.x, 1),
                    vertical_speed_ms=round(self.vz, 1), sideways_speed_ms=round(self.vx, 1),
                    tilt_deg=round(self.tilt, 1), fuel_kg=round(self.fuel), engines_running=self.lit(),
                    engines_commanded=self.engines_cmd, throttle=round(self.throttle, 2),
                    mass_kg=round(DRY + self.fuel), tower_health='OK' if self.tower_ok else 'FAULT',
                    wind_ms=round(self.wind, 1))

    def lit(self):
        return max(0, self.engines_on - (self.dead_engines if self.engines_on == 13 else 0))

    def apply(self, cmd):
        if cmd.get('abort'):
            self.aborted = True
        e = int(cmd.get('engines', self.engines_cmd))
        e = 13 if e >= 8 else 3 if e >= 2 else 0
        if e > 0 and self.engines_on == 0 and self.ign_t is None:
            self.ign_t = self.t + IGN_DELAY          # cold start: ignition delay
        if e == 0:
            self.engines_on, self.ign_t = 0, None
        elif self.engines_on > 0:
            self.engines_on = e                      # 13 -> 3 shutdown or 3 -> 13 relight of hot engines: instant
        self.engines_cmd = e
        self.throttle = min(1.0, max(0.4, float(cmd.get('throttle', self.throttle))))
        self.tilt_cmd = min(15.0, max(-15.0, float(cmd.get('tilt', self.tilt_cmd))))
        self.fins = min(1.0, max(-1.0, float(cmd.get('fins', self.fins))))

    def step(self, dt):
        if self.done: return
        self.t += dt
        if self.fault_t and self.t >= self.fault_t: self.tower_ok = False
        if self.ign_t is not None and self.t >= self.ign_t:
            self.engines_on, self.ign_t = self.engines_cmd, None
            if self.engine_fault and self.engines_on == 13: self.dead_engines = 2   # two engines fail to light
        d = TILT_RATE * dt
        self.tilt += max(-d, min(d, self.tilt_cmd - self.tilt))
        m = DRY + self.fuel
        n = self.lit()
        if self.fuel <= 0: n = 0
        thrust = n * T_ENG * self.throttle
        self.fuel = max(0.0, self.fuel - n * MDOT * self.throttle * dt)
        gust = 3.0 * math.sin(self.t * 0.7 + self.gust_seed) + 1.5 * math.sin(self.t * 2.3 + 2 * self.gust_seed)
        rvx, rvz = self.vx - (self.wind + gust), self.vz
        v = math.hypot(rvx, rvz)
        q = 0.5 * rho(self.z) * v * v
        drag = q * CD * AREA
        ax = -drag * rvx / max(v, 1e-6) / m
        az = -drag * rvz / max(v, 1e-6) / m - G
        a = math.radians(self.tilt)
        ax += -thrust * math.sin(a) / m
        az += thrust * math.cos(a) / m
        if n == 0:                                   # grid fins only bite when falling fast
            ax += -self.fins * FIN_ACC * min(1.0, abs(self.vz) / 150.0)
        self.vx += ax * dt; self.vz += az * dt
        self.x += self.vx * dt; self.z += self.vz * dt
        if self.aborted and not self.done:
            self.done, self.result = True, 'aborted to sea'
        elif self.z <= 0:
            self.done = True
            ok = abs(self.x) < CATCH['x'] and abs(self.vz) < CATCH['vz'] and abs(self.vx) < CATCH['vx'] and abs(self.tilt) < CATCH['tilt']
            if ok and self.tower_ok: self.result = 'CAUGHT'
            elif ok: self.result = 'crashed (tower fault, should have aborted)'
            else:
                why = []
                if abs(self.x) >= CATCH['x']: why.append(f'missed by {abs(self.x):.0f} m')
                if abs(self.vz) >= CATCH['vz']: why.append(f'hit at {abs(self.vz):.0f} m/s')
                if abs(self.vx) >= CATCH['vx']: why.append(f'sideways {abs(self.vx):.1f} m/s')
                if abs(self.tilt) >= CATCH['tilt']: why.append(f'tilted {abs(self.tilt):.0f} deg')
                self.result = 'crashed: ' + ', '.join(why)
        elif self.vz > 5 and self.engines_on and self.z > 0:
            pass                                     # going up: allowed, it will fall back
        if self.t > 120 and not self.done:
            self.done, self.result = True, 'timeout'

def fly(pilot, seed=0, scenario='nominal', latency=0.0, decide_every=1.0, dt=0.02, log=None):
    """Run one flight. pilot(telemetry) -> command dict. latency: seconds before a command takes effect."""
    b = Booster(seed, scenario)
    queue = []                                       # (apply_time, cmd)
    next_dec = 0.0
    while not b.done:
        if b.t >= next_dec - 1e-9:
            tel = b.telemetry()
            cmd = pilot(tel)
            lat = latency(tel) if callable(latency) else latency
            queue.append((b.t + lat, cmd))
            if log is not None: log.append(dict(t=b.t, tel=tel, cmd=cmd, applies_at=b.t + lat))
            next_dec = b.t + (decide_every(tel) if callable(decide_every) else decide_every)
        while queue and queue[0][0] <= b.t + 1e-9:
            b.apply(queue.pop(0)[1])
        b.step(dt)
    return b.result, b
