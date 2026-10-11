# Booster-catch film, 3D part. The booster's position, tilt, engines, throttle and grid fins in every frame
# come from the simulator flights (flights/*.json via shots.py). Built in code with Blender / Cycles.
#   python3 film.py -- <outdir> <a:b:step | f1,f2,...> <res_w> <spp>
import bpy, bmesh, math, os, sys, time, shutil
from mathutils import Vector, Matrix, Euler
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import shots
from shots import FPS, ARM_Z

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
if os.environ.get('BUBO_GPU'):
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for typ in ('OPTIX', 'CUDA', 'METAL'):
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
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2
sc.cycles.transparent_max_bounces = 16; sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.03
sc.render.fps = FPS; sc.render.use_persistent_data = True
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
try:
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Punchy'
except Exception:
    sc.view_settings.view_transform = 'Filmic'
sc.view_settings.exposure = 0.0

# ---------------------------------------------------------------- materials
def mat(name, color=(0.8, 0.8, 0.8), metal=0.0, rough=0.5, emit=None, strength=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
    return m

def steel_mat():
    m = bpy.data.materials.new('steel'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N['Principled BSDF']
    b.inputs['Metallic'].default_value = 1.0; b.inputs['Roughness'].default_value = 0.28
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -63; mr.inputs['From Max'].default_value = -30
    L.new(sep.outputs['Z'], mr.inputs['Value'])
    noise = N.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 0.4; L.new(tc.outputs['Object'], noise.inputs['Vector'])
    mix = N.new('ShaderNodeMath'); mix.operation = 'MULTIPLY'; L.new(mr.outputs[0], mix.inputs[0]); L.new(noise.outputs['Fac'], mix.inputs[1])
    add = N.new('ShaderNodeMath'); add.operation = 'ADD'; add.use_clamp = True; L.new(mix.outputs[0], add.inputs[0]); L.new(mr.outputs[0], add.inputs[1])
    ramp = N.new('ShaderNodeValToRGB'); L.new(add.outputs[0], ramp.inputs[0])
    ramp.color_ramp.elements[0].color = (0.035, 0.03, 0.028, 1)      # soot at the base
    ramp.color_ramp.elements[1].color = (0.6, 0.6, 0.62, 1)
    dv = N.new('ShaderNodeMath'); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = 1.83; L.new(sep.outputs['Z'], dv.inputs[0])
    fr_ = N.new('ShaderNodeMath'); fr_.operation = 'FRACT'; L.new(dv.outputs[0], fr_.inputs[0])
    weld = N.new('ShaderNodeMath'); weld.operation = 'LESS_THAN'; weld.inputs[1].default_value = 0.035; L.new(fr_.outputs[0], weld.inputs[0])
    wmix = N.new('ShaderNodeMix'); wmix.data_type = 'RGBA'; L.new(weld.outputs[0], wmix.inputs['Factor'])
    L.new(ramp.outputs[0], wmix.inputs['A']); wmix.inputs['B'].default_value = (0.2, 0.19, 0.18, 1)
    fz = N.new('ShaderNodeMapRange'); fz.inputs['From Min'].default_value = -55; fz.inputs['From Max'].default_value = -20
    fz.inputs['To Min'].default_value = 1.0; fz.inputs['To Max'].default_value = 0.0; L.new(sep.outputs['Z'], fz.inputs['Value'])
    fz2 = N.new('ShaderNodeMapRange'); fz2.inputs['From Min'].default_value = -60; fz2.inputs['From Max'].default_value = -55
    L.new(sep.outputs['Z'], fz2.inputs['Value'])
    fn = N.new('ShaderNodeTexNoise'); fn.inputs['Scale'].default_value = 0.45; fn.inputs['Detail'].default_value = 6; L.new(tc.outputs['Object'], fn.inputs['Vector'])
    fm = N.new('ShaderNodeMath'); fm.operation = 'MULTIPLY'; L.new(fz.outputs[0], fm.inputs[0]); L.new(fz2.outputs[0], fm.inputs[1])
    fm2 = N.new('ShaderNodeMath'); fm2.operation = 'MULTIPLY'; L.new(fm.outputs[0], fm2.inputs[0]); L.new(fn.outputs['Fac'], fm2.inputs[1])
    frost = N.new('ShaderNodeMapRange'); frost.inputs['From Min'].default_value = 0.42; frost.inputs['From Max'].default_value = 0.5
    L.new(fm2.outputs[0], frost.inputs['Value'])
    fmix = N.new('ShaderNodeMix'); fmix.data_type = 'RGBA'; L.new(frost.outputs[0], fmix.inputs['Factor'])
    L.new(wmix.outputs[2], fmix.inputs['A']); fmix.inputs['B'].default_value = (0.82, 0.83, 0.85, 1)
    L.new(fmix.outputs[2], b.inputs['Base Color'])
    fmet = N.new('ShaderNodeMath'); fmet.operation = 'SUBTRACT'; fmet.inputs[0].default_value = 1.0; L.new(frost.outputs[0], fmet.inputs[1])
    L.new(fmet.outputs[0], b.inputs['Metallic'])
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.85; rr.inputs['To Max'].default_value = 0.34
    L.new(add.outputs[0], rr.inputs['Value'])
    rmax = N.new('ShaderNodeMath'); rmax.operation = 'MAXIMUM'; L.new(rr.outputs[0], rmax.inputs[0]); L.new(frost.outputs[0], rmax.inputs[1])
    L.new(rmax.outputs[0], b.inputs['Roughness'])
    return m

def flame_mat(name, core=(1.0, 0.62, 0.32), edge=(1.0, 0.22, 0.04), strength=6.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; L = nt.links
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs[0])
    # generated Z: 1 at the nozzle, 0 at the tip (cone points down)
    ramp = N.new('ShaderNodeValToRGB'); L.new(sep.outputs['Z'], ramp.inputs[0])
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (*edge, 1)
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (*core, 1)
    em = N.new('ShaderNodeEmission'); L.new(ramp.outputs[0], em.inputs['Color'])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6; L.new(sep.outputs['Z'], pw.inputs[0])
    st = N.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = strength; L.new(pw.outputs[0], st.inputs[0])
    oi = N.new('ShaderNodeObjectInfo'); sep2 = N.new('ShaderNodeSeparateColor'); L.new(oi.outputs['Color'], sep2.inputs[0])
    st2 = N.new('ShaderNodeMath'); st2.operation = 'MULTIPLY'; L.new(st.outputs[0], st2.inputs[0]); L.new(sep2.outputs[0], st2.inputs[1])
    L.new(st2.outputs[0], em.inputs['Strength'])
    lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.35
    alpha = N.new('ShaderNodeMath'); alpha.operation = 'MULTIPLY'; L.new(sep.outputs['Z'], alpha.inputs[0])
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; L.new(lw.outputs['Facing'], inv.inputs[1])
    L.new(inv.outputs[0], alpha.inputs[1])
    sq = N.new('ShaderNodeMath'); sq.operation = 'POWER'; sq.inputs[1].default_value = 0.6; sq.use_clamp = True; L.new(alpha.outputs[0], sq.inputs[0])
    tr = N.new('ShaderNodeBsdfTransparent'); mix = N.new('ShaderNodeMixShader')
    L.new(sq.outputs[0], mix.inputs['Fac']); L.new(tr.outputs[0], mix.inputs[1]); L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs['Surface'])
    m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    return m

STEEL = steel_mat()
DARK = mat('dark', (0.025, 0.025, 0.027), 0.6, 0.55)
TOWER = mat('tower', (0.05, 0.05, 0.055), 0.4, 0.7)
ARMS = mat('arms', (0.16, 0.16, 0.17), 0.6, 0.5)
CONCRETE = mat('concrete', (0.09, 0.088, 0.085), 0.0, 0.92)
SAND = mat('sand', (0.2, 0.17, 0.13), 0.0, 1.0)
NOZZLE = mat('nozzle', (0.06, 0.05, 0.05), 0.9, 0.35)
FIRE = flame_mat('flame')

def link(o, coll=None):
    (coll or sc.collection).objects.link(o); return o

def mesh_obj(name, bm, material):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(material); o = bpy.data.objects.new(name, me); link(o)
    for p in me.polygons: p.use_smooth = True
    return o

def beam(bm, a, b, r, seg=6):
    a, b = Vector(a), Vector(b); d = b - a; L_ = d.length
    if L_ < 1e-6: return
    m = Matrix.Translation((a + b) / 2) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=L_, matrix=m)

