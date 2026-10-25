"""Shared helpers (materials, primitives, furniture) copied from sunset-room/build_room.py."""
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------------------------------------------------------- materials
MATS = {}
def mat(name, color, rough=0.6, metal=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    if b is None:
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.get("Material Output") or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    MATS[name] = m
    return m

for args in [
    ("Plaster", (0.78, 0.70, 0.60), 0.92),
    ("Ceiling", (0.82, 0.76, 0.68), 0.95),
    ("Floor", (0.72, 0.64, 0.54), 0.32),
    ("BalconyTile", (0.62, 0.56, 0.48), 0.6),
    ("Concrete", (0.62, 0.58, 0.52), 0.9),
    ("Trim", (0.85, 0.82, 0.76), 0.5),
    ("WoodWarm", (0.42, 0.19, 0.07), 0.42),
    ("WoodLight", (0.52, 0.32, 0.16), 0.5),
    ("WoodDark", (0.22, 0.11, 0.05), 0.5),
    ("Fabric", (0.62, 0.52, 0.40), 0.95),
    ("Pillow", (0.70, 0.60, 0.46), 0.95),
    ("Cushion", (0.74, 0.66, 0.54), 0.95),
    ("Ceramic", (0.70, 0.56, 0.42), 0.55),
    ("CeramicWhite", (0.82, 0.80, 0.76), 0.45),
    ("Terracotta", (0.55, 0.28, 0.15), 0.8),
    ("MetalDark", (0.03, 0.03, 0.03), 0.35, 1.0),
    ("Aluminium", (0.55, 0.55, 0.55), 0.35, 1.0),
    ("Glass", (0.9, 0.95, 0.95), 0.02),
    ("Curtain", (0.92, 0.88, 0.80), 0.9),
    ("Leaf", (0.06, 0.13, 0.04), 0.55),
    ("LeafEuca", (0.16, 0.25, 0.18), 0.6),
    ("LeafIvy", (0.05, 0.16, 0.04), 0.45),
    ("Bark", (0.18, 0.12, 0.07), 0.85),
    ("Soil", (0.06, 0.04, 0.03), 1.0),
    ("Rug", (0.70, 0.62, 0.50), 1.0),
    ("Screen", (0.01, 0.01, 0.012), 0.12),
    ("Paper", (0.86, 0.80, 0.68), 0.9),
    ("BookCover", (0.62, 0.50, 0.30), 0.8),
    ("LampShade", (0.86, 0.78, 0.64), 0.9),
]:
    mat(*args)

# ---------------------------------------------------------------- accumulator
class Group:
    """Collects geometry per material, flushed into one object per material."""
    def __init__(self, name):
        self.name = name
        self.bms = {}

    def bm(self, m):
        if m not in self.bms:
            self.bms[m] = bmesh.new()
        return self.bms[m]

    def add(self, m, tmp, M=Matrix()):
        tmp.transform(M)
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        self.bm(m).from_mesh(me)
        bpy.data.meshes.remove(me)

    def flush(self):
        for m, bm in self.bms.items():
            bm.normal_update()
            uv = bm.loops.layers.uv.new("UVMap")
            for f in bm.faces:
                n = f.normal
                ax = max(range(3), key=lambda i: abs(n[i]))
                for l in f.loops:
                    c = l.vert.co
                    l[uv].uv = (c.y, c.z) if ax == 0 else (c.x, c.z) if ax == 1 else (c.x, c.y)
            name = f"{self.name}__{m}"
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            for p in me.polygons:
                p.use_smooth = True
            try:
                me.set_sharp_from_angle(angle=math.radians(38))
            except Exception:
                pass
            me.materials.append(MATS[m])
            o = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(o)
        self.bms = {}

def T(x, y, z):
    return Matrix.Translation((x, y, z))

def Rz(deg):
    return Matrix.Rotation(math.radians(deg), 4, "Z")

def Rx(deg):
    return Matrix.Rotation(math.radians(deg), 4, "X")

def Ry(deg):
    return Matrix.Rotation(math.radians(deg), 4, "Y")

# ---------------------------------------------------------------- primitives (return temp bmesh)
def p_box(sx, sy, sz, bevel=0.0, segs=3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=bevel,
                        segments=segs, affect="EDGES", profile=0.5, clamp_overlap=True)
    return bm

def p_cyl(r1, r2, h, segs=24, caps=True):
    """Cylinder/cone with base at z=0, top at z=h."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs,
                          radius1=r1, radius2=r2, depth=h)
    bm.transform(T(0, 0, h / 2))
    return bm

def p_lathe(profile, segs=40, cap=True):
    """profile: list of (radius, z) from bottom to top."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = [bm.verts.new((r * math.cos(2 * math.pi * i / segs),
                              r * math.sin(2 * math.pi * i / segs), z)) for i in range(segs)]
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
    return bm

