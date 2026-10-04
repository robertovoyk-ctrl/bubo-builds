# UFO + giant fruit fly: night desert, a saucer hovers, the fly stands in the beam,
# the camera pushes in to the head, the head capsule opens and the brain lights up.
# Everything is built here in code (Blender / Cycles). Run:
#   python3.11 scene.py -- <outdir> <frames csv> <res_w> <spp>
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix, Euler, noise

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 24
DUR = 28.0
rng = np.random.RandomState(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
if os.environ.get('BUBO_GPU'):
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for typ in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = typ; prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == typ]
            if devs:
                for d in prefs.devices: d.use = (d.type == typ)
                sc.cycles.device = 'GPU'; print('GPU', typ, [d.name for d in devs]); break
        except Exception as e: print('gpu', typ, 'unavailable:', e)
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 1; sc.cycles.glossy_bounces = 2
sc.cycles.transmission_bounces = 4; sc.cycles.transparent_max_bounces = 8
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.cycles.use_adaptive_sampling = True
sc.render.fps = FPS
sc.render.use_persistent_data = True
sc.cycles.adaptive_threshold = 0.03
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass
sc.render.film_transparent = False

# ---------------------------------------------------------------- helpers
def link(o):
    sc.collection.objects.link(o); return o

def mesh_obj(name, verts, faces, mat=None, smooth=True):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces]); me.update()
    if smooth:
        me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    o = link(bpy.data.objects.new(name, me))
    if mat: me.materials.append(mat)
    return o

def bm_obj(name, bm, mat=None, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth: me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    o = link(bpy.data.objects.new(name, me))
    if mat: me.materials.append(mat)
    return o

def ellipsoid(name, c, r, mat, seg=64, ring=32):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * r[0], v.co.y * r[1], v.co.z * r[2]))
    o = bm_obj(name, bm, mat); o.location = c; return o

def nodes(mat):
    mat.use_nodes = True; nt = mat.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); return nt, out

def principled(name, col, rough=0.5, metal=0.0, coat=0.0, emit=None, es=0.0, **kw):
    m = bpy.data.materials.new(name); nt, out = nodes(m)
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (*col, 1); p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal; p.inputs['Coat Weight'].default_value = coat
    if emit: p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = es
    for k, v in kw.items(): p.inputs[k].default_value = v
    nt.links.new(p.outputs[0], out.inputs[0]); return m

def emission(name, col, strength):
    m = bpy.data.materials.new(name); nt, out = nodes(m)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs[0].default_value = (*col, 1); e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], out.inputs[0]); return m

def smooth01(u):
    u = min(1.0, max(0.0, u)); return u * u * (3 - 2 * u)

