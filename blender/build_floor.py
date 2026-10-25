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
OUT = os.path.join(HERE, "..", "floor.glb")
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
    ("Skirting", (0.70, 0.55, 0.40), 0.5),
    ("WashTile", (0.85, 0.85, 0.83), 0.2),
    ("SteelPipe", (0.25, 0.25, 0.26), 0.4, 0.8),
    ("IronBlack", (0.03, 0.03, 0.03), 0.5, 0.6),
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

def wall(g, w, h, d, x, y, z, m="Cream", col=True):
    box3(g, m, w, h, d, x, y, z, col=col, bevel=0.008)                       # slightly rounded arrises catch the light
    if abs(h - H) < 1e-6 and max(w, d) > 0.3:                                # tile skirting on full walls (site video)
        if w >= d:
            for s in (-1, 1):
                box3(g, "Skirting", w, 0.1, 0.012, x, 0.1, z + s * (d / 2 + 0.006))
        else:
            for s in (-1, 1):
                box3(g, "Skirting", 0.012, 0.1, d, x + s * (w / 2 + 0.006), 0.1, z)

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

def loft_cabinet(g, x0, x1, z0, z1, y0, y1, face):
    """Wall-hung loft cabinet with shutter doors on one face ('-x', '+x', '-z', '+z')."""
    cx, cz, cy = (x0 + x1) / 2, (z0 + z1) / 2, (y0 + y1) / 2
    box3(g, "WoodWarm", x1 - x0, y1 - y0, z1 - z0, cx, cy, cz)
    along_x = face in ("-z", "+z")
    length = (x1 - x0) if along_x else (z1 - z0)
    n = max(2, round(length / 0.6))
    pw = length / n
    for i in range(n):
        c = (x0 if along_x else z0) + pw * (i + 0.5)
        hx = c + (0.2 * pw if i % 2 == 0 else -0.2 * pw)
        if face == "-x":
            box3(g, "Walnut", 0.02, y1 - y0 - 0.04, pw - 0.012, x0 - 0.01, cy, c)
            box3(g, "Brass", 0.025, 0.12, 0.02, x0 - 0.03, y0 + 0.12, c + (0.38 * pw if i % 2 == 0 else -0.38 * pw))
        elif face == "+x":
            box3(g, "Walnut", 0.02, y1 - y0 - 0.04, pw - 0.012, x1 + 0.01, cy, c)
            box3(g, "Brass", 0.025, 0.12, 0.02, x1 + 0.03, y0 + 0.12, c + (0.38 * pw if i % 2 == 0 else -0.38 * pw))
        elif face == "-z":
            box3(g, "Walnut", pw - 0.012, y1 - y0 - 0.04, 0.02, c, cy, z0 - 0.01)
            box3(g, "Brass", 0.02, 0.12, 0.025, c + (0.38 * pw if i % 2 == 0 else -0.38 * pw), y0 + 0.12, z0 - 0.03)
        else:
            box3(g, "Walnut", pw - 0.012, y1 - y0 - 0.04, 0.02, c, cy, z1 + 0.01)
            box3(g, "Brass", 0.02, 0.12, 0.025, c + (0.38 * pw if i % 2 == 0 else -0.38 * pw), y0 + 0.12, z1 + 0.03)

