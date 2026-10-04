# Blender/Cycles rebuild of the Jev + fruit fly Für Elise film.
# All layout math is written in the old three.js coordinates (Y up, camera on +Z) and converted with B().
import bpy, bmesh, json, math, sys, os, time
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, 'tex')
score = json.load(open(os.path.join(HERE, 'score.json')))
FPS = 24

# ---------------- coordinates ----------------
C3 = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))          # three (x,y,z) -> blender (x,-z,y)
C4 = C3.to_4x4()
def B(x, y=None, z=None):
    if y is None: x, y, z = x
    return Vector((x, -z, y))
def M3(R):  # three rotation -> blender rotation
    return C3 @ R @ C3.transposed()
def lookR(pos, target, up=(0, 1, 0)):   # three Object3D.lookAt: +z toward target
    z = (Vector(target) - Vector(pos)).normalized(); x = Vector(up).cross(z).normalized(); y = z.cross(x)
    return Matrix((x, y, z)).transposed()
def euler3(x, y, z):  # three Euler XYZ
    return (Matrix.Rotation(x, 3, 'X') @ Matrix.Rotation(y, 3, 'Y') @ Matrix.Rotation(z, 3, 'Z'))
def mat4(R3, pos, s=1.0):
    s3 = s if isinstance(s, (tuple, list)) else (s, s, s)
    m = (M3(R3) @ Matrix.Diagonal(Vector((s3[0], s3[2], s3[1])))).to_4x4()
    m.translation = B(pos); return m

# ---------------- scene setup ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = 64; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 3; sc.cycles.transparent_max_bounces = 8
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False; sc.cycles.blur_glossy = 1.0
sc.render.use_persistent_data = True
sc.render.resolution_x = sc.render.resolution_y = 720
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'AgX'
for lk in ('AgX - Medium High Contrast', 'Medium High Contrast'):
    try: sc.view_settings.look = lk; break
    except Exception: pass
sc.view_settings.exposure = 0.3
world = bpy.data.worlds.new('W'); sc.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.006, 0.008, 0.016, 1); world.node_tree.nodes['Background'].inputs[1].default_value = 1.0

COL_MAIN = bpy.data.collections.new('main'); sc.collection.children.link(COL_MAIN)
COL_WIN = bpy.data.collections.new('win'); sc.collection.children.link(COL_WIN)
CUR = [COL_MAIN]

def link(o): CUR[0].objects.link(o); return o

# ---------------- materials ----------------
def mat(name, color, rough=0.5, coat=0.0, metal=0.0, emit=None, estr=0.0, sss=0.0, alpha=1.0, spec=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color, 1); p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal; p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.2
    p.inputs['Alpha'].default_value = alpha
    if sss: p.inputs['Subsurface Weight'].default_value = sss; p.inputs['Subsurface Radius'].default_value = (1.0, 0.3, 0.3); p.inputs['Subsurface Scale'].default_value = 0.05
    if emit: p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = estr
    return m