def box(bm, center, size, rot=None):
    m = Matrix.Translation(center) @ (rot or Matrix.Identity(4)) @ Matrix.Diagonal((*size, 1))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)

# ---------------------------------------------------------------- booster (origin = catch point, 8 m below the top)
R = 4.5
booster = bpy.data.objects.new('booster', None); link(booster)
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=R, radius2=R, depth=67.5,
                                        matrix=Matrix.Translation((0, 0, 5.5 - 33.75)))
body = mesh_obj('body', bm, STEEL); body.parent = booster
bm = bmesh.new()                                                  # hot-stage ring: vented band on top, then a flat dome
bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=R * 0.97, radius2=R * 0.97, depth=2.5, matrix=Matrix.Translation((0, 0, 6.75)))
for i in range(36):
    a_ = i / 36 * 2 * math.pi
    box(bm, Vector((math.cos(a_) * R * 0.99, math.sin(a_) * R * 0.99, 6.75)), (0.25, 0.42, 2.5), Matrix.Rotation(a_, 4, 'Z'))
bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=R * 1.01, radius2=R * 1.01, depth=0.35, matrix=Matrix.Translation((0, 0, 8.0)))
bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=R * 1.01, radius2=R * 1.01, depth=0.35, matrix=Matrix.Translation((0, 0, 5.55)))
ring = mesh_obj('hotstage', bm, DARK); ring.parent = booster
bm = bmesh.new()                                                  # catch hardpoints the arms take the load on, raceway, chines
for side in (-1, 1):
    box(bm, Vector((side * (R + 0.55), 0, 0.3)), (1.2, 1.8, 1.1))
    box(bm, Vector((side * (R + 0.25), 0, -0.7)), (0.6, 1.4, 1.2))