def builtin_cabinet(g, xf, z0, z1, y0, y1, depth, face, doors):
    """Cabinet set flush into a wall at x = xf; face '+x' or '-x' is the side the doors open to."""
    sgn = 1 if face == "+x" else -1
    box3(g, "WoodWarm", depth, y1 - y0, z1 - z0, xf - sgn * depth / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    dw_ = (z1 - z0) / doors
    for i in range(doors):
        zc = z0 + dw_ * (i + 0.5)
        box3(g, "Walnut", 0.025, y1 - y0 - 0.03, dw_ - 0.012, xf + sgn * 0.012, (y0 + y1) / 2, zc)
        kz = zc + (0.3 * dw_ if i % 2 == 0 else -0.3 * dw_)
        g.add("Brass", p_lathe([(0.0, 0), (0.018, 0.005), (0.022, 0.02), (0.012, 0.035), (0.0, 0.04)], 16),
              M3(xf + sgn * 0.025, (y0 + y1) / 2, kz) @ Ry(90 * sgn))

def builtin_cabinet_z(g, zf, x0, x1, y0, y1, depth, face, doors):
    """Like builtin_cabinet, for walls running along x; face '+z' or '-z'."""
    sgn = 1 if face == "+z" else -1
    box3(g, "WoodWarm", x1 - x0, y1 - y0, depth, (x0 + x1) / 2, (y0 + y1) / 2, zf - sgn * depth / 2)
    dw_ = (x1 - x0) / doors
    for i in range(doors):
        xc = x0 + dw_ * (i + 0.5)
        box3(g, "Walnut", dw_ - 0.012, y1 - y0 - 0.03, 0.025, xc, (y0 + y1) / 2, zf + sgn * 0.012)
        kx = xc + (0.3 * dw_ if i % 2 == 0 else -0.3 * dw_)
        g.add("Brass", p_lathe([(0.0, 0), (0.018, 0.005), (0.022, 0.02), (0.012, 0.035), (0.0, 0.04)], 16),
              M3(kx, (y0 + y1) / 2, zf + sgn * 0.025) @ Rx(-90 * sgn))

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
WELL = (-5.88, -4.62, -4.08, -0.97)   # stair well inside the stair block (hall west corner)

# 12.35 x 13.35 floor slab with stone fascia, ground floor below, street
slab(st, "StoneTrim", (-6.175, 6.175, -6.675, 6.675), -0.38, -0.06, WELL)
box3(st, "Facade", 12.2, 3.0, 13.2, 0, -1.9, 0)
box3(st, "StoneTrim", 12.5, 0.12, 13.5, 0, -0.42, 0)
box3(st, "Ground", 80, 0.1, 80, 0, -3.45, 0)

# zone floors (top at y = 0.05)
slab(st, "TileBeige", (-6.0, -0.5, -6.5, -1.3), -0.06, 0.05, WELL)          # hall
slab(st, "TileBeige", (-0.5, 4.5, -6.5, -1.3), -0.06, 0.05)                 # room 1
slab(st, "Marble", (4.5, 6.0, -6.5, -1.3), -0.06, 0.055)                    # room 1 washroom
slab(st, "TileBeige", (1.0, 6.0, -1.3, 2.4), -0.06, 0.05)                   # room 2
slab(st, "TileBeige", (1.0, 6.0, 2.4, 6.5), -0.06, 0.05)                    # room 3
slab(st, "Marble", (-6.0, 1.0, -1.3, 6.5), -0.06, 0.045, WELL)              # open court
slab(st, "Marble", (-6.0, -3.5, 3.7, 6.5), -0.06, 0.055)                    # bottom-left washroom

# ---- Zone 1: hall
wall(st, TW, H, 5.2, -6.0, H / 2, -3.9)
wall(st, 1.2, H, TW, -5.4, H / 2, -6.5)
wall(st, 0.8, H, TW, -0.9, H / 2, -6.5)
wall(st, 3.5, 0.85, 0.22, -3.05, 0.425, -6.5)                               # hall outer opening parapet
box3(st, "StoneTrim", 3.6, 0.06, 0.3, -3.05, 0.88, -6.5)
for ry in (1.05, 1.28, 1.5):                                                 # steel pipe railing (site video)
    st.add("SteelPipe", p_rod((-4.8, 6.5, ry), (-1.3, 6.5, ry), 0.022, segs=10))
for px in (-4.75, -3.9, -3.05, -2.2, -1.35):
    st.add("SteelPipe", p_rod((px, 6.5, 0.91), (px, 6.5, 1.52), 0.02, segs=10))
wall(st, 3.5, 0.35, TW, -3.05, H - 0.175, -6.5, col=False)                  # beam over the opening

# ---- stair block (site photos): a closed box in the hall's west corner, x[-6,-4.5] z[-4.2,-0.85].
# Its hall face has a black grille door with a fixed grille transom; the stairs drop straight in, turn
# under the cabet. Right of the door: waist-high wall with a shelf top, open cabet niche above to the ceiling,
# a pillar closing the niche on the north side.
BX0, BX1, BZ0, BZ1 = -6.0, -4.5, -4.2, -0.85
DZ0, DZ1 = -2.05, -1.15                                                       # door opening (z)
NZ0, NZ1 = -3.8, -2.35                                                        # niche opening (z)
SILL = 1.15
wall(st, 1.5, H, 0.2, -5.25, H / 2, BZ0)                                      # north wall
wall(st, 1.62, H, TW, -5.31, H / 2, BZ1)                                      # south wall (court side)
wall(st, TW, H, BZ1 - DZ1, BX1, H / 2, (BZ1 + DZ1) / 2)                       # pier south of the door
wall(st, TW, H - 2.6, DZ1 - DZ0, BX1, 2.6 + (H - 2.6) / 2, (DZ0 + DZ1) / 2)    # wall above the transom
wall(st, TW, H, DZ0 - NZ1, BX1, H / 2, (NZ1 + DZ0) / 2)                       # pier between door and niche
wall(st, TW, 2.0, NZ1 - NZ0, BX1, 1.0, (NZ0 + NZ1) / 2)                       # solid wall where the niche was
wall(st, TW, H - 2.84, NZ1 - NZ0, BX1, 2.84 + (H - 2.84) / 2, (NZ0 + NZ1) / 2, col=False)
builtin_cabinet(st, BX1 + TW / 2, NZ0, NZ1, 2.0, 2.84, 0.7, "+x", 2)            # two-door cabet above the stairs
wall(st, TW, H, NZ0 - (BZ0 + 0.1), BX1, H / 2, (NZ0 + BZ0 + 0.1) / 2)         # pillar north of the niche
box3(st, "Cream", 1.38, 0.1, NZ1 - (BZ0 + 0.1), -5.31, SILL - 0.05, (BZ0 + 0.1 + NZ1) / 2)  # niche floor = stair ceiling
collide((BX0 + BX1) / 2, (BZ0 + BZ1) / 2, BX1 - BX0, BZ1 - BZ0)

# black steel door frame, grille gate (slightly open) and fixed grille transom
dz_mid, dw_ = (DZ0 + DZ1) / 2, DZ1 - DZ0
for (pz, py, sz, sy) in [(DZ0 + 0.025, 1.3, 0.05, 2.6), (DZ1 - 0.025, 1.3, 0.05, 2.6), (dz_mid, 2.6 - 0.025, dw_, 0.05),
                         (dz_mid, 2.1, dw_, 0.05)]:
    box3(st, "IronBlack", 0.1, sy, sz, BX1, py + 0.05, pz)
for i in range(1, 10):                                                        # transom: flat vertical bars
    box3(st, "IronBlack", 0.03, 0.46, 0.012, BX1, 2.36, DZ0 + i * dw_ / 10)
GATE = M3(BX1 - 0.02, 0.05, DZ1 - 0.05, -0.35)                                # hinged on the south jamb
gw, gh = dw_ - 0.1, 2.0
st.add("IronBlack", p_box(0.03, 0.03, gh), GATE @ T(0, 0, gh / 2))
st.add("IronBlack", p_box(0.03, 0.03, gh), GATE @ T(0, gw, gh / 2))
for gz in (0.05, 1.0, 1.05, gh - 0.02):
    st.add("IronBlack", p_box(0.03, gw, 0.03), GATE @ T(0, gw / 2, gz))
for i in range(1, 17):
    st.add("IronBlack", p_box(0.012, 0.012, gh), GATE @ T(0, i * gw / 17, gh / 2))
st.add("IronBlack", p_box(0.04, 0.06, 0.08), GATE @ T(-0.03, gw - 0.05, 1.05))   # latch

# the stairs: 3 steps west from the door, a landing, then a flight north under the cabet
STONE_BOTTOM = -3.0
def step(x0, x1, z0, z1, ytop):
    box3(st, "Stone", x1 - x0, ytop - STONE_BOTTOM, z1 - z0, (x0 + x1) / 2, (ytop + STONE_BOTTOM) / 2, (z0 + z1) / 2)
for k in range(3):
    step(-4.62 - 0.26 * (k + 1), -4.62 - 0.26 * k, DZ0 - 0.25, BZ1 - 0.12, -0.12 - 0.17 * k)
step(-5.88, -5.4, DZ0 - 0.25, BZ1 - 0.12, -0.63)                              # landing
for k in range(7):
    step(-5.88, -4.62, DZ0 - 0.25 - 0.25 * (k + 1), DZ0 - 0.25 - 0.25 * k, -0.8 - 0.17 * k)
for (w_, d_, x, z) in [(1.3, 0.06, -5.25, BZ0 + 0.13), (1.3, 0.06, -5.25, BZ1 - 0.09), (0.06, 3.2, -4.59, (BZ0 + BZ1) / 2),
                       (0.06, 3.2, -5.91, (BZ0 + BZ1) / 2)]:
    box3(st, "Cream", w_, 3.1, d_, x, -1.6, z)                                # shaft walls below the floor

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
wall(st, TW, 2.05, 3.8, 4.5, 1.025, -4.6)                                    # partition below the loft
wall(st, TW, H - 2.84, 3.8, 4.5, 2.84 + (H - 2.84) / 2, -4.6, col=False)
wall(st, TW, 0.79, 0.12, 4.5, 2.445, -2.76, col=False)                         # end stub beside the door wall
builtin_cabinet(st, 4.5 - TW / 2, -6.38, -2.82, 2.05, 2.84, 0.62 + TW, "-x", 6)
box3(st, "Cream", 0.62, 0.06, 3.56, 4.69 + 0.12, 2.02, -4.6)                    # loft floor slab over the washroom
wall(st, 0.25, 2.15, TW, 4.62, 1.075, -2.7)
wall(st, 0.85, 0.05, TW, 5.18, 2.125, -2.7)
wall(st, 0.4, 2.15, TW, 5.8, 1.075, -2.7)
wall(st, 1.5, H - 2.84, TW, 5.25, 2.84 + (H - 2.84) / 2, -2.7, col=False)
builtin_cabinet_z(st, -2.7 + TW / 2, 4.38, 5.88, 2.15, 2.84, 0.62 + TW, "+z", 2)  # cabinets above the washroom door
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
box3(st, "WashTile", 2.1, 0.02, 2.2, -4.95, 0.055, 2.6)                       # washing area: tiles only
box3(st, "Chrome", 0.12, 0.004, 0.12, -4.4, 0.066, 2.0)                       # floor drain
box3(st, "WashTile", 2.2, 0.12, 0.1, -4.95, 0.105, 1.5)                        # border kerb (front)
box3(st, "WashTile", 0.1, 0.12, 2.18, -3.9, 0.105, 2.59)                       # border kerb (side)
B = M3(-5.62, 0.065, 3.3, -math.pi / 2)                                        # pedestal wash basin
st.add("Porcelain", p_lathe([(0.11, 0), (0.09, 0.08), (0.07, 0.4), (0.09, 0.66), (0.0, 0.7)], 24), B)
bowl = p_lathe([(0.06, 0), (0.2, 0.1), (0.24, 0.16), (0.23, 0.17), (0.07, 0.04)], 32, cap=True)
bowl.transform(Matrix.Diagonal((1, 0.75, 1, 1)))
st.add("Porcelain", bowl, B @ T(0, 0.02, 0.66))
st.add("Chrome", p_rod((0, 0.17, 0.83), (0, 0.17, 1.0), 0.015, segs=10), B)
st.add("Chrome", p_rod((0, 0.17, 1.0), (0, 0.04, 0.97), 0.012, segs=10), B)
collide(-5.62, 3.3, 0.5, 0.42)
st.add("Chrome", p_rod((0, 0, 0), (0.0, -0.18, 0), 0.015, segs=8), M3(-5.86, 0.95, 2.9))   # wall tap
st.add("Chrome", p_rod((0, 0, 0), (0, 0, -0.08), 0.012, segs=8), M3(-5.86, 0.95, 2.9) @ T(0, -0.18, 0))
wall(st, 1.6, H, TW, -5.2, H / 2, 3.7)                                        # front wall, door at the stair end x[-4.4,-3.62]
wall(st, 0.78, H - 2.1, TW, -4.01, 2.1 + (H - 2.1) / 2, 3.7)
wall(st, TW, H, 2.8, -3.5, H / 2, 5.1)
wall(st, 2.5, H, TW, -4.75, H / 2, 6.5)
box3(st, "WindowDark", 0.9, 0.14, 0.05, -4.75, 2.6, 6.39)                   # ventilator slit

LAND = 1.19                                                                   # landing height
for s in range(6):                                                             # first flight, rising toward the back wall
    sy = (s + 1) * 0.17
    box3(st, "Stone", 1.1, sy, 0.22, -2.83, sy / 2, 4.08 + s * 0.22, col=True)
box3(st, "Stone", 1.13, LAND, 1.08, -2.815, LAND / 2, 5.84, col=True)              # landing in the corner
for s in range(10):                                                            # second flight along the back wall
    sy = LAND + (s + 1) * 0.2
    box3(st, "Stone", 0.32, 0.2, 1.05, -2.1 + s * 0.32, sy - 0.1, 5.88, col=True)
st.add("Chrome", p_rod((-2.25, -5.32, LAND + 0.95), (0.95, -5.32, 3.2 + 0.95), 0.02, segs=10))
for s in range(0, 10, 3):
    sy = LAND + (s + 1) * 0.2
    st.add("Chrome", p_rod((0, 0, 0), (0, 0, 0.95), 0.012, segs=8), M3(-2.1 + s * 0.32, sy, 5.36))
wall(st, 4.5, H, TW, -1.25, H / 2, 6.5)

# ---- structure seen in the site video
# stairs up: sloped waist slab under the treads + brick piers carrying the flight
for s in range(10):
    sy = LAND + (s + 1) * 0.2
    box3(st, "Stone", 0.32, 0.12, 1.05, -2.1 + s * 0.32, sy - 0.32, 5.88)
for s in range(0, 10, 3):
    sy = LAND + (s + 1) * 0.2 - 0.38
    box3(st, "Cream", 0.24, sy, 0.24, -2.1 + s * 0.32, sy / 2, 6.25)
# court boundary walls rise a few courses above the roof line
for (w_, d_, x, z) in [(TW, 7.8, -6.0, 2.6), (4.5, TW, -1.25, 6.5), (2.5, TW, -4.75, 6.5)]:
    box3(st, "Cream", w_, 0.42, d_, x, H + 0.21, z)
    box3(st, "StoneTrim", (w_ + 0.06) if w_ > d_ else 0.3, 0.05, (d_ + 0.06) if d_ > w_ else 0.3, x, H + 0.445, z)
# concrete chajja (sunshade) over the court-side doors
for (x, z, w_, d_) in [(0.7, 1.25, 0.6, 1.4), (0.7, 3.25, 0.6, 1.4), (0.35, -0.98, 1.4, 0.6)]:
    box3(st, "StoneTrim", w_, 0.09, d_, x, 2.42, z)
box3(st, "StoneTrim", 3.0, 0.12, 0.75, -4.6, 2.45, 3.7 - 0.375)                     # chajja (shade) across the washroom front

# ================================================================ ROOFS (rooms only; the court stays open)
roof = Group("Roof")
ROOFED = [(-6.12, 6.12, -6.62, -1.3), (1.0, 6.12, -1.3, 6.62), (-6.12, -3.5, 3.7, 6.62)]
for (x0, x1, z0, z1) in ROOFED:
    box3(roof, "RoofTop", x1 - x0, 0.02, z1 - z0, (x0 + x1) / 2, H + ROOF_T + 0.01, (z0 + z1) / 2)
    box3(roof, "Ceiling", x1 - x0, ROOF_T, z1 - z0, (x0 + x1) / 2, H + ROOF_T / 2, (z0 + z1) / 2)
# roof parapets: outer perimeter + safety walls around the open court
PH, PT = 0.9, 0.18
y_p = H + ROOF_T + PH / 2
for (w_, d_, x, z) in [(12.24, PT, 0, -6.62 + PT / 2), (PT, 13.24, 6.12 - PT / 2, 0),
                       (5.1, PT, 3.57, 6.62 - PT / 2), (2.6, PT, -4.82, 6.62 - PT / 2),
                       (PT, 5.32, -6.12 + PT / 2, -3.96), (PT, 2.92, -6.12 + PT / 2, 5.16),
                       (7.1, PT, -2.55, -1.3 + PT / 2), (PT, 6.55, 1.0 + PT / 2, 1.975),
                       (2.6, PT, -4.82, 3.7 + PT / 2), (PT, 2.92, -3.5 - PT / 2, 5.16)]:
    box3(roof, "Cream", w_, PH, d_, x, y_p, z)
    box3(roof, "StoneTrim", w_ + 0.06, 0.05, d_ + 0.06, x, H + ROOF_T + PH + 0.025, z)
# low coping on the court's own boundary walls (west and south) so they read as parapets too
box3(roof, "StoneTrim", 7.1, 0.16, 0.25, -2.55, H + 0.1, -1.3 - 0.12)          # slab edge over the court (site video)
box3(roof, "StoneTrim", 0.25, 0.16, 7.8, 1.0 + 0.12, H + 0.1, 2.6)
for k in range(14):                                                               # jaali vents in the court parapets
    roof.add("WindowDark", p_cyl(0.09, 0.09, PT + 0.02, 3), M3(-5.6 + k * 0.48, y_p + 0.1, -1.3 + PT / 2) @ Rx(90) @ T(0, 0, -(PT + 0.02) / 2))
for k in range(13):
    roof.add("WindowDark", p_cyl(0.09, 0.09, PT + 0.02, 3), M3(1.0 + PT / 2, y_p + 0.1, -1.0 + k * 0.48) @ Rz(90) @ Rx(90) @ T(0, 0, -(PT + 0.02) / 2))

# modern cove ceilings + LED strips under each roofed room
cove = Group("Ceil")
for (cx, cz, w_, d_) in [(-3.25, -3.9, 5.26, 4.96), (2.0, -3.9, 4.76, 4.96), (5.25, -3.9, 1.26, 4.96),
                         (3.5, 0.55, 4.76, 3.46), (3.5, 4.45, 4.76, 3.86)]:
    bw = 0.42 if w_ > 2 else 0.0
    if bw:
        for (bx, bz, bwid, bdep) in [(0, -d_ / 2 + bw / 2, w_, bw), (0, d_ / 2 - bw / 2, w_, bw),
                                     (-w_ / 2 + bw / 2, 0, bw, d_ - 2 * bw), (w_ / 2 - bw / 2, 0, bw, d_ - 2 * bw)]:
            box3(cove, "Ceiling", bwid, 0.16, bdep, cx + bx, H - 0.08, cz + bz)
        for (bx, bz, bwid, bdep) in [(0, -d_ / 2 + bw + 0.02, w_ - 2 * bw, 0.03), (0, d_ / 2 - bw - 0.02, w_ - 2 * bw, 0.03),
                                     (-w_ / 2 + bw + 0.02, 0, 0.03, d_ - 2 * bw), (w_ / 2 - bw - 0.02, 0, 0.03, d_ - 2 * bw)]:
            box3(cove, "CoveLED", bwid, 0.02, bdep, cx + bx, H - 0.155, cz + bz)

# ================================================================ DOORS & WINDOWS
dw = Group("Openings")
DOOR_OPEN = 0.42 * math.pi * 0.48
def door(x, z, w, h, rot):
    base = M3(x, 0, z, rot)
    for (px, py, sx, sy) in [(-w / 2 + 0.035, h / 2, 0.07, h), (w / 2 - 0.035, h / 2, 0.07, h), (0, h - 0.035, w, 0.07)]:
        dw.add("Teak", p_box(sx, 0.26, sy, 0.006, 1), base @ T(px, 0, py))
    lw, lh = w - 0.12, h - 0.08
    piv = base @ T(-w / 2 + 0.06, 0, 0) @ Rz(-math.degrees(DOOR_OPEN))
    dw.add("Teak", p_box(lw, 0.045, lh, 0.006, 1), piv @ T(lw / 2, 0, lh / 2 + 0.01))
    for pz in (0.72, 0.27):                                                  # raised panels
        dw.add("Teak", p_box(lw * 0.7, 0.06, lh * 0.34, 0.012, 2), piv @ T(lw / 2, 0, lh * pz))
    for side in (-1, 1):
        dw.add("Brass", p_box(0.025, 0.04, 0.16, 0.004, 1), piv @ T(lw - 0.09, side * 0.045, lh * 0.48))
        dw.add("Brass", p_rod((0, 0, 0), (-0.11, 0, 0), 0.009, segs=8), piv @ T(lw - 0.09, side * 0.07, lh * 0.5))

def window(x, y, z, w, h, rot):
    base = M3(x, y, z, rot)
    for (px, pz, sx, sz) in [(0, h / 2 - 0.03, w, 0.06), (0, -h / 2 + 0.03, w, 0.06),
                             (-w / 2 + 0.03, 0, 0.06, h), (w / 2 - 0.03, 0, 0.06, h), (0, 0, 0.045, h)]:
        dw.add("Trim", p_box(sx, 0.12, sz, 0.004, 1), base @ T(px, 0, pz))
    for side, yoff in ((-1, -0.02), (1, 0.02)):                              # two sliding sashes
        sw = w / 2 - 0.04
        cx = side * (w / 4 - 0.01)
        for (px, pz, sx, sz) in [(cx, h / 2 - 0.08, sw, 0.04), (cx, -h / 2 + 0.08, sw, 0.04),
                                 (cx - sw / 2 + 0.02, 0, 0.04, h - 0.16), (cx + sw / 2 - 0.02, 0, 0.04, h - 0.16)]:
            dw.add("Trim", p_box(sx, 0.035, sz), base @ T(px, yoff, pz))
        dw.add("Glass", p_box(sw - 0.06, 0.008, h - 0.2), base @ T(cx, yoff, 0))
    dw.add("StoneTrim", p_box(w + 0.1, 0.3, 0.04, 0.005, 1), base @ T(0, 0, -h / 2 - 0.02))  # sill

door(0.35, -1.3, 1.0, 2.2, 0)
door(5.18, -2.7, 0.85, 2.1, 0)
door(1.0, 1.25, 1.0, 2.2, -math.pi / 2)
door(1.0, 3.25, 1.0, 2.2, -math.pi / 2)
door(-4.01, 3.7, 0.78, 2.1, math.pi)
window(2.0, 1.5, -6.5, 2.8, 1.4, 0)
window(5.25, 1.98, -6.5, 0.8, 0.75, 0)
window(6.0, 1.98, -0.55, 0.8, 0.75, math.pi / 2)
window(1.0, 1.5, -0.3, 1.3, 1.4, math.pi / 2)
window(1.0, 1.5, 5.15, 1.2, 1.4, math.pi / 2)

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

# hall
sofa(fur, M3(-2.5, 0.05, -5.45, math.pi))
collide(-2.5, -5.45, 2.3, 0.95)
armchair(fur, M3(-3.8, 0.05, -4.25, math.pi / 2 + math.pi))           # clear of the stair block face (x -4.38)
collide(-3.8, -4.25, 0.75, 0.75)
round_table(fur, M3(-2.5, 0.05, -4.2), 0.48, 0.42, "CeramicWhite")
collide(-2.5, -4.2, 0.9, 0.9)
pot(fur, M3(-2.5, 0.47, -4.2), 0.06, 0.08, 0.12, "Terracotta")
ivy(plants, M3(-2.5, 0.58, -4.2), seed=4)
rug(-2.5, -4.25, 0)
pot(fur, M3(-5.3, 0.05, -5.8), 0.17, 0.22, 0.45, "Terracotta")
tree(plants, M3(-5.3, 0.45, -5.8), 1.85, 0.44, 2600, seed=31)
collide(-5.3, -5.8, 0.5, 0.5)

# room 1
bed(3.1, -4.1, -math.pi / 2, "DuvetSand")
rug(2.6, -4.1, math.pi / 2)
console(0.1, -4.2, math.pi / 2)
vase(fur, M3(0.1, 0.94, -4.9), 0.3, 0.08, "Ceramic")
eucalyptus(plants, M3(0.1, 1.22, -4.9), 4, 0.55, seed=12)
fur.add("BookCover", p_box(0.3, 0.22, 0.05, 0.004, 1), M3(0.1, 0.96, -3.6, 0.2))
wc(5.62, -5.2, -math.pi / 2)
basin(5.62, -3.5, -math.pi / 2)


# room 2
bed(3.7, 0.45, -math.pi / 2, "DuvetSage")
rug(3.4, 0.45, math.pi / 2)
console(5.5, 0.55, -math.pi / 2)

# room 3
bed(3.4, 5.0, math.pi, "DuvetGrey")
rug(3.4, 4.6, 0)
console(5.5, 4.45, -math.pi / 2)

# open court
washer(-5.5, 2.25, math.pi / 2, 0.065)                                        # front faces the court, back to the wall
pot(fur, M3(0.35, 0.045, 4.85), 0.17, 0.22, 0.45, "Terracotta")
tree(plants, M3(0.35, 0.45, 4.85), 1.75, 0.42, 2400, seed=21)
collide(0.35, 4.85, 0.5, 0.5)
for (px, pz, sd) in [(-5.45, -0.35, 41), (0.4, -0.72, 43)]:
    pot(fur, M3(px, 0.045, pz), 0.15, 0.2, 0.42, "Terracotta")
    tree(plants, M3(px, 0.42, pz), 1.7, 0.34, 2200, seed=sd)
    collide(px, pz, 0.45, 0.45)
wc(-4.3, 6.05, math.pi)
basin(-5.62, 4.6, math.pi / 2)

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

for g in (st, roof, cove, dw, fur, plants, nb):
    g.flush()

# ceiling fans: own objects so Three.js can spin them about their hub
for i, (fx, fz) in enumerate([(-3.25, -3.9), (2.0, -3.9), (3.5, 0.55), (3.5, 4.45)]):
    bm = bmesh.new()
    def merge(tmp, M=Matrix()):
        tmp.transform(M)
        me = bpy.data.meshes.new("t"); tmp.to_mesh(me); tmp.free(); bm.from_mesh(me); bpy.data.meshes.remove(me)
    merge(p_cyl(0.012, 0.012, 0.32, 8), T(0, 0, 0.0))
    merge(p_lathe([(0.03, -0.05), (0.13, -0.02), (0.14, 0.03), (0.06, 0.07), (0.02, 0.08)], 28))
    for b in range(3):
        blade = p_box(0.6, 0.12, 0.012, 0.004, 1)
        merge(blade, Rz(b * 120) @ T(0.43, 0, 0.0) @ Rx(10))
    make_obj(f"Fan_{i}", "FanWhite", bm, Vector((fx, -fz, H - 0.42)))

COL.sort()
with open(COLLIDERS, "w") as f:
    json.dump({"walk": [-5.88, 5.88, -6.38, 6.38], "boxes": COL}, f)

# ================================================================ GI LIGHTMAPS (set BAKE=1)
# Cycles bakes how much sky light reaches each surface, including bounces off walls and floors,
# into a second UV set. The viewer uses it to shade ambient light, so rooms, corners and the
# undersides of shelves darken the way they do in a photo.
BAKE_GROUPS = ("Arch", "Roof", "Ceil", "Openings", "Furniture")
BAKE_SKIP = {"Ground", "Facade", "StoneTrim", "Glass", "Chrome", "Brass", "Screen", "WindowDark", "SteelPipe",
             "IronBlack", "Leaf", "LeafEuca", "LeafIvy", "Bark", "Soil", "CoveLED", "LampShade", "Porcelain"}

def use_gpu(scene):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP"):
            prefs.compute_device_type = kind
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                scene.cycles.device = "GPU"
                return kind
    except Exception as e:
        print("GPU setup failed:", e)
    return "CPU"

def bake_lightmaps():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    print("bake device:", use_gpu(sc))
    sc.cycles.samples = int(os.environ.get("BAKE_SAMPLES", "384"))
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 3
    world = bpy.data.worlds.new("BakeSky")
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 1.0
    sc.world = world
    bk = sc.render.bake
    bk.use_pass_direct, bk.use_pass_indirect, bk.use_pass_color = True, True, False
    bk.margin = 6
    out_dir = os.path.join(HERE, "..", "lightmaps")
    os.makedirs(out_dir, exist_ok=True)
    manifest = {}
    for o in [o for o in sc.objects if o.type == "MESH" and "__" in o.name]:
        group, mname = o.name.split("__", 1)
        if group not in BAKE_GROUPS or mname in BAKE_SKIP:
            continue
        area = sum(p.area for p in o.data.polygons)
        res = 4096 if area > 150 else 2048 if area > 60 else 1024 if area > 10 else 512
        uv = o.data.uv_layers.new(name="Lightmap")
        o.data.uv_layers.active = uv
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        try:
            bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_PACK_IN_ONE=True, PREF_NEW_UVLAYER=False,
                                     PREF_MARGIN_DIV=0.25)
        except TypeError:
            bpy.ops.uv.smart_project(island_margin=0.004)
        bpy.ops.object.mode_set(mode="OBJECT")
        img = bpy.data.images.new(o.name + "_lm", res, res, alpha=False)
        nt = o.data.materials[0].node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=6, use_clear=True)
        fname = o.name + ".png"
        img.filepath_raw = os.path.join(out_dir, fname)
        img.file_format = "PNG"
        img.save()
        nt.nodes.remove(node)
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
        manifest[o.name] = fname
        print("baked", o.name, res, flush=True)
    with open(os.path.join(out_dir, "index.json"), "w") as f:
        json.dump(manifest, f, indent=1)

if os.environ.get("BAKE") == "1":
    bake_lightmaps()

bpy.ops.export_scene.gltf(filepath=os.path.abspath(OUT), export_format="GLB",
                          export_yup=True, export_apply=True)
print("EXPORTED", os.path.abspath(OUT), len(bpy.data.objects), "objects", len(COL), "colliders")
