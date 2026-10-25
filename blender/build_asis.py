"""
1st-floor house from "1st_floor_3d_architectural_interior_design_simulator.html" -> floor.glb
Run:  blender -b --python build_floor.py

Plan coordinates are written in the simulator's Three.js frame (x right, y up, z toward
the bottom of the map) and converted to Blender (x, -z, y), so the exported glTF lands
back in exactly the same Three.js coordinates.

Zones (Three.js x/z):
  Hall (roof)          x[-6.0,-0.5]  z[-6.5,-1.3]   + cabet above stairs, stairs down
  Room 1 (roof)        x[-0.5, 4.5]  z[-6.5,-1.3]   + washroom x[4.5,6.0] with roshan daan
  Room 2 (roof)        x[ 1.0, 6.0]  z[-1.3, 2.4]
  Room 3 (roof)        x[ 1.0, 6.0]  z[ 2.4, 6.5]
  Open court (NO ROOF) x[-6.0, 1.0]  z[-1.3, 6.5]   washing area, washroom (roof), stairs up
"""
import bpy, bmesh, math, random, os, json
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, "lib_room.py"), encoding="utf-8").read())
random.seed(7)
OUT = os.path.join(HERE, "..", "floor.glb")  # as-is build (matches the site walkthrough video)
COLLIDERS = os.path.join(HERE, "..", "colliders.json")

H, TW = 3.0, 0.24          # wall height / thickness
ROOF_T = 0.2

for args in [
    ("Cream", (0.80, 0.72, 0.60), 0.9),
    ("TileBeige", (0.70, 0.62, 0.52), 0.3),
    ("Marble", (0.85, 0.85, 0.83), 0.18),
    ("Stone", (0.35, 0.36, 0.38), 0.55),
    ("StoneTrim", (0.62, 0.55, 0.43), 0.7),
    ("Teak", (0.40, 0.18, 0.06), 0.4),
    ("Brass", (0.85, 0.60, 0.20), 0.25, 1.0),
    ("Porcelain", (0.92, 0.92, 0.92), 0.08),
    ("Chrome", (0.8, 0.8, 0.82), 0.12, 1.0),
    ("Linen", (0.88, 0.87, 0.84), 0.9),
    ("DuvetSand", (0.66, 0.59, 0.47), 0.95),
    ("DuvetSage", (0.30, 0.38, 0.31), 0.95),
    ("DuvetGrey", (0.33, 0.36, 0.40), 0.95),
    ("Headboard", (0.55, 0.47, 0.38), 0.95),
    ("Walnut", (0.22, 0.11, 0.05), 0.45),
    ("Slate", (0.12, 0.15, 0.2), 0.6),
    ("CoveLED", (1.0, 0.85, 0.6), 0.5),
    ("Facade", (0.72, 0.66, 0.56), 0.9),
    ("Facade2", (0.66, 0.60, 0.52), 0.9),
    ("Ground", (0.40, 0.37, 0.33), 0.95),
    ("RoofTop", (0.58, 0.54, 0.48), 0.9),
    ("WindowDark", (0.03, 0.04, 0.05), 0.2),
    ("WasherBody", (0.9, 0.9, 0.9), 0.35),
    ("FanWhite", (0.9, 0.9, 0.88), 0.35),
    # as-is site materials seen in the walkthrough video
    ("Cement", (0.55, 0.54, 0.51), 0.95),
    ("TileDusty", (0.62, 0.57, 0.50), 0.55),
    ("Skirting", (0.70, 0.55, 0.40), 0.5),
    ("BrickCeiling", (0.45, 0.30, 0.24), 0.95),
    ("BrickRaw", (0.50, 0.25, 0.15), 0.95),
    ("RedSteel", (0.35, 0.04, 0.04), 0.45, 0.4),
    ("IronBlack", (0.03, 0.03, 0.03), 0.5, 0.6),
    ("SteelPipe", (0.25, 0.25, 0.26), 0.4, 0.8),
    ("Charpai", (0.35, 0.08, 0.06), 0.85),
    ("CharpaiBlue", (0.08, 0.10, 0.30), 0.85),
    ("PlasticGrey", (0.45, 0.47, 0.50), 0.45),
    ("CoolerBody", (0.08, 0.08, 0.09), 0.5),
    ("Stainless", (0.75, 0.75, 0.76), 0.25, 1.0),
    ("BucketWhite", (0.85, 0.85, 0.82), 0.4),
    ("BucketBlue", (0.10, 0.25, 0.45), 0.4),
    ("TrunkGreen", (0.55, 0.65, 0.55), 0.4, 0.5),
    ("Cloth", (0.85, 0.83, 0.80), 0.95),
    ("ClothStripe", (0.45, 0.30, 0.30), 0.95),
    ("Sack", (0.75, 0.60, 0.40), 0.95),
    ("Wire", (0.02, 0.02, 0.02), 0.6),
    ("WireRed", (0.6, 0.02, 0.02), 0.5),
    ("Switch", (0.85, 0.84, 0.8), 0.4),
]:
    mat(*args)

# ---------------------------------------------------------------- helpers in Three.js coordinates
def M3(x, y, z, rot=0.0):
    """Three.js position + rotation about +Y  ->  Blender matrix."""
    return T(x, -z, y) @ Rz(math.degrees(rot))

COL = []   # 2D colliders in Three.js xz: [x0, x1, z0, z1]

def collide(x, z, w, d, rot=0.0, pad=0.0):
    c, s = abs(math.cos(rot)), abs(math.sin(rot))
    hw, hd = (w * c + d * s) / 2 + pad, (w * s + d * c) / 2 + pad
    COL.append([round(x - hw, 3), round(x + hw, 3), round(z - hd, 3), round(z + hd, 3)])

def box3(g, m, w, h, d, x, y, z, rot=0.0, bevel=0.0, col=False):
    """w = x size, h = y size, d = z size (Three.js), centred at (x, y, z)."""
    g.add(m, p_box(w, d, h, bevel, 3 if bevel else 1), M3(x, y, z, rot))
    if col:
        collide(x, z, w, d, rot)

def wall(g, w, h, d, x, y, z, m="Cement", col=True):
    box3(g, m, w, h, d, x, y, z, col=col)
    if abs(h - H) < 1e-6 and max(w, d) > 0.3:                                # tile skirting on full walls
        if w >= d:
            for s in (-1, 1):
                box3(g, "Skirting", w, 0.1, 0.012, x, 0.1, z + s * (d / 2 + 0.006))
        else:
            for s in (-1, 1):
                box3(g, "Skirting", 0.012, 0.1, d, x + s * (w / 2 + 0.006), 0.1, z)