def srgb(h):  # hex -> linear
    c = [((h >> s) & 255) / 255 for s in (16, 8, 0)]
    return tuple((v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)
def img_mat(name, path, rough=0.8, alpha=False, emit=0.0, tint=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    p = nt.nodes['Principled BSDF']; t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path)
    t.interpolation = 'Cubic'
    if tint:
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1
        nt.links.new(t.outputs['Color'], mix.inputs[6]); mix.inputs[7].default_value = (*tint, 1); nt.links.new(mix.outputs[2], p.inputs['Base Color'])
    else: nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = rough
    if alpha: nt.links.new(t.outputs['Alpha'], p.inputs['Alpha'])
    if emit: nt.links.new(t.outputs['Color'], p.inputs['Emission Color']); p.inputs['Emission Strength'].default_value = emit
    return m
def emis_img(name, path, strength=1.0, alpha=False):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.remove(nt.nodes['Principled BSDF'])
    out = nt.nodes['Material Output']; t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Strength'].default_value = strength; nt.links.new(t.outputs['Color'], e.inputs['Color'])
    if alpha:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(t.outputs['Alpha'], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(e.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs['Surface'])
    else: nt.links.new(e.outputs[0], out.inputs['Surface'])
    return m
def add_noise_rough(m, scale=40, lo=0.3, hi=0.6, bump=0.0):
    nt = m.node_tree; p = nt.nodes['Principled BSDF']
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = 8
    r = nt.nodes.new('ShaderNodeMapRange'); r.inputs['To Min'].default_value = lo; r.inputs['To Max'].default_value = hi
    nt.links.new(n.outputs['Fac'], r.inputs['Value']); nt.links.new(r.outputs['Result'], p.inputs['Roughness'])
    if bump:
        b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = bump; b.inputs['Distance'].default_value = 0.01
        nt.links.new(n.outputs['Fac'], b.inputs['Height']); nt.links.new(b.outputs['Normal'], p.inputs['Normal'])

M = {}
M['piano'] = mat('piano', srgb(0x22385a), rough=0.42, coat=0.25); add_noise_rough(M['piano'], 25, 0.32, 0.55, 0.15)
M['groove'] = mat('groove', srgb(0x0e1622), rough=0.7)
M['ivory'] = mat('ivory', srgb(0xeee3cc), rough=0.28, coat=0.4, sss=0.08)
M['ebony'] = mat('ebony', srgb(0x111112), rough=0.2, coat=0.8)
M['felt'] = mat('felt', srgb(0x5e1818), rough=1.0)
M['brass'] = mat('brass', srgb(0xc9a050), rough=0.25, metal=1.0)
M['wax'] = mat('wax', srgb(0xf4ecdc), rough=0.4, sss=0.4)
M['flame'] = mat('flame', (1, 0.8, 0.45), emit=(1.0, 0.62, 0.25), estr=60)
M['wood'] = mat('wood', srgb(0x6b3a1e), rough=0.35, coat=0.6); add_noise_rough(M['wood'], 6, 0.3, 0.45)
M['mug'] = mat('mug', srgb(0x5f7a52), rough=0.25, coat=0.8)
M['wall'] = mat('wall', srgb(0x3e2a1e), rough=0.9); add_noise_rough(M['wall'], 60, 0.8, 0.95, 0.3)
M['frame'] = mat('frame', srgb(0x2e1d10), rough=0.5)
M['gold'] = mat('gold', srgb(0xb8933e), rough=0.35, metal=1.0)
M['floor'] = mat('floor', srgb(0x24170f), rough=0.7)
M['cover'] = mat('cover', srgb(0x5b4a30), rough=0.8)
M['skin'] = mat('skin', srgb(0xd03ab8), rough=0.33, coat=0.5, sss=0.15)
M['spot'] = mat('spot', srgb(0xb8309f), rough=0.33, coat=0.5)
M['sucker'] = mat('sucker', srgb(0xe887d8), rough=0.4, coat=0.3)
M['eyew'] = mat('eyew', (0.95, 0.95, 0.95), rough=0.1, coat=1)
M['iris'] = mat('iris', srgb(0x2f7fe0), rough=0.15, coat=1)
M['pupil'] = mat('pupil', srgb(0x0a1630), rough=0.1, coat=1)
M['glint'] = mat('glint', (1, 1, 1), emit=(1, 1, 1), estr=4)
M['mouth'] = mat('mouth', srgb(0x4a0f3e), rough=0.6)
M['blush'] = mat('blush', srgb(0xff7fc8), rough=0.5, alpha=0.5)
M['dust'] = mat('dust', (1, 0.85, 0.6), emit=(1, 0.8, 0.55), estr=0.9)
M['pebble'] = [mat(f'peb{i}', srgb(c), rough=0.6) for i, c in enumerate((0xb9ad98, 0xd8d0c0, 0x9c9283))]
M['curtain'] = mat('curtain', srgb(0x5a1a1c), rough=0.9); add_noise_rough(M['curtain'], 8, 0.85, 0.95, 0.2)
M['winframe'] = mat('winframe', srgb(0xd9d2c4), rough=0.5)

# ---------------- mesh helpers ----------------
def mesh_obj(name, verts, faces, m, smooth=True, three=True):
    me = bpy.data.meshes.new(name)
    vs = [tuple(B(v)) for v in verts] if three else verts
    me.from_pydata(vs, [], faces); me.update()
    if smooth: me.shade_smooth()
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); link(o); return o
def box(name, size, center, m, bevel=0.03, segs=3):
    w, h, d = size
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * w, v.co.y * d, v.co.z * h))
    bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); o.location = B(center); link(o)
    if bevel > 0:
        md = o.modifiers.new('bev', 'BEVEL'); md.width = bevel; md.segments = segs; md.limit_method = 'NONE'
        o.modifiers.new('ws', 'WEIGHTED_NORMAL')
        me.shade_smooth()
    return o
def sphere_verts(r=1.0, seg=48, ring=32):
    V = [(0, r, 0)]; F = []
    for i in range(1, ring):
        th = math.pi * i / ring
        for j in range(seg):
            ph = 2 * math.pi * j / seg; V.append((r * math.sin(th) * math.cos(ph), r * math.cos(th), r * math.sin(th) * math.sin(ph)))
    V.append((0, -r, 0)); S = len(V) - 1
    for j in range(seg): F.append((0, 1 + (j + 1) % seg, 1 + j))
    for i in range(ring - 2):
        for j in range(seg):
            a = 1 + i * seg + j; b = 1 + i * seg + (j + 1) % seg; F.append((a, b, b + seg, a + seg))
    base = 1 + (ring - 2) * seg
    for j in range(seg): F.append((base + j, base + (j + 1) % seg, S))
    return V, F
def ellipsoid(name, r, scale, R3, pos, m, seg=32, ring=20):
    V, F = sphere_verts(r, seg, ring)
    V = [tuple(Vector(pos) + R3 @ Vector((x * scale[0], y * scale[1], z * scale[2]))) for x, y, z in V]
    return mesh_obj(name, V, F, m)
def lathe(name, prof, pos, m, seg=48, rotY=0.0):
    V = []; F = []; n = len(prof)
    for j in range(seg):
        a = 2 * math.pi * j / seg + rotY
        for (r, y) in prof: V.append((pos[0] + r * math.cos(a), pos[1] + y, pos[2] + r * math.sin(a)))
    for j in range(seg):
        for i in range(n - 1):
            a = j * n + i; b = ((j + 1) % seg) * n + i; F.append((a, a + 1, b + 1, b))
    return mesh_obj(name, V, F, m)
def plane(name, w, h, center, R3, m):
    V = [(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)]
    V = [tuple(Vector(center) + R3 @ Vector(v)) for v in V]
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(B(v)) for v in V], [], [(0, 1, 2, 3)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]): uv[i].uv = c
    me.materials.append(m); o = bpy.data.objects.new(name, me); link(o); return o
I3 = Matrix.Identity(3)