def p_rod(p0, p1, r0, r1=None, segs=8):
    """Cylinder between two points."""
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = p_cyl(r0, r1, d.length, segs, caps=False)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bm.transform(T(*p0) @ q.to_matrix().to_4x4())
    return bm

def add_leaf(bm, M, L, W, fold=0.25, shape="olive"):
    """Leaf outline in local XY (base at origin, tip along +X), folded along the midrib."""
    if shape == "round":
        pts = [(L * (0.5 - 0.5 * math.cos(a)), W * 0.5 * math.sin(a))
               for a in [math.pi * i / 6 for i in range(1, 6)]]
    elif shape == "heart":
        pts = [(0.15 * L, 0.45 * W), (0.45 * L, 0.5 * W), (0.75 * L, 0.3 * W)]
    else:
        pts = [(0.2 * L, 0.32 * W), (0.5 * L, 0.5 * W), (0.8 * L, 0.3 * W)]
    left = [Vector((x, y, abs(y) * fold)) for x, y in pts if y > 0] if shape == "round" else \
           [Vector((x, y, y * fold)) for x, y in pts]
    rib = [Vector((0, 0, 0))] + [Vector((p.x, 0, 0)) for p in left] + [Vector((L, 0, 0))]
    vb = lambda v: bm.verts.new(M @ v)
    rv = [vb(v) for v in rib]
    lv = [vb(v) for v in left]
    rgt = [vb(Vector((v.x, -v.y, v.z))) for v in left]
    n = len(left)
    for side in (lv, rgt):
        for i in range(n + 1):
            a, b = rv[i], rv[i + 1]
            if i == 0:
                f = (a, side[0], b)
            elif i == n:
                f = (a, side[n - 1], b)
            else:
                f = (a, side[i - 1], side[i], b)
            if side is rgt:
                f = tuple(reversed(f))
            try:
                bm.faces.new(f)
            except ValueError:
                pass

# ================================================================ FURNITURE
def sofa(g, M):
    W, D = 2.3, 0.95
    g.add("Fabric", p_box(W, D, 0.25, 0.02), M @ T(0, 0, 0.225))
    g.add("Fabric", p_box(W, 0.2, 0.46, 0.05, 4), M @ T(0, -D / 2 + 0.1, 0.58))
    for s in (-1, 1):
        g.add("Fabric", p_box(0.18, D, 0.32, 0.06, 4), M @ T(s * (W / 2 - 0.09), 0, 0.5))
        for yy in (-D / 2 + 0.06, D / 2 - 0.06):
            g.add("WoodDark", p_cyl(0.022, 0.018, 0.1, 12), M @ T(s * (W / 2 - 0.08), yy, 0))
    cw = (W - 0.36) / 2 - 0.01
    for s in (-1, 1):
        g.add("Cushion", p_box(cw, D - 0.22, 0.17, 0.07, 5), M @ T(s * (cw / 2 + 0.005), 0.09, 0.43))
        g.add("Cushion", p_box(cw, 0.2, 0.44, 0.08, 5), M @ T(s * (cw / 2 + 0.005), -D / 2 + 0.3, 0.73) @ Rx(-9))
    g.add("Pillow", p_box(0.44, 0.14, 0.44, 0.09, 5), M @ T(-0.62, -0.08, 0.72) @ Rx(-14) @ Ry(8))
    g.add("Pillow", p_box(0.40, 0.14, 0.40, 0.09, 5), M @ T(0.66, -0.06, 0.70) @ Rx(-12) @ Ry(-10) @ Rz(12))
    g.add("Pillow", p_box(0.36, 0.13, 0.36, 0.08, 5), M @ T(-0.18, -0.02, 0.66) @ Rx(-16) @ Rz(-8))