def charpai(g, x, y, z, rot=0.0, tilt=0.0, weave="Charpai"):
    """Woven rope bed: turned legs, wooden rails, rope net (Punjabi charpai)."""
    B = M3(x, y, z, rot)
    if tilt:                                                                    # stood up on its side, leaning
        B = B @ T(0, 0, 0.55) @ Rx(tilt)
    g.add(weave, p_box(1.8, 0.95, 0.025), B @ T(0, 0, 0.46))
    for sy in (-0.5, 0.5):
        g.add("WoodDark", p_cyl(0.035, 0.035, 1.95, 10), B @ T(-0.975, sy, 0.46) @ Ry(90))
    for sx in (-0.95, 0.95):
        g.add("WoodDark", p_cyl(0.03, 0.03, 1.0, 10), B @ T(sx, -0.5, 0.46) @ Rx(-90))
        for sy in (-0.5, 0.5):
            g.add("WoodDark", p_lathe([(0.03, 0), (0.045, 0.1), (0.035, 0.22), (0.05, 0.36), (0.035, 0.5), (0.03, 0.56)], 12), B @ T(sx, sy, 0))

def plastic_chair(g, x, z, rot):
    B = M3(x, 0.05, z, rot)
    g.add("PlasticGrey", p_box(0.48, 0.46, 0.04, 0.015, 2), B @ T(0, 0, 0.44))
    g.add("PlasticGrey", p_box(0.5, 0.04, 0.4, 0.015, 2), B @ T(0, 0.24, 0.68) @ Rx(-10))
    for sx in (-0.25, 0.25):
        g.add("PlasticGrey", p_box(0.04, 0.42, 0.04, 0.012, 2), B @ T(sx, 0.02, 0.64))
        g.add("PlasticGrey", p_box(0.035, 0.035, 0.24, 0.01, 1), B @ T(sx, -0.18, 0.54))
        for sy in (-0.2, 0.22):
            g.add("PlasticGrey", p_rod((sx * 1.05, sy * 1.15, 0), (sx, sy, 0.43), 0.016, 0.02, 8), B)
    collide(x, z, 0.55, 0.55)

def air_cooler(g, x, z, rot):
    B = M3(x, 0.05, z, rot)
    g.add("CoolerBody", p_box(0.65, 0.5, 1.0, 0.03, 2), B @ T(0, 0, 0.62))
    for i in range(11):
        g.add("PlasticGrey", p_box(0.5, 0.03, 0.025), B @ T(0, -0.255, 0.4 + i * 0.06) @ Rx(30))
    g.add("PlasticGrey", p_box(0.66, 0.51, 0.06, 0.02, 2), B @ T(0, 0, 1.12))
    for sx in (-0.28, 0.28):
        for sy in (-0.2, 0.2):
            g.add("SteelPipe", p_cyl(0.02, 0.02, 0.12, 8), B @ T(sx, sy, 0))
    collide(x, z, 0.7, 0.55, rot)

def pedestal_fan(g, x, z, rot):
    B = M3(x, 0.05, z, rot)
    g.add("PlasticGrey", p_cyl(0.2, 0.22, 0.04, 20), B)
    g.add("SteelPipe", p_cyl(0.015, 0.015, 1.15, 8), B)
    g.add("FanWhite", p_cyl(0.07, 0.07, 0.16, 16), B @ T(0, 0.05, 1.2) @ Rx(90))
    for i in range(3):
        g.add("FanWhite", p_box(0.18, 0.01, 0.08, 0.005, 1), B @ T(0, -0.06, 1.2) @ Ry(i * 120) @ T(0.1, 0, 0))
    for r in (0.1, 0.2, 0.25):
        g.add("SteelPipe", p_lathe([(r, 0), (r + 0.004, 0.004), (r, 0.008)], 32, cap=False), B @ T(0, -0.1, 1.2) @ Rx(90))
    for i in range(16):
        a = i / 16 * math.tau
        g.add("SteelPipe", p_rod((0, 0, 0), (math.cos(a) * 0.25, 0, math.sin(a) * 0.25), 0.002, segs=4), B @ T(0, -0.1, 1.2))

def bucket(g, x, y, z, r=0.15, h=0.3, m="BucketWhite"):
    g.add(m, p_lathe([(r * 0.78, 0), (r, h), (r * 0.96, h), (r * 0.74, 0.01)], 24), M3(x, y, z))

def switchboard(g, x, y, z, rot):
    B = M3(x, y, z, rot)
    g.add("Switch", p_box(0.2, 0.03, 0.14, 0.004, 1), B)
    for i in range(3):
        g.add("WireRed" if i % 2 else "Wire", p_rod((0.02 * i - 0.02, -0.01, -0.07), (0.03 * i - 0.04, -0.03, -0.3 - 0.06 * i), 0.003, segs=4), B)

def ceiling_box(g, x, z):
    """Junction box with a dangling red wire and a fan hook, on the raw brick ceiling."""
    box3(g, "Switch", 0.14, 0.01, 0.14, x, H - 0.006, z)
    g.add("WireRed", p_rod((x, -z, H - 0.01), (x + 0.04, -z, H - 0.35), 0.004, segs=4))
    g.add("IronBlack", p_rod((x - 0.05, -z, H - 0.01), (x - 0.05, -z, H - 0.12), 0.006, segs=6))

def rect_minus(r, hole):
    """Split rect (x0,x1,z0,z1) around an axis-aligned hole."""
    x0, x1, z0, z1 = r
    hx0, hx1, hz0, hz1 = max(x0, hole[0]), min(x1, hole[1]), max(z0, hole[2]), min(z1, hole[3])
    if hx0 >= hx1 or hz0 >= hz1:
        return [r]
    out = []
    if hz0 > z0: out.append((x0, x1, z0, hz0))
    if hz1 < z1: out.append((x0, x1, hz1, z1))
    if hx0 > x0: out.append((x0, hx0, hz0, hz1))
    if hx1 < x1: out.append((hx1, x1, hz0, hz1))
    return out

def slab(g, m, r, y0, y1, hole=None):
    for (x0, x1, z0, z1) in (rect_minus(r, hole) if hole else [r]):
        box3(g, m, x1 - x0, y1 - y0, z1 - z0, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)