# ---------------------------------------------------------------- world: night sky, clouds, stars
world = bpy.data.worlds.new('W'); sc.world = world; world.use_nodes = True
wn = world.node_tree; [wn.nodes.remove(n) for n in list(wn.nodes)]
wout = wn.nodes.new('ShaderNodeOutputWorld'); bg = wn.nodes.new('ShaderNodeBackground')
tc = wn.nodes.new('ShaderNodeTexCoord')
sep = wn.nodes.new('ShaderNodeSeparateXYZ'); wn.links.new(tc.outputs['Generated'], sep.inputs[0])
grad = wn.nodes.new('ShaderNodeValToRGB')  # by elevation
grad.color_ramp.elements[0].position = 0.0; grad.color_ramp.elements[0].color = (0.020, 0.030, 0.075, 1)
grad.color_ramp.elements[1].position = 0.35; grad.color_ramp.elements[1].color = (0.004, 0.007, 0.022, 1)
wn.links.new(sep.outputs['Z'], grad.inputs[0])
cl = wn.nodes.new('ShaderNodeTexNoise'); cl.inputs['Scale'].default_value = 3.2; cl.inputs['Detail'].default_value = 9
cl.inputs['Roughness'].default_value = 0.62
wn.links.new(tc.outputs['Generated'], cl.inputs['Vector'])
clr = wn.nodes.new('ShaderNodeValToRGB')
clr.color_ramp.elements[0].position = 0.48; clr.color_ramp.elements[0].color = (0, 0, 0, 1)
clr.color_ramp.elements[1].position = 0.78; clr.color_ramp.elements[1].color = (1, 1, 1, 1)
wn.links.new(cl.outputs['Fac'], clr.inputs[0])
# moon proximity glow (moon direction)
MOON_DIR = Vector((-0.42, 1.0, 0.36)).normalized()
dotn = wn.nodes.new('ShaderNodeVectorMath'); dotn.operation = 'DOT_PRODUCT'
dotn.inputs[1].default_value = MOON_DIR
wn.links.new(tc.outputs['Generated'], dotn.inputs[0])  # Generated in world = view direction
mg = wn.nodes.new('ShaderNodeMath'); mg.operation = 'POWER'; mg.inputs[1].default_value = 40.0
mx0 = wn.nodes.new('ShaderNodeMath'); mx0.operation = 'MAXIMUM'; mx0.inputs[1].default_value = 0.0
wn.links.new(dotn.outputs['Value'], mx0.inputs[0]); wn.links.new(mx0.outputs[0], mg.inputs[0])
cloudcol = wn.nodes.new('ShaderNodeMixRGB'); cloudcol.blend_type = 'MIX'
cloudcol.inputs[1].default_value = (0.05, 0.065, 0.12, 1); cloudcol.inputs[2].default_value = (0.55, 0.62, 0.8, 1)
wn.links.new(mg.outputs[0], cloudcol.inputs[0])
mix_sky = wn.nodes.new('ShaderNodeMixRGB'); mix_sky.blend_type = 'MIX'
wn.links.new(clr.outputs['Color'], mix_sky.inputs[0])
wn.links.new(grad.outputs['Color'], mix_sky.inputs[1]); wn.links.new(cloudcol.outputs['Color'], mix_sky.inputs[2])
# stars
st = wn.nodes.new('ShaderNodeTexVoronoi'); st.inputs['Scale'].default_value = 420
wn.links.new(tc.outputs['Generated'], st.inputs['Vector'])
stm = wn.nodes.new('ShaderNodeMath'); stm.operation = 'LESS_THAN'; stm.inputs[1].default_value = 0.035
wn.links.new(st.outputs['Distance'], stm.inputs[0])
stk = wn.nodes.new('ShaderNodeMath'); stk.operation = 'MULTIPLY'; stk.inputs[1].default_value = 1.4
wn.links.new(stm.outputs[0], stk.inputs[0])
inv = wn.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
wn.links.new(clr.outputs['Color'], inv.inputs[1])
stk2 = wn.nodes.new('ShaderNodeMath'); stk2.operation = 'MULTIPLY'
wn.links.new(stk.outputs[0], stk2.inputs[0]); wn.links.new(inv.outputs[0], stk2.inputs[1])
add = wn.nodes.new('ShaderNodeMixRGB'); add.blend_type = 'ADD'; add.inputs[0].default_value = 1.0
wn.links.new(mix_sky.outputs['Color'], add.inputs[1]); wn.links.new(stk2.outputs[0], add.inputs[2])
wn.links.new(add.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0
wn.links.new(bg.outputs[0], wout.inputs[0])

# moon disc + moonlight
moon = ellipsoid('moon', MOON_DIR * 900, (14, 14, 14), emission('moonM', (0.85, 0.9, 1.0), 14), 32, 16)
sun = bpy.data.lights.new('moonlight', 'SUN'); sun.energy = 0.55; sun.color = (0.55, 0.66, 1.0); sun.angle = math.radians(1.5)
so = link(bpy.data.objects.new('moonlight', sun))
so.rotation_euler = (-MOON_DIR).to_track_quat('-Z', 'Y').to_euler()

# ---------------------------------------------------------------- ground + rocks
rockM = bpy.data.materials.new('rock'); nt, out = nodes(rockM)
p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = 0.85
tco = nt.nodes.new('ShaderNodeTexCoord')
nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 12; nz.inputs['Roughness'].default_value = 0.7
nt.links.new(tco.outputs['Object'], nz.inputs['Vector'])
cr = nt.nodes.new('ShaderNodeValToRGB')
cr.color_ramp.elements[0].position = 0.35; cr.color_ramp.elements[0].color = (0.035, 0.04, 0.05, 1)
cr.color_ramp.elements[1].position = 0.7; cr.color_ramp.elements[1].color = (0.22, 0.23, 0.26, 1)
nt.links.new(nz.outputs['Fac'], cr.inputs[0]); nt.links.new(cr.outputs['Color'], p.inputs['Base Color'])
nz2 = nt.nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 14; nz2.inputs['Detail'].default_value = 14
nt.links.new(tco.outputs['Object'], nz2.inputs['Vector'])
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.6; bump.inputs['Distance'].default_value = 0.08
nt.links.new(nz2.outputs['Fac'], bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
nt.links.new(p.outputs[0], out.inputs[0])

def terrain():
    N = 260; size = 260.0
    xs = np.linspace(-size / 2, size / 2, N); ys = np.linspace(-60, 200, N)
    V = []; F = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            d = math.hypot(x, y - 1.0)
            h = 0.9 * noise.fractal(Vector((x * 0.035, y * 0.035, 0.3)), 0.6, 2.1, 6)
            h += 0.35 * noise.fractal(Vector((x * 0.22, y * 0.22, 1.7)), 0.55, 2.2, 4)
            flat = smooth01((d - 7) / 14)            # clearing under the saucer
            h *= 0.25 + 0.75 * flat
            ridge = smooth01((y - 70) / 60)          # distant mountains
            h += ridge * (14 + 22 * (noise.fractal(Vector((x * 0.012, 3.1, y * 0.012)), 0.6, 2.0, 6) + 0.4))
            side = smooth01((abs(x) - 60) / 50)
            h += side * 10 * (noise.fractal(Vector((x * 0.02, y * 0.02, 5.0)), 0.6, 2.0, 5) + 0.5)
            V.append((x, y, h - 0.15))
    for j in range(N - 1):
        for i in range(N - 1):
            a = j * N + i; F.append((a, a + 1, a + N + 1, a + N))
    return mesh_obj('ground', V, F, rockM)
ground = terrain()

def rock(name, c, s, seed, flat=0.6):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    off = Vector((seed * 7.3, seed * 3.1, seed * 1.7))
    for v in bm.verts:
        n = v.co.normalized()
        d = 0.38 * noise.fractal(n * 1.4 + off, 0.55, 2.0, 6) + 0.12 * noise.fractal(n * 5.0 + off, 0.5, 2.0, 4)
        v.co = n * (1 + d)
    o = bm_obj(name, bm, rockM); o.location = c; o.scale = (s[0], s[1], s[2] * flat)
    o.rotation_euler = (rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(0, 6.28)); return o

FG = rock('fg_rock', (-5.95, -34.2, 1.0), (1.5, 1.3, 2.6), 1, 1.0)   # camera starts behind this one
rock('r1', (-9, -18, 0.2), (2.6, 2.0, 1.6), 2)
rock('r2', (8, -14, 0.1), (3.0, 2.2, 1.4), 3)
rock('r3', (-14, -4, 0.0), (4.0, 3.0, 2.0), 4)
rock('r4', (15, 2, 0.0), (5.0, 3.6, 2.4), 5)
rock('r5', (5, -24, 0.0), (1.6, 1.2, 1.0), 6)
rock('r6', (-6, 12, 0.0), (3.5, 2.5, 1.8), 7)
rock('r7', (10, 16, 0.0), (4.2, 3.0, 2.2), 8)
for k in range(46):
    a = rng.uniform(0, 6.28); r = rng.uniform(9, 45)
    x, y = math.cos(a) * r, math.sin(a) * r * 0.9 - 4
    if abs(x) < 3 and y < -10: continue
    s = rng.uniform(0.25, 1.1)
    rock(f'p{k}', (x, y, -0.05), (s, s * rng.uniform(0.6, 1.0), s), 10 + k)

# ---------------------------------------------------------------- the saucer
UFO_C = Vector((0.0, 0.6, 9.6))
prof = [(0.0, 1.9), (1.2, 1.85), (2.6, 1.55), (3.6, 1.05), (5.5, 0.72), (8.0, 0.38), (10.5, 0.14), (11.6, 0.03),
        (11.7, -0.06), (10.4, -0.22), (8.0, -0.42), (6.0, -0.62), (4.9, -0.74), (4.3, -0.78), (2.4, -0.86), (0.0, -0.9)]
SEG = 192; V = []; F = []
for i in range(SEG):
    a = i / SEG * 2 * math.pi
    for (r, z) in prof: V.append((r * math.cos(a), r * math.sin(a), z))
P = len(prof)
for i in range(SEG):
    for k in range(P - 1):
        a = i * P + k; b = ((i + 1) % SEG) * P + k
        F.append((a, b, b + 1, a + 1))
hullM = bpy.data.materials.new('hull'); nt, out = nodes(hullM)
p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.inputs['Base Color'].default_value = (0.09, 0.1, 0.12, 1)
p.inputs['Metallic'].default_value = 1.0; p.inputs['Roughness'].default_value = 0.32
tco = nt.nodes.new('ShaderNodeTexCoord'); wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'
wv.inputs['Scale'].default_value = 1.4; wv.inputs['Distortion'].default_value = 0.0; wv.inputs['Detail'].default_value = 0
nt.links.new(tco.outputs['Object'], wv.inputs['Vector'])
rp = nt.nodes.new('ShaderNodeValToRGB'); rp.color_ramp.elements[0].position = 0.0; rp.color_ramp.elements[1].position = 0.06
nt.links.new(wv.outputs['Fac'], rp.inputs[0])
bmp = nt.nodes.new('ShaderNodeBump'); bmp.inputs['Strength'].default_value = 0.35; bmp.inputs['Distance'].default_value = 0.02
nt.links.new(rp.outputs['Color'], bmp.inputs['Height']); nt.links.new(bmp.outputs['Normal'], p.inputs['Normal'])
nt.links.new(p.outputs[0], out.inputs[0])
ufo = mesh_obj('saucer', V, F, hullM); ufo.location = UFO_C
BLUE = (0.35, 0.68, 1.0)
ringM = emission('ring', BLUE, 35.0)
bm = bmesh.new();
seg = 256; mr = 4.55; nr = 0.11; tv = []
for i in range(seg):
    a = i / seg * 2 * math.pi
    for k in range(10):
        b = k / 10 * 2 * math.pi
        tv.append(((mr + nr * math.cos(b)) * math.cos(a), (mr + nr * math.cos(b)) * math.sin(a), nr * math.sin(b)))
tf = []
for i in range(seg):
    for k in range(10):
        a = i * 10 + k; b2 = ((i + 1) % seg) * 10 + k
        tf.append((a, b2, ((i + 1) % seg) * 10 + (k + 1) % 10, i * 10 + (k + 1) % 10))
ring = mesh_obj('ring', tv, tf, ringM); ring.location = UFO_C + Vector((0, 0, -0.8)); ring.parent = None
coreM = emission('core', (0.45, 0.75, 1.0), 0.7)
bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=2.3)
core = bm_obj('core', bm, coreM, smooth=False); core.location = UFO_C + Vector((0, 0, -0.9))
beamL = bpy.data.lights.new('beam', 'SPOT'); beamL.energy = 5000; beamL.color = BLUE
beamL.spot_size = math.radians(38); beamL.spot_blend = 0.6; beamL.shadow_soft_size = 2.2
beamO = link(bpy.data.objects.new('beam', beamL)); beamO.location = UFO_C + Vector((0, 0, -1.0)); beamO.rotation_euler = (0, 0, 0)
underL = bpy.data.lights.new('under', 'AREA'); underL.shape = 'DISK'; underL.size = 9.0; underL.energy = 1200; underL.color = BLUE
underO = link(bpy.data.objects.new('under', underL)); underO.location = UFO_C + Vector((0, 0, -0.95)); underO.visible_camera = False; underO.visible_glossy = False
# fake light shaft: open cone, emission that fades toward silhouette edges
shaftM = bpy.data.materials.new('shaft'); nt, out = nodes(shaftM)
lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
fac = nt.nodes.new('ShaderNodeMath'); fac.operation = 'POWER'; fac.inputs[1].default_value = 2.2
inv2 = nt.nodes.new('ShaderNodeMath'); inv2.operation = 'SUBTRACT'; inv2.inputs[0].default_value = 1.0
nt.links.new(lw.outputs['Facing'], inv2.inputs[1]); nt.links.new(inv2.outputs[0], fac.inputs[0])
tcs = nt.nodes.new('ShaderNodeTexCoord'); sx = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tcs.outputs['Generated'], sx.inputs[0])
zf = nt.nodes.new('ShaderNodeMath'); zf.operation = 'POWER'; zf.inputs[1].default_value = 0.6
nt.links.new(sx.outputs['Z'], zf.inputs[0])
nzs = nt.nodes.new('ShaderNodeTexNoise'); nzs.inputs['Scale'].default_value = 3.0; nzs.inputs['Detail'].default_value = 4
nt.links.new(tcs.outputs['Object'], nzs.inputs['Vector'])
m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; nt.links.new(fac.outputs[0], m1.inputs[0]); nt.links.new(zf.outputs[0], m1.inputs[1])
m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(nzs.outputs['Fac'], m2.inputs[1])
shaftK = nt.nodes.new('ShaderNodeMath'); shaftK.operation = 'MULTIPLY'; shaftK.name = 'K'; shaftK.inputs[1].default_value = 0.55
nt.links.new(m2.outputs[0], shaftK.inputs[0])
em = nt.nodes.new('ShaderNodeEmission'); em.inputs[0].default_value = (*BLUE, 1)
tr = nt.nodes.new('ShaderNodeBsdfTransparent'); add = nt.nodes.new('ShaderNodeAddShader')
nt.links.new(shaftK.outputs[0], em.inputs['Strength']); nt.links.new(em.outputs[0], add.inputs[0]); nt.links.new(tr.outputs[0], add.inputs[1])
nt.links.new(add.outputs[0], out.inputs[0])
shaftM.blend_method = 'BLEND' if hasattr(shaftM, 'blend_method') else None
V = []; F = []; S2 = 128; H = UFO_C.z - 0.9
for i in range(S2):
    a = i / S2 * 2 * math.pi
    for k, (r, z) in enumerate([(4.4, H), (5.6, H * 0.5), (6.6, 0.0)]):
        V.append((r * math.cos(a), r * math.sin(a) + UFO_C.y, z))