# centripetal Catmull-Rom sampled by arc length (three CatmullRomCurve3.getPointAt)
def catmull(pts, n=60):
    P = [Vector(p) for p in pts]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0; t1 = t0 + max((p1 - p0).length ** 0.5, 1e-4); t2 = t1 + max((p2 - p1).length ** 0.5, 1e-4); t3 = t2 + max((p3 - p2).length ** 0.5, 1e-4)
        for k in range(24):
            t = t1 + (t2 - t1) * k / 24
            A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
            B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
            dense.append((t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2)
    dense.append(P[-2])
    L = [0.0]
    for i in range(1, len(dense)): L.append(L[-1] + (dense[i] - dense[i - 1]).length)
    out = []; j = 0
    for k in range(n + 1):
        s = L[-1] * k / n
        while j < len(L) - 2 and L[j + 1] < s: j += 1
        u = (s - L[j]) / max(L[j + 1] - L[j], 1e-9); out.append(dense[j].lerp(dense[j + 1], u))
    return out
def tube_geo(path, r0, r1, radial=20, suckers=0, closed_tip=True, rfun=None):
    n = len(path) - 1
    T = [(path[min(i + 1, n)] - path[max(i - 1, 0)]).normalized() for i in range(n + 1)]
    # parallel transport frame
    a = Vector((0, 1, 0)) if abs(T[0].y) < 0.9 else Vector((1, 0, 0))
    N = [T[0].cross(a).normalized()]
    for i in range(1, n + 1):
        v = N[-1] - T[i] * N[-1].dot(T[i]); N.append(v.normalized() if v.length > 1e-6 else N[-1])
    V = []; F = []
    rad = lambda t: rfun(t) if rfun else r1 + (r0 - r1) * (1 - t) ** 1.3
    for i in range(n + 1):
        t = i / n; Bn = T[i].cross(N[i]); r = rad(t)
        for j in range(radial):
            ang = 2 * math.pi * j / radial; d = N[i] * math.cos(ang) + Bn * math.sin(ang)
            V.append(tuple(path[i] + d * r))
    for i in range(n):
        for j in range(radial):
            a0 = i * radial + j; b0 = i * radial + (j + 1) % radial; F.append((a0, b0, b0 + radial, a0 + radial))
    # caps
    tip = len(V); V.append(tuple(path[-1] + T[-1] * rad(1.0) * 0.9))
    for j in range(radial): F.append((n * radial + j, n * radial + (j + 1) % radial, tip))
    st = len(V); V.append(tuple(path[0] - T[0] * rad(0.0) * 0.5))
    for j in range(radial): F.append(((j + 1) % radial, j, st))
    # suckers: little domes on the underside (-N side as in the old build)
    for s in range(suckers):
        t = 0.12 + s * 0.08; i = round(t * n); r = rad(t)
        c = path[i] - N[i] * r * 0.78; sr = r * 0.4
        sv, sf = sphere_verts(sr, 12, 8); base = len(V)
        V += [tuple(c + Vector(v)) for v in sv]; F += [tuple(base + k for k in f) for f in sf]
    return V, F

def set_mesh(o, V, F, three=True):
    me = o.data; me.clear_geometry(); me.from_pydata([tuple(B(v)) for v in V] if three else V, [], F); me.shade_smooth(); me.update()

# ======================= ROOM =======================
KEY = dict(W=0.235, GAP=0.014, LEN=1.5, H=0.14, N=36); LID_Y = 2.62
span = KEY['N'] * KEY['W']
keys = []
for i in range(KEY['N']):
    x = i * KEY['W'] + KEY['W'] / 2
    o = box(f'wk{i}', (KEY['W'] - KEY['GAP'], KEY['H'], KEY['LEN']), (x, -KEY['H'] / 2, -KEY['LEN'] / 2), M['ivory'], bevel=0.02, segs=2)
    keys.append(dict(obj=o, black=False, x=x, rest=-KEY['H'] / 2, z=-KEY['LEN'] / 2))
pattern = [1, 1, 0, 1, 1, 1, 0]
for i in range(KEY['N'] - 1):
    if not pattern[i % 7]: continue
    x = (i + 1) * KEY['W']; y = KEY['H'] / 2 - 0.01; z = -KEY['LEN'] + KEY['LEN'] * 0.31
    o = box(f'bk{i}', (KEY['W'] * 0.55, KEY['H'], KEY['LEN'] * 0.62), (x, y, z), M['ebony'], bevel=0.025, segs=3)
    keys.append(dict(obj=o, black=True, x=x, rest=y, z=z))
P = M['piano']
box('keybed', (span + 0.6, 0.5, 2.0), (span / 2, -0.42, -0.75), P, 0.02)
box('slip', (span + 0.7, 0.24, 0.16), (span / 2, -0.2, 0.08), P, 0.04)
box('cheekL', (0.32, 0.48, 2.05), (-0.16, 0.0, -0.74), P, 0.06); box('cheekR', (0.32, 0.48, 2.05), (span + 0.16, 0.0, -0.74), P, 0.06)
box('felt', (span, 0.05, 0.07), (span / 2, 0.08, -KEY['LEN'] - 0.035), M['felt'], 0.01)
box('fallboard', (span + 0.6, 0.52, 0.14), (span / 2, 0.28, -KEY['LEN'] - 0.14), P, 0.04)
box('ledge', (span * 0.55, 0.06, 0.36), (span * 0.6, 0.63, -KEY['LEN'] - 0.08), P, 0.02)
box('panel', (span + 0.6, 2.0, 0.24), (span / 2, 1.58, -KEY['LEN'] - 0.33), P, 0.05)
for gy in (0.82, 2.32): box(f'groove{gy}', (span + 0.3, 0.028, 0.02), (span / 2, gy, -KEY['LEN'] - 0.205), M['groove'], 0.008)
box('lid', (span + 0.8, 0.13, 1.05), (span / 2, LID_Y, -KEY['LEN'] - 0.45), P, 0.06)
box('base', (span + 0.6, 1.8, 2.0), (span / 2, -1.55, -0.95), P, 0.03)
# open music book, pages gently curved up from the spine (like a real open book)
book_c = Vector((span * 0.6, 0.7, -KEY['LEN'] - 0.1)); bookR = euler3(-0.16, 0, 0)
for page, img in ((0, 'sheet_a.png'), (1, 'sheet_b.png')):
    nx, ny = 30, 2; V = []; F = []; UV = []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u = i / nx; fromSpine = u if page else 1 - u
            x = (u - 0.5) * 1.35 + (0.68 if page else -0.68); y = (j / ny - 0.5) * 1.8 + 0.9
            z = 0.09 * (1 - math.exp(-fromSpine * 5)) * (1 - fromSpine * 0.6)
            V.append(tuple(book_c + bookR @ Vector((x, y, z)))); UV.append((u, j / ny))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i; F.append((a, a + 1, a + nx + 2, a + nx + 1))
    o = mesh_obj(f'page{page}', V, F, img_mat(f'sheet{page}', os.path.join(TEX, img), rough=0.9, tint=(0.92, 0.89, 0.83)))
    uvl = o.data.uv_layers.new()
    for poly in o.data.polygons:
        for li in poly.loop_indices: uvl.data[li].uv = UV[o.data.loops[li].vertex_index]
box('bookcover', (2.8, 1.86, 0.02), tuple(book_c + bookR @ Vector((0, 0.9, -0.03))), M['cover'], 0.005)
# things on the lid
lidTop = LID_Y + 0.065; lz = -KEY['LEN'] - 0.38
cx = span * 0.79
lathe('candlestick', [(0, 0), (0.2, 0), (0.21, 0.03), (0.12, 0.06), (0.05, 0.1), (0.04, 0.4), (0.06, 0.46), (0.11, 0.5), (0.1, 0.53), (0.075, 0.53), (0, 0.53)], (cx, lidTop, lz), M['brass'])
lathe('wax', [(0, 0), (0.072, 0), (0.07, 0.55), (0.055, 0.57), (0, 0.565)], (cx, lidTop + 0.525, lz), M['wax'])
flame = ellipsoid('flame', 0.05, (0.8, 2.4, 0.8), I3, (0, 0, 0), M['flame'])
flame_base = Vector((cx, lidTop + 1.13, lz))
candle = bpy.data.lights.new('candle', 'POINT'); candle.color = (1.0, 0.6, 0.28); candle.shadow_soft_size = 0.04
cL = bpy.data.objects.new('candleL', candle); cL.location = B(cx, lidTop + 1.2, lz + 0.1); link(cL)
mx = span * 0.9
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.34, radius2=0.12, depth=0.95); met = bpy.context.object
for c in met.users_collection: c.objects.unlink(met)
link(met); met.location = B(mx, lidTop + 0.475, lz - 0.05); met.rotation_euler = (0, 0, math.pi / 4); met.data.materials.append(M['wood'])
pend = bpy.data.objects.new('pend', None); link(pend); pend_pos = (mx, lidTop + 0.18, lz + 0.2)
rod = box('rod', (0.018, 0.75, 0.012), (0, 0.375, 0), M['brass'], 0); rod.parent = pend
wgt = box('wgt', (0.07, 0.06, 0.03), (0, 0.55, 0), M['brass'], 0.005); wgt.parent = pend
lathe('mug', [(0, 0), (0.15, 0), (0.16, 0.02), (0.16, 0.3), (0.145, 0.3), (0.145, 0.03), (0, 0.03)], (span * 0.12, lidTop, lz + 0.1), M['mug'])
for k, (px, ps) in enumerate(((span * 0.2, 0.06), (span * 0.22, 0.045), (span * 0.235, 0.05))):
    ellipsoid(f'peb{k}', ps, (1, 0.7, 1), I3, (px, lidTop + ps * 0.7, lz + 0.25), M['pebble'][k], 24, 14)