def make_obj(name, m, bm, loc):
    """Standalone object with its own origin (used for animated ceiling fans)."""
    bm.normal_update()
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            l[uv].uv = (l.vert.co.x, l.vert.co.y)
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
    o.location = loc
    bpy.context.scene.collection.objects.link(o)

# ================================================================ STRUCTURE
st = Group("Arch")
WELL = (-5.2, -3.19, -2.11, -0.94)    # stair well down to the ground floor

# 12.35 x 13.35 floor slab with stone fascia, ground floor below, street
slab(st, "StoneTrim", (-6.175, 6.175, -6.675, 6.675), -0.38, -0.06, WELL)
box3(st, "Facade", 12.2, 3.0, 13.2, 0, -1.9, 0)
box3(st, "StoneTrim", 12.5, 0.12, 13.5, 0, -0.42, 0)
box3(st, "Ground", 80, 0.1, 80, 0, -3.45, 0)

# zone floors (top at y = 0.05)
slab(st, "TileDusty", (-6.0, -0.5, -6.5, -1.3), -0.06, 0.05, WELL)          # hall
slab(st, "TileDusty", (-0.5, 4.5, -6.5, -1.3), -0.06, 0.05)                 # room 1
slab(st, "Marble", (4.5, 6.0, -6.5, -1.3), -0.06, 0.055)                    # room 1 washroom
slab(st, "TileDusty", (1.0, 6.0, -1.3, 2.4), -0.06, 0.05)                   # room 2
slab(st, "TileDusty", (1.0, 6.0, 2.4, 6.5), -0.06, 0.05)                    # room 3
slab(st, "TileDusty", (-6.0, 1.0, -1.3, 6.5), -0.06, 0.045, WELL)              # open court
slab(st, "Marble", (-6.0, -3.5, 3.7, 6.5), -0.06, 0.055)                    # bottom-left washroom

# ---- Zone 1: hall
wall(st, TW, H, 5.2, -6.0, H / 2, -3.9)
wall(st, 1.2, H, TW, -5.4, H / 2, -6.5)
wall(st, 0.8, H, TW, -0.9, H / 2, -6.5)
wall(st, 3.5, 0.85, 0.22, -3.05, 0.425, -6.5)                               # hall outer opening parapet
box3(st, "Cement", 3.6, 0.06, 0.3, -3.05, 0.88, -6.5)
for ry in (1.05, 1.28, 1.5):
    st.add("SteelPipe", p_rod((-4.8, 6.5, ry), (-1.3, 6.5, ry), 0.022, segs=10))
for px in (-4.75, -3.9, -3.05, -2.2, -1.35):
    st.add("SteelPipe", p_rod((px, 6.5, 0.88), (px, 6.5, 1.52), 0.02, segs=10))
wall(st, 3.5, 0.35, TW, -3.05, H - 0.175, -6.5, col=False)                  # beam over the opening

# cabet above the stairs + wood lining + slate cap
wall(st, 1.5, H, 0.2, -5.25, H / 2, -4.2)
wall(st, 0.2, H, 2.0, -4.5, H / 2, -3.2)
box3(st, "Cement", 1.3, 0.08, 1.8, -5.25, 2.2, -3.2)                       # loft shelf (parchatti)
for (sx, sz) in [(-5.6, -3.6), (-5.15, -3.4), (-4.85, -3.75)]:
    st.add("Sack", p_box(0.42, 0.3, 0.28, 0.1, 3), M3(sx, 2.38, sz, 0.3))
box3(st, "Cement", 1.58, 0.16, 1.05, -5.25, 3.0 + ROOF_T + 0.08, -3.72)

# stairs down to the ground floor: parapets, steps, shaft
wall(st, 1.5, 1.0, 0.18, -3.85, 0.5, -2.2)
wall(st, 0.18, 1.0, 1.45, -3.1, 0.5, -1.55)
wall(st, 1.6, 0.85, 0.18, -3.85, 0.425, -0.85)
for (x, y, z) in [(-3.85, 1.03, -2.2), (-3.1, 1.03, -1.55), (-3.85, 0.88, -0.85)]:
    pass
box3(st, "Cement", 1.55, 0.05, 0.24, -3.85, 1.025, -2.2)
box3(st, "Cement", 0.24, 0.05, 1.5, -3.1, 1.025, -1.55)
box3(st, "Cement", 1.65, 0.05, 0.24, -3.85, 0.875, -0.85)
for s in range(6):
    box3(st, "Stone", 0.42, 0.14, 1.17, -5.4 + s * 0.42, -0.08 - s * 0.16, -1.525)
box3(st, "Stone", 1.0, 0.14, 1.17, -2.98 - 0.0, -1.06, -1.525)               # landing
for (w_, d_, x, z) in [(2.3, 0.1, -4.2, -2.16), (2.3, 0.1, -4.2, -0.89)]:
    box3(st, "Cement", w_, 3.2, d_, x, -1.75, z)
box3(st, "Cement", 0.1, 3.2, 1.3, -2.45, -1.75, -1.525)
# black iron grille gate at the top of the stairs down (video)
for i in range(12):
    st.add("IronBlack", p_rod((-5.22, 0.98 + i * 0.1, 0.05), (-5.22, 0.98 + i * 0.1, 2.1), 0.009, segs=6))
for gy in (0.06, 1.0, 2.08):
    st.add("IronBlack", p_box(0.03, 1.2, 0.03), T(-5.22, 1.53, gy))
collide(-4.2, -1.525, 2.1, 1.17)

# ---- Zone 2: room 1 + washroom with roshan daan
wall(st, TW, H, 5.2, -0.5, H / 2, -3.9)
wall(st, TW, H, 5.2, 6.0, H / 2, -3.9)
wall(st, 1.1, H, TW, 0.05, H / 2, -6.5)
wall(st, 2.8, 0.8, TW, 2.0, 0.4, -6.5)
wall(st, 2.8, H - 2.2, TW, 2.0, 2.2 + (H - 2.2) / 2, -6.5)
wall(st, 1.45, H, TW, 4.12, H / 2, -6.5)
wall(st, 0.8, 1.6, TW, 5.25, 0.8, -6.5)
wall(st, 0.8, H - 2.35, TW, 5.25, 2.35 + (H - 2.35) / 2, -6.5)
wall(st, 0.35, H, TW, 5.82, H / 2, -6.5)
wall(st, TW, H, 3.8, 4.5, H / 2, -4.6)
wall(st, 0.25, H, TW, 4.62, H / 2, -2.7)
wall(st, 0.85, H - 2.1, TW, 5.18, 2.1 + (H - 2.1) / 2, -2.7)
wall(st, 0.4, H, TW, 5.8, H / 2, -2.7)
wall(st, 0.35, H, TW, -0.32, H / 2, -1.3)
wall(st, 1.0, H - 2.2, TW, 0.35, 2.2 + (H - 2.2) / 2, -1.3)
wall(st, 5.15, H, TW, 3.42, H / 2, -1.3)