for i in range(S2):
    for k in range(2):
        a = i * 3 + k; b2 = ((i + 1) % S2) * 3 + k; F.append((a, b2, b2 + 1, a + 1))
shaft = mesh_obj('shaft', V, F, shaftM)
shaft.visible_shadow = False; ring.visible_shadow = False; core.visible_shadow = False

# ---------------------------------------------------------------- the fly (faces -Y, toward the camera)
FS = 1.5
HEAD_C = Vector((0.0, -0.95, 1.36))
HEAD_W = HEAD_C * FS
_before = set(bpy.data.objects)
chitin = principled('chitin', (0.13, 0.075, 0.03), rough=0.5, coat=0.35, **{'Coat Roughness': 0.3})
_nt = chitin.node_tree; _p = _nt.nodes['Principled BSDF']; _tc = _nt.nodes.new('ShaderNodeTexCoord')
_nz = _nt.nodes.new('ShaderNodeTexNoise'); _nz.inputs['Scale'].default_value = 60; _nz.inputs['Detail'].default_value = 8
_nt.links.new(_tc.outputs['Object'], _nz.inputs['Vector'])
_bp = _nt.nodes.new('ShaderNodeBump'); _bp.inputs['Strength'].default_value = 0.25; _bp.inputs['Distance'].default_value = 0.004
_nt.links.new(_nz.outputs['Fac'], _bp.inputs['Height']); _nt.links.new(_bp.outputs['Normal'], _p.inputs['Normal'])
_nz3 = _nt.nodes.new('ShaderNodeTexNoise'); _nz3.inputs['Scale'].default_value = 9; _nz3.inputs['Detail'].default_value = 6
_nt.links.new(_tc.outputs['Object'], _nz3.inputs['Vector'])
_cr = _nt.nodes.new('ShaderNodeValToRGB'); _cr.color_ramp.elements[0].position = 0.3; _cr.color_ramp.elements[0].color = (0.05, 0.028, 0.012, 1)
_cr.color_ramp.elements[1].position = 0.75; _cr.color_ramp.elements[1].color = (0.2, 0.12, 0.05, 1)
_nt.links.new(_nz3.outputs['Fac'], _cr.inputs[0]); _nt.links.new(_cr.outputs['Color'], _p.inputs['Base Color'])
dark = principled('darkchitin', (0.05, 0.03, 0.02), rough=0.38, coat=0.5)
abdM = bpy.data.materials.new('abdomen'); nt, out = nodes(abdM)
p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = 0.4; p.inputs['Coat Weight'].default_value = 0.5
tco = nt.nodes.new('ShaderNodeTexCoord'); sxa = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tco.outputs['Object'], sxa.inputs[0])
wva = nt.nodes.new('ShaderNodeMath'); wva.operation = 'SINE'; mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 7.5
nt.links.new(sxa.outputs['Y'], mul.inputs[0]); nt.links.new(mul.outputs[0], wva.inputs[0])
cra = nt.nodes.new('ShaderNodeValToRGB'); cra.color_ramp.elements[0].position = 0.35; cra.color_ramp.elements[0].color = (0.32, 0.22, 0.09, 1)
cra.color_ramp.elements[1].position = 0.6; cra.color_ramp.elements[1].color = (0.03, 0.02, 0.012, 1)
nt.links.new(wva.outputs[0], cra.inputs[0]); nt.links.new(cra.outputs['Color'], p.inputs['Base Color']); nt.links.new(p.outputs[0], out.inputs[0])