# wall, paintings, floor
wall = plane('wall', 40, 16, (span / 2, 4, -KEY['LEN'] - 1.0), I3, M['wall'])
for (x, y, w2, h2, img) in ((span * 0.26, 4.05, 1.5, 1.1, 'paint_a.png'), (span * 0.62, 4.25, 1.15, 0.85, 'paint_b.png')):
    box(f'fr{x}', (w2 + 0.22, h2 + 0.22, 0.08), (x, y, -KEY['LEN'] - 0.95), M['frame'], 0.03)
    box(f'gd{x}', (w2 + 0.04, h2 + 0.04, 0.09), (x, y, -KEY['LEN'] - 0.95), M['gold'], 0.01)
    plane(f'art{x}', w2, h2, (x, y, -KEY['LEN'] - 0.9), I3, img_mat(f'art{x}', os.path.join(TEX, img), 0.7))
fl = plane('floor', 60, 60, (span / 2, -2.45, 0), euler3(-math.pi / 2, 0, 0), M['floor'])

# ---- light: one warm lamp pool raking the keys (like the reference), soft glow on the panel, candle, faint cool fill ----
def spot(name, pos, target, energy, color, size_deg, blend, radius):
    l = bpy.data.lights.new(name, 'SPOT'); l.energy = energy; l.color = color; l.spot_size = math.radians(size_deg); l.spot_blend = blend; l.shadow_soft_size = radius
    o = bpy.data.objects.new(name, l); link(o); o.location = B(pos)
    d = (B(target) - B(pos)); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return o
key_light = spot('lamp', (-2.5, 6.0, 5.0), (4.0, 0.0, -0.6), 16000, (1.0, 0.68, 0.4), 24, 0.6, 0.45)
panel_light = spot('panelglow', (3.0, 4.5, 6.0), (4.6, 1.6, -1.9), 2600, (1.0, 0.84, 0.62), 26, 1.0, 1.0)
wall_light = spot('wallwash', (4.2, 0.5, 4.0), (4.2, 4.2, -2.5), 5500, (1.0, 0.7, 0.45), 80, 1.0, 1.5)
rim = bpy.data.lights.new('rim', 'AREA'); rim.energy = 120; rim.size = 4; rim.color = (0.55, 0.65, 1.0)
rimO = bpy.data.objects.new('rim', rim); link(rimO); rimO.location = B(14, 3, 6); rimO.rotation_euler = (B(4, 0.5, -1) - B(14, 3, 6)).to_track_quat('-Z', 'Y').to_euler()