ra = math.radians(235)
box(bm, Vector((math.cos(ra) * (R + 0.22), math.sin(ra) * (R + 0.22), -28.0)), (0.45, 0.7, 64.0), Matrix.Rotation(ra, 4, 'Z'))
for ca in (math.radians(150), math.radians(330)):
    box(bm, Vector((math.cos(ca) * (R + 0.12), math.sin(ca) * (R + 0.12), -46.0)), (0.25, 0.25, 30.0), Matrix.Rotation(ca, 4, 'Z'))
bits = mesh_obj('bits', bm, DARK); bits.parent = booster
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=R * 0.99, radius2=R, depth=1.2,
                                        matrix=Matrix.Translation((0, 0, -62.6)))
skirt = mesh_obj('skirt', bm, DARK); skirt.parent = booster
BASE_Z = -63.2
ENG = [(1.05 * math.cos(a_), 1.05 * math.sin(a_)) for a_ in (math.pi / 2, math.pi / 2 + 2.094, math.pi / 2 + 4.189)]
ENG += [(2.55 * math.cos(i / 10 * 2 * math.pi + 0.3), 2.55 * math.sin(i / 10 * 2 * math.pi + 0.3)) for i in range(10)]
OUTER = [(3.88 * math.cos(i / 20 * 2 * math.pi), 3.88 * math.sin(i / 20 * 2 * math.pi)) for i in range(20)]
bm = bmesh.new()
for k, (ex, ey) in enumerate(ENG + OUTER):                         # 33 engines: 13 gimbaled inside, 20 fixed outside
    rr = 0.6 if k < 13 else 0.52
    bmesh.ops.create_cone(bm, cap_ends=False, segments=20, radius1=rr, radius2=rr * 0.5, depth=1.7,
                          matrix=Matrix.Translation((ex, ey, BASE_Z - 0.85)))
nozz = mesh_obj('nozzles', bm, NOZZLE); nozz.parent = booster
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=R * 0.95, radius2=R * 0.95, depth=0.2,
                                        matrix=Matrix.Translation((0, 0, BASE_Z + 0.05)))
plate = mesh_obj('plate', bm, DARK); plate.parent = booster
flames = []
for k, (ex, ey) in enumerate(ENG):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=1.1, radius2=0.6, depth=1.0,
                                            matrix=Matrix.Translation((0, 0, -0.5)))
    f = mesh_obj(f'flame{k}', bm, FIRE); f.parent = booster; f.location = (ex, ey, BASE_Z - 1.7)
    f.visible_shadow = False; flames.append(f)