thorax = ellipsoid('thorax', Vector((0, 0.15, 1.12)), (0.66, 0.82, 0.62), chitin)
scut = ellipsoid('scutellum', Vector((0, 0.82, 1.48)), (0.32, 0.26, 0.16), chitin)
abd = ellipsoid('abdomen', Vector((0, 1.5, 0.98)), (0.58, 1.0, 0.52), abdM)
abd.rotation_euler = (math.radians(-10), 0, 0)
neck = ellipsoid('neck', Vector((0, -0.62, 1.28)), (0.2, 0.2, 0.2), dark)

# compound eyes: voronoi facets, deep red, glossy
eyeM = bpy.data.materials.new('eye'); nt, out = nodes(eyeM)
p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.inputs['Roughness'].default_value = 0.35
p.inputs['Coat Weight'].default_value = 1.0; p.inputs['Coat Roughness'].default_value = 0.08
tco = nt.nodes.new('ShaderNodeTexCoord'); vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'
vor.inputs['Scale'].default_value = 38.0; nt.links.new(tco.outputs['Object'], vor.inputs['Vector'])
vb = nt.nodes.new('ShaderNodeBump'); vb.inputs['Strength'].default_value = 0.55; vb.inputs['Distance'].default_value = 0.012; vb.invert = True
vr = nt.nodes.new('ShaderNodeMath'); vr.operation = 'POWER'; vr.inputs[1].default_value = 0.35
nt.links.new(vor.outputs['Distance'], vr.inputs[0]); nt.links.new(vr.outputs[0], vb.inputs['Height'])
nt.links.new(vb.outputs['Normal'], p.inputs['Normal']); nt.links.new(vb.outputs['Normal'], p.inputs['Coat Normal'])
vor2 = nt.nodes.new('ShaderNodeTexVoronoi'); vor2.inputs['Scale'].default_value = 38.0; nt.links.new(tco.outputs['Object'], vor2.inputs['Vector'])
ecol = nt.nodes.new('ShaderNodeValToRGB'); ecol.color_ramp.elements[0].color = (0.16, 0.002, 0.002, 1); ecol.color_ramp.elements[1].color = (0.42, 0.012, 0.006, 1)
nt.links.new(vor2.outputs['Color'], ecol.inputs[0]); nt.links.new(ecol.outputs['Color'], p.inputs['Base Color'])
nt.links.new(ecol.outputs['Color'], p.inputs['Emission Color'])
eyeGlow = nt.nodes.new('ShaderNodeValue'); eyeGlow.name = 'G'; eyeGlow.outputs[0].default_value = 0.0
nt.links.new(eyeGlow.outputs[0], p.inputs['Emission Strength'])
nt.links.new(p.outputs[0], out.inputs[0])
EYES = []
for s in (-1, 1):
    e = ellipsoid(f'eye{s}', Vector((0, 0, 0)), (0.30, 0.34, 0.40), eyeM, 96, 48)
    e.location = HEAD_C + Vector((s * 0.36, -0.04, 0.02))
    e.rotation_euler = (0, s * math.radians(-12), s * math.radians(14))
    EYES.append((e, s, e.location.copy(), e.rotation_euler.copy()))

# head capsule split into panels (gold inner face), the brain sits inside
goldM = principled('gold', (1.0, 0.7, 0.28), rough=0.22, metal=1.0)
HR = (0.40, 0.33, 0.40)
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
for v in bm.verts: v.co = Vector((v.co.x * HR[0], v.co.y * HR[1], v.co.z * HR[2]))
bm.faces.ensure_lookup_table()
groups = {}
for f in bm.faces:
    c = f.calc_center_median()
    az = math.atan2(c.x, -c.y)                          # 0 = front (toward camera)
    el = math.atan2(c.z, math.hypot(c.x, c.y))
    sector = int(((az + math.pi) / (2 * math.pi)) * 6 + 0.5) % 6
    band = 0 if el < 0.2 else 1
    groups.setdefault((sector, band), []).append(f.index)
PANELS = []
for key, idx in groups.items():
    b2 = bmesh.new(); vmap = {}
    for fi in idx:
        f = bm.faces[fi]; vs = []
        for v in f.verts:
            if v.index not in vmap: vmap[v.index] = b2.verts.new(v.co)
            vs.append(vmap[v.index])
        b2.faces.new(vs)
    cen = sum((v.co for v in b2.verts), Vector()) / len(b2.verts)
    for v in b2.verts: v.co = cen + (v.co - cen) * 1.0 - cen     # tiny seam, origin at centroid
    o = bm_obj(f'panel_{key[0]}_{key[1]}', b2, chitin)
    o.data.materials.append(goldM)
    sol = o.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = 0.03; sol.material_offset = 1; sol.material_offset_rim = 0
    o.location = HEAD_C + cen
    d = cen.normalized()
    PANELS.append((o, HEAD_C + cen, d, key))