# ---- Zone 3: room 2
wall(st, TW, H, 0.35, 6.0, H / 2, -1.12)
wall(st, TW, 1.6, 0.8, 6.0, 0.8, -0.55)
wall(st, TW, H - 2.35, 0.8, 6.0, 2.35 + (H - 2.35) / 2, -0.55)
wall(st, TW, H, 2.55, 6.0, H / 2, 1.12)
wall(st, 5.0, H, TW, 3.5, H / 2, 2.4)
wall(st, TW, H, 0.35, 1.0, H / 2, -1.12)
wall(st, TW, 0.8, 1.3, 1.0, 0.4, -0.3)
wall(st, TW, H - 2.2, 1.3, 1.0, 2.2 + (H - 2.2) / 2, -0.3)
wall(st, TW, H, 0.4, 1.0, H / 2, 0.55)
wall(st, TW, H - 2.2, 1.0, 1.0, 2.2 + (H - 2.2) / 2, 1.25)
wall(st, TW, H, 0.65, 1.0, H / 2, 2.08)

# ---- Zone 4: room 3
wall(st, TW, H, 4.1, 6.0, H / 2, 4.45)
wall(st, 5.0, H, TW, 3.5, H / 2, 6.5)
wall(st, TW, H, 0.35, 1.0, H / 2, 2.58)
wall(st, TW, H - 2.2, 1.0, 1.0, 2.2 + (H - 2.2) / 2, 3.25)
wall(st, TW, H, 0.8, 1.0, H / 2, 4.15)
wall(st, TW, 0.8, 1.2, 1.0, 0.4, 5.15)
wall(st, TW, H - 2.2, 1.2, 1.0, 2.2 + (H - 2.2) / 2, 5.15)
wall(st, TW, H, 0.75, 1.0, H / 2, 6.12)

# ---- Zone 5: open court, washing area, washroom with roof, stairs up
wall(st, TW, H, 7.8, -6.0, H / 2, 2.6)
box3(st, "TileBeige", 2.1, 0.22, 2.2, -4.95, 0.11, 2.6, col=True)
box3(st, "TileBeige", 0.45, 0.14, 0.55, -4.15, 0.07, 1.85)
box3(st, "TileBeige", 0.45, 0.08, 0.55, -3.85, 0.04, 1.85)
wall(st, 1.4, 1.05, 0.18, -5.3, 0.525, 1.5)
wall(st, 0.18, 1.05, 1.35, -3.8, 0.525, 3.02)
st.add("Chrome", p_rod((0, 0, 0), (0.0, -0.18, 0), 0.015, segs=8), M3(-5.86, 0.95, 2.9))   # wall tap
st.add("Chrome", p_rod((0, 0, 0), (0, 0, -0.08), 0.012, segs=8), M3(-5.86, 0.95, 2.9) @ T(0, -0.18, 0))
wall(st, 1.9, H, TW, -5.05, H / 2, 3.7)
wall(st, TW, H, 2.2, -3.5, H / 2, 5.4)
st.add("Cement", p_box(0.9, TW, H - 2.1), M3(-3.82, 2.1 + (H - 2.1) / 2, 4.02, math.pi / 4))
wall(st, 2.5, H, TW, -4.75, H / 2, 6.5)
box3(st, "WindowDark", 0.9, 0.14, 0.05, -4.75, 2.6, 6.39)                   # ventilator slit

for s in range(3):
    sh = (s + 1) * 0.22
    box3(st, "Concrete", 0.35, sh, 1.5, -3.3 + s * 0.35, sh / 2, 5.65, col=True)
wall(st, 0.22, 1.45, 0.7, -2.35, 0.725, 5.2)
for s in range(10):
    sy = 0.66 + (s + 1) * 0.23
    box3(st, "Concrete", 0.32, 0.23, 1.05, -2.1 + s * 0.32, sy - 0.115, 5.88, col=True)   # tread blocks
    box3(st, "Concrete", 0.32, 0.12, 1.05, -2.1 + s * 0.32, sy - 0.33, 5.88)               # sloped waist slab
for s in range(0, 10, 3):                                                        # brick piers under the flight
    sy = 0.66 + (s + 1) * 0.23 - 0.4
    box3(st, "BrickRaw", 0.24, sy, 0.24, -2.1 + s * 0.32, sy / 2, 6.25)
for (bx, bz, n) in [(-1.4, 5.6, 7), (-0.7, 5.75, 5)]:                           # loose brick stack under the stairs
    for k in range(n):
        st.add("BrickRaw", p_box(0.23, 0.115, 0.075), M3(bx + (k % 2) * 0.05, 0.08 + k * 0.076, bz, (k % 2) * 0.2))
collide(-1.05, 5.68, 1.0, 0.4)
st.add("SteelPipe", p_rod((-2.25, -5.32, 1.0), (0.95, -5.32, 3.2), 0.022, segs=10))
for s in range(0, 10, 3):
    sy = 0.66 + (s + 1) * 0.23
    st.add("SteelPipe", p_rod((0, 0, 0), (0, 0, 0.95), 0.018, segs=8), M3(-2.1 + s * 0.32, sy, 5.36))
wall(st, 4.5, H, TW, -1.25, H / 2, 6.5)

# raw brick courses laid on top of the court's boundary walls (unfinished, as in the video)
for (w_, d_, x, z) in [(TW, 7.8, -6.0, 2.6), (4.5, TW, -1.25, 6.5), (2.5, TW, -4.75, 6.5)]:
    box3(st, "BrickRaw", w_, 0.42, d_, x, H + 0.21, z)
# concrete chajja (sunshade) over the court-side doors
for (x, z, w_, d_) in [(0.7, 1.25, 0.6, 1.4), (0.7, 3.25, 0.6, 1.4), (0.35, -0.98, 1.4, 0.6)]:
    box3(st, "Concrete", w_, 0.09, d_, x, 2.42, z)