glow = bpy.data.lights.new('glow', 'POINT'); glow.color = (1.0, 0.55, 0.25); glow.shadow_soft_size = 4.0
glow_o = bpy.data.objects.new('glow', glow); link(glow_o); glow_o.parent = booster; glow_o.location = (0, 0, BASE_Z - 25)
fins = []
for i in range(4):                                               # grid fins: big lattice panels near the top
    a_ = i * math.pi / 2 + math.pi / 4
    piv = bpy.data.objects.new(f'finpiv{i}', None); link(piv); piv.parent = booster
    piv.location = (math.cos(a_) * R, math.sin(a_) * R, 3.0); piv.rotation_euler = (0, 0, a_)
    bm = bmesh.new()
    FW, FL, TH = 5.0, 3.6, 0.75                                   # tangential width, radial length, depth
    for gx in range(7):
        box(bm, Vector((0.35 + FL / 2, -FW / 2 + gx * FW / 6, 0)), (FL, 0.07, TH))
    for gy in range(6):
        box(bm, Vector((0.35 + gy * FL / 5, 0, 0)), (0.07, FW, TH))
    box(bm, Vector((0.2, 0, 0)), (0.5, 1.6, 1.6))                 # hinge
    fo = mesh_obj(f'fin{i}', bm, DARK); fo.parent = piv; fins.append(piv)

# ---------------------------------------------------------------- tower, arms, launch mount
TY = 20.0                                                        # tower center y (behind the booster, camera looks +y)
bm = bmesh.new(); H = 146.0; hw = 6.0
legs = [(-hw, TY - hw), (hw, TY - hw), (hw, TY + hw), (-hw, TY + hw)]
for (lx, ly) in legs: beam(bm, (lx, ly, 0), (lx, ly, H), 0.55, 8)
lv = 0.0
while lv < H - 1:
    nz = min(H, lv + 9.0)
    for i in range(4):
        (ax, ay), (bx, by) = legs[i], legs[(i + 1) % 4]
        beam(bm, (ax, ay, lv), (bx, by, lv), 0.3)
        beam(bm, (ax, ay, lv), (bx, by, nz), 0.2); beam(bm, (bx, by, lv), (ax, ay, nz), 0.2)
    lv = nz
beam(bm, (0, TY, H), (0, TY, H + 14), 0.35)                    # mast on top
box(bm, Vector((0, TY, H + 1)), (14, 14, 2))
tower = mesh_obj('tower', bm, TOWER)
bm = bmesh.new()                                                  # carriage that wraps the tower and carries the arms
box(bm, Vector((0, TY, ARM_Z + 2.5)), (15.5, 15.5, 1.2)); box(bm, Vector((0, TY, ARM_Z - 2.5)), (15.5, 15.5, 1.2))
box(bm, Vector((0, TY - hw - 1.6, ARM_Z)), (17, 3.2, 6.2))
for (lx, ly) in legs: box(bm, Vector((lx * 1.2, TY + (ly - TY) * 1.2, ARM_Z)), (1.0, 1.0, 6.2))
carriage = mesh_obj('carriage', bm, ARMS)
arms = []
ARM_LEN, ARM_X = 34.0, R + 1.3
for side in (-1, 1):                                              # chopsticks: long box-truss arms
    piv = bpy.data.objects.new(f'armpiv{side}', None); link(piv); piv.location = (side * ARM_X, TY - hw - 3.2, ARM_Z - 2.0)
    bm = bmesh.new(); w2, h2 = 0.9, 1.6
    for (cx, cz) in ((-w2, -h2), (w2, -h2), (-w2, h2), (w2, h2)):
        beam(bm, (cx, 0, cz), (cx, -ARM_LEN, cz), 0.22, 6)
    step = 2.8; yy = 0.0
    while yy > -ARM_LEN + 0.1:
        y2 = max(-ARM_LEN, yy - step)
        for cx in (-w2, w2):
            beam(bm, (cx, yy, -h2), (cx, y2, h2), 0.12); beam(bm, (cx, yy, h2), (cx, yy, -h2), 0.12)
        for cz in (-h2, h2): beam(bm, (-w2, yy, cz), (w2, yy, cz), 0.12)
        yy = y2
    box(bm, Vector((0, -ARM_LEN / 2, h2 + 0.15)), (2.0, ARM_LEN, 0.3))                 # deck plate
    box(bm, Vector((-side * (w2 + 0.15), -(TY - hw - 3.2), 0.3)), (0.6, 3.2, 1.4))  # catch rail where the hardpoint lands
    a_o = mesh_obj(f'arm{side}', bm, ARMS); a_o.parent = piv; arms.append((side, piv))
    bm = bmesh.new(); box(bm, Vector((0, -ARM_LEN / 2, 0)), (2 * w2 - 0.1, ARM_LEN - 0.2, 2 * h2 - 0.1))   # solid core: no see-through gaps
    core = mesh_obj(f'armcore{side}', bm, TOWER); core.parent = piv