# dust specks in the lamp beam
rs = np.random.RandomState(5)
dust = []
dme = bpy.data.meshes.new('dust'); bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.005); bm.to_mesh(dme); bm.free(); dme.materials.append(M['dust'])
for i in range(110):
    o = bpy.data.objects.new(f'dust{i}', dme); link(o)
    base = (0.5 + rs.rand() * (span - 1), 0.3 + rs.rand() * 3.0, -1.3 + rs.rand() * 3.5); dust.append((o, base))

# ======================= FLY =======================
flyimg = os.path.join(TEX, 'fly_clean.png')
fly_aspect = 1598 / 769
def fly_card(name, length, tint=None):
    h = length / fly_aspect
    m = img_mat(name, flyimg, rough=0.55, alpha=True, emit=0.18, tint=tint)
    root = bpy.data.objects.new(name + 'R', None); link(root)
    o = plane(name, length, h, (0, h / 2, 0), I3, m); o.parent = root
    return root
FLY = fly_card('fly', 1.05)

# ======================= OCTOPUS =======================
OS = 0.78; OPOS = Vector((2.6, 0.22, -1.0))
octo = bpy.data.objects.new('octo', None); link(octo)
def child(o, L=None):
    o.parent = octo; o.matrix_parent_inverse = Matrix.Identity(4)
    if L is not None: o.matrix_basis = L
    return o
V, F = sphere_verts(1.0, 96, 64)
HV = []
for x, y, z in V:
    k = 1.18 if y > 0 else 0.92; bul = 1 + 0.06 * math.exp(-((y - 0.55) ** 2) * 6); HV.append((x * bul, y * k + 1.55, z * bul))
child(mesh_obj('head', HV, F, M['skin']))
for (x, y, z, r) in ((0.55, 2.35, 0.55, 0.11), (-0.62, 2.2, 0.48, 0.09), (0.18, 2.62, 0.62, 0.07), (-0.3, 2.5, 0.75, 0.06), (0.8, 1.9, 0.45, 0.07)):
    v = Vector((x, (y - 1.55) / 1.18, z)).normalized(); p = Vector((v.x, 1.55 + v.y * 1.18, v.z))
    child(ellipsoid('dot', r, (1, 1, 0.12), lookR(p, p + (p - Vector((0, 1.6, 0)))), p, M['spot'], 24, 14))
eyes = []
for s in (-1, 1):
    pos = Vector((s * 0.37, 1.7, 0.76)); R = lookR(pos, (s * 0.9, 1.78, 3.5))
    e = bpy.data.objects.new('eye', None); link(e); child(e, mat4(R, pos))
    parts = [ellipsoid('ball', 0.33, (1, 1.18, 0.62), I3, (0, 0, 0), M['eyew']),
             ellipsoid('iris', 0.2, (1, 1.1, 0.4), I3, (0, -0.02, 0.13), M['iris']),
             ellipsoid('pupil', 0.11, (1, 1.1, 0.4), I3, (0, -0.02, 0.18), M['pupil']),
             ellipsoid('g1', 0.045, (1, 1, 1), I3, (-0.06, 0.07, 0.24), M['glint'], 12, 8),
             ellipsoid('g2', 0.022, (1, 1, 1), I3, (0.06, -0.06, 0.24), M['glint'], 12, 8)]
    for p_ in parts: p_.parent = e; p_.matrix_parent_inverse = Matrix.Identity(4)
    eyes.append((e, R, pos))
    bp = Vector((s * 0.6, 1.36, 0.78)); child(ellipsoid('blush', 0.13, (1, 0.8, 0.12), lookR(bp, (s * 1.8, 1.4, 2.6)), bp, M['blush'], 24, 14))
arc = [Vector((0.17 * math.cos(a), 0.17 * math.sin(a), 0)) for a in np.linspace(0, math.pi * 0.85, 30)]
Rz = Matrix.Rotation(math.pi + math.pi * 0.075, 3, 'Z')
arc = [Rz @ p + Vector((0, 1.36, 0.93)) for p in arc]
sv, sfc = tube_geo(arc, 0.028, 0.028, 12, rfun=lambda t: 0.028)
smile = bpy.data.objects.new('smile', bpy.data.meshes.new('smile')); link(smile); smile.data.materials.append(M['mouth'])
set_mesh(smile, [tuple(v - Vector((0, 1.36, 0.93))) for v in map(Vector, sv)], sfc)
smile_pos = Vector((0, 1.36, 0.93)); child(smile, mat4(I3, smile_pos))
tents = []
for k in range(8):
    me = bpy.data.meshes.new(f'tent{k}'); o = bpy.data.objects.new(f'tent{k}', me); link(o); me.materials.append(M['skin']); me.materials.append(M['sucker'])
    child(o); tents.append(o)

# ======================= WINDOW SET (separate location) =======================
CUR[0] = COL_WIN
WO = Vector((-80, 0, 0))   # local: lid top at y=0, window wall at z=0, room on -z, camera looks toward +z
def wp(x, y, z): return tuple(WO + Vector((x, y, z)))
box('wlid', (4.6, 0.13, 3.4), wp(0, -0.065, -1.9), M['piano'], 0.06)
box('wlidbody', (4.6, 3.0, 3.2), wp(0, -1.6, -2.0), M['piano'], 0.03)
# wall with a window opening x -1.3..1.3, y 0.35..3.5
OX0, OX1, OY0, OY1 = -1.3, 1.3, 0.35, 3.55
for nm, (cx_, cy_, w_, h_) in {'wl': (-6.65, 3, 10.7, 12), 'wr': (6.65, 3, 10.7, 12), 'wb': (0, (OY0 - 3) / 2, 2.6, OY0 + 3), 'wt': (0, (OY1 + 9) / 2, 2.6, 9 - OY1)}.items():
    box(nm, (w_, h_, 0.25), wp(cx_, cy_, 0.125), M['wall'], 0)