bm.free()
# antennae + proboscis ride on the front panels
def tube(name, pts, r0, r1, mat, sides=10):
    V = []; F = []; n = len(pts)
    for i, p0 in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized(); b = t.cross(a)
        r = r0 + (r1 - r0) * i / (n - 1)
        for k in range(sides):
            th = k / sides * 2 * math.pi; V.append(p0 + (a * math.cos(th) + b * math.sin(th)) * r)
    for i in range(n - 1):
        for k in range(sides):
            F.append((i * sides + k, i * sides + (k + 1) % sides, (i + 1) * sides + (k + 1) % sides, (i + 1) * sides + k))
    return mesh_obj(name, V, F, mat)
def front_panel():
    best = None
    for o, c, d, key in PANELS:
        if key[1] == 0 and (best is None or c.y < best[1].y): best = (o, c)
    return best[0]
fp = front_panel()
for s in (-1, 1):
    base = HEAD_C + Vector((s * 0.08, -0.31, 0.06))
    pts = [base, base + Vector((s * 0.015, -0.06, 0.0)), base + Vector((s * 0.03, -0.11, -0.05)), base + Vector((s * 0.04, -0.13, -0.15)), base + Vector((s * 0.045, -0.13, -0.22))]
    a = tube(f'ant{s}', pts, 0.045, 0.05, chitin)
    tip = pts[2]
    arpts = [tip + Vector((s * 0.04 * i, -0.07 * i, 0.09 * i)) for i in range(5)]
    ar = tube(f'arista{s}', arpts, 0.007, 0.003, dark)
    br = []
    for i in range(1, 9):     # arista branches
        q = tip.lerp(arpts[-1], i / 9)
        br.append(tube(f'arb{s}{i}', [q, q + Vector((s * 0.03, -0.02, -0.035 if i % 2 else 0.04))], 0.003, 0.0015, dark, 4))
    for ob in [a, ar] + br:
        ob.parent = fp; ob.matrix_parent_inverse = fp.matrix_world.inverted()
ocM = principled('ocelli', (0.6, 0.15, 0.05), rough=0.15, coat=1.0)
hr = np.random.RandomState(31)
TOPP = min((p_ for p_ in PANELS if p_[3][1] == 1), key=lambda p_: (p_[1] - (HEAD_C + Vector((0, 0, HR[2])))).length)[0]
for o, c, d, key in PANELS:
    if key[1] != 1: continue
    me = o.data; V2 = []; F2 = []
    vs = [v.co.copy() for v in me.vertices]
    for j in range(60 if abs(d.x) < 0.5 else 25):
        p0 = vs[hr.randint(len(vs))]; n = (p0 + c - HEAD_C).normalized()
        big = j < 4
        L = (0.16 if big else 0.05) * hr.uniform(0.7, 1.0); w = 0.008 if big else 0.003
        tip = p0 + (n + Vector((0, 0.5, 0.3))).normalized() * L
        b0 = len(V2); ax = (tip - p0).normalized(); a1 = ax.orthogonal().normalized(); a2 = ax.cross(a1)
        for q, ww in ((p0, w), (p0.lerp(tip, 0.5), w * 0.6), (tip, w * 0.15)):
            for k in range(4): V2.append(q + (a1 * math.cos(k * 1.5708) + a2 * math.sin(k * 1.5708)) * ww)
        for jj in range(2):
            for k in range(4): F2.append((b0 + jj * 4 + k, b0 + jj * 4 + (k + 1) % 4, b0 + (jj + 1) * 4 + (k + 1) % 4, b0 + (jj + 1) * 4 + k))
    hb = mesh_obj(f'hb_{key[0]}', V2, F2, dark); hb.parent = o; hb.location = (0, 0, 0)
    if False:
        for k2, off in enumerate(((0, 0.0), (-0.05, 0.05), (0.05, 0.05))):
            top = HEAD_C + Vector((off[0], -0.02 + off[1], HR[2] * 0.98)) - c
            oc = ellipsoid(f'oc{key[0]}{k2}', Vector((0, 0, 0)), (0.025, 0.025, 0.015), ocM, 16, 8); oc.parent = o; oc.location = top
prob = tube('proboscis', [HEAD_C + Vector((0, -0.08, -0.31)), HEAD_C + Vector((0, -0.1, -0.35))], 0.03, 0.035, dark)

# wings: thin film, veins from a generated texture
from PIL import Image, ImageDraw, ImageFilter
wimg = os.path.join(HERE, 'wing.png')
if not os.path.exists(wimg):
    W, Hh = 1400, 560; im = Image.new('L', (W, Hh), 0); d = ImageDraw.Draw(im)
    def P(u, v): return (u * W, (0.5 - v) * Hh)
    for path in [[(0.02, 0.0), (0.4, 0.18), (0.75, 0.28), (0.98, 0.3)], [(0.02, 0.0), (0.45, 0.06), (0.8, 0.1), (0.99, 0.12)],
                 [(0.02, 0.0), (0.42, -0.06), (0.8, -0.1), (0.97, -0.12)], [(0.05, -0.02), (0.4, -0.2), (0.7, -0.3), (0.9, -0.34)],
                 [(0.4, 0.06), (0.42, -0.06)], [(0.62, 0.0), (0.66, -0.12)]]:
        d.line([P(*q) for q in path], fill=255, width=7, joint='curve')
    im = im.filter(ImageFilter.GaussianBlur(1.2)); im.save(wimg)
wingM = bpy.data.materials.new('wing'); nt, out = nodes(wingM)
p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.inputs['Base Color'].default_value = (0.8, 0.85, 0.9, 1)
p.inputs['Roughness'].default_value = 0.08; p.inputs['Thin Film Thickness'].default_value = 520; p.inputs['Thin Film IOR'].default_value = 1.45
p.inputs['Alpha'].default_value = 0.22
uv = nt.nodes.new('ShaderNodeTexCoord'); timg = nt.nodes.new('ShaderNodeTexImage'); timg.image = bpy.data.images.load(wimg)
nt.links.new(uv.outputs['UV'], timg.inputs['Vector'])
vein = principled('vein', (0.08, 0.05, 0.03), rough=0.4)
pv = nt.nodes.new('ShaderNodeBsdfPrincipled'); pv.inputs['Base Color'].default_value = (0.07, 0.045, 0.025, 1); pv.inputs['Roughness'].default_value = 0.4
mixw = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(timg.outputs['Color'], mixw.inputs[0])
nt.links.new(p.outputs[0], mixw.inputs[1]); nt.links.new(pv.outputs[0], mixw.inputs[2]); nt.links.new(mixw.outputs[0], out.inputs[0])
def wing(s):
    outline = []
    for i in range(48):
        a = i / 48 * 2 * math.pi
        u = 0.5 + 0.5 * math.cos(a); v = 0.18 * math.sin(a) * (0.55 + 0.45 * u)
        outline.append((u, v))
    bm = bmesh.new(); vs = [bm.verts.new((u * 2.3, v * 2.3, 0)) for (u, v) in outline]
    f = bm.faces.new(vs); bmesh.ops.triangulate(bm, faces=[f])
    me = bpy.data.meshes.new(f'wing{s}'); bm.to_mesh(me); bm.free()
    uvl = me.uv_layers.new(name='UVMap')
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co; uvl.data[loop.index].uv = (co.x / 2.3, co.y / 2.3 / 0.9 + 0.5)
    o = link(bpy.data.objects.new(f'wing{s}', me)); me.materials.append(wingM)
    o.location = (s * 0.22, 0.35, 1.62)
    o.rotation_euler = (math.radians(4), math.radians(s * -6), math.radians(90 + s * -22))
    o.scale = (1, s, 1)
    return o