bm = bmesh.new()                                                  # launch mount: a ring on six legs, open in the middle
for i in range(30):
    a_ = i / 30 * 2 * math.pi
    box(bm, Vector((math.cos(a_) * 9.5, math.sin(a_) * 9.5, 22.0)), (4.0, 2.1, 3.0), Matrix.Rotation(a_, 4, 'Z'))
for i in range(6):
    a_ = i / 6 * 2 * math.pi + 0.26
    box(bm, Vector((math.cos(a_) * 11.2, math.sin(a_) * 11.2, 10.5)), (2.0, 2.0, 21), Matrix.Rotation(a_, 4, 'Z'))
mount = mesh_obj('mount', bm, CONCRETE)
bm = bmesh.new(); box(bm, Vector((0, 0, -0.5)), (120, 120, 1.0)); pad = mesh_obj('pad', bm, CONCRETE)
bpy.ops.mesh.primitive_plane_add(size=40000, location=(0, 0, -0.6)); ground = bpy.context.active_object
ground.data.materials.append(SAND)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 9000, -0.3)); sea = bpy.context.active_object
sea.scale = (40000, 15000, 1); sea.data.materials.append(mat('sea', (0.02, 0.05, 0.07), 0.0, 0.08))
def fire_mat():
    m = bpy.data.materials.new('fireball'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; L = nt.links
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputMaterial'); tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.2; nz.inputs['Detail'].default_value = 8.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    oi = N.new('ShaderNodeObjectInfo'); sep = N.new('ShaderNodeSeparateColor'); L.new(oi.outputs['Color'], sep.inputs[0])
    sh = N.new('ShaderNodeMath'); sh.operation = 'SUBTRACT'; L.new(nz.outputs['Fac'], sh.inputs[0]); L.new(sep.outputs[1], sh.inputs[1])
    ramp = N.new('ShaderNodeValToRGB'); L.new(sh.outputs[0], ramp.inputs[0]); cr = ramp.color_ramp
    cr.elements[0].position = 0.15; cr.elements[0].color = (0.02, 0.004, 0.0, 1)
    cr.elements[1].position = 0.6; cr.elements[1].color = (1.0, 0.5, 0.1, 1)
    e = cr.elements.new(0.38); e.color = (0.9, 0.14, 0.01, 1)
    em = N.new('ShaderNodeEmission'); L.new(ramp.outputs[0], em.inputs['Color'])
    st = N.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = 6.0; L.new(sep.outputs[0], st.inputs[0])
    st2 = N.new('ShaderNodeMath'); st2.operation = 'MULTIPLY'; L.new(st.outputs[0], st2.inputs[0]); L.new(sh.outputs[0], st2.inputs[1])
    L.new(st2.outputs[0], em.inputs['Strength'])
    smoke = N.new('ShaderNodeBsdfPrincipled'); smoke.inputs['Base Color'].default_value = (0.008, 0.007, 0.006, 1)
    smoke.inputs['Roughness'].default_value = 1.0
    mx = N.new('ShaderNodeMixShader'); L.new(sh.outputs[0], mx.inputs['Fac']); L.new(smoke.outputs[0], mx.inputs[1]); L.new(em.outputs[0], mx.inputs[2])
    lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0; L.new(lw.outputs['Facing'], inv.inputs[1])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 0.7; L.new(inv.outputs[0], pw.inputs[0])
    tr = N.new('ShaderNodeBsdfTransparent'); mx2 = N.new('ShaderNodeMixShader')
    L.new(pw.outputs[0], mx2.inputs['Fac']); L.new(tr.outputs[0], mx2.inputs[1]); L.new(mx.outputs[0], mx2.inputs[2])
    L.new(mx2.outputs[0], out.inputs['Surface'])
    return m
balls = []
for j in range(3):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.0); b_ = bpy.context.active_object
    tex = bpy.data.textures.new(f'cl{j}', 'CLOUDS'); tex.noise_scale = 0.45
    md = b_.modifiers.new('d', 'DISPLACE'); md.texture = tex; md.strength = 0.45; md.texture_coords = 'OBJECT'
    b_.data.materials.append(fire_mat() if j == 0 else balls[0].data.materials[0]); b_.hide_render = True
    for p in b_.data.polygons: p.use_smooth = True
    b_.visible_shadow = False; balls.append(b_)