st.add("Concrete", p_box(1.3, 0.55, 0.09), M3(-3.6, 2.42, 3.82, math.pi / 4))
# clotheslines across the open court with drying sheets
for (a, b) in [((-5.88, 2.35, 0.2), (0.88, 2.35, 0.9)), ((-5.88, 2.25, 3.2), (0.88, 2.45, 3.0))]:
    st.add("Wire", p_rod((a[0], -a[2], a[1]), (b[0], -b[2], b[1]), 0.004, segs=4))
def sheet(x0, x1, zl, y, drop, m):
    bm = bmesh.new()
    nx, ny = 14, 8
    rows = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            t = i / nx
            x = x0 + (x1 - x0) * t
            sag = 0.03 * math.sin(t * math.pi)
            row.append(bm.verts.new((x, -(zl + 0.02 * math.sin(t * 9 + j)), y - sag - drop * j / ny)))
        rows.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    st.add(m, bm)
sheet(-3.6, -2.5, 0.53, 2.33, 1.0, "Cloth")
sheet(-1.4, -0.6, 0.73, 2.33, 0.85, "ClothStripe")
sheet(-4.6, -3.7, 3.13, 2.29, 0.9, "Cloth")
# washing area kit: stainless twin-tub washer (lid open), steel tub, buckets, wooden stool, tap pipe
B = M3(-5.35, 0.22, 2.35, math.pi / 2)
st.add("Stainless", p_box(0.75, 0.48, 0.85, 0.02, 2), B @ T(0, 0, 0.425))
st.add("Stainless", p_box(0.74, 0.47, 0.02), B @ T(0, 0.2, 1.05) @ Rx(-75))
st.add("PlasticGrey", p_box(0.7, 0.05, 0.08), B @ T(0, -0.25, 0.75))
collide(-5.35, 2.35, 0.5, 0.75)
bucket(st, -4.5, 0.22, 2.9, 0.33, 0.32, "SteelPipe")
bucket(st, -4.4, 0.22, 2.1, 0.15, 0.3, "BucketWhite")
bucket(st, -4.9, 0.22, 3.25, 0.18, 0.34, "BucketBlue")
box3(st, "WoodLight", 0.36, 0.04, 0.36, -4.0, 0.55, 0.4)
for (sx, sz) in [(-0.15, -0.15), (0.15, -0.15), (-0.15, 0.15), (0.15, 0.15)]:
    box3(st, "WoodLight", 0.04, 0.5, 0.04, -4.0 + sx, 0.3, 0.4 + sz)
collide(-4.0, 0.4, 0.4, 0.4)
st.add("SteelPipe", p_rod((-5.86, -2.9, 0.95), (-5.86, -2.9, 2.9), 0.015, segs=8))
for (x, y, z, r) in [(-5.86, 1.4, 1.0, math.pi / 2), (-5.86, 1.4, -1.0, math.pi / 2), (0.86, 1.3, 2.0, -math.pi / 2),
                     (-3.38, 1.3, 5.9, -math.pi / 2), (0.86, 1.3, -1.1, -math.pi / 2)]:
    switchboard(st, x, y, z, r)
for (bx, bz, m) in [(-0.2, 6.1, "BucketWhite"), (0.1, 6.15, "BucketBlue"), (-0.05, 5.9, "BucketWhite")]:
    bucket(st, bx, 0.045, bz, 0.13, 0.25, m)

# ================================================================ ROOFS (rooms only; the court stays open)
roof = Group("Roof")
ROOFED = [(-6.12, 6.12, -6.62, -1.3), (1.0, 6.12, -1.3, 6.62), (-6.12, -3.5, 3.7, 6.62)]
for (x0, x1, z0, z1) in ROOFED:
    box3(roof, "RoofTop", x1 - x0, 0.02, z1 - z0, (x0 + x1) / 2, H + ROOF_T + 0.01, (z0 + z1) / 2)
    box3(roof, "BrickCeiling", x1 - x0, ROOF_T, z1 - z0, (x0 + x1) / 2, H + ROOF_T / 2, (z0 + z1) / 2)
# roof parapets: outer perimeter + safety walls around the open court
PH, PT = 0.9, 0.18
y_p = H + ROOF_T + PH / 2
for (w_, d_, x, z) in [(12.24, PT, 0, -6.62 + PT / 2), (PT, 13.24, 6.12 - PT / 2, 0),
                       (5.1, PT, 3.57, 6.62 - PT / 2), (2.6, PT, -4.82, 6.62 - PT / 2),
                       (PT, 5.32, -6.12 + PT / 2, -3.96), (PT, 2.92, -6.12 + PT / 2, 5.16),
                       (7.1, PT, -2.55, -1.3 + PT / 2), (PT, 7.92, 1.0 + PT / 2, 2.66),
                       (2.6, PT, -4.82, 3.7 + PT / 2), (PT, 2.92, -3.5 - PT / 2, 5.16)]:
    box3(roof, "Cement", w_, PH, d_, x, y_p, z)
    box3(roof, "Cement", w_ + 0.06, 0.05, d_ + 0.06, x, H + ROOF_T + PH + 0.025, z)
# low coping on the court's own boundary walls (west and south) so they read as parapets too
for k in range(14):                                                               # jaali vents in the court parapets
    roof.add("WindowDark", p_cyl(0.09, 0.09, PT + 0.02, 3), M3(-5.6 + k * 0.48, y_p + 0.1, -1.3 + PT / 2) @ Rx(90) @ T(0, 0, -(PT + 0.02) / 2))
for k in range(15):
    roof.add("WindowDark", p_cyl(0.09, 0.09, PT + 0.02, 3), M3(1.0 + PT / 2, y_p + 0.1, -1.0 + k * 0.48) @ Rz(90) @ Rx(90) @ T(0, 0, -(PT + 0.02) / 2))
# concrete roof-slab edge projecting over the court (drip edge seen in the video)
box3(roof, "Concrete", 7.1, 0.16, 0.25, -2.55, H + 0.1, -1.3 - 0.12)
box3(roof, "Concrete", 0.25, 0.16, 7.8, 1.0 + 0.12, H + 0.1, 2.6)

# raw ceilings: junction boxes with red wires and fan hooks; black cable runs along the walls
cove = Group("Ceil")
for (cx, cz) in [(-3.25, -3.9), (2.0, -3.9), (3.5, 0.55), (3.5, 4.45), (5.25, -4.6), (-4.75, 5.1), (-2.0, -5.2)]:
    ceiling_box(cove, cx, cz)
