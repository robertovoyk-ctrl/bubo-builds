# Raspberry spider crawling down a wall of green code, then infecting it.
# Everything is built here in code (Blender / Cycles). Run:
#   python3.11 spider.py -- <outdir> <times csv | start:stop:step> <res_w> <spp> [frames]
import bpy, bmesh, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 24
DUR = 14.0
RASP = (1.0, 0.035, 0.24)          # neon raspberry  #ff1f6e-ish in linear
GREEN = (0.04, 1.0, 0.22)

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
sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 3
sc.cycles.transmission_bounces = 4; sc.cycles.transparent_max_bounces = 8
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.03
sc.render.fps = FPS; sc.render.use_persistent_data = True
sc.view_settings.view_transform = os.environ.get('VT', 'Standard')
try: sc.view_settings.look = os.environ.get('LOOK', 'Medium High Contrast')
except Exception: pass

# ---------------------------------------------------------------- helpers
def link(o): sc.collection.objects.link(o); return o
def mesh_obj(name, V, F, mat=None, smooth=True):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in V], [], [tuple(f) for f in F]); me.update()
    if smooth: me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    o = link(bpy.data.objects.new(name, me))
    if mat: me.materials.append(mat)
    return o
def ellipsoid(name, c, r, mat, seg=64, ring=32, parent=None):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * r[0], v.co.y * r[1], v.co.z * r[2]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    o = link(bpy.data.objects.new(name, me)); me.materials.append(mat); o.location = c
    if parent: o.parent = parent
    return o
def nodes(mat):
    mat.use_nodes = True; nt = mat.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    return nt, nt.nodes.new('ShaderNodeOutputMaterial')
def Mth(nt, op, a=None, b=None, va=None, vb=None, clamp=False):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
    if a is not None: nt.links.new(a, n.inputs[0])
    elif va is not None: n.inputs[0].default_value = va
    if b is not None: nt.links.new(b, n.inputs[1])
    elif vb is not None: n.inputs[1].default_value = vb
    return n.outputs[0]
def val(nt, name, v=0.0):
    n = nt.nodes.new('ShaderNodeValue'); n.name = name; n.outputs[0].default_value = v; return n.outputs[0]
def smooth01(u): u = min(1.0, max(0.0, u)); return u * u * (3 - 2 * u)

# ---------------------------------------------------------------- world: near-black
world = bpy.data.worlds.new('W'); sc.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.0, 0.0, 0.0, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = 0.0

# ---------------------------------------------------------------- the code wall
NFEET = 8
gimg = bpy.data.images.load(os.path.join(HERE, 'glyphs.png')); gimg.colorspace_settings.name = 'Non-Color'
ROWS_ATLAS = 64; ROW_H = 0.075; ROW_W = 9.0          # wall units: row height, length of one atlas row
wallM = bpy.data.materials.new('codewall'); nt, out = nodes(wallM)
T = val(nt, 'T'); REV = val(nt, 'REV'); INF_R = val(nt, 'INF_R')
IX, IY, IZ = val(nt, 'IX'), val(nt, 'IY'), val(nt, 'IZ')
geo = nt.nodes.new('ShaderNodeNewGeometry')
sxyz = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(geo.outputs['Position'], sxyz.inputs[0])
X_, Z_ = sxyz.outputs['X'], sxyz.outputs['Z']
rowg = Mth(nt, 'FLOOR', Mth(nt, 'DIVIDE', Z_, vb=ROW_H))                    # global row index
fz = Mth(nt, 'FRACT', Mth(nt, 'DIVIDE', Z_, vb=ROW_H))
def hash1(x, seed):
    wn = nt.nodes.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '1D'
    nt.links.new(Mth(nt, 'ADD', x, vb=seed), wn.inputs['W']); return wn.outputs['Value']