ball = balls[0]
boom = bpy.data.lights.new('boom', 'POINT'); boom.color = (1.0, 0.5, 0.2); boom_o = bpy.data.objects.new('boom', boom); link(boom_o)

# ---------------------------------------------------------------- world: low sun over the Gulf
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True; N = w.node_tree.nodes; L = w.node_tree.links
bg = N['Background']; sky = N.new('ShaderNodeTexSky')
for typ in ('NISHITA', 'SINGLE_SCATTERING', 'MULTIPLE_SCATTERING', 'HOSEK_WILKIE'):
    try: sky.sky_type = typ; break
    except Exception: pass
for attr, val in (('sun_elevation', math.radians(3.0)), ('sun_rotation', math.radians(225)), ('altitude', 10.0),
                  ('air_density', 1.2), ('dust_density', 2.0)):
    try: setattr(sky, attr, val)
    except Exception: pass
L.new(sky.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.35
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 2.2; sun.color = (1.0, 0.72, 0.5); sun.angle = math.radians(1.0)
sun_o = bpy.data.objects.new('sun', sun); link(sun_o); sun_o.rotation_euler = Euler((math.radians(86), 0, math.radians(-135)))

cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); link(cam); sc.camera = cam
cam_d.sensor_fit = 'VERTICAL'; cam_d.sensor_height = 36.0; cam_d.clip_start = 1.0; cam_d.clip_end = 60000

# ---------------------------------------------------------------- per-frame state
def smooth(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)

def look(pos, target, focal):
    pos, target = Vector(pos), Vector(target)
    q = (target - pos).to_track_quat('-Z', 'Y')
    return pos, q.to_euler(), focal

def impact_tl(s):
    T = shots.flight(s['flight'])['T']
    for (a, x), (b, y) in zip(s['keys'], s['keys'][1:]):
        if y >= T - 1e-6 and x < T - 1e-6: return a + (b - a) * (T - x) / (y - x)
    return None

TRACK_POS = tuple(float(v) for v in os.environ.get('TRACK', '-900,-5200,4').split(','))
def camera_for(info, bpos):
    s, cam_kind, tl = info['shot'], info['cam'], info['tl']
    if cam_kind == 'track':
        pos = Vector(TRACK_POS)
        tgt = bpos + Vector((0, 0, -26.0))
        d = (tgt - pos).length
        return look(pos, tgt, max(50.0, 36.0 * d / 190.0))
    if cam_kind == 'wide_hook':                                   # low angle under the tower, booster coming down with fire
        pos = Vector((-115.0 + 6.0 * tl, -190.0 + 10.0 * tl, 10.0))
        return look(pos, Vector((0.0, 0.0, ARM_Z + 22.0)), 29.0)
    if cam_kind == 'follow':                                      # far side cam: tower and booster in one frame, tilts up with it
        pos = Vector((160.0, -1500.0, 3.0))
        tgt = Vector((165.0, 0.0, max(380.0, bpos.z - 26.0)))
        return look(pos, tgt, 36.0 * (tgt - pos).length / 820.0)
    if cam_kind == 'close':                                       # the arms take the booster
        pos = Vector((-16.0 + 2.0 * tl, -72.0 + 4.0 * tl, ARM_Z + 14.0))
        return look(pos, Vector((0, 3, ARM_Z - 8)), 30.0)
    if cam_kind == 'wide_end':
        a = math.radians(-12 + 6 * tl / s['dur'])
        r = 150.0 - 8 * tl / s['dur']
        a += math.radians(-12)
        pos = Vector((math.sin(a) * r, -math.cos(a) * r, 40.0))
        return look(pos, Vector((0, 4, ARM_Z - 12)), 36.0)
    # wide tower cam; on the catch shot it eases in as the booster comes down
    z_b = bpos.z - ARM_Z
    k = smooth((260.0 - z_b) / 240.0) if s['id'] == 'v10' else (0.75 if s['id'][:1] == 'v' else 0.0)
    pos = Vector((-125.0, -290.0, 30.0)).lerp(Vector((-72.0, -170.0, 48.0)), k)
    tgt = Vector((0.0, 0.0, 150.0)).lerp(Vector((0.0, 0.0, ARM_Z - 14.0)), k)
    if s['id'] == 'frozen':                                        # keep the high booster and the tower in one frame
        hi = max(380.0, bpos.z + 60.0); lo = -10.0
        tgt = Vector((0.0, 0.0, (hi + lo) / 2)); dist = (tgt - pos).length
        return look(pos, tgt, 36.0 * dist / (hi - lo) * 0.92)
    return look(pos, tgt, 26.0 + 12.0 * k)