wing(-1); wing(1)

# legs
for s in (-1, 1):
    for k, y in enumerate((-0.32, 0.12, 0.52)):
        hip = Vector((s * 0.36, y, 0.82)); spread = (-0.5, 0.0, 0.55)[k]
        knee = Vector((s * 0.78, y + spread * 0.6, 0.74))
        ankle = Vector((s * 1.02, y + spread * 1.0, 0.12)); foot = Vector((s * 1.2, y + spread * 1.25, 0.02))
        def seg(a, b, n): return [a.lerp(b, i / n) for i in range(n)]
        pts = seg(hip, knee, 6) + seg(knee, ankle, 10) + seg(ankle, foot, 4) + [foot]
        tube(f'leg{s}{k}', pts, 0.095, 0.04, chitin, 12)
        for i in range(16):   # leg bristles
            q = pts[3 + i]; dirn = (pts[4 + i] - q).normalized()
            out_ = dirn.cross(Vector((0, 0, 1))).normalized() * s
            tube(f'lb{s}{k}{i}', [q, q + out_ * 0.05 + dirn * 0.06], 0.006, 0.002, dark, 4)

# bristles: thorax macrochaetae + fine hairs on head and thorax
def bristles(name, center, radii, count, length, upper=0.0, seed=1, thick=0.007):
    r = np.random.RandomState(seed); V = []; F = []
    for i in range(count):
        th = r.uniform(0, 2 * math.pi); z = r.uniform(upper, 1.0); rr = math.sqrt(1 - z * z)
        n = Vector((rr * math.cos(th), rr * math.sin(th), z))
        p0 = center + Vector((n.x * radii[0], n.y * radii[1], n.z * radii[2]))
        tip = p0 + (n + Vector((0, 0.9, 0.2))).normalized() * length * r.uniform(0.6, 1.0)
        mid = p0.lerp(tip, 0.5) + n * length * 0.12
        base = len(V)
        for q, w in ((p0, thick), (mid, thick * 0.6), (tip, thick * 0.15)):
            a = (tip - p0).normalized().orthogonal().normalized(); b = (tip - p0).normalized().cross(a)
            for k in range(4): V.append(q + (a * math.cos(k * 1.5708) + b * math.sin(k * 1.5708)) * w)
        for j in range(2):
            for k in range(4): F.append((base + j * 4 + k, base + j * 4 + (k + 1) % 4, base + (j + 1) * 4 + (k + 1) % 4, base + (j + 1) * 4 + k))
    return mesh_obj(name, V, F, dark)
bristles('thorax_macro', Vector((0, 0.15, 1.12)), (0.66, 0.82, 0.62), 26, 0.42, 0.35, 3, 0.012)
bristles('thorax_fine', Vector((0, 0.15, 1.12)), (0.66, 0.82, 0.62), 900, 0.07, 0.05, 4, 0.004)
bristles('abd_fine', Vector((0, 1.5, 0.98)), (0.58, 1.0, 0.52), 700, 0.06, -0.2, 5, 0.0035)

# ---------------------------------------------------------------- the brain
BR = HEAD_C
blobs = [((-0.11, 0.0, 0.03), (0.13, 0.12, 0.15)), ((0.11, 0.0, 0.03), (0.13, 0.12, 0.15)),
         ((-0.26, 0.0, 0.02), (0.09, 0.10, 0.17)), ((0.26, 0.0, 0.02), (0.09, 0.10, 0.17)),
         ((0.0, -0.01, -0.13), (0.11, 0.09, 0.06))]
def inside(p):
    best = 9.0
    for c, r in blobs:
        q = ((p[0] - c[0]) / r[0]) ** 2 + ((p[1] - c[1]) / r[1]) ** 2 + ((p[2] - c[2]) / r[2]) ** 2
        best = min(best, q)
    return best
def rand_in(r):
    while True:
        p = np.array([r.uniform(-0.36, 0.36), r.uniform(-0.13, 0.13), r.uniform(-0.2, 0.2)])
        if inside(p) < 1.0: return p
def neurons(name, count, seed):
    r = np.random.RandomState(seed); paths = []
    def walk(p, d, n, step=0.0095, wob=0.13):
        pts = [p.copy()]
        for k in range(n):
            d = d + r.normal(size=3) * wob; d /= np.linalg.norm(d)
            q = p + d * step
            if inside(q) > 1.0:
                d = -q / (np.linalg.norm(q) + 1e-6) + r.normal(size=3) * 0.2; d /= np.linalg.norm(d); q = p + d * step
            p = q; pts.append(p.copy())
        return np.array(pts)
    for i in range(count):
        p = rand_in(r); d = r.normal(size=3); d /= np.linalg.norm(d)
        if i % 4 == 0: d = np.array([np.sign(r.uniform(-1, 1)), r.normal() * 0.15, r.normal() * 0.15]); d /= np.linalg.norm(d)
        trunk = walk(p, d, r.randint(45, 95)); paths.append(trunk)
        for j in range(r.randint(1, 4)):
            q = trunk[r.randint(5, len(trunk) - 1)]; dd = r.normal(size=3); dd /= np.linalg.norm(dd)
            paths.append(walk(q, dd, r.randint(12, 35), 0.008, 0.22))
    V = []; F = []; UV = []; COL = []
    pal = [(0.7, 0.85, 1.0), (0.42, 0.22, 1.0), (1.0, 0.55, 0.12), (0.12, 0.55, 1.0)]
    for i, P_ in enumerate(paths):
        phase = r.uniform(); col = pal[r.choice(4, p=[0.12, 0.32, 0.24, 0.32])]; rad = r.uniform(0.0022, 0.0048)
        base = len(V); n = len(P_); sides = 4
        for j in range(n):
            t = P_[min(j + 1, n - 1)] - P_[max(j - 1, 0)]; t /= (np.linalg.norm(t) + 1e-9)
            a = np.cross(t, [0.3, 0.5, 0.81]); a /= np.linalg.norm(a); b = np.cross(t, a)
            for k in range(sides):
                th = k / sides * 2 * math.pi
                V.append(tuple(P_[j] + (a * math.cos(th) + b * math.sin(th)) * rad))
                UV.append((j / (n - 1), phase)); COL.append(col)
        for j in range(n - 1):
            for k in range(sides):
                F.append((base + j * sides + k, base + j * sides + (k + 1) % sides, base + (j + 1) * sides + (k + 1) % sides, base + (j + 1) * sides + k))
    me = bpy.data.meshes.new(name); me.from_pydata(V, [], F); me.update()
    uvl = me.uv_layers.new(name='nuv'); vi = np.zeros(len(me.loops), dtype=np.int32); me.loops.foreach_get('vertex_index', vi)
    UVa = np.array(UV, dtype=np.float32); uvl.data.foreach_set('uv', UVa[vi].ravel())
    ca = me.color_attributes.new('ncol', 'FLOAT_COLOR', 'POINT')
    C4_ = np.ones((len(V), 4), dtype=np.float32); C4_[:, :3] = np.array(COL); ca.data.foreach_set('color', C4_.ravel())
    o = link(bpy.data.objects.new(name, me)); return o