h_off, h_spd, h_rev, h_dim = hash1(rowg, 0.0), hash1(rowg, 17.3), hash1(rowg, 41.9), hash1(rowg, 73.1)
speed = Mth(nt, 'MULTIPLY', Mth(nt, 'SUBTRACT', h_spd, vb=0.5), vb=0.9)          # rows drift both ways
u = Mth(nt, 'ADD', Mth(nt, 'DIVIDE', X_, vb=ROW_W), Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', h_off, vb=13.0), Mth(nt, 'MULTIPLY', speed, T)))
u = Mth(nt, 'FRACT', u)
rloc = Mth(nt, 'MODULO', Mth(nt, 'ADD', rowg, vb=6400.0), vb=float(ROWS_ATLAS))
v = Mth(nt, 'DIVIDE', Mth(nt, 'ADD', rloc, fz), vb=float(ROWS_ATLAS))
cmb = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(u, cmb.inputs[0]); nt.links.new(v, cmb.inputs[1])
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = gimg; tex.extension = 'REPEAT'; tex.interpolation = 'Linear'
nt.links.new(cmb.outputs[0], tex.inputs['Vector'])
glyph = tex.outputs['Color']
gs = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(glyph, gs.inputs[0]); g = gs.outputs[0]
# rows switch on one by one at the start, each wiping in from the left
rowon = Mth(nt, 'SMOOTHSTEP' if False else 'GREATER_THAN', REV, h_rev)
wipe = Mth(nt, 'MULTIPLY', Mth(nt, 'SUBTRACT', REV, h_rev), vb=14.0)
xn = Mth(nt, 'DIVIDE', Mth(nt, 'ADD', X_, vb=3.0), vb=6.0)
reveal = Mth(nt, 'MULTIPLY', rowon, Mth(nt, 'GREATER_THAN', wipe, xn))
# travelling bright heads and slow shimmer
head = Mth(nt, 'POWER', Mth(nt, 'FRACT', Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', X_, vb=0.22), Mth(nt, 'SUBTRACT', Mth(nt, 'MULTIPLY', h_dim, vb=9.0), Mth(nt, 'MULTIPLY', T, vb=0.55)))), vb=14.0)
dim = Mth(nt, 'MULTIPLY', Mth(nt, 'GREATER_THAN', h_dim, vb=0.32), Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', h_dim, vb=0.7), vb=0.1))
bright = Mth(nt, 'ADD', dim, Mth(nt, 'MULTIPLY', head, vb=3.5))
# infection: raspberry spreads from a point on the wall
pos = geo.outputs['Position']
ipt = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(IX, ipt.inputs[0]); nt.links.new(IY, ipt.inputs[1]); nt.links.new(IZ, ipt.inputs[2])
dvec = nt.nodes.new('ShaderNodeVectorMath'); dvec.operation = 'DISTANCE'; nt.links.new(pos, dvec.inputs[0]); nt.links.new(ipt.outputs[0], dvec.inputs[1])
nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 4; nt.links.new(pos, nz.inputs['Vector'])
dd = Mth(nt, 'ADD', dvec.outputs['Value'], Mth(nt, 'MULTIPLY', Mth(nt, 'SUBTRACT', nz.outputs['Fac'], vb=0.5), vb=1.4))
dd = Mth(nt, 'ADD', dd, Mth(nt, 'MULTIPLY', h_off, vb=0.35))                       # ragged per row
infect = Mth(nt, 'SUBTRACT', va=1.0, b=Mth(nt, 'DIVIDE', Mth(nt, 'SUBTRACT', dd, INF_R), vb=0.25), clamp=True)
front = Mth(nt, 'MULTIPLY', Mth(nt, 'GREATER_THAN', INF_R, vb=0.01), Mth(nt, 'SUBTRACT', va=1.0, b=Mth(nt, 'ABSOLUTE', Mth(nt, 'DIVIDE', Mth(nt, 'SUBTRACT', dd, INF_R), vb=0.18)), clamp=True))
# footfall flashes (eight feet)
feet = []
fsum = None
for i in range(NFEET):
    fx, fy, fzv, fa = val(nt, f'F{i}x'), val(nt, f'F{i}y'), val(nt, f'F{i}z'), val(nt, f'F{i}a')
    fp = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(fx, fp.inputs[0]); nt.links.new(fy, fp.inputs[1]); nt.links.new(fzv, fp.inputs[2])
    dv = nt.nodes.new('ShaderNodeVectorMath'); dv.operation = 'DISTANCE'; nt.links.new(pos, dv.inputs[0]); nt.links.new(fp.outputs[0], dv.inputs[1])
    k = Mth(nt, 'MULTIPLY', fa, Mth(nt, 'EXPONENT', Mth(nt, 'MULTIPLY', Mth(nt, 'POWER', dv.outputs['Value'], vb=2.0), vb=-90.0)))
    fsum = k if fsum is None else Mth(nt, 'ADD', fsum, k)
rasp_mix = Mth(nt, 'MINIMUM', Mth(nt, 'ADD', infect, Mth(nt, 'MULTIPLY', fsum, vb=1.6)), vb=1.0)
col = nt.nodes.new('ShaderNodeMix'); col.data_type = 'RGBA'; nt.links.new(rasp_mix, col.inputs['Factor'])
col.inputs[6].default_value = (*GREEN, 1); col.inputs[7].default_value = (*RASP, 1)
strength = Mth(nt, 'MULTIPLY', Mth(nt, 'MULTIPLY', g, reveal), Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', bright, vb=1.5), Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', fsum, vb=10.0), Mth(nt, 'MULTIPLY', front, vb=8.0))))
em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(col.outputs[2], em.inputs['Color']); nt.links.new(strength, em.inputs['Strength'])
# the wall itself is a dark glossy panel so the spider stands on something
dk = nt.nodes.new('ShaderNodeBsdfPrincipled'); dk.inputs['Base Color'].default_value = (0.003, 0.004, 0.0035, 1); dk.inputs['Roughness'].default_value = 0.7; dk.inputs['Specular IOR Level'].default_value = 0.15
ad = nt.nodes.new('ShaderNodeAddShader'); nt.links.new(em.outputs[0], ad.inputs[0]); nt.links.new(dk.outputs[0], ad.inputs[1]); nt.links.new(ad.outputs[0], out.inputs[0])
WALL_W, WALL_H = 14.0, 22.0
wall = mesh_obj('wall', [(-WALL_W / 2, 0, -WALL_H / 2), (WALL_W / 2, 0, -WALL_H / 2), (WALL_W / 2, 0, WALL_H / 2), (-WALL_W / 2, 0, WALL_H / 2)], [(0, 1, 2, 3)], wallM, smooth=False)
# deeper layers of code behind, seen through nothing: they peek past the edges in the side shot
wallM2 = wallM.copy(); wall2 = mesh_obj('wall_far', [(-14, 6, -16), (14, 6, -16), (14, 6, 16), (-14, 6, 16)], [(0, 1, 2, 3)], wallM2, smooth=False)
wall2.hide_render = True

# ---------------------------------------------------------------- spider materials
def hairy_mat(name, base, edge, es0, es1, sss=0.8):
    m = bpy.data.materials.new(name); nt, out = nodes(m)
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (*base, 1); p.inputs['Roughness'].default_value = 0.4
    p.inputs['Subsurface Weight'].default_value = sss; p.inputs['Subsurface Radius'].default_value = (1.0, 0.25, 0.4)
    p.inputs['Subsurface Scale'].default_value = 0.05
    p.inputs['Coat Weight'].default_value = 0.3; p.inputs['Coat Roughness'].default_value = 0.25
    bump = nt.nodes.new('ShaderNodeBump'); bn = nt.nodes.new('ShaderNodeTexNoise'); bn.inputs['Scale'].default_value = 140.0
    nt.links.new(bn.outputs['Fac'], bump.inputs['Height']); bump.inputs['Strength'].default_value = 0.25; nt.links.new(bump.outputs[0], p.inputs['Normal'])
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    es = Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', Mth(nt, 'POWER', Mth(nt, 'SUBTRACT', va=1.0, b=lw.outputs['Facing']), vb=2.5), vb=es1), vb=es0)
    p.inputs['Emission Color'].default_value = (*edge, 1); nt.links.new(es, p.inputs['Emission Strength'])
    nt.links.new(p.outputs[0], out.inputs[0]); return m
legM = hairy_mat('leg', (1.0, 0.0, 0.1), (1.0, 0.04, 0.24), 0.12, 2.2)
hairM = bpy.data.materials.new('hair'); nt, out = nodes(hairM)          # fine hair: glows when backlit
hp = nt.nodes.new('ShaderNodeBsdfPrincipled'); hp.inputs['Roughness'].default_value = 0.45
hi = nt.nodes.new('ShaderNodeHairInfo'); hcm = nt.nodes.new('ShaderNodeMix'); hcm.data_type = 'RGBA'
nt.links.new(hi.outputs['Random'], hcm.inputs['Factor']); hcm.inputs[6].default_value = (1.0, 0.04, 0.22, 1); hcm.inputs[7].default_value = (1.0, 0.42, 0.6, 1)
hgr = nt.nodes.new('ShaderNodeMix'); hgr.data_type = 'RGBA'; nt.links.new(hi.outputs['Intercept'], hgr.inputs['Factor'])
nt.links.new(hcm.outputs[2], hgr.inputs[7]); hgr.inputs[6].default_value = (0.5, 0.0, 0.08, 1)          # darker at the root
nt.links.new(hgr.outputs[2], hp.inputs['Base Color'])
tl = nt.nodes.new('ShaderNodeBsdfTranslucent'); tl.inputs['Color'].default_value = (1.0, 0.35, 0.55, 1)
hm = nt.nodes.new('ShaderNodeMixShader'); hm.inputs[0].default_value = 0.45; nt.links.new(hp.outputs[0], hm.inputs[1]); nt.links.new(tl.outputs[0], hm.inputs[2])
he = nt.nodes.new('ShaderNodeEmission'); he.inputs[0].default_value = (1.0, 0.1, 0.32, 1); he.inputs[1].default_value = 0.35
ha = nt.nodes.new('ShaderNodeAddShader'); nt.links.new(hm.outputs[0], ha.inputs[0]); nt.links.new(he.outputs[0], ha.inputs[1]); nt.links.new(ha.outputs[0], out.inputs[0])
tipM = bpy.data.materials.new('tip'); nt, out = nodes(tipM)
p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.inputs['Base Color'].default_value = (0.05, 0.004, 0.012, 1); p.inputs['Roughness'].default_value = 0.3
p.inputs['Coat Weight'].default_value = 0.6; nt.links.new(p.outputs[0], out.inputs[0])

def vein_mat(name, scale, core_w, base_col, edge_glow):
    """glossy black shell with a bilaterally symmetric glowing crack network and a midline"""
    m = bpy.data.materials.new(name); nt, out = nodes(m)
    B = val(nt, 'B', 1.0)
    tc = nt.nodes.new('ShaderNodeTexCoord'); sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sp.inputs[0])
    ax = Mth(nt, 'ABSOLUTE', sp.outputs['X'])
    cb = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(ax, cb.inputs[0]); nt.links.new(sp.outputs['Y'], cb.inputs[1]); nt.links.new(sp.outputs['Z'], cb.inputs[2])
    warp = nt.nodes.new('ShaderNodeTexNoise'); warp.inputs['Scale'].default_value = 2.2; warp.inputs['Detail'].default_value = 3
    nt.links.new(cb.outputs[0], warp.inputs['Vector'])
    wv = nt.nodes.new('ShaderNodeVectorMath'); wv.operation = 'MULTIPLY_ADD'; nt.links.new(warp.outputs['Color'], wv.inputs[0])
    wv.inputs[1].default_value = (0.13, 0.13, 0.13); nt.links.new(cb.outputs[0], wv.inputs[2])
    vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = scale
    try: vor.inputs['Randomness'].default_value = 0.85
    except Exception: pass
    nt.links.new(wv.outputs[0], vor.inputs['Vector'])
    dist = Mth(nt, 'MINIMUM', vor.outputs['Distance'], Mth(nt, 'MULTIPLY', Mth(nt, 'ABSOLUTE', sp.outputs['X']), vb=scale * 1.1))   # midline joins the network
    core = Mth(nt, 'POWER', Mth(nt, 'SUBTRACT', va=1.0, b=Mth(nt, 'DIVIDE', dist, vb=core_w), clamp=True), vb=1.5)
    halo = Mth(nt, 'POWER', Mth(nt, 'SUBTRACT', va=1.0, b=Mth(nt, 'DIVIDE', dist, vb=core_w * 4.0), clamp=True), vb=3.0)
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (*base_col, 1); p.inputs['Roughness'].default_value = 0.2
    p.inputs['Coat Weight'].default_value = 1.0; p.inputs['Coat Roughness'].default_value = 0.04
    bump = nt.nodes.new('ShaderNodeBump'); bn = nt.nodes.new('ShaderNodeTexNoise'); bn.inputs['Scale'].default_value = 90.0
    nt.links.new(bn.outputs['Fac'], bump.inputs['Height']); bump.inputs['Strength'].default_value = 0.08
    groove = Mth(nt, 'MULTIPLY', core, vb=-1.0); nt.links.new(groove, bump.inputs['Height']) if False else None
    nt.links.new(bump.outputs[0], p.inputs['Normal'])
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3
    rimg = Mth(nt, 'MULTIPLY', Mth(nt, 'POWER', lw.outputs['Fresnel'], vb=2.0), vb=edge_glow)
    em = Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', Mth(nt, 'ADD', Mth(nt, 'MULTIPLY', core, vb=4.0), Mth(nt, 'MULTIPLY', halo, vb=0.3)), B), rimg)
    p.inputs['Emission Color'].default_value = (1.0, 0.03, 0.2, 1); nt.links.new(em, p.inputs['Emission Strength'])
    nt.links.new(p.outputs[0], out.inputs[0]); return m