def booster_world(st):
    return Vector((st['x'], 0.0, ARM_Z + st['z']))

def arm_contact_angle(side, bx, margin=1.6):
    """Outward angle (deg) at which this arm's centre line passes R + margin from the booster axis."""
    px, py = side * ARM_X, TY - hw - 3.2
    a = 30.0
    while a > -45.0:
        th = math.radians(side * a); dx, dy = math.sin(th), -math.cos(th)
        vx, vy = bx - px, -py
        if -side * (dx * vy - dy * vx) <= R + margin: return a
        a -= 0.1
    return a

def pose(info, fr):
    """Set every animated thing for frame `fr` and key it (frame fr-1 too, for motion blur)."""
    s = info['shot']
    if s.get('flight'):
        st = info['st']; bpos = booster_world(st)
        booster.hide_render = False
        for o in booster.children_recursive: o.hide_render = False
        booster.location = bpos; booster.rotation_euler = (0, math.radians(st['tilt']), 0)
        lit = int(st['lit']); thr = st['throttle']
        if st['result'] == 'CAUGHT' and info['ts'] >= shots.flight(s['flight'])['T'] - 1e-6:
            lit = 0                                              # shut down in the arms
        dead = 2 if (s['flight'].endswith('engine_out') and lit == 11) else 0
        for k, f in enumerate(flames):
            on = (k < 3 and lit >= 3) or (k >= 3 and lit >= 11 and not (k - 3) in (2, 7)[:dead])
            f.hide_render = not on
            ln = (22.0 + 30.0 * thr) * (0.9 + 0.1 * math.sin(fr * 1.7 + k))
            f.scale = (1.0 + 0.6 * thr, 1.0 + 0.6 * thr, ln)
            kk = 1.0 if lit <= 3 else 0.4
            f.color = (kk, kk, kk, 1.0)
        glow.energy = 0.0 if lit == 0 else 6e5 * thr * (1.0 if lit <= 3 else 2.6)
        for i, piv in enumerate(fins):
            piv.rotation_euler = (math.radians(10.0 * st['fins']) * (1 if i % 2 else -1), 0, i * math.pi / 2 + math.pi / 4)
        caught = st['result'] == 'CAUGHT'
        # arms: open, close in the last 2.5 s of a catch flight (sim time), stay closed after
        T = shots.flight(s['flight'])['T']
        close = smooth((info['ts'] - (T - 4.5)) / 3.0) if (caught or s.get('hard')) else 0.0
        # each arm closes until it meets the hull where the booster really is (the sim allows up to 6 m off centre)
        bx_now = st['x']                                          # arms track the booster while they close
        for side, piv in arms:
            a_closed = arm_contact_angle(side, bx_now)
            a_now = 22.0 * (1 - close) + a_closed * close
            piv.rotation_euler = (0, 0, side * math.radians(a_now))
        # crash: fireball at the catch point
        for b_ in balls: b_.hide_render = True
        boom.energy = 0.0
        if st['result'].startswith('crashed'):
            it = impact_tl(s)
            miss = abs(st['x']) > 20.0
            if it is not None and miss:                          # missed the tower: it keeps falling to the ground
                fall = (ARM_Z - 63.0) / max(abs(st['vz']), 1.0)
                if it <= info['tl'] < it + fall:
                    booster.location = bpos - Vector((0, 0, abs(st['vz']) * (info['tl'] - it)))
                it = it + fall
            if it is not None and s.get('hard') and info['tl'] >= it:   # hit the arms too fast: sparks, no fireball
                u = (info['tl'] - it) / 0.25
                for j, b_ in enumerate(balls):
                    b_.hide_render = u > 1.6 or j > 0
                    r_ = 1.5 + 4.0 * smooth(u); b_.location = bpos + Vector((-5.0, -1.0, 0.5)); b_.scale = (r_, r_, r_)
                    b_.color = (1.0 - 0.6 * smooth(u / 1.6), 0.05, 0, 1)
                boom_o.location = bpos; boom.energy = 2e6 * (1.0 - smooth(u / 1.6))
            elif it is not None and info['tl'] >= it:
                u = (info['tl'] - it) / 0.35
                c = (Vector((st['x'], 0.0, 18.0)) if miss else bpos + Vector((0, 0, -22.0)))
                offs = [Vector((0, 0, 0)), Vector((-9, -4, 14)), Vector((10, 3, -10))]
                for j, b_ in enumerate(balls):
                    uj = max(0.0, u - 0.12 * j)
                    b_.hide_render = uj <= 0
                    r_ = (8.0 + 22.0 * smooth(uj)) * (1.0 - 0.25 * j)
                    b_.location = c + offs[j] * (0.4 + smooth(uj)); b_.scale = (r_, r_, r_ * 1.15)
                    b_.rotation_euler = (j * 1.3 + uj, j * 0.7, uj * 0.6)
                    b_.color = (1.0 - 0.55 * smooth(uj / 2.5), 0.05 + 0.35 * smooth(uj / 2.5), 0, 1)   # R heat, G how much has burned to smoke
                for o in booster.children_recursive: o.hide_render = True
                boom_o.location = c; boom.energy = 1.2e7 * (1.2 - 0.9 * smooth(u))
    else:
        bpos = Vector((0.0, 0.0, ARM_Z + 4000.0))
        for o in [booster] + list(booster.children_recursive): o.hide_render = True
        for b_ in balls: b_.hide_render = True
        boom.energy = 0.0
        for side, piv in arms: piv.rotation_euler = (0, 0, side * math.radians(22.0))
        glow.energy = 0.0
    p, e, f = camera_for(info, bpos)
    if os.environ.get('TOP'):
        p, e, f = look(Vector((0.0, -6.0, ARM_Z + 160.0)), Vector((0.0, -5.0, ARM_Z)), 50.0)
    if os.environ.get('CLOSE'):
        p, e, f = look(Vector((-38.0, -62.0, ARM_Z + 4)), Vector((0, 4, ARM_Z - 6)), 30.0)
    cam.location = p; cam.rotation_euler = e; cam_d.lens = f