def armchair(g, M):
    W, D = 0.66, 0.68
    for sx in (-1, 1):
        g.add("WoodLight", p_box(0.045, 0.045, 0.62, 0.006), M @ T(sx * W / 2, D / 2 - 0.04, 0.31) @ Rx(6))
        g.add("WoodLight", p_box(0.045, 0.045, 0.62, 0.006), M @ T(sx * W / 2, -D / 2 + 0.06, 0.31) @ Rx(-8))
        g.add("WoodLight", p_box(0.07, D + 0.08, 0.035, 0.01), M @ T(sx * W / 2, 0.02, 0.63))
        g.add("WoodLight", p_box(0.035, D - 0.06, 0.06, 0.005), M @ T(sx * W / 2, 0, 0.3))
    for yy in (D / 2 - 0.04, -D / 2 + 0.06):
        g.add("WoodLight", p_box(W, 0.035, 0.06, 0.005), M @ T(0, yy, 0.3))
    for z in (0.62, 0.86):
        g.add("WoodLight", p_box(W - 0.02, 0.03, 0.05, 0.005), M @ T(0, -D / 2 - 0.02 - (z - 0.6) * 0.3, z))
    for sx in (-1, 1):
        g.add("WoodLight", p_box(0.04, 0.04, 0.6, 0.005), M @ T(sx * (W / 2 - 0.02), -D / 2 - 0.04, 0.62) @ Rx(-17))
    g.add("Cushion", p_box(W - 0.08, D - 0.08, 0.11, 0.045, 4), M @ T(0, 0.02, 0.39))
    g.add("Cushion", p_box(W - 0.1, 0.1, 0.42, 0.045, 4), M @ T(0, -D / 2 + 0.03, 0.68) @ Rx(-17))

def round_table(g, M, r, h, m="WoodLight"):
    g.add(m, p_cyl(r, r, 0.035, 40), M @ T(0, 0, h - 0.035))
    g.add(m, p_cyl(0.03, 0.03, h - 0.035, 16), M)
    g.add(m, p_cyl(r * 0.55, r * 0.5, 0.025, 32), M)

def pot(g, M, r0, r1, h, m="CeramicWhite"):
    g.add(m, p_lathe([(r0 * 0.95, 0), (r0, 0.02), (r1, h), (r1 - 0.015, h), (r1 * 0.96 - 0.015, h - 0.04)], 36), M)
    g.add("Soil", p_cyl(r1 * 0.94 - 0.015, r1 * 0.94 - 0.015, 0.01, 24), M @ T(0, 0, h - 0.05))