abdM = vein_mat('abdomen', 2.5, 0.045, (0.004, 0.003, 0.005), 0.5)
cepM = vein_mat('carapace', 3.2, 0.035, (0.012, 0.006, 0.008), 1.6)
eyeM = bpy.data.materials.new('eye'); nt, out = nodes(eyeM)
p = nt.nodes.new('ShaderNodeBsdfPrincipled'); p.inputs['Base Color'].default_value = (0.001, 0.001, 0.0015, 1); p.inputs['Roughness'].default_value = 0.03
p.inputs['Coat Weight'].default_value = 1.0; p.inputs['Coat Roughness'].default_value = 0.0
EYE = val(nt, 'E', 0.0); p.inputs['Emission Color'].default_value = (*RASP, 1); nt.links.new(EYE, p.inputs['Emission Strength'])
nt.links.new(p.outputs[0], out.inputs[0])

def add_hair(o, count, length, radius=0.0016, children=6, spines=0, mat_index=2, lean=0.6):
    if len(o.data.materials) < mat_index: o.data.materials.append(hairM)
    ps = o.modifiers.new('fur', 'PARTICLE_SYSTEM'); st = ps.particle_system.settings
    st.type = 'HAIR'; st.count = count; st.hair_length = length; st.emit_from = 'FACE'; st.use_emit_random = True
    k_ = (length / 4.0) / math.hypot(0.8, lean)      # advanced hair: length = 4 x |velocity|
    st.use_advanced_hair = True; st.normal_factor = 0.8 * k_; st.object_align_factor = (0.0, 0.0, lean * k_); st.factor_random = 0.2 * k_
    st.material = mat_index; st.root_radius = 1.0; st.tip_radius = 0.0; st.radius_scale = radius
    st.display_step = 2; st.render_step = 3
    if children:
        st.child_type = 'INTERPOLATED'; st.child_percent = 2; st.rendered_child_count = children
        st.child_length = 0.9; st.child_length_threshold = 0.3; st.roughness_1 = 0.004; st.roughness_endpoint = 0.006
    ps.particle_system.seed = int(rs.randint(1, 10000))
    if spines:
        ps2 = o.modifiers.new('spines', 'PARTICLE_SYSTEM'); s2 = ps2.particle_system.settings
        s2.type = 'HAIR'; s2.count = spines; s2.hair_length = length * 2.6; s2.emit_from = 'FACE'; s2.use_emit_random = True
        k2 = (length * 2.6 / 4.0) / math.hypot(0.8, lean * 1.2)
        s2.use_advanced_hair = True; s2.normal_factor = 0.8 * k2; s2.object_align_factor = (0.0, 0.0, lean * 1.2 * k2); s2.factor_random = 0.1 * k2
        s2.material = mat_index; s2.root_radius = 1.0; s2.tip_radius = 0.0; s2.radius_scale = radius * 1.8
        s2.display_step = 2; s2.render_step = 3; ps2.particle_system.seed = int(rs.randint(1, 10000))