ANIM = None
def set_frame(fr):
    """Key the previous frame and this one so Cycles blurs real motion; same state at a freeze."""
    objs = [booster, cam] + fins + [p for _, p in arms]
    for o in objs: o.animation_data_clear()
    cam_d.animation_data_clear()
    prev = shots.frame_info(max(fr - 1, 0)); cur = shots.frame_info(fr)
    if prev['shot'] is not cur['shot']: prev = cur                  # no blur across a cut
    for k, info in ((fr - 1, prev), (fr, cur)):
        pose(info, fr)
        for o in objs:
            o.keyframe_insert('location', frame=k + 10); o.keyframe_insert('rotation_euler', frame=k + 10)
        cam_d.keyframe_insert('lens', frame=k + 10)
    sc.frame_set(fr + 10)

def state_key(fr):
    i = shots.frame_info(fr)
    s = i['shot']; anim = i['cam'] == 'wide_end'
    if s.get('flight') and i['st']['result'].startswith('crashed') and i['st']['end']: anim = True   # fireball keeps growing
    return (s['id'], round(i.get('ts', -1), 4), round(i['tl'], 3) if anim else i['cam'])

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    outd = argv[0] if argv else os.path.join(HERE, 'test')
    spec = argv[1] if len(argv) > 1 else '0'
    resw = int(argv[2]) if len(argv) > 2 else 270
    spp = int(argv[3]) if len(argv) > 3 else 8
    sc.render.resolution_x = resw; sc.render.resolution_y = int(round(resw * 16 / 9)); sc.cycles.samples = spp
    os.makedirs(outd, exist_ok=True)
    if ':' in spec:
        a_, b_, c_ = (int(x) for x in spec.split(':')); frames = list(range(a_, min(b_, shots.NFRAMES), c_))
    else: frames = [int(x) for x in spec.split(',')]
    done = {}
    for fr in frames:
        p = os.path.join(outd, f'f{fr:04d}.png')
        key = state_key(fr); prevkey = state_key(fr - 1) if fr > 0 else None
        if os.path.exists(p) and os.path.getsize(p) > 1000: done[key] = p; continue
        if key in done and key == prevkey:                        # frozen frame: copy, don't render
            shutil.copy(done[key], p); print('COPY', fr, flush=True); continue
        t0 = time.time(); set_frame(fr); sc.render.filepath = p
        bpy.ops.render.render(write_still=True); done[key] = p
        print('DONE', fr, round(time.time() - t0, 1), flush=True)