for (a, b) in [((-5.85, 2.75, -6.3), (-0.65, 2.75, -6.3)), ((-0.65, 2.8, -6.3), (-0.65, 2.8, -1.45)),
               ((1.15, 2.8, -1.1), (5.85, 2.8, -1.1)), ((1.15, 2.8, 2.6), (5.85, 2.8, 2.6)), ((-0.35, 2.75, -1.45), (4.35, 2.75, -1.45))]:
    cove.add("Wire", p_rod((a[0], -a[2], a[1]), (b[0], -b[2], b[1]), 0.005, segs=4))
for (x, y, z, r) in [(-0.62, 1.3, -2.2, -math.pi / 2), (-5.88, 1.3, -5.0, math.pi / 2), (0.62, 1.3, -6.38, 0),
                     (5.88, 1.3, 0.0, math.pi / 2), (5.88, 1.3, 4.0, math.pi / 2), (4.38, 1.3, -3.5, -math.pi / 2)]:
    switchboard(cove, x, y, z, r)

# wall niches (almari recesses) with loft shelves as seen in the rooms
for (x, z, w_, rot) in [(4.23, -5.4, 1.0, -math.pi / 2), (5.73, 1.6, 1.1, math.pi / 2), (5.73, 5.6, 1.0, math.pi / 2)]:
    B = M3(x, 0.05, z, rot)
    cove.add("Cement", p_box(w_ + 0.3, 0.3, 0.08), B @ T(0, 0.0, 2.2))                 # loft shelf slab
    cove.add("Cement", p_box(0.12, 0.3, 2.15), B @ T(-w_ / 2 - 0.06, 0.0, 1.075))      # side fins
    cove.add("Cement", p_box(0.12, 0.3, 2.15), B @ T(w_ / 2 + 0.06, 0.0, 1.075))
    cove.add("Sack", p_box(0.5, 0.3, 0.3, 0.1, 3), B @ T(-0.2, 0.0, 2.4))
    cove.add("ClothStripe", p_box(0.45, 0.28, 0.2, 0.08, 3), B @ T(0.3, 0.0, 2.35))
    collide(x, z, w_ + 0.5, 0.3, rot)

# ================================================================ DOORS & WINDOWS
dw = Group("Openings")
def door(x, z, w, h, rot):
    """Dark red painted steel chokhat (frame) without a leaf, as on site."""
    base = M3(x, 0.05, z, rot)
    for (px, py, sx, sy) in [(-w / 2 + 0.035, h / 2, 0.07, h), (w / 2 - 0.035, h / 2, 0.07, h), (0, h - 0.035, w, 0.07)]:
        dw.add("RedSteel", p_box(sx, 0.12, sy, 0.004, 1), base @ T(px, 0, py))
        dw.add("RedSteel", p_box(sx * 0.4, 0.2, sy, 0.0, 1), base @ T(px, 0, py))
    for hz in (0.4, 1.1, 1.8):                                                  # hinge plates
        dw.add("IronBlack", p_box(0.02, 0.05, 0.1), base @ T(-w / 2 + 0.075, 0.06, hz))

def window(x, y, z, w, h, rot, bars=True, curtain=False, bricked=False):
    base = M3(x, y, z, rot)
    for (px, pz, sx, sz) in [(0, h / 2 - 0.03, w, 0.06), (0, -h / 2 + 0.03, w, 0.06),
                             (-w / 2 + 0.03, 0, 0.06, h), (w / 2 - 0.03, 0, 0.06, h)]:
        dw.add("RedSteel", p_box(sx, 0.1, sz, 0.004, 1), base @ T(px, 0, pz))
    if bricked:                                                                 # opening filled with raw bricks
        dw.add("BrickRaw", p_box(w - 0.1, 0.2, h - 0.1), base)
        return
    if bars:
        for i in range(1, 6):
            dw.add("IronBlack", p_rod((0, 0, 0), (0, 0, h - 0.1), 0.008, segs=6), base @ T(-w / 2 + i * w / 6, 0.02, -h / 2 + 0.05))
        for zz in (-h / 6, h / 6):
            dw.add("IronBlack", p_box(w - 0.08, 0.012, 0.02), base @ T(0, 0.02, zz))
    if curtain:
        dw.add("IronBlack", p_rod((-w / 2 - 0.2, 0, 0), (w / 2 + 0.2, 0, 0), 0.008, segs=6), base @ T(0, 0.22, h / 2 + 0.12))
        bm = bmesh.new()
        rows = []
        for j in range(13):
            row = []
            for i in range(9):
                t = i / 8
                row.append(bm.verts.new((w / 2 - 0.05 - t * 0.4, 0.22 + 0.04 * math.sin(t * 14), h / 2 + 0.1 - j / 12 * (h + 0.6))))
            rows.append(row)
        for j in range(12):
            for i in range(8):
                bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
        bm.transform(base)
        dw.add("ClothStripe", bm)

door(0.35, -1.3, 1.0, 2.2, 0)
door(5.18, -2.7, 0.85, 2.1, 0)
door(1.0, 1.25, 1.0, 2.2, -math.pi / 2)
door(1.0, 3.25, 1.0, 2.2, -math.pi / 2)
door(-3.82, 4.02, 0.85, 2.1, math.pi / 4)
window(2.0, 1.5, -6.5, 2.8, 1.4, 0, bars=False, curtain=True)
window(5.25, 1.98, -6.5, 0.8, 0.75, 0)
window(6.0, 1.98, -0.55, 0.8, 0.75, math.pi / 2)
window(1.0, 1.5, -0.3, 1.3, 1.4, math.pi / 2)
window(1.0, 1.5, 5.15, 1.2, 1.4, math.pi / 2, bricked=True)
# steel pipe railing outside room 1's window (video: window looks onto a railed ledge)
for ry in (0.95, 1.2):
    dw.add("SteelPipe", p_rod((0.6, 6.75, ry), (3.4, 6.75, ry), 0.018, segs=8))

# ================================================================ FURNITURE (Final Map preset)
fur = Group("Furniture")
plants = Group("Plants")