# ---------------------------------------------------------------- spider body (local frame: x right, y forward, z up/dorsal)
rs = np.random.RandomState(9)
BODY = link(bpy.data.objects.new('body', None))
cep = ellipsoid('carapace', (0, 0.15, 0.03), (0.2, 0.25, 0.11), cepM, parent=BODY)
for v in cep.data.vertices:                       # pear shape: wider at the back, head lifted at the front
    x, y, z = v.co; v.co.x = x * (1.0 - 0.25 * max(0.0, y / 0.25)); v.co.z = z + 0.04 * max(0.0, y / 0.25) ** 2
add_hair(cep, 260, 0.018, 0.0012, 4)
abd = ellipsoid('abdomen', (0, -0.47, 0.16), (0.37, 0.4, 0.35), abdM, 96, 48, parent=BODY); abd.rotation_euler = (math.radians(-8), 0, 0)
for v in abd.data.vertices:                       # slightly fuller at the rear, like the reference
    x, y, z = v.co; k = 1.0 + 0.08 * (-y / 0.44); v.co.x = x * k; v.co.z = z * k
ellipsoid('petiole', (0, -0.08, 0.06), (0.045, 0.07, 0.045), legM, 24, 12, parent=BODY)
for (x, y, z, r) in [(0.052, 0.39, 0.105, 0.05), (-0.052, 0.39, 0.105, 0.05), (0.115, 0.355, 0.118, 0.026), (-0.115, 0.355, 0.118, 0.026),
                     (0.045, 0.335, 0.16, 0.024), (-0.045, 0.335, 0.16, 0.024), (0.13, 0.3, 0.14, 0.02), (-0.13, 0.3, 0.14, 0.02)]:
    ellipsoid('eye', (x, y, z), (r, r, r * 0.9), eyeM, 32, 16, parent=BODY)