def tree(g, M, height=1.75, crown_r=0.42, n_leaves=900, seed=3, clusters=16):
    """Olive-like tree: trunk, twigs to sub-clusters, many small leaves."""
    rnd = random.Random(seed)
    top = Vector((0.02, 0.0, height * 0.62))
    g.add("Bark", p_rod((0, 0, 0.3), top, 0.025, 0.016, 10), M)
    centers = []
    for k in range(clusters):
        a = rnd.uniform(0, math.tau)
        el = rnd.uniform(-0.2, 1.0)
        c = top + Vector((math.cos(a) * crown_r * 0.75, math.sin(a) * crown_r * 0.75,
                          0.12 + el * crown_r * 0.9))
        centers.append(c)
        mid = top.lerp(c, 0.5) + Vector((rnd.uniform(-.04, .04), rnd.uniform(-.04, .04), 0.05))
        g.add("Bark", p_rod(top, mid, 0.012, 0.008, 6), M)
        g.add("Bark", p_rod(mid, c, 0.008, 0.004, 6), M)
    bm = g.bm("Leaf")
    for i in range(n_leaves):
        c = centers[i % len(centers)]
        d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.8))).normalized() * rnd.uniform(0.02, 0.22)
        p = c + d
        out = (p - top).normalized()
        yaw = math.atan2(out.y, out.x) + rnd.uniform(-1.2, 1.2)
        pitch = rnd.uniform(-0.9, 0.5)
        roll = rnd.uniform(-1.0, 1.0)
        LM = M @ T(*p) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "Y") @ Matrix.Rotation(roll, 4, "X")
        s = rnd.uniform(0.75, 1.2)
        add_leaf(bm, LM, 0.095 * s, 0.026 * s, 0.35)

def eucalyptus(g, M, n_stems=4, h=0.75, seed=5):
    rnd = random.Random(seed)
    bm = g.bm("LeafEuca")
    for s in range(n_stems):
        a = rnd.uniform(0, math.tau)
        lean = rnd.uniform(0.15, 0.45)
        pts = []
        p = Vector((0, 0, 0))
        dirv = Vector((math.cos(a) * lean, math.sin(a) * lean, 1)).normalized()
        L = h * rnd.uniform(0.8, 1.1)
        n = 14
        for k in range(n + 1):
            pts.append(p.copy())
            dirv = (dirv + Vector((math.cos(a) * 0.06, math.sin(a) * 0.06, -0.015))).normalized()
            p = p + dirv * (L / n)
        for k in range(n):
            g.add("Bark", p_rod(pts[k], pts[k + 1], 0.004, 0.003, 5), M)
        for k in range(2, n + 1):
            for side in (0, math.pi):
                base = pts[k]
                yaw = a + math.pi / 2 + side + rnd.uniform(-0.4, 0.4) + k * 0.6
                LM = M @ T(*base) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(rnd.uniform(-0.6, 0.2), 4, "Y")
                r = 0.05 * (1.15 - k / n * 0.5) * rnd.uniform(0.85, 1.1)
                add_leaf(bm, LM, r, r * 0.95, 0.15, shape="round")

def ivy(g, M, seed=8):
    rnd = random.Random(seed)
    bm = g.bm("LeafIvy")
    for v in range(9):
        a = v / 9 * math.tau + rnd.uniform(-0.2, 0.2)
        p = Vector((0, 0, 0.02))
        dirv = Vector((math.cos(a), math.sin(a), rnd.uniform(0.3, 1.2))).normalized()
        steps = rnd.randint(8, 16)
        for k in range(steps):
            q = p + dirv * 0.04
            g.add("Bark", p_rod(p, q, 0.0025, 0.0025, 4), M)
            p = q
            dirv = (dirv + Vector((rnd.uniform(-.2, .2), rnd.uniform(-.2, .2), -0.22))).normalized()
            for side in (-1, 1):
                yaw = math.atan2(dirv.y, dirv.x) + side * rnd.uniform(0.9, 1.6)
                LM = M @ T(*p) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(rnd.uniform(-0.5, 0.4), 4, "Y")
                s = rnd.uniform(0.7, 1.2)
                add_leaf(bm, LM, 0.055 * s, 0.05 * s, 0.25, shape="heart")

def vase(g, M, h, r, m="Ceramic"):
    prof = []
    for i in range(17):
        t = i / 16
        rr = r * (0.55 + 0.55 * math.sin(math.pi * (0.12 + 0.8 * t)) - 0.25 * t)
        prof.append((max(rr, r * 0.32), t * h))
    prof += [(prof[-1][0] - 0.008, h), (prof[-1][0] - 0.01, h - 0.05)]
    g.add(m, p_lathe(prof, 40), M)
