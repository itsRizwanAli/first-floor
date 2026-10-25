// Procedural, tileable canvas textures. UVs from Blender are in meters,
// so each texture's `repeat` = 1 / (meters the texture covers).
import * as THREE from 'three';

function hash(x, y, s) {
  let h = Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(s, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967295;
}

function vnoise(x, y, px, py, s) {
  const xi = Math.floor(x), yi = Math.floor(y);
  const xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const x0 = ((xi % px) + px) % px, x1 = (x0 + 1) % px;
  const y0 = ((yi % py) + py) % py, y1 = (y0 + 1) % py;
  const a = hash(x0, y0, s), b = hash(x1, y0, s), c = hash(x0, y1, s), d = hash(x1, y1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}

// tileable fbm over the unit square; fx/fy = base lattice frequency
function fbm(u, v, fx, fy, oct = 5, s = 1) {
  let sum = 0, amp = 0.5, norm = 0;
  for (let o = 0; o < oct; o++) {
    const m = 1 << o;
    sum += amp * vnoise(u * fx * m, v * fy * m, fx * m, fy * m, s + o * 17);
    norm += amp;
    amp *= 0.5;
  }
  return sum / norm;
}

function canvasTex(size, fn, { meters = 1, srgb = true, aniso = 8 } = {}) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(size, size);
  const d = img.data;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const [r, g, b] = fn(x / size, y / size, x, y);
      const i = (y * size + x) * 4;
      d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return finishTex(c, meters, srgb, aniso);
}

function finishTex(canvas, meters, srgb, aniso) {
  const t = new THREE.CanvasTexture(canvas);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(1 / meters, 1 / meters);
  t.anisotropy = aniso;
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  return t;
}

const g = (v) => { const c = Math.max(0, Math.min(255, v)); return [c, c, c]; };

export function buildTextures() {
  const T = {};

  // plaster: soft mottling + fine trowel bump
  T.plaster = canvasTex(512, (u, v) => {
    const n = fbm(u, v, 6, 6, 5, 3);
    return g(232 + (n - 0.5) * 26);
  }, { meters: 2 });
  T.plasterBump = canvasTex(512, (u, v) => g(fbm(u, v, 24, 24, 4, 9) * 255), { meters: 2, srgb: false });

  // wood: grayscale grain, tinted by material color
  T.wood = canvasTex(512, (u, v) => {
    const warp = fbm(u, v, 3, 1, 4, 5);
    const ring = Math.sin((u * 22 + warp * 5) * Math.PI * 2) * 0.5 + 0.5;
    const fine = fbm(u, v, 96, 3, 3, 7);
    const pores = fbm(u, v, 160, 8, 2, 11);
    return g(255 * (0.8 + ring * ring * 0.08 + fine * 0.1 - pores * 0.05));
  }, { meters: 0.9 });
  T.woodRough = canvasTex(256, (u, v) => g(110 + fbm(u, v, 48, 3, 3, 21) * 80), { meters: 0.9, srgb: false });

  // polished floor tiles 60cm, 1.2m per texture
  const tileTint = (tx, ty) => (hash(tx, ty, 77) - 0.5) * 10;
  T.floor = canvasTex(1024, (u, v) => {
    const tx = Math.floor(u * 2), ty = Math.floor(v * 2);
    const fu = (u * 2) % 1, fv = (v * 2) % 1;
    const grout = Math.min(fu, fv, 1 - fu, 1 - fv) < 0.004;
    if (grout) return [176, 166, 152];
    const vein = Math.abs(fbm(u, v, 4, 4, 6, 31) - 0.5);
    const cloud = fbm(u, v, 8, 8, 4, 41);
    const k = tileTint(tx, ty) + (cloud - 0.5) * 12 - Math.max(0, 0.04 - vein) * 300;
    return [228 + k, 216 + k, 198 + k];
  }, { meters: 1.2 });
  T.floorRough = canvasTex(512, (u, v) => {
    const fu = (u * 2) % 1, fv = (v * 2) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.006) return g(240);
    return g(46 + fbm(u, v, 16, 16, 4, 51) * 50);
  }, { meters: 1.2, srgb: false });

  // matte balcony tiles 40cm
  T.balcony = canvasTex(512, (u, v) => {
    const tx = Math.floor(u * 2), ty = Math.floor(v * 2);
    const fu = (u * 2) % 1, fv = (v * 2) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.008) return [150, 140, 128];
    const k = tileTint(tx, ty) * 1.5 + (fbm(u, v, 20, 20, 4, 61) - 0.5) * 22;
    return [204 + k, 190 + k, 170 + k];
  }, { meters: 0.8 });

  T.concrete = canvasTex(512, (u, v) => g(226 + (fbm(u, v, 10, 10, 6, 71) - 0.5) * 34), { meters: 3 });

  // fabric weave (tint)
  T.weave = canvasTex(256, (u, v, x, y) => {
    const warp = (x % 4 < 2) !== (y % 4 < 2);
    const n = fbm(u, v, 32, 32, 3, 81);
    return g(205 + (warp ? 22 : 0) + (n - 0.5) * 40);
  }, { meters: 0.06 });
  T.weaveBump = canvasTex(256, (u, v, x, y) => g(((x % 4 < 2) !== (y % 4 < 2)) ? 220 : 60), { meters: 0.06, srgb: false });

  // pillow: interlocking lattice pattern like the reference
  T.pillow = (() => {
    const s = 512, c = document.createElement('canvas');
    c.width = c.height = s;
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#e9dcc4'; ctx.fillRect(0, 0, s, s);
    ctx.strokeStyle = '#b89f7c'; ctx.lineWidth = 9; ctx.lineCap = 'square';
    const st = s / 4;
    for (let i = -1; i <= 4; i++) {
      for (let j = -1; j <= 4; j++) {
        const x = i * st, y = j * st;
        ctx.beginPath();
        ctx.moveTo(x, y + st / 2); ctx.lineTo(x + st / 2, y); ctx.lineTo(x + st, y + st / 2);
        ctx.moveTo(x + st / 4, y + st / 2); ctx.lineTo(x + st / 2, y + st / 4); ctx.lineTo(x + 3 * st / 4, y + st / 2);
        ctx.stroke();
      }
    }
    const img = ctx.getImageData(0, 0, s, s);
    for (let y = 0; y < s; y++) for (let x = 0; x < s; x++) {
      const k = ((x % 4 < 2) !== (y % 4 < 2) ? 10 : -6) + (hash(x, y, 5) - 0.5) * 14;
      const i = (y * s + x) * 4;
      img.data[i] += k; img.data[i + 1] += k; img.data[i + 2] += k;
    }
    ctx.putImageData(img, 0, 0);
    return finishTex(c, 0.36, true, 8);
  })();

  // rug: heathered loop pile with soft stripes
  T.rug = canvasTex(512, (u, v, x, y) => {
    const loop = ((x >> 1) + (y >> 1)) % 2 ? 10 : -10;
    const stripe = Math.sin(v * Math.PI * 2 * 6) > 0.85 ? -22 : 0;
    const n = (fbm(u, v, 40, 40, 3, 91) - 0.5) * 40;
    return [226 + loop + n + stripe, 214 + loop + n + stripe, 192 + loop + n + stripe];
  }, { meters: 1 });

  T.speckle = canvasTex(256, (u, v, x, y) => g(236 + (fbm(u, v, 16, 16, 3, 101) - 0.5) * 30 - (hash(x, y, 3) > 0.985 ? 70 : 0)), { meters: 0.3 });
  T.paper = canvasTex(256, (u, v) => g(240 + (fbm(u, v, 20, 20, 4, 111) - 0.5) * 16), { meters: 0.5 });
  T.rattan = canvasTex(256, (u, v, x, y) => {
    const a = ((x >> 3) + (y >> 3)) % 2;
    const s = a ? Math.sin(x * 0.8) : Math.sin(y * 0.8);
    return g(200 + s * 30 + (hash(x, y, 9) - 0.5) * 20);
  }, { meters: 0.12 });
  T.bark = canvasTex(256, (u, v) => g(140 + fbm(u, v, 30, 4, 4, 121) * 115), { meters: 0.2 });

  // Carrara marble, 60cm tiles with thin joints and soft grey veining
  T.marble = canvasTex(1024, (u, v) => {
    const tx = Math.floor(u * 2), ty = Math.floor(v * 2);
    const fu = (u * 2) % 1, fv = (v * 2) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.003) return [190, 188, 184];
    const warp = fbm(u, v, 3, 3, 5, 131 + tx * 7 + ty * 13);
    const vein = Math.abs(Math.sin((u * 3 + v * 5 + warp * 4) * Math.PI));
    const fine = fbm(u, v, 24, 24, 4, 141);
    const k = -Math.pow(1 - vein, 14) * 80 - (1 - fine) * 14 + (hash(tx, ty, 5) - 0.5) * 6;
    return [244 + k, 243 + k, 240 + k * 0.95];
  }, { meters: 1.2 });
  T.marbleRough = canvasTex(256, (u, v) => {
    const fu = (u * 2) % 1, fv = (v * 2) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.006) return g(230);
    return g(30 + fbm(u, v, 12, 12, 3, 151) * 40);
  }, { meters: 1.2, srgb: false });

  // granite-like stair stone
  T.stone = canvasTex(256, (u, v, x, y) => {
    const n = fbm(u, v, 20, 20, 4, 161);
    const fleck = hash(x, y, 17);
    return g(150 + (n - 0.5) * 50 + (fleck > 0.93 ? 60 : fleck < 0.06 ? -50 : 0));
  }, { meters: 0.4 });

  // ---- as-is site textures (walkthrough video)
  // raw cement plaster: trowel swirls, darker damp patches
  T.cement = canvasTex(512, (u, v) => {
    const swirl = fbm(u, v, 14, 6, 4, 201);
    const patch = fbm(u, v, 3, 3, 5, 211);
    return g(170 + (swirl - 0.5) * 40 - Math.max(0, 0.5 - patch) * 70 + (fbm(u, v, 60, 60, 2, 221) - 0.5) * 18);
  }, { meters: 2.5 });

  // brick-tile roof underside: red bricks in rows, smeared with cement and stained
  T.brickCeiling = canvasTex(1024, (u, v) => {
    const bw = 1 / 9, bh = 1 / 18;
    const row = Math.floor(v / bh), off = (row % 2) * 0.5 * bw;
    const bu = ((u + off) % bw) / bw, bv = (v % bh) / bh;
    const id = hash(Math.floor((u + off) / bw), row, 5);
    const joint = Math.min(bu, 1 - bu) < 0.05 || Math.min(bv, 1 - bv) < 0.1;
    const smear = fbm(u, v, 10, 10, 5, 231);
    const stain = fbm(u, v, 4, 4, 5, 241);
    const showBrick = !joint && smear < 0.44 + id * 0.1;
    const mould = Math.max(0, fbm(u, v, 22, 22, 4, 291) - 0.58) * 300;
    const dark = Math.max(0, stain - 0.5) * 240 + mould;
    if (showBrick) {
      const k = (fbm(u, v, 80, 80, 2, 251) - 0.5) * 40 + (id - 0.5) * 30 - dark;
      return [150 + k, 84 + k * 0.6, 66 + k * 0.5];
    }
    const k = (smear - 0.5) * 40 - dark;
    return [150 + k, 143 + k, 134 + k];
  }, { meters: 2.4 });

  // raw brick courses (parapets, bricked-up window)
  T.brickRaw = canvasTex(512, (u, v) => {
    const bw = 1 / 4, bh = 1 / 12;
    const row = Math.floor(v / bh), off = (row % 2) * 0.5 * bw;
    const bu = ((u + off) % bw) / bw, bv = (v % bh) / bh;
    if (Math.min(bu, 1 - bu) < 0.035 || Math.min(bv, 1 - bv) < 0.09) return g(150 + (hash(Math.floor(u * 512), Math.floor(v * 512), 3) - 0.5) * 30);
    const id = hash(Math.floor((u + off) / bw), row, 9);
    const k = (fbm(u, v, 60, 60, 3, 261) - 0.5) * 45 + (id - 0.5) * 50;
    return [170 + k, 88 + k * 0.6, 62 + k * 0.45];
  }, { meters: 0.9 });

  // dusty beige tiles with grey cement smudges
  T.tileDusty = canvasTex(1024, (u, v) => {
    const tx = Math.floor(u * 2), ty = Math.floor(v * 2);
    const fu = (u * 2) % 1, fv = (v * 2) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.004) return [140, 132, 120];
    const smudge = fbm(u, v, 6, 6, 5, 271);
    const vein = fbm(u, v, 3, 3, 5, 281 + tx * 3 + ty * 5);
    const k = (hash(tx, ty, 21) - 0.5) * 16 + (vein - 0.5) * 22;
    const dust = Math.max(0, smudge - 0.52) * 220;
    return [216 + k - dust * 0.6, 196 + k - dust * 0.45, 168 + k - dust * 0.25];
  }, { meters: 1.2 });

  // charpai rope weave (diagonal), tinted by material colour
  T.weaveRope = canvasTex(256, (u, v, x, y) => {
    const a = ((x + y) >> 3) % 2, b = ((x - y + 256) >> 3) % 2;
    const over = a ^ b;
    const s = over ? Math.sin(((x + y) % 8) / 8 * Math.PI) : Math.sin(((x - y + 256) % 8) / 8 * Math.PI);
    return g(120 + s * 120);
  }, { meters: 0.2 });

  // striped cotton (razai / bedsheets / curtain)
  T.stripe = canvasTex(256, (u, v, x, y) => {
    const band = Math.floor(u * 24) % 4;
    const c = band === 0 ? [96, 58, 52] : band === 2 ? [150, 110, 96] : [186, 160, 148];
    const n = (hash(x, y, 7) - 0.5) * 16;
    return [c[0] + n, c[1] + n, c[2] + n];
  }, { meters: 0.6 });

  // reddish-orange floor tiles, 40cm, thin light joints
  T.terracotta = canvasTex(1024, (u, v) => {
    const n = 3;
    const tx = Math.floor(u * n), ty = Math.floor(v * n);
    const fu = (u * n) % 1, fv = (v * n) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.006) return [196, 170, 140];
    const k = (hash(tx, ty, 31) - 0.5) * 22 + (fbm(u, v, 9, 9, 5, 301) - 0.5) * 26;
    const fleck = (fbm(u, v, 70, 70, 2, 311) - 0.5) * 14;
    return [196 + k + fleck, 96 + k * 0.55 + fleck * 0.6, 58 + k * 0.35 + fleck * 0.4];
  }, { meters: 1.2 });
  T.terracottaRough = canvasTex(256, (u, v) => {
    const fu = (u * 3) % 1, fv = (v * 3) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.01) return g(235);
    return g(70 + fbm(u, v, 12, 12, 3, 321) * 60);
  }, { meters: 1.2, srgb: false });

  // white glazed wet-area tiles (washing pad), 20cm
  T.washTile = canvasTex(512, (u, v) => {
    const n = 6;
    const fu = (u * n) % 1, fv = (v * n) % 1;
    if (Math.min(fu, fv, 1 - fu, 1 - fv) < 0.02) return [170, 172, 170];
    const k = (hash(Math.floor(u * n), Math.floor(v * n), 41) - 0.5) * 10;
    return [236 + k, 238 + k, 236 + k];
  }, { meters: 1.2 });

  // dusty street
  T.ground = canvasTex(512, (u, v) => g(200 + (fbm(u, v, 12, 12, 6, 171) - 0.5) * 70), { meters: 6 });

  return T;
}