for s in (-1, 1):
    ch = ellipsoid('chelicera', (s * 0.052, 0.405, 0.0), (0.05, 0.06, 0.085), legM, 32, 16, parent=BODY); ch.rotation_euler = (math.radians(35), 0, 0)
    add_hair(ch, 120, 0.02, 0.0012, 4)
    ellipsoid('fang', (s * 0.05, 0.45, -0.085), (0.014, 0.014, 0.035), tipM, 12, 8, parent=BODY)

# ---------------------------------------------------------------- legs: shaped, curved, furry segments posed every frame
def seg_mesh(name, L, r0, r1, mat, bulge=0.18, bend=0.0, fur=(500, 0.03), spines=12, tip=False):
    V, F = [], []; sides, rings = 14, 22
    for j in range(rings + 1):
        u = j / rings; zz = L * u
        rr = (r0 + (r1 - r0) * u) * (1.0 + bulge * math.sin(math.pi * u) ** 0.8) * (1.0 - 0.18 * max(0.0, 1 - u / 0.06) - 0.12 * max(0.0, (u - 0.94) / 0.06))
        cx = bend * L * math.sin(math.pi * u)                  # arc toward local +X
        for k in range(sides):
            a = k / sides * 2 * math.pi; V.append((cx + rr * math.cos(a), rr * math.sin(a), zz))
    for j in range(rings):
        for k in range(sides):
            F.append((j * sides + k, j * sides + (k + 1) % sides, (j + 1) * sides + (k + 1) % sides, (j + 1) * sides + k))
    V.append((0, 0, 0)); V.append((0, 0, L)); c0, c1 = len(V) - 2, len(V) - 1
    for k in range(sides):
        F.append((c0, (k + 1) % sides, k)); F.append((c1, rings * sides + k, rings * sides + (k + 1) % sides))
    o = mesh_obj(name, V, F, mat)
    if fur: add_hair(o, fur[0], fur[1], 0.0009 if not tip else 0.0006, 6, spines)
    return o