fw = 0.07
box('sill', (3.0, 0.08, 0.5), wp(0, OY0 - 0.04, -0.05), M['winframe'], 0.02)
for x in (OX0 + fw / 2, 0, OX1 - fw / 2): box('mv', (fw, OY1 - OY0, 0.12), wp(x, (OY0 + OY1) / 2, 0.1), M['winframe'], 0.01)
for i in range(6):
    y = OY0 + fw / 2 + i * (OY1 - OY0 - fw) / 5; box('mh', (OX1 - OX0, fw, 0.12), wp(0, y, 0.1), M['winframe'], 0.01)
box('curtain', (1.0, 4.6, 0.12), wp(OX0 - 0.35, 2.0, -0.25), M['curtain'], 0.05)
skyO = plane('sky', 90, 45, wp(0, 17, 40), I3, emis_img('sky', os.path.join(TEX, 'sky.png'), 1.6))
plane('far', 70, 17.5, wp(0, 4.9, 30), I3, emis_img('farm', os.path.join(TEX, 'far.png'), 0.25, alpha=True))
plane('near', 46, 11.5, wp(0, 2.6, 16), I3, emis_img('nearm', os.path.join(TEX, 'near.png'), 0.6, alpha=True))
win_area = bpy.data.lights.new('winlight', 'AREA'); win_area.shape = 'RECTANGLE'; win_area.size = 2.6; win_area.size_y = 3.2; win_area.energy = 220; win_area.color = (0.75, 0.62, 0.85)
wa = bpy.data.objects.new('winlight', win_area); link(wa); wa.location = B(wp(0, 2.0, 0.4)); wa.rotation_euler = (B(wp(0, 0, -2)) - B(wp(0, 2.0, 0.4))).to_track_quat('-Z', 'Y').to_euler()
wl2 = bpy.data.lights.new('wwarm', 'AREA'); wl2.size = 1.2; wl2.energy = 140; wl2.color = (1.0, 0.65, 0.38)
wo2 = bpy.data.objects.new('wwarm', wl2); link(wo2); wo2.location = B(wp(-2.2, 1.6, -2.6)); wo2.rotation_euler = (B(wp(0.1, 0.2, -1.3)) - B(wp(-2.2, 1.6, -2.6))).to_track_quat('-Z', 'Y').to_euler()
lathe('wmug', [(0, 0), (0.15, 0), (0.16, 0.02), (0.16, 0.3), (0.145, 0.3), (0.145, 0.03), (0, 0.03)], wp(0.95, 0, -0.9), M['mug'])
for k, (px, pz, ps) in enumerate(((0.45, -0.7, 0.06), (0.6, -0.62, 0.045), (0.55, -0.85, 0.05))):
    ellipsoid(f'wpeb{k}', ps, (1, 0.7, 1), I3, wp(px, ps * 0.7, pz), M['pebble'][k], 24, 14)
FLY2 = fly_card('fly2', 0.7, tint=(0.8, 0.72, 0.62))
CUR[0] = COL_MAIN

# ======================= CAMERA =======================
camd = bpy.data.cameras.new('cam'); camd.lens_unit = 'FOV'; camd.sensor_fit = 'VERTICAL'; camd.clip_start = 0.05; camd.clip_end = 300
camd.dof.use_dof = True; camd.dof.aperture_blades = 7
cam = bpy.data.objects.new('cam', camd); sc.collection.objects.link(cam); sc.camera = cam

# ======================= ANIMATION LOGIC (ported from film2.html) =======================
S = lambda a, b, x: (lambda t: t * t * (3 - 2 * t))(min(1, max(0, (x - a) / (b - a))))
lerp = lambda a, b, u: a + (b - a) * u
NAT = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}
def keyFor(midi):
    octv = midi // 12 - 1; pc = midi % 12
    if pc in NAT: return keys[(octv - 2) * 7 + NAT[pc]]
    wi = (octv - 2) * 7 + NAT[pc - 1]; x = (wi + 1) * KEY['W']
    return next(k for k in keys if k['black'] and abs(k['x'] - x) < 1e-6)
surfaceY = lambda k: 0.13 if k['black'] else 0.0
presses = {}
def addPress(k, on, off): presses.setdefault(id(k), []).append((on, off))
def pressDepth(k, t):
    d = 0
    for on, off in presses.get(id(k), []):
        if on <= t < off + 0.07: d = max(d, min(1, (t - on) / 0.025) if t < off else 1 - (t - off) / 0.07)
    return max(0, d)
flyEv = [dict(t=e['t'], k=keyFor(e['midi'])) for e in score['events'] if e['player'] == 'fly']
flyZ = lambda k: -0.86 if k['black'] else -0.5
for i, e in enumerate(flyEv):
    nx = flyEv[i + 1] if i + 1 < len(flyEv) else None
    e['hopIn'] = min(0.13, 0.7 * (e['t'] - flyEv[i - 1]['t'])) if i else 0.3
    e['leave'] = nx['t'] - min(0.13, 0.7 * (nx['t'] - e['t'])) if nx else 18.45
    addPress(e['k'], e['t'], e['leave'])