def bed(x, z, rot, duvet):
    B = M3(x, 0, z, rot)
    fur.add("Walnut", p_box(2.0, 2.15, 0.3, 0.02, 2), B @ T(0, 0, 0.2))
    for (lx, ly) in [(-0.9, -0.95), (0.9, -0.95), (-0.9, 0.95), (0.9, 0.95)]:
        fur.add("Walnut", p_cyl(0.03, 0.025, 0.06, 10), B @ T(lx, ly, 0))
    fur.add("Linen", p_box(1.86, 2.0, 0.24, 0.07, 4), B @ T(0, -0.04, 0.47))
    fur.add(duvet, p_box(1.96, 1.4, 0.08, 0.04, 3), B @ T(0, -0.36, 0.6) @ Rx(-1))
    fur.add(duvet, p_box(2.02, 0.22, 0.42, 0.04, 3), B @ T(0, -0.97, 0.42))       # duvet drape at foot
    fur.add("Headboard", p_box(2.1, 0.14, 1.15, 0.05, 4), B @ T(0, 1.04, 0.6))
    for ix in range(6):                                                         # tufted channels
        fur.add("Headboard", p_box(0.3, 0.05, 0.62, 0.03, 3), B @ T(-0.85 + ix * 0.34, 0.96, 0.82))
    for sx in (-0.46, 0.46):
        fur.add("Linen", p_box(0.56, 0.36, 0.17, 0.07, 4), B @ T(sx, 0.74, 0.69) @ Rx(-20))
        fur.add(duvet, p_box(0.46, 0.3, 0.15, 0.06, 4), B @ T(sx, 0.5, 0.7) @ Rx(-28))
    for nx in (-1.32, 1.32):
        fur.add("Walnut", p_box(0.48, 0.44, 0.46, 0.012, 2), B @ T(nx, 0.82, 0.25))
        fur.add("Walnut", p_box(0.42, 0.01, 0.16, 0.0), B @ T(nx, 0.6, 0.33))
        fur.add("Brass", p_box(0.08, 0.01, 0.012), B @ T(nx, 0.595, 0.33))
        fur.add("CeramicWhite", p_lathe([(0.05, 0), (0.07, 0.08), (0.065, 0.2), (0.025, 0.26), (0.012, 0.3)], 24), B @ T(nx, 0.82, 0.48))
        fur.add("LampShade", p_cyl(0.13, 0.1, 0.18, 28, caps=False), B @ T(nx, 0.82, 0.76))
    collide(x, z, 2.0, 2.15, rot, 0.0)
    for nx in (-1.32, 1.32):
        c, s = math.cos(rot), math.sin(rot)
        collide(x + nx * c + 0.82 * s, z - nx * s + 0.82 * c, 0.5, 0.5)

def console(x, z, rot):
    """Long walnut console / wardrobe with fluted front (Final Map 'wooden console cabinet')."""
    B = M3(x, 0, z, rot)
    fur.add("WoodWarm", p_box(2.3, 0.55, 0.72, 0.01, 2), B @ T(0, 0, 0.5))
    fur.add("Walnut", p_box(2.34, 0.58, 0.04, 0.006, 1), B @ T(0, 0, 0.88))
    for i in range(46):
        fur.add("WoodWarm", p_cyl(0.022, 0.022, 0.66, 8), B @ T(-1.125 + i * 0.05, -0.285, 0.17))
    for lx in (-1.05, 1.05):
        for ly in (-0.2, 0.2):
            fur.add("Walnut", p_rod((0, 0, 0), (0, 0, 0.14), 0.018, 0.022, 10), B @ T(lx, ly, 0))
    fur.add("Brass", p_box(0.02, 0.02, 0.3), B @ T(0, -0.3, 0.5))
    collide(x, z, 2.3, 0.55, rot)

def rug(x, z, rot, w=2.5, d=1.9):
    fur.add("Rug", p_box(w, d, 0.014, 0.005, 1), M3(x, 0.057, z, rot))

def washer(x, z, rot, y0):
    B = M3(x, y0, z, rot)
    fur.add("WasherBody", p_box(0.6, 0.6, 0.85, 0.025, 3), B @ T(0, 0, 0.425))
    fur.add("Chrome", p_lathe([(0.21, 0), (0.22, 0.02), (0.2, 0.05), (0.0, 0.055)], 32), B @ T(0, -0.3, 0.46) @ Rx(90))
    fur.add("WindowDark", p_cyl(0.16, 0.16, 0.03, 32), B @ T(0, -0.31, 0.46) @ Rx(90))
    fur.add("Screen", p_box(0.5, 0.01, 0.1), B @ T(0, -0.302, 0.77))
    fur.add("Chrome", p_cyl(0.025, 0.025, 0.02, 16), B @ T(0.15, -0.31, 0.77) @ Rx(90))
    collide(x, z, 0.62, 0.62, rot)

def wc(x, z, rot):
    B = M3(x, 0.05, z, rot)
    fur.add("Porcelain", p_box(0.4, 0.18, 0.42, 0.03, 3), B @ T(0, 0.22, 0.55))
    fur.add("Porcelain", p_box(0.42, 0.2, 0.04, 0.01, 2), B @ T(0, 0.22, 0.77))
    fur.add("Chrome", p_cyl(0.022, 0.022, 0.012, 16), B @ T(0, 0.22, 0.79))
    bowl = p_lathe([(0.12, 0), (0.14, 0.1), (0.2, 0.3), (0.21, 0.4)], 32)
    bowl.transform(Matrix.Diagonal((0.85, 1.15, 1, 1)))
    fur.add("Porcelain", bowl, B @ T(0, -0.08, 0))
    seat = p_cyl(0.2, 0.2, 0.03, 32)
    seat.transform(Matrix.Diagonal((0.88, 1.18, 1, 1)))
    fur.add("Porcelain", seat, B @ T(0, -0.08, 0.4))
    collide(x, z, 0.45, 0.65, rot)

def basin(x, z, rot):
    B = M3(x, 0.05, z, rot)
    fur.add("Walnut", p_box(0.6, 0.45, 0.5, 0.01, 2), B @ T(0, 0.02, 0.55))
    fur.add("Marble", p_box(0.64, 0.48, 0.04, 0.006, 1), B @ T(0, 0.02, 0.82))
    bowl = p_lathe([(0.08, 0), (0.17, 0.09), (0.19, 0.13), (0.18, 0.13), (0.07, 0.03)], 32, cap=True)
    bowl.transform(Matrix.Diagonal((1, 0.72, 1, 1)))
    fur.add("Porcelain", bowl, B @ T(0, 0.02, 0.84))
    fur.add("Chrome", p_rod((0, 0.2, 0.84), (0, 0.2, 1.06), 0.016, segs=10), B)
    fur.add("Chrome", p_rod((0, 0.2, 1.06), (0, 0.06, 1.06), 0.013, segs=10), B)
    fur.add("Glass", p_box(0.55, 0.01, 0.7), B @ T(0, 0.23, 1.5))             # mirror
    fur.add("Chrome", p_box(0.58, 0.012, 0.73), B @ T(0, 0.235, 1.5))
    collide(x, z, 0.6, 0.48, rot)