LEGS = []
spec = [(28, 22, 1.85, 1.02, 1.42), (62, 58, 1.68, 0.94, 1.28), (104, 112, 1.14, 0.64, 0.86), (140, 158, 1.56, 0.88, 1.2)]
for s in (-1, 1):
    for i, (ha, fa, reach, L1, L2) in enumerate(spec):
        hip = np.array([s * 0.17 * math.sin(math.radians(ha)), 0.15 + 0.21 * math.cos(math.radians(ha)), -0.01])
        rest = np.array([s * reach * math.sin(math.radians(fa)), 0.15 + reach * math.cos(math.radians(fa))])
        g = (i + (0 if s < 0 else 1)) % 2
        tib, met = 0.47 * L2, 0.43 * L2
        lt = math.hypot(tib, 0.05 * L2); lm = math.hypot(met, 0.04 * L2); lta = math.hypot(L2 - tib - met, 0.01 * L2)
        segs = [seg_mesh(f'femur{s}{i}', L1, 0.029, 0.024, legM, 0.2, 0.09, (int(1300 * L1), 0.026), 14),
                seg_mesh(f'tibia{s}{i}', lt, 0.023, 0.018, legM, 0.12, 0.05, (int(1200 * lt), 0.024), 10),
                seg_mesh(f'meta{s}{i}', lm, 0.016, 0.01, legM, 0.06, 0.015, (int(900 * lm), 0.018), 6),
                seg_mesh(f'tarsus{s}{i}', lta, 0.009, 0.004, tipM, 0.05, 0.0, (60, 0.01), 0, True)]
        joints = [ellipsoid(f'j{s}{i}{k}', (0, 0, 0), (r, r, r), legM, 20, 10) for k, r in enumerate((0.03, 0.024, 0.018, 0.012))]
        LEGS.append(dict(s=s, i=i, hip=hip, rest=rest, L1=L1, L2=L2, g=g, segs=segs, joints=joints, tib=tib, met=met))
PALPS = []
for s in (-1, 1):
    a = seg_mesh(f'palpA{s}', 0.2, 0.02, 0.017, legM, 0.15, 0.04, (220, 0.016), 4)
    b = seg_mesh(f'palpB{s}', 0.17, 0.017, 0.013, legM, 0.12, 0.04, (180, 0.016), 4)
    PALPS.append((s, a, b))

def frame_from(p0, p1, x_hint):
    z = Vector(p1) - Vector(p0); z.normalize()
    x = Vector(x_hint); x = x - z * x.dot(z)
    if x.length < 1e-6: x = Vector((1, 0, 0)) - z * z.x
    x.normalize(); y = z.cross(x)
    return Matrix(((x.x, y.x, z.x, p0[0]), (x.y, y.y, z.y, p0[1]), (x.z, y.z, z.z, p0[2]), (0, 0, 0, 1)))

# ---------------------------------------------------------------- motion
NW = np.array([0.0, -1.0, 0.0])         # wall normal, toward camera
BODY_H = 0.30
TS = 0.40                                # step cycle
PATH = [(0.0, 0.0, 9.6, 0.0), (2.0, 0.0, 7.7, 0.0), (5.0, 0.08, 1.0, 0.05), (7.5, -0.05, 0.1, -0.12),
        (9.4, -0.12, -0.32, -0.2), (14.0, -0.12, -0.36, -0.2)]