def flyPose(t):
    first, last = flyEv[0], flyEv[-1]; tilt = 0; squash = 1
    if t < first['t'] - first['hopIn']:
        x = first['k']['x']; z = flyZ(first['k']); y = surfaceY(first['k']) + 0.25 + 0.03 * math.sin(t * 6)
    elif t >= last['leave']:
        u = min(1, (t - last['leave']) / 0.45); x = last['k']['x']; z = flyZ(last['k']); y = surfaceY(last['k']) + 0.3 * 4 * u * (1 - u)
    else:
        i = next((j for j in range(len(flyEv)) if t < (flyEv[j + 1]['t'] if j + 1 < len(flyEv) else 1e9)), len(flyEv) - 1)
        e = flyEv[i]
        if t < e['t']:
            u = S(e['t'] - e['hopIn'], e['t'], t); x = e['k']['x']; z = flyZ(e['k']); y = surfaceY(e['k']) + 0.25 * (1 - u)
        elif t < e['leave']:
            d = pressDepth(e['k'], t); x = e['k']['x']; z = flyZ(e['k']); y = surfaceY(e['k']) - d * 0.07; squash = 1 - 0.1 * math.exp(-(t - e['t']) * 30)
        else:
            nx = flyEv[i + 1]; u = (t - e['leave']) / (nx['t'] - e['leave']); ue = u * u * (3 - 2 * u)
            x = lerp(e['k']['x'], nx['k']['x'], ue); z = lerp(flyZ(e['k']), flyZ(nx['k']), ue)
            y = lerp(surfaceY(e['k']), surfaceY(nx['k']), ue) + 4 * u * (1 - u) * (0.1 + 0.05 * abs(nx['k']['x'] - e['k']['x']) / KEY['W'])
            tilt = (nx['k']['x'] - e['k']['x']) * -0.35 * math.sin(math.pi * u)
    FLY.matrix_basis = mat4(euler3(0, -0.1, tilt), (x, y, z), (1, squash, 1))
    return Vector((x, y + 0.2, z))
octoNotes = sorted(set(e['midi'] for e in score['events'] if e['player'] == 'octo'))
HOLD = score['step'] * 0.9
tent = [dict(key=keyFor(m), times=[e['t'] for e in score['events'] if e['player'] == 'octo' and e['midi'] == m]) for m in octoNotes]
for T in tent:
    for t0 in T['times']: addPress(T['key'], t0, t0 + HOLD)
def tentacleLift(T, t):
    prevEnd = -1e9; nxt = 1e9
    for t0 in T['times']:
        if t0 <= t < t0 + HOLD: return -pressDepth(T['key'], t) * 0.07
        if t0 + HOLD <= t: prevEnd = t0 + HOLD
        if t0 > t and nxt == 1e9: nxt = t0
    a = t - prevEnd; b = nxt - t; gap = nxt - prevEnd
    hmax = 0.12 if nxt == 1e9 else min(0.32, 0.12 + gap * 0.35)
    return hmax * min(S(0, 0.09, a), S(0, 0.11, b))
def octoPose(t):
    busyX = 0; busyN = 0
    for k, T in enumerate(tent):
        lift = tentacleLift(T, t)
        if lift < 0: busyX += T['key']['x']; busyN += 1
        tz = -1.05 if T['key']['black'] else -0.42
        Pp = (Vector((T['key']['x'], surfaceY(T['key']) + 0.03 + lift, tz)) - OPOS) / OS
        root = Vector((-0.6 + 1.2 * k / 7, 0.85, 0.45))
        mid = root.lerp(Pp, 0.45); mid.y = max(root.y, Pp.y) + 0.12 + lift / OS * 0.4; mid.z += 0.25
        path = catmull([root, root + Vector((0, -0.3, 0.3)), mid, Pp + Vector((0, 0.38, -0.12)), Pp + Vector((0, 0.1, 0.02)), Pp], 70)
        V, F = tube_geo(path, 0.3, 0.075, 22, suckers=9)
        set_mesh(tents[k], V, F)
        nbody = 70 * 22 + 22 * 2   # faces before the suckers
        for pi_, poly in enumerate(tents[k].data.polygons): poly.material_index = 1 if pi_ >= nbody else 0
    beat = (t - score['t0']) / (score['step'] * 3)
    pos = Vector((OPOS.x + 0.04 * math.sin(beat * math.pi), OPOS.y + 0.035 * abs(math.sin(beat * math.pi)), OPOS.z))
    octo.matrix_basis = mat4(euler3(0, 0.06 * math.sin(beat * 0.5), 0.03 * math.sin(beat * math.pi)), pos, OS)
    blink = 0.12 if any(abs(t - b) < 0.07 for b in (3.1, 8.2, 11.7, 16.0)) else 1
    lookX = (busyX / busyN - OPOS.x) if busyN else 0
    atFly = S(16.9, 17.5, t)
    for e, R, p in eyes:
        q = euler3(0, lerp(max(-0.15, min(0.15, lookX * 0.08)), 0.3, atFly), 0)
        e.matrix_basis = mat4(R @ q, p, (1, blink, 1))
    sinceBar = ((t - score['t0'] - 2 * score['step']) / (score['step'] * 6)) % 1
    sm = 1 + 0.25 * math.exp(-sinceBar * 6) * (1 if t > score['t0'] else 0) + 0.3 * atFly
    smile.matrix_basis = mat4(I3, smile_pos, sm)

# camera keyframes (lower, closer to key level than v2, like the reference)
Vv = lambda x, y, z: Vector((x, y, z))
camA = [
    dict(t=0.0,  p=Vv(14.5, 1.5, 12.0), l=Vv(3.9, 1.35, -1.0), f=Vv(3.8, 0.45, -0.7), fov=21, fs=0.55),
    dict(t=3.6,  p=Vv(11.6, 1.0, 8.6),   l=Vv(4.4, 1.1, -0.9), f=Vv(4.6, 0.35, -0.6), fov=18.5, fs=0.45),
    dict(t=5.4,  p=Vv(8.6, 0.42, 4.6),   l=Vv(5.0, 0.3, -0.7),  f=Vv(5.0, 0.25, -0.6), fov=17, fs=0.38),
    dict(t=8.6,  p=Vv(8.1, 0.38, 4.0),   l=Vv(4.95, 0.3, -0.7), f=Vv(4.95, 0.25, -0.6), fov=16, fs=0.38),
    dict(t=10.4, p=Vv(-0.8, 0.85, 6.3),  l=Vv(2.6, 0.8, -0.9),  f=Vv(2.6, 0.9, -0.6), fov=19, fs=0.42),
    dict(t=12.6, p=Vv(-1.3, 0.95, 6.9),  l=Vv(2.6, 0.85, -0.9), f=Vv(2.6, 0.9, -0.6), fov=19, fs=0.42),
]
camB = [
    dict(t=14.1, p=Vv(6.4, 0.75, 7.4),   l=Vv(3.9, 0.95, -0.8), f=Vv(3.9, 0.5, -0.7), fov=20, fs=0.45),
    dict(t=17.0, p=Vv(9.4, 1.0, 10.0),   l=Vv(3.8, 1.3, -0.9), f=Vv(3.9, 0.55, -0.7), fov=21, fs=0.5),
    dict(t=19.5, p=Vv(11.6, 1.7, 12.6), l=Vv(3.8, 1.5, -0.9), f=Vv(3.9, 0.55, -0.7), fov=21, fs=0.55),
]
def cr(a, b, c, d, u):
    return catmull([a, b, c, d], 60)[0] if False else _cr(a, b, c, d, u)