neuM = bpy.data.materials.new('neuron'); nt, out = nodes(neuM)
uvm = nt.nodes.new('ShaderNodeUVMap'); uvm.uv_map = 'nuv'; sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(uvm.outputs[0], sp.inputs[0])
Tn = nt.nodes.new('ShaderNodeValue'); Tn.name = 'T'
Bn = nt.nodes.new('ShaderNodeValue'); Bn.name = 'B'
def M(op, a=None, b=None, va=None, vb=None):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op
    if a is not None: nt.links.new(a, n.inputs[0])
    elif va is not None: n.inputs[0].default_value = va
    if b is not None: nt.links.new(b, n.inputs[1])
    elif vb is not None: n.inputs[1].default_value = vb
    return n.outputs[0]
x = M('MULTIPLY', sp.outputs['X'], vb=2.5)
x = M('SUBTRACT', x, M('MULTIPLY', Tn.outputs[0], vb=1.1))
x = M('ADD', x, M('MULTIPLY', sp.outputs['Y'], vb=9.0))
fr_ = M('FRACT', x); pulse = M('POWER', M('SUBTRACT', va=1.0, b=fr_), vb=28.0)
strength = M('MULTIPLY', M('ADD', M('MULTIPLY', pulse, vb=14.0), vb=0.7), Bn.outputs[0])
att = nt.nodes.new('ShaderNodeAttribute'); att.attribute_name = 'ncol'
emn = nt.nodes.new('ShaderNodeEmission'); nt.links.new(att.outputs['Color'], emn.inputs['Color']); nt.links.new(strength, emn.inputs['Strength'])
nt.links.new(emn.outputs[0], out.inputs[0])
brain = neurons('neurons', 230, 11); brain.data.materials.append(neuM); brain.location = BR
# brain membrane: translucent gold shell around the neuropils
memM = bpy.data.materials.new('membrane'); nt, out = nodes(memM)
lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.35
mb = nt.nodes.new('ShaderNodeValue'); mb.name = 'B'
mm = nt.nodes.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; nt.links.new(lw.outputs['Facing'], mm.inputs[0]); nt.links.new(mb.outputs[0], mm.inputs[1])
mm2 = nt.nodes.new('ShaderNodeMath'); mm2.operation = 'MULTIPLY'; mm2.inputs[1].default_value = 0.18; nt.links.new(mm.outputs[0], mm2.inputs[0])
eme = nt.nodes.new('ShaderNodeEmission'); eme.inputs[0].default_value = (0.55, 0.4, 1.0, 1); nt.links.new(mm2.outputs[0], eme.inputs[1])
trm = nt.nodes.new('ShaderNodeBsdfTransparent'); adm = nt.nodes.new('ShaderNodeAddShader')
nt.links.new(eme.outputs[0], adm.inputs[0]); nt.links.new(trm.outputs[0], adm.inputs[1]); nt.links.new(adm.outputs[0], out.inputs[0])
for i, (c, r) in enumerate(blobs):
    o = ellipsoid(f'neuropil{i}', BR + Vector(c), tuple(x * 1.06 for x in r), memM, 48, 24); o.visible_shadow = False
# synapse sparks inside + sparks that drift out when the head opens
def sparks(name, count, seed, spread, col, s):
    r = np.random.RandomState(seed); V = []; F = []
    for i in range(count):
        p = rand_in(r) if spread is None else r.normal(size=3) * spread
        base = len(V); e = r.uniform(0.5, 1.0) * s
        for d in ((e, 0, 0), (-e, 0, 0), (0, e, 0), (0, -e, 0), (0, 0, e), (0, 0, -e)): V.append(tuple(np.array(p) + d))
        for f in ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)): F.append(tuple(base + k for k in f))
    m = emission(name + 'M', col, 0.0); m.node_tree.nodes['Emission'].name = 'E'
    o = mesh_obj(name, V, F, m, smooth=False); o.visible_shadow = False; return o
syn = sparks('synapses', 450, 21, None, (1.0, 0.85, 0.55), 0.0022); syn.location = BR
dust = sparks('dust', 260, 22, 0.55, (1.0, 0.8, 0.45), 0.006); dust.location = BR

FLY = bpy.data.objects.new('fly_root', None); link(FLY); FLY.scale = (FS, FS, FS)
for o in set(bpy.data.objects) - _before:
    if o is not FLY and o.parent is None:
        o.parent = FLY
# ---------------------------------------------------------------- close-up lights (purple / gold)
def area(name, loc, target, col, size):
    L = bpy.data.lights.new(name, 'SPOT'); L.shadow_soft_size = size * 0.4; L.spot_size = math.radians(34); L.spot_blend = 0.5; L.color = col; L.energy = 0
    o = link(bpy.data.objects.new(name, L)); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return L
purple = area('purple', (-3.2, -4.6, 3.6), HEAD_W, (0.48, 0.3, 1.0), 3.0)
gold = area('gold', (3.0, -4.3, 1.6), HEAD_W, (1.0, 0.66, 0.3), 2.4)
rim = area('rim', (0.0, 1.6, 4.6), HEAD_W, (0.5, 0.75, 1.0), 2.5)