JUMP0 = 13.15
def path(t):
    t = min(max(t, PATH[0][0]), PATH[-1][0])
    for a, b in zip(PATH, PATH[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / (b[0] - a[0]); e = u * u * (3 - 2 * u) if b is PATH[-1] or a[0] >= 7.5 else u
            return tuple(a[k] + (b[k] - a[k]) * e for k in (1, 2, 3))
def body_frame(t):
    x, z, psi = path(t)
    f = np.array([math.sin(psi), 0.0, -math.cos(psi)])            # psi=0: heading straight down
    up = -NW * -1.0; up = np.array([0.0, -1.0, 0.0])
    r = np.cross(f, up)
    c = np.array([x, -BODY_H, z])
    return c, r, f, up
def to_world(t, local):
    c, r, f, up = body_frame(t)
    return c + r * local[0] + f * local[1] + up * local[2]
def rest_world(t, leg):
    c, r, f, up = body_frame(t)
    p = np.array([c[0], 0.0, c[2]]) + r * leg['rest'][0] + f * leg['rest'][1]
    p[1] = -0.012; return p
def plant(k, leg):
    ph = 0.5 * leg['g']
    return rest_world((k + ph + 0.75) * TS, leg)
def foot_state(t, leg):
    ph = 0.5 * leg['g']; x = t / TS - ph; k = math.floor(x); uu = x - k
    P0, P1 = plant(k - 1, leg), plant(k, leg)
    if uu < 0.5:
        s = uu / 0.5; e = s * s * (3 - 2 * s); dist = np.linalg.norm(P1 - P0)
        p = P0 + (P1 - P0) * e + NW * 0.22 * math.sin(math.pi * s) * min(1.0, dist / 0.2)
        land_t, land_p = (k - 1 + ph + 0.5) * TS, P0
    else:
        p = P1; land_t, land_p = (k + ph + 0.5) * TS, P1
    moved = np.linalg.norm(plant(k, leg) - plant(k - 1, leg)) if uu >= 0.5 else np.linalg.norm(P0 - plant(k - 2, leg))
    return p, land_t, land_p, moved
def ik(H, F, L1, L2):
    d = F - H; D = np.linalg.norm(d); dn = d / (D + 1e-9)
    D = min(D, L1 + L2 - 1e-3); D = max(D, abs(L1 - L2) + 1e-3)
    a = (L1 * L1 - L2 * L2 + D * D) / (2 * D); h = math.sqrt(max(0.0, L1 * L1 - a * a))
    upp = NW - dn * np.dot(NW, dn); upp /= (np.linalg.norm(upp) + 1e-9)
    K = H + dn * a + upp * h; Fp = H + dn * D
    return K, Fp, upp

# ---------------------------------------------------------------- lights
def spot(name, loc, target, col, energy, size, ang=40):
    L = bpy.data.lights.new(name, 'SPOT'); L.color = col; L.energy = energy; L.shadow_soft_size = size
    L.spot_size = math.radians(ang); L.spot_blend = 0.6
    o = link(bpy.data.objects.new(name, L)); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
key = spot('key', (-2.5, -4.0, 4.0), (0, 0, 0.5), (1.0, 0.85, 0.92), 1600, 1.5, 50)
rim = spot('rim', (2.8, -0.9, 3.6), (0, 0, 0.3), (0.75, 0.25, 1.0), 2400, 0.8, 45)
rim2 = spot('rim2', (-3.0, -0.7, -2.4), (0, 0, 0.3), (0.55, 0.3, 1.0), 1400, 0.8, 45)       # magenta rim like the reference
under = spot('under', (0.0, -3.0, -3.0), (0, 0, 0.0), (0.2, 1.0, 0.35), 110, 4.0, 60)     # green bounce from the code
TRACK = [key, rim, rim2, under]
TRACK_OFF = [o.location.copy() for o in TRACK]

# ---------------------------------------------------------------- camera
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); link(cam); sc.camera = cam
cam.data.sensor_fit = 'VERTICAL'; cam.data.sensor_height = 36.0
cam.data.dof.use_dof = True; cam.data.dof.aperture_blades = 7
KEYS = [  # t, cam pos, target, lens(vertical), fstop
    (0.0, (0.25, -5.6, 2.9), (0.0, 0.0, 2.6), 30, 4.0),
    (2.0, (0.2, -5.4, 2.6), (0.0, 0.0, 2.3), 30, 4.0),
    (5.0, (0.0, -4.6, 1.3), (0.02, -0.2, 0.9), 32, 3.2),
    (7.6, (3.3, -2.7, 1.2), (-0.02, -0.3, 0.2), 34, 2.8),
    (9.4, (3.1, -1.9, 0.0), (-0.12, -0.3, -0.3), 36, 2.6),
    (11.6, (0.4, -5.6, 0.2), (-0.1, -0.1, -0.3), 26, 3.5),
    (12.7, (-0.1, -1.75, -1.75), (-0.12, -0.3, -0.62), 28, 2.4),
    (13.25, (-0.11, -1.35, -1.45), (-0.12, -0.3, -0.6), 30, 2.2),
    (14.0, (-0.11, -1.3, -1.42), (-0.12, -0.3, -0.6), 30, 2.2)]
def lerp(a, b, u): return tuple(a[i] + (b[i] - a[i]) * u for i in range(len(a)))
def cam_at(t):
    for a, b in zip(KEYS, KEYS[1:]):
        if a[0] <= t <= b[0]:
            u = smooth01((t - a[0]) / (b[0] - a[0]))
            return lerp(a[1], b[1], u), lerp(a[2], b[2], u), a[3] + (b[3] - a[3]) * u, a[4] + (b[4] - a[4]) * u
    k = KEYS[-1]; return k[1], k[2], k[3], k[4]

# ---------------------------------------------------------------- per-frame state
def set_time(t):
    # body (and the jump at the end)
    c, r, f, up = body_frame(t)
    jump = smooth01((t - JUMP0) / 0.45)
    camp, tgt, lens, fst = cam_at(t)
    cpos = np.array(camp)
    if jump > 0:
        c = c + (cpos - c) * 0.82 * jump ** 1.6
    bob = 0.012 * math.sin(2 * math.pi * t / TS * 2) * (0 if t > 10 else 1)
    c = c + up * bob
    BODY.matrix_world = Matrix(((r[0], f[0], up[0], c[0]), (r[1], f[1], up[1], c[1]), (r[2], f[2], up[2], c[2]), (0, 0, 0, 1)))
    wn = wallM.node_tree.nodes
    for i, leg in enumerate(LEGS):
        H = c + r * leg['hip'][0] + f * leg['hip'][1] + up * leg['hip'][2]
        Fp, land_t, land_p, moved = foot_state(t, leg)
        if jump > 0:   # legs fling forward and wide toward the lens
            spread = c + r * leg['rest'][0] * 0.9 + f * (leg['rest'][1] * 0.6 + 0.4) + (cpos - c) / (np.linalg.norm(cpos - c) + 1e-9) * 0.55
            Fp = Fp + (spread - Fp) * jump
        K, Fr, upp = ik(H, Fp, leg['L1'], leg['L2'])
        dn = (Fr - K) / leg['L2']
        J1 = K + dn * leg['tib'] + upp * 0.05 * leg['L2']
        J2 = K + dn * (leg['tib'] + leg['met']) + upp * 0.01 * leg['L2']
        pts = [H, K, J1, J2, Fr]
        for k, o in enumerate(leg['segs']):
            o.matrix_world = frame_from(pts[k], pts[k + 1], upp)
        for k, o in enumerate(leg['joints']):
            o.matrix_world = Matrix.Translation(Vector(pts[k]))
        # footfall flash on the wall
        a = math.exp(-(t - land_t) / 0.32) * (1.0 if moved > 0.06 else 0.0) * (1 - jump)
        if t < 2.0: a = 0.0
        wn[f'F{i}x'].outputs[0].default_value = land_p[0]; wn[f'F{i}y'].outputs[0].default_value = 0.0
        wn[f'F{i}z'].outputs[0].default_value = land_p[2]; wn[f'F{i}a'].outputs[0].default_value = a
    for (s, a, b) in PALPS:
        w = 0.06 * math.sin(t * 7 + s)
        p0 = c + r * (s * 0.07) + f * 0.4 + up * 0.0
        p1 = p0 + r * (s * 0.1) + f * (0.14 + w) - up * 0.06
        p2 = p1 + r * (s * 0.02) + f * 0.12 - up * 0.08
        a.matrix_world = frame_from(p0, p1, up); b.matrix_world = frame_from(p1, p2, up)
    # code wall
    wn['T'].outputs[0].default_value = t
    wn['REV'].outputs[0].default_value = 1.15 * smooth01((t - 0.15) / 1.9)
    ic = path(9.5); wn['IX'].outputs[0].default_value = ic[0]; wn['IY'].outputs[0].default_value = 0.0; wn['IZ'].outputs[0].default_value = ic[1]
    wn['INF_R'].outputs[0].default_value = 7.5 * smooth01((t - 9.6) / 2.6) ** 1.3
    # abdomen veins pulse with the steps, flare during the infection
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * t / TS)
    abdM.node_tree.nodes['B'].outputs[0].default_value = 0.8 + 0.5 * pulse + 2.5 * smooth01((t - 9.4) / 0.6) * (1 - 0.6 * smooth01((t - 11.0) / 1.5))
    eyeM.node_tree.nodes['E'].outputs[0].default_value = 3.0 * smooth01((t - 12.4) / 0.6)
    # lights follow the spider
    for o, off in zip(TRACK, TRACK_OFF):
        o.location = Vector((off[0] + c[0], off[1], off[2] + c[2]))
        o.rotation_euler = (Vector(c) - o.location).to_track_quat('-Z', 'Y').to_euler()
    # camera
    cam.location = camp; cam.rotation_euler = (Vector(tgt) - Vector(camp)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens; cam.data.dof.aperture_fstop = fst
    if os.environ.get('CAM'):          # look-dev override: px,py,pz,tx,ty,tz,lens,fstop
        q = [float(x) for x in os.environ['CAM'].split(',')]
        camp, tgt = tuple(q[0:3]), tuple(q[3:6]); cam.location = camp
        cam.rotation_euler = (Vector(tgt) - Vector(camp)).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = q[6]; cam.data.dof.aperture_fstop = q[7]
    focus = c if t > 2.4 else np.array([0.0, 0.0, 2.3])
    cam.data.dof.focus_distance = float(np.linalg.norm(np.array(camp) - focus))
    # blackout at the very end
    sc.view_settings.exposure = -10.0 * smooth01((t - 13.62) / 0.12)

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    outd = argv[0] if argv else os.path.join(HERE, 'test')
    spec_ = argv[1] if len(argv) > 1 else '6.0'
    resw = int(argv[2]) if len(argv) > 2 else 540
    spp = int(argv[3]) if len(argv) > 3 else 16
    mode = argv[4] if len(argv) > 4 else 'stills'
    sc.render.resolution_x = resw; sc.render.resolution_y = int(resw * 16 / 9); sc.cycles.samples = spp
    os.makedirs(outd, exist_ok=True)
    if mode == 'frames':
        if ':' in spec_:
            a_, b_, c_ = (int(x) for x in spec_.split(':')); frames = list(range(a_, b_, c_))
        else: frames = [int(x) for x in spec_.split(',')]
        jobs = [(fr / FPS, os.path.join(outd, f'f{fr:04d}.png')) for fr in frames]
    else:
        jobs = [(float(x), os.path.join(outd, f't{float(x):05.2f}.png')) for x in spec_.split(',')]
    for t, p in jobs:
        if os.path.exists(p) and os.path.getsize(p) > 1000: continue
        t0 = time.time(); set_time(t); sc.render.filepath = p
        bpy.ops.render.render(write_still=True); print('DONE', round(t, 2), round(time.time() - t0, 1), flush=True)