# hall: charpais (one leaning on the wall), plastic chairs, air cooler, steel trunk
charpai(fur, -3.4, 0.05, -5.3, 0)
collide(-3.4, -5.3, 1.95, 1.05)
charpai(fur, -1.25, 0.05, -4.6, math.pi / 2, weave="CharpaiBlue")
collide(-1.25, -4.6, 1.05, 1.95)
fur.add("ClothStripe", p_box(1.6, 0.85, 0.12, 0.05, 3), M3(-3.4, 0.56, -5.3))   # folded razai on the charpai
charpai(fur, -5.68, 0.045, 0.35, -math.pi / 2, tilt=-72)                        # leaning against the court wall
collide(-5.7, 0.35, 0.5, 2.0)
plastic_chair(fur, -2.2, -3.0, 0.4)
plastic_chair(fur, -1.0, -2.6, -0.6)
air_cooler(fur, -0.95, -6.0, math.pi)
fur.add("TrunkGreen", p_box(1.0, 0.55, 0.6, 0.02, 2), M3(-5.4, 0.35, -5.1, math.pi / 2))
collide(-5.4, -5.1, 0.6, 1.0)

# room 1: charpai under the window, cooler + pedestal fan, wooden ladder against the washroom wall
charpai(fur, 2.3, 0.05, -5.4, 0)
collide(2.3, -5.4, 1.95, 1.05)
air_cooler(fur, 0.6, -4.8, math.pi / 2)
pedestal_fan(fur, 1.3, -4.2, 2.6)
B = M3(4.25, 0.05, -3.2, math.pi / 2) @ Rx(-12)
for sx in (-0.22, 0.22):
    fur.add("WoodLight", p_box(0.05, 0.05, 2.3), B @ T(sx, 0, 1.15))
for r in range(6):
    fur.add("WoodLight", p_box(0.44, 0.035, 0.035), B @ T(0, 0, 0.3 + r * 0.35))
wc(5.62, -5.2, -math.pi / 2)
bucket(fur, 5.2, 0.055, -4.3, 0.13, 0.25, "BucketBlue")

# room 2: stacked charpais leaning on the wall
for k in range(2):
    charpai(fur, 3.6 + k * 0.28, 0.05, -0.85, 0, tilt=-80 + k * 6)
collide(3.75, -0.95, 2.0, 0.5)
plastic_chair(fur, 2.4, 1.5, 2.2)

# room 3: plastic chair, paint buckets, plaster tools
plastic_chair(fur, 2.1, 5.2, -1.2)
bucket(fur, 3.2, 0.05, 4.2, 0.16, 0.3, "BucketWhite")
bucket(fur, 3.6, 0.05, 4.45, 0.13, 0.25, "BucketWhite")

# open court: charpai in the sun, washroom WC
charpai(fur, -0.4, 0.045, -0.2, math.pi / 2, weave="Charpai")
collide(-0.4, -0.2, 1.05, 1.95)
wc(-5.6, 4.35, math.pi / 2)
bucket(fur, -5.3, 0.055, 5.6, 0.14, 0.28, "BucketBlue")

# ================================================================ NEIGHBOURHOOD
nb = Group("Neighbours")
rnd = random.Random(3)
for (x0, x1, z0, z1, top) in [
    (6.6, 16, -12, -2, 4.2), (6.6, 14, -1.6, 7, 1.0), (6.6, 18, 7.4, 16, 5.0),
    (-17, -6.6, -14, -4, -0.2), (-15, -6.6, -3.6, 5, 0.4), (-16, -6.6, 5.4, 15, 2.4),
    (-6, 6, 7.2, 18, 3.6), (-14, 14, -26, -15.5, 6.5), (-5.5, 5.5, -14, -9.6, 1.6),
]:
    y0 = -3.45
    box3(nb, "Facade2", x1 - x0, top - y0, z1 - z0, (x0 + x1) / 2, (top + y0) / 2, (z0 + z1) / 2)
    box3(nb, "StoneTrim", x1 - x0 + 0.1, 0.12, z1 - z0 + 0.1, (x0 + x1) / 2, top + 0.06, (z0 + z1) / 2)
    # punched windows on the faces looking at our house
    for level in range(int((top - y0) // 3.2)):
        wy = y0 + 1.6 + level * 3.2
        if wy > top - 0.8:
            break
        for t in [0.2, 0.5, 0.8]:
            if rnd.random() < 0.25:
                continue
            if abs(x0) > 6 and x0 > 0:
                box3(nb, "WindowDark", 0.06, 1.2, 1.0, x0 - 0.02, wy, z0 + (z1 - z0) * t)
            elif x1 < -6:
                box3(nb, "WindowDark", 0.06, 1.2, 1.0, x1 + 0.02, wy, z0 + (z1 - z0) * t)
            elif z0 > 6:
                box3(nb, "WindowDark", 1.0, 1.2, 0.06, x0 + (x1 - x0) * t, wy, z0 - 0.02)
            elif z1 < -6:
                box3(nb, "WindowDark", 1.0, 1.2, 0.06, x0 + (x1 - x0) * t, wy, z1 + 0.02)

for x in [-5.0 + i * 1.0 for i in range(11)]:
    nb.add("RedSteel", p_rod((x, 9.7, 1.6), (x, 9.7, 2.6), 0.02, segs=6))
for ry in (2.0, 2.3, 2.6):
    nb.add("RedSteel", p_rod((-5.4, 9.7, ry), (5.4, 9.7, ry), 0.022, segs=6))
box3(nb, "Facade2", 11.0, 3.6, 2.6, 0, 3.4, -12.9)
box3(nb, "BucketBlue", 2.4, 0.9, 0.02, -1.5, 2.1, -9.75)
box3(nb, "Cloth", 1.8, 1.0, 0.02, 2.2, 2.1, -9.76)

for g in (st, roof, cove, dw, fur, plants, nb):
    g.flush()

COL.sort()
with open(COLLIDERS, "w") as f:
    json.dump({"walk": [-5.88, 5.88, -6.38, 6.38], "boxes": COL}, f)

bpy.ops.export_scene.gltf(filepath=os.path.abspath(OUT), export_format="GLB",
                          export_yup=True, export_apply=True)
print("EXPORTED", os.path.abspath(OUT), len(bpy.data.objects), "objects", len(COL), "colliders")