# ---------------------------------------------------------------- camera
cam = bpy.data.cameras.new('cam'); cam.lens = 30; cam.sensor_width = 36; cam.sensor_fit = 'HORIZONTAL'
cam.dof.use_dof = True; cam.dof.aperture_fstop = 8.0
co = link(bpy.data.objects.new('cam', cam)); sc.camera = co
# keys: (t, position, look-at, lens, fstop)
KEYS = [
    (0.0,  (-7.2, -37.5, 1.3), (0.2, 0.0, 5.2), 28, 11),
    (3.0,  (-0.8, -35.5, 1.6), (0.0, 0.0, 5.2), 28, 11),
    (8.0,  (0.3, -22.0, 1.8),  (0.0, 0.0, 4.2), 30, 11),
    (11.5, (0.25, -9.5, 2.1), (0.0, -1.4, 2.2), 36, 8),
    (14.0, (0.0, -5.2, 2.1), HEAD_W[:],        45, 5.6),
    (18.5, (0.04, -3.05, 2.45), HEAD_W[:],        40, 4.0),
    (22.5, (-0.14, -2.85, 2.5), HEAD_W[:],        40, 4.0),
    (28.0, (0.0, -4.8, 2.08), HEAD_W[:],         45, 5.6),
]
def cr_(p0, p1, p2, p3, u):
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
def cam_at(t):
    ks = KEYS
    for i in range(len(ks) - 1):
        if ks[i][0] <= t <= ks[i + 1][0]: break
    else: i = len(ks) - 2
    a, b = ks[i], ks[i + 1]; u = smooth01((t - a[0]) / (b[0] - a[0]))
    p0 = ks[max(i - 1, 0)]; p3 = ks[min(i + 2, len(ks) - 1)]
    pos = cr_(Vector(p0[1]), Vector(a[1]), Vector(b[1]), Vector(p3[1]), u)
    tgt = cr_(Vector(p0[2]), Vector(a[2]), Vector(b[2]), Vector(p3[2]), u)
    return pos, tgt, a[3] + (b[3] - a[3]) * u, a[4] + (b[4] - a[4]) * u

# ---------------------------------------------------------------- animation state for time t
OPEN0, OPEN1, CLOSE0, CLOSE1 = 15.0, 17.6, 22.6, 25.0
def set_time(t):
    pos, tgt, lens, fs = cam_at(t)
    co.location = pos; co.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()
    cam.lens = lens; cam.dof.aperture_fstop = fs; cam.dof.focus_distance = (tgt - pos).length
    # saucer: slow spin + bob, light flicker
    ufo.rotation_euler.z = t * 0.12; bob = 0.08 * math.sin(t * 1.3)
    for o in (ufo, ring, core): o.location.z = (UFO_C.z if o is ufo else (UFO_C.z - 0.8 if o is ring else UFO_C.z - 0.9)) + bob
    fl = 1.0 + 0.06 * math.sin(t * 17.0) * math.sin(t * 3.1)
    ringM.node_tree.nodes['Emission'].inputs[1].default_value = 35.0 * fl
    shaftM.node_tree.nodes['K'].inputs[1].default_value = 0.55 * fl
    # head opening
    op = smooth01((t - OPEN0) / (OPEN1 - OPEN0)) * (1 - smooth01((t - CLOSE0) / (CLOSE1 - CLOSE0)))
    for o, c, d, key in PANELS:
        delay = (key[0] % 3) * 0.08 + key[1] * 0.06
        k = smooth01((op - delay) / max(0.01, 1 - delay)) if op > 0 else 0.0
        hz = Vector((d.x, d.y, 0)); hz = hz.normalized() if hz.length > 1e-4 else Vector((0, -1, 0))
        axis = Vector((0, 0, 1)).cross(hz).normalized()
        ang = (1.05 if key[1] == 1 else -1.15) * k
        R = Matrix.Rotation(ang, 4, axis)
        o.location = c + hz * (0.18 * k) + Vector((0, 0, (0.18 if key[1] == 1 else -0.16) * k))
        o.rotation_euler = R.to_euler()
    for e, s, l0, r0 in EYES:
        e.location = l0 + Vector((s * 0.42 * op, 0.02 * op, 0.0))
        e.rotation_euler = (r0.x, r0.y, r0.z + s * 0.45 * op)
    ramp = smooth01((t - 10.5) / 3.5)
    purple.energy = 550 * ramp; gold.energy = 500 * ramp; rim.energy = 650 * ramp
    beamL.energy = 5000 * (1 - 0.9 * ramp); underL.energy = 1200 * (1 - 0.9 * ramp)
    bg.inputs['Strength'].default_value = 1.0 - 0.85 * ramp; sun.energy = 0.55 * (1 - 0.7 * ramp)
    shaftM.node_tree.nodes['K'].inputs[1].default_value *= (1 - smooth01((t - 8.0) / 2.5))
    shaft.hide_render = t > 10.6
    for o_ in bpy.data.objects:
        if o_.name.startswith('neuropil') or o_.name in ('neurons', 'synapses', 'dust'): o_.hide_render = not (OPEN0 - 0.2 < t < CLOSE1 + 0.3)
    bval = 0.08 + 1.0 * smooth01((t - OPEN0 - 0.6) / 1.8) * (1 - smooth01((t - CLOSE0 - 0.5) / 1.8))
    neuM.node_tree.nodes['T'].outputs[0].default_value = t
    neuM.node_tree.nodes['B'].outputs[0].default_value = bval
    memM.node_tree.nodes['B'].outputs[0].default_value = bval
    syn.data.materials[0].node_tree.nodes['E'].inputs[1].default_value = 18.0 * bval * (0.7 + 0.3 * math.sin(t * 9))
    dk = smooth01((t - OPEN0 - 0.4) / 3.0) * (1 - smooth01((t - CLOSE0) / 2.0))
    dust.scale = (0.15 + 0.85 * dk,) * 3; dust.rotation_euler = (t * 0.15, t * 0.22, t * 0.1)
    dust.data.materials[0].node_tree.nodes['E'].inputs[1].default_value = 25.0 * dk
    flare = smooth01((t - 24.6) / 0.6) * (1 - 0.6 * smooth01((t - 26.2) / 1.6))
    eyeM.node_tree.nodes['G'].outputs[0].default_value = 6.0 * flare

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    outd = argv[0] if argv else os.path.join(HERE, 'test')
    times = [float(x) for x in argv[1].split(',')] if len(argv) > 1 and ':' not in argv[1] else [6.0]
    resw = int(argv[2]) if len(argv) > 2 else 540
    spp = int(argv[3]) if len(argv) > 3 else 32
    sc.render.resolution_x = resw; sc.render.resolution_y = int(resw * 16 / 9); sc.cycles.samples = spp
    os.makedirs(outd, exist_ok=True)
    mode = argv[4] if len(argv) > 4 else 'stills'
    if mode == 'frames':
        spec = argv[1]
        if ':' in spec:      # start:stop:step, e.g. 671:335:-1 renders backwards
            a_, b_, c_ = (int(x) for x in spec.split(':')); frames = list(range(a_, b_, c_))
        else:
            frames = [int(x) for x in spec.split(',')]
        jobs = [(fr / FPS, os.path.join(outd, f'f{fr:04d}.png')) for fr in frames]
    else:
        jobs = [(t, os.path.join(outd, f't{t:05.2f}.png')) for t in times]
    for t, p in jobs:
        if os.path.exists(p) and os.path.getsize(p) > 1000: continue
        t0 = time.time(); set_time(t); sc.render.filepath = p
        bpy.ops.render.render(write_still=True); print('DONE', round(t, 2), round(time.time() - t0, 1), flush=True)