def _cr(p0, p1, p2, p3, u):  # centripetal CR between p1 and p2 at param u
    pts = catmull([p0, p1, p2, p3], 90)
    # catmull pads ends; points for segment p1->p2 are the middle third by arc length; approximate with parameter mapping
    L = [0]
    for i in range(1, len(pts)): L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    l1 = (p1 - p0).length; l2 = (p2 - p1).length; l3 = (p3 - p2).length; tot = l1 + l2 + l3
    s = (l1 + u * l2) / tot * L[-1] if tot > 1e-9 else 0
    j = 0
    while j < len(L) - 2 and L[j + 1] < s: j += 1
    w = (s - L[j]) / max(L[j + 1] - L[j], 1e-9); return pts[j].lerp(pts[j + 1], w)
def along(K, t):
    i = next((j for j in range(len(K) - 1) if t < K[j + 1]['t']), len(K) - 2)
    k0, k1, k2, k3 = K[max(0, i - 1)], K[i], K[i + 1], K[min(len(K) - 1, i + 2)]
    u = min(1, max(0, (t - k1['t']) / (k2['t'] - k1['t']))); us = u * u * (3 - 2 * u) * 0.5 + u * 0.5
    def c(f):
        a, b, cc, d = k0[f], k1[f], k2[f], k3[f]
        if (b - cc).length < 1e-6: return b.copy()
        if (a - b).length < 1e-6: a = b + (b - cc) * 0.5
        if (d - cc).length < 1e-6: d = cc + (cc - b) * 0.5
        return _cr(a, b, cc, d, us)
    return c('p'), c('l'), c('f'), lerp(k1['fov'], k2['fov'], us), lerp(k1['fs'], k2['fs'], us)
def place_cam(p, l, fov, fdist, fstop):
    cam.location = B(p); cam.rotation_euler = (B(l) - B(p)).to_track_quat('-Z', 'Y').to_euler()
    camd.angle = math.radians(fov); camd.dof.focus_distance = fdist; camd.dof.aperture_fstop = fstop

def set_frame(fr):
    t = fr / FPS
    for k in keys:
        d = pressDepth(k, t); k['obj'].location = B(k['x'], k['rest'] - d * 0.07, k['z'])
        k['obj'].rotation_euler = M3(euler3(-d * 0.035, 0, 0)).to_euler()
    flyc = flyPose(t); octoPose(t)
    f = 1 + 0.07 * math.sin(t * 13) + 0.05 * math.sin(t * 31 + 1) + 0.03 * math.sin(t * 7.3)
    candle.energy = 6.0 * f
    flame.matrix_basis = mat4(euler3(0, 0, 0.06 * math.sin(t * 5)), flame_base, (1, f, 1))
    pend.matrix_basis = mat4(euler3(0, 0, 0.32 * math.sin(math.pi * (t - score['t0']) / (score['step'] * 3))), pend_pos)
    for i, (o, b) in enumerate(dust):
        o.location = B(b[0] + 0.12 * math.sin(t * 0.3 + i), b[1] + ((t * 0.04 + i * 0.37) % 1) * 0.35, b[2] + 0.1 * math.cos(t * 0.25 + i))
    inWin = 12.6 <= t < 14.1
    COL_WIN.hide_render = not inWin; COL_MAIN.hide_render = inWin
    if inWin:
        u = (t - 12.6) / 1.5
        FLY2.matrix_basis = mat4(euler3(0, 0.12 + math.pi, 0), wp(0.1, 0.012 * abs(math.sin(t * 9)), -1.3))
        p = Vector(wp(-0.35 + 0.15 * u, 0.42 - 0.03 * u, -3.7 + 0.35 * u)); l = Vector(wp(0.1, 0.6, 0))
        place_cam(p, l, 34, (p - Vector(wp(0.1, 0.25, -1.3))).length, 0.6)
    else:
        p, l, fpt, fov, fs = along(camA if t < 13 else camB, t)
        place_cam(p, l, fov, (p - fpt).length, fs)
    return t

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[0] if argv else os.path.join(HERE, 'test')
    frames = [int(x) for x in argv[1].split(',')] if len(argv) > 1 else [48]
    res = int(argv[2]) if len(argv) > 2 else 720
    spp = int(argv[3]) if len(argv) > 3 else 64
    sc.render.resolution_x = sc.render.resolution_y = res; sc.cycles.samples = spp
    os.makedirs(out, exist_ok=True)
    for fr in frames:
        p = os.path.join(out, f'f{fr:04d}.png')
        if os.path.exists(p) and os.path.getsize(p) > 1000: continue
        t0 = time.time(); set_frame(fr); sc.render.filepath = p
        bpy.ops.render.render(write_still=True); print('FRAME', fr, round(time.time() - t0, 1), flush=True)
