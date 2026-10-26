import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { Sky } from 'three/addons/objects/Sky.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { FullScreenQuad } from 'three/addons/postprocessing/Pass.js';
import { buildTextures } from './textures.js';
import { volumeAOMaterial, blurMaterial, compositeMaterial, lensMaterial } from './post.js';

const $ = (id) => document.getElementById(id);
// ?q=low for weak GPUs; ?shot&t=&pos=x,z&yaw=&pitch=&eye= for a fixed, paused camera
const URLP = new URLSearchParams(location.search);
const LOW = URLP.get('q') === 'low';
const setStatus = (s) => { $('loading-text').textContent = s; };

// ------------------------------------------------------------------ renderer
const canvas = $('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
const DPR = Math.min(window.devicePixelRatio, LOW ? 0.75 : 1.25);
renderer.setPixelRatio(DPR);
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.NoToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate = false;
RectAreaLightUniformsLib.init();

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.05, 20000);
camera.layers.enable(1); // sky / clouds
camera.layers.enable(2); // dust

// ------------------------------------------------------------------ sky + environment
const sky = new Sky();
sky.scale.setScalar(18000);
sky.layers.set(1);
const skyGain = { value: 1.0 };
const patchSky = (s, showSun) => {
  s.material.uniforms.skyGain = skyGain;
  s.material.fragmentShader = s.material.fragmentShader
    .replace('void main() {', 'uniform float skyGain;\nvoid main() {')
    .replace('* sundisk;', `* sundisk * ${showSun ? '1.0' : '0.0'};`)
    .replace('gl_FragColor = vec4( retColor, 1.0 );', 'gl_FragColor = vec4( retColor * skyGain, 1.0 );');
};
patchSky(sky, true);
scene.add(sky);

// the environment sky has no sun disc: the directional light already carries the sun
const envScene = new THREE.Scene();
const envSky = new Sky();
envSky.scale.setScalar(60);
patchSky(envSky, false);
envScene.add(envSky);
const pmrem = new THREE.PMREMGenerator(renderer);
let envRT = null;

const cloudMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, side: THREE.DoubleSide,
  uniforms: {
    time: { value: 0 }, sunDir: { value: new THREE.Vector3() },
    sunColor: { value: new THREE.Color() }, skyColor: { value: new THREE.Color() },
  },
  vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
  fragmentShader: `
    uniform float time; uniform vec3 sunDir, sunColor, skyColor; varying vec3 vW;
    float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
      return mix(mix(h(i), h(i+vec2(1,0)), f.x), mix(h(i+vec2(0,1)), h(i+vec2(1,1)), f.x), f.y); }
    float fbm(vec2 p){ float s = 0., a = .5; for (int i = 0; i < 6; i++){ s += a*n(p); p = p*2.03 + 7.1; a *= .5; } return s; }
    void main(){
      vec2 p = vW.xz * 0.00045 + vec2(time * 0.0025, time * 0.001);
      float base = fbm(p * vec2(1., 2.6));
      float cov = smoothstep(0.5, 0.78, base);
      float thick = smoothstep(0.5, 0.95, base);
      vec3 vd = normalize(vW - cameraPosition);
      float fwd = pow(max(dot(vd, sunDir), 0.), 5.);
      vec3 col = skyColor * (1.1 - thick * 0.5) + sunColor * (0.25 + 3.0 * fwd) * (1. - thick * 0.6);
      float dist = length(vW.xz - cameraPosition.xz);
      float fade = smoothstep(16000., 2500., dist);
      gl_FragColor = vec4(col, cov * fade * 0.92);
    }`,
});
const clouds = new THREE.Mesh(new THREE.PlaneGeometry(40000, 40000), cloudMat);
clouds.rotation.x = Math.PI / 2;
clouds.position.y = 1400;
clouds.layers.set(1);
scene.add(clouds);

// ------------------------------------------------------------------ lights
const SHADOW_EXTENT = 11;
const sun = new THREE.DirectionalLight(0xffffff, 4);
sun.castShadow = true;
sun.shadow.mapSize.setScalar(LOW ? 2048 : 4096);
Object.assign(sun.shadow.camera, { left: -SHADOW_EXTENT, right: SHADOW_EXTENT, top: SHADOW_EXTENT, bottom: -SHADOW_EXTENT, near: 0.5, far: 70 });
sun.shadow.bias = -0.00025;
sun.shadow.normalBias = 0.02;
const sunTarget = new THREE.Object3D();
sunTarget.position.set(0, 1.0, 0);
scene.add(sun, sunTarget);
sun.target = sunTarget;

const hemi = new THREE.HemisphereLight(0xbcd2ff, 0xb07a4a, 0.05);
scene.add(hemi);

// skylight spilling through each opening that faces the open court or the street
// [x, y, z, width, height, lookX, lookZ]
const OPENINGS = [
  [-3.25, 1.5, -1.36, 5.4, 2.9, 0, -1],     // hall: whole south side open to the court
  [-3.05, 1.75, -6.42, 3.4, 1.8, 0, 1],     // hall outer opening above the parapet
  [2.0, 1.5, -6.4, 2.7, 1.3, 0, 1],         // room 1 window
  [0.35, 1.1, -1.4, 0.9, 2.1, 0, -1],       // room 1 door
  [1.1, 1.5, -0.3, 1.2, 1.3, 1, 0],         // room 2 window
  [1.1, 1.1, 1.25, 0.9, 2.1, 1, 0],         // room 2 door
  [1.1, 1.1, 3.25, 0.9, 2.1, 1, 0],         // room 3 door
  [1.1, 1.5, 5.15, 1.1, 1.3, 1, 0],         // room 3 window
];
const openingLights = OPENINGS.map(([x, y, z, w, h, lx, lz]) => {
  const l = new THREE.RectAreaLight(0xffffff, 1, w, h);
  l.position.set(x, y, z);
  l.lookAt(x + lx, y, z + lz);
  l.userData.area = w * h;
  scene.add(l);
  return l;
});

// warm room lights for the evening (ceiling centre of each roofed room)
const roomLights = [[-3.25, -3.9], [2.0, -3.9], [3.5, 0.55], [3.5, 4.45], [5.25, -4.6], [-4.75, 5.1]].map(([x, z]) => {
  const l = new THREE.PointLight(0xffb36b, 0, 7, 1.7);
  l.position.set(x, 2.55, z);
  scene.add(l);
  return l;
});

// light-space depth used by sun shafts and dust (layer 0 only)
const LIGHT_RES = LOW ? 768 : 2048;
const lightRT = new THREE.WebGLRenderTarget(LIGHT_RES, LIGHT_RES, { depthTexture: new THREE.DepthTexture(LIGHT_RES, LIGHT_RES) });
const lightCam = new THREE.OrthographicCamera(-SHADOW_EXTENT, SHADOW_EXTENT, SHADOW_EXTENT, -SHADOW_EXTENT, 0.5, 70);
const depthOverride = new THREE.MeshDepthMaterial({ side: THREE.DoubleSide });
const lightVP = new THREE.Matrix4();

setStatus('Weaving textures…');
await new Promise((r) => setTimeout(r, 30));
const TX = buildTextures();
scene.fog = new THREE.Fog(0xd8b48a, 300, 9000);

// ------------------------------------------------------------------ sky visibility for image-based light
// Image-based light (the sky) is scaled per fragment: full strength in the open court and
// outdoors, faint under the roofs. The roofed footprint is a union of rectangles (wall centrelines).
const ROOFED = [[-6.0, 6.0, -6.5, -1.3], [1.0, 6.0, -1.3, 6.5], [-6.0, -3.5, 3.7, 6.5]];
const skyUniforms = {
  uRoofed: { value: ROOFED.map(([a, b, c, d]) => new THREE.Vector4(a, b, c, d)) },
  uEnvIn: { value: 0.08 }, uEnvOut: { value: 0.55 },
};
// meshes with a baked GI lightmap (aoMap) already carry sky occlusion, so they skip the roof-rectangle guess
const bakedEnv = { value: 0.95 };
const bakedUniforms = { uRoofed: skyUniforms.uRoofed, uEnvIn: bakedEnv, uEnvOut: bakedEnv };
let bakedMode = false;
function skyAware(m, baked = bakedMode) {
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, baked ? bakedUniforms : skyUniforms);
    sh.vertexShader = 'varying vec3 vWPos;\nvarying vec3 vWNrm;\n' + sh.vertexShader.replace('#include <project_vertex>', `#include <project_vertex>
      vWPos = (modelMatrix * vec4(transformed, 1.0)).xyz;
      vWNrm = normalize(mat3(modelMatrix) * objectNormal);`);
    sh.fragmentShader = 'varying vec3 vWPos;\nvarying vec3 vWNrm;\nuniform vec4 uRoofed[3];\nuniform float uEnvIn, uEnvOut;\n' +
      sh.fragmentShader.replace('#include <lights_fragment_maps>', `#include <lights_fragment_maps>
      {
        vec3 sp = vWPos + normalize(vWNrm) * 0.06;
        float roofed = 0.0;
        for (int i = 0; i < 3; i++) {
          vec4 r = uRoofed[i];
          roofed = max(roofed, step(r.x, sp.x) * step(sp.x, r.y) * step(r.z, sp.z) * step(sp.z, r.w));
        }
        roofed *= step(sp.y, 3.05) * step(-0.5, sp.y);
        float k = mix(uEnvOut, uEnvIn, roofed);
        iblIrradiance *= k;
        #if defined( RE_IndirectSpecular )
          radiance *= k;
        #endif
      }`);
  };
  m.customProgramCacheKey = () => 'skyaware';
  return m;
}

// ------------------------------------------------------------------ materials by Blender name
const std = (o) => skyAware(new THREE.MeshStandardMaterial(o));
const wood = (color, rough = 0.5) => std({ color, map: TX.wood, roughnessMap: TX.woodRough, roughness: rough * 1.6 });
const MATERIALS = {
  Cream: () => std({ color: 0xf0dfc4, map: TX.plaster, bumpMap: TX.plasterBump, bumpScale: 0.2, roughness: 0.93 }),
  Ceiling: () => std({ color: 0xf6efe4, map: TX.plaster, roughness: 0.96 }),
  // all floors: reddish-orange tiles
  TileBeige: () => std({ color: 0xffffff, map: TX.terracotta, roughnessMap: TX.terracottaRough, roughness: 0.9 }),
  Marble: () => std({ color: 0xffffff, map: TX.terracotta, roughnessMap: TX.terracottaRough, roughness: 0.9 }),
  WashTile: () => std({ color: 0xffffff, map: TX.washTile, roughness: 0.15 }),
  Stone: () => std({ color: 0x8d9097, map: TX.stone, roughness: 0.55 }),
  StoneTrim: () => std({ color: 0xcdbb9b, map: TX.concrete, roughness: 0.75 }),
  Trim: () => std({ color: 0xf4f1ea, roughness: 0.4 }),
  Teak: () => wood(0xa45a26, 0.38),
  WoodWarm: () => wood(0xb8642c, 0.42),
  WoodLight: () => wood(0xc98f57, 0.5),
  WoodDark: () => wood(0x5a3218, 0.5),
  Walnut: () => wood(0x6b3a1c, 0.42),
  Fabric: () => std({ color: 0xe3d5bf, map: TX.weave, bumpMap: TX.weaveBump, bumpScale: 0.5, roughness: 1 }),
  Cushion: () => std({ color: 0xe9dcc6, map: TX.weave, bumpMap: TX.weaveBump, bumpScale: 0.5, roughness: 1 }),
  Pillow: () => std({ color: 0xffffff, map: TX.pillow, bumpMap: TX.weaveBump, bumpScale: 0.4, roughness: 1 }),
  Linen: () => std({ color: 0xf3f0ea, map: TX.weave, bumpMap: TX.weaveBump, bumpScale: 0.3, roughness: 1 }),
  DuvetSand: () => std({ color: 0xd6cbb5, map: TX.weave, bumpMap: TX.weaveBump, bumpScale: 0.4, roughness: 1 }),
  DuvetSage: () => std({ color: 0x7d917f, map: TX.weave, bumpMap: TX.weaveBump, bumpScale: 0.4, roughness: 1 }),
  DuvetGrey: () => std({ color: 0x858d96, map: TX.weave, bumpMap: TX.weaveBump, bumpScale: 0.4, roughness: 1 }),
  Headboard: () => std({ color: 0xcbb89c, map: TX.weave, bumpMap: TX.weaveBump, bumpScale: 0.6, roughness: 1 }),
  Ceramic: () => std({ color: 0xcfae8c, map: TX.speckle, roughness: 0.62 }),
  CeramicWhite: () => std({ color: 0xece6dc, map: TX.speckle, roughness: 0.45 }),
  Terracotta: () => std({ color: 0xb06a43, map: TX.speckle, roughness: 0.85 }),
  Porcelain: () => std({ color: 0xf7f7f5, roughness: 0.12 }),
  Chrome: () => std({ color: 0xdcdde0, metalness: 1, roughness: 0.15 }),
  Brass: () => std({ color: 0xd8a24a, metalness: 1, roughness: 0.28 }),
  MetalDark: () => std({ color: 0x1b1b1d, metalness: 0.8, roughness: 0.38 }),
  Aluminium: () => std({ color: 0xb9b6b0, metalness: 0.9, roughness: 0.32 }),
  Slate: () => std({ color: 0x2f3742, roughness: 0.6 }),
  Glass: () => skyAware(new THREE.MeshPhysicalMaterial({ color: 0xf2fbfa, metalness: 0, roughness: 0.03, transparent: true, opacity: 0.12, depthWrite: false })),
  Leaf: () => std({ color: 0x4f6b2a, roughness: 0.5, side: THREE.DoubleSide }),
  LeafEuca: () => std({ color: 0x7c9a82, roughness: 0.6, side: THREE.DoubleSide }),
  LeafIvy: () => std({ color: 0x3d6b22, roughness: 0.4, side: THREE.DoubleSide }),
  Bark: () => std({ color: 0x6a5240, map: TX.bark, roughness: 0.9 }),
  Soil: () => std({ color: 0x2a1d14, roughness: 1 }),
  Rug: () => std({ color: 0xe6dccb, map: TX.rug, bumpMap: TX.weaveBump, bumpScale: 1, roughness: 1 }),
  Screen: () => std({ color: 0x050506, roughness: 0.12, metalness: 0.2 }),
  Paper: () => std({ color: 0xf3ead8, map: TX.paper, roughness: 0.9 }),
  BookCover: () => std({ color: 0xd2b27a, map: TX.rattan, roughness: 0.8 }),
  LampShade: () => std({ color: 0xf0dfc2, map: TX.weave, roughness: 0.95, side: THREE.DoubleSide, emissive: 0xffa75a, emissiveIntensity: 0 }),
  CoveLED: () => std({ color: 0xfff4e0, emissive: 0xffc27a, emissiveIntensity: 0 }),
  Facade: () => std({ color: 0xe2d2b8, map: TX.concrete, roughness: 0.92 }),
  Facade2: () => std({ color: 0xd6c3a6, map: TX.concrete, roughness: 0.92 }),
  Ground: () => std({ color: 0x9c8e7c, map: TX.ground, roughness: 0.95 }),
  RoofTop: () => std({ color: 0xc9b9a0, map: TX.concrete, roughness: 0.95 }),
  WindowDark: () => std({ color: 0x0b0e12, roughness: 0.15, metalness: 0.3 }),
  WasherBody: () => std({ color: 0xf4f4f2, roughness: 0.3 }),
  FanWhite: () => std({ color: 0xf1efe9, roughness: 0.35, metalness: 0.2 }),
  // as-is site (walkthrough video)
  Cement: () => whitewash(std({ color: 0xbdb9b2, map: TX.cement, bumpMap: TX.plasterBump, bumpScale: 0.35, roughness: 0.95 })),
  Concrete: () => std({ color: 0xb8b4ac, map: TX.cement, roughness: 0.92 }),
  TileDusty: () => std({ color: 0xffffff, map: TX.tileDusty, roughnessMap: TX.floorRough, roughness: 1.6 }),
  Skirting: () => std({ color: 0xc89c70, map: TX.speckle, roughness: 0.5 }),
  BrickCeiling: () => std({ color: 0xffffff, map: TX.brickCeiling, bumpMap: TX.brickCeiling, bumpScale: 0.6, roughness: 0.95 }),
  BrickRaw: () => std({ color: 0xffffff, map: TX.brickRaw, bumpMap: TX.brickRaw, bumpScale: 0.8, roughness: 0.95 }),
  RedSteel: () => std({ color: 0x6e1414, roughness: 0.5, metalness: 0.35 }),
  IronBlack: () => std({ color: 0x141414, roughness: 0.55, metalness: 0.6 }),
  SteelPipe: () => std({ color: 0x55575a, roughness: 0.4, metalness: 0.85 }),
  Charpai: () => std({ color: 0x9a3328, map: TX.weaveRope, roughness: 0.9, side: THREE.DoubleSide }),
  CharpaiBlue: () => std({ color: 0x2c3c86, map: TX.weaveRope, roughness: 0.9, side: THREE.DoubleSide }),
  PlasticGrey: () => std({ color: 0x8b9097, roughness: 0.45 }),
  CoolerBody: () => std({ color: 0x1e1f22, roughness: 0.5 }),
  Stainless: () => std({ color: 0xd4d5d8, roughness: 0.22, metalness: 1 }),
  BucketWhite: () => std({ color: 0xece9e2, roughness: 0.4, side: THREE.DoubleSide }),
  BucketBlue: () => std({ color: 0x2a5d9a, roughness: 0.4, side: THREE.DoubleSide }),
  TrunkGreen: () => std({ color: 0xa9c1aa, roughness: 0.35, metalness: 0.5 }),
  Cloth: () => std({ color: 0xece8e0, map: TX.weave, roughness: 0.95, side: THREE.DoubleSide }),
  ClothStripe: () => std({ color: 0xffffff, map: TX.stripe, roughness: 0.95, side: THREE.DoubleSide }),
  Sack: () => std({ color: 0xd2b07a, map: TX.weave, roughness: 0.95 }),
  Wire: () => std({ color: 0x0a0a0a, roughness: 0.6 }),
  WireRed: () => std({ color: 0xb01818, roughness: 0.5 }),
  Switch: () => std({ color: 0xe8e5dd, roughness: 0.4 }),
};

// patchy white primer on the lower part of the interior walls, ragged top edge (as on site)
function whitewash(m) {
  const prev = m.onBeforeCompile;
  m.onBeforeCompile = (sh, r) => {
    prev(sh, r);
    sh.fragmentShader = `float wwH(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float wwN(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(wwH(i), wwH(i + vec2(1, 0)), f.x), mix(wwH(i + vec2(0, 1)), wwH(i + vec2(1, 1)), f.x), f.y); }
` + sh.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
      {
        float roofedW = 0.0;
        for (int i = 0; i < 3; i++) {
          vec4 rr = uRoofed[i];
          vec3 sp = vWPos + normalize(vWNrm) * 0.06;
          roofedW = max(roofedW, step(rr.x, sp.x) * step(sp.x, rr.y) * step(rr.z, sp.z) * step(sp.z, rr.w));
        }
        float s = vWPos.x + vWPos.z;                                   // position along the wall
        float edge = 1.72 + (wwN(vec2(s * 2.0, 0.5)) - 0.5) * 0.22 + (wwN(vec2(s * 22.0, vWPos.y * 6.0)) - 0.5) * 0.14;
        float wash = (1.0 - smoothstep(edge - 0.015, edge + 0.015, vWPos.y)) * step(0.0, vWPos.y) * roofedW;
        wash *= 0.62 + 0.38 * smoothstep(0.2, 0.7, wwN(vec2(s * 45.0, vWPos.y * 1.5)));   // vertical brush streaks
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.9, 0.89, 0.86), wash);
      }`);
  };
  m.customProgramCacheKey = () => 'skyaware-whitewash';
  return m;
}
const matCache = new Map();
const emissiveMats = { lamp: [], cove: [] };
const floorMaterials = [];
const wallMaterials = [];
const texLoader = new THREE.TextureLoader();
function materialFor(name, objName) {
  let m;
  if (LIGHTMAPS[objName]) {                                    // own material instance carrying this mesh's GI bake
    bakedMode = true;
    m = MATERIALS[name] ? MATERIALS[name]() : std({ color: 0xcccccc });
    bakedMode = false;
    const t = texLoader.load('lightmaps/' + LIGHTMAPS[objName]);
    t.flipY = false;
    t.channel = 1;
    t.colorSpace = THREE.SRGBColorSpace;
    m.aoMap = t;
    m.aoMapIntensity = 1;
  } else {
    if (!matCache.has(name)) {
      m = MATERIALS[name] ? MATERIALS[name]() : std({ color: 0xcccccc });
      if (name === 'LampShade') emissiveMats.lamp.push(m);
      if (name === 'CoveLED') emissiveMats.cove.push(m);
      matCache.set(name, m);
    }
    m = matCache.get(name);
  }
  if (name === 'TileBeige' || name === 'Marble') floorMaterials.push(m);
  if (name === 'Cream') wallMaterials.push(m);
  return m;
}

// ------------------------------------------------------------------ load the Blender house
setStatus('Loading Blender house…');
const [gltf, colliders] = await Promise.all([
  new GLTFLoader().loadAsync('floor.glb', (e) => {
    if (e.total) setStatus(`Loading Blender house… ${Math.round(e.loaded / e.total * 100)}%`);
  }),
  fetch('colliders.json').then((r) => r.json()),
]);
const LIGHTMAPS = await fetch('lightmaps/index.json').then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
const house = gltf.scene;
const focusTargets = [];
const fans = [];
// Remove misplaced tree in front of room 1 door (x = 0.4, z = -0.72)
const REMOVE_X = 0.4, REMOVE_Z = -0.72;
house.traverse((o) => {
  if (o.isMesh && (o.name.includes('Plants') || o.name.includes('Furniture__Terracotta'))) {
    const posAttr = o.geometry.attributes.position;
    if (posAttr) {
      for (let i = 0; i < posAttr.count; i++) {
        const vx = posAttr.getX(i);
        const vz = posAttr.getZ(i);
        if (Math.hypot(vx - REMOVE_X, vz - REMOVE_Z) < 0.65) {
          posAttr.setY(i, -100);
        }
      }
      posAttr.needsUpdate = true;
    }
  }
  if (o.name.startsWith('Fan_')) fans.push(o);
  if (!o.isMesh) return;
  const name = o.material.name;
  o.material = materialFor(name, o.name);
  const solid = name !== 'Glass' && name !== 'CoveLED';
  o.castShadow = solid;
  o.receiveShadow = name !== 'Glass';
  if (name === 'Glass') o.renderOrder = 2;
  if (solid) focusTargets.push(o);
});

// Remove doorway collider
colliders.boxes = colliders.boxes.filter(([x0, x1, z0, z1]) => {
  const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
  return Math.hypot(cx - REMOVE_X, cz - REMOVE_Z) > 0.4;
});

// Add missing tree wood trunks to connect pot soil to tree foliage
const treeCoords = [
  [-5.3, -5.8],
  [0.35, 4.85],
  [-5.45, -0.35],
];
const trunkGeo = new THREE.CylinderGeometry(0.022, 0.026, 0.38, 12);
const trunkMat = std({ color: 0x5a3e28, roughness: 0.9 });
for (const [tx, tz] of treeCoords) {
  const trunk = new THREE.Mesh(trunkGeo, trunkMat);
  trunk.position.set(tx, 0.52, tz);
  trunk.castShadow = true;
  trunk.receiveShadow = true;
  scene.add(trunk);
}

scene.add(house);

// ------------------------------------------------------------------ dust motes
const DUST = LOW ? 4000 : 14000;
const dustGeo = new THREE.BufferGeometry();
const dpos = new Float32Array(DUST * 3), dseed = new Float32Array(DUST * 3);
const BOX_MIN = new THREE.Vector3(-6, 0.05, -6.5), BOX_SIZE = new THREE.Vector3(12, 3.0, 13);
for (let i = 0; i < DUST; i++) {
  dpos[i * 3] = BOX_MIN.x + Math.random() * BOX_SIZE.x;
  dpos[i * 3 + 1] = BOX_MIN.y + Math.random() * BOX_SIZE.y;
  dpos[i * 3 + 2] = BOX_MIN.z + Math.random() * BOX_SIZE.z;
  dseed[i * 3] = Math.random(); dseed[i * 3 + 1] = Math.random(); dseed[i * 3 + 2] = Math.random();
}
dustGeo.setAttribute('position', new THREE.BufferAttribute(dpos, 3));
dustGeo.setAttribute('seed', new THREE.BufferAttribute(dseed, 3));
const dustMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  uniforms: {
    time: { value: 0 }, lightVP: { value: lightVP }, tLightDepth: { value: lightRT.depthTexture },
    sunColor: { value: new THREE.Color() }, sunDir: { value: new THREE.Vector3() },
    boxMin: { value: BOX_MIN }, boxSize: { value: BOX_SIZE }, size: { value: 3.2 * DPR }, amount: { value: 1 },
  },
  vertexShader: `
    attribute vec3 seed;
    uniform float time, size;
    uniform mat4 lightVP;
    uniform sampler2D tLightDepth;
    uniform vec3 boxMin, boxSize, sunDir;
    varying float vLit; varying float vTw;
    void main(){
      vec3 p = position + vec3(
        sin(time * 0.11 + seed.x * 40.) * 0.18 + time * 0.012,
        sin(time * 0.07 + seed.y * 40.) * 0.12 + time * 0.004 * (seed.z - 0.4),
        cos(time * 0.09 + seed.z * 40.) * 0.18);
      p = boxMin + mod(p - boxMin, boxSize);
      vec4 lc = lightVP * vec4(p, 1.);
      vec3 l = lc.xyz / lc.w * 0.5 + 0.5;
      vLit = step(l.z - 0.002, texture2D(tLightDepth, l.xy).x);
      vec4 mv = modelViewMatrix * vec4(p, 1.);
      gl_Position = projectionMatrix * mv;
      vec3 vd = normalize(p - cameraPosition);
      float fwd = 0.35 + 1.6 * pow(max(dot(vd, sunDir), 0.), 4.);
      vTw = (0.45 + 0.55 * sin(time * (1. + seed.x * 2.) + seed.y * 30.)) * fwd * (0.4 + seed.z);
      gl_PointSize = clamp(size * (0.5 + seed.x) / -mv.z, 1.0, 40.0);
    }`,
  fragmentShader: `
    uniform vec3 sunColor; uniform float amount; varying float vLit; varying float vTw;
    void main(){
      float d = length(gl_PointCoord - 0.5);
      float a = smoothstep(0.5, 0.1, d);
      gl_FragColor = vec4(sunColor * (vLit * 0.45 + 0.004) * vTw * a * amount, 1.0);
    }`,
});
const dust = new THREE.Points(dustGeo, dustMat);
dust.frustumCulled = false;
dust.layers.set(2);
scene.add(dust);

// ------------------------------------------------------------------ render targets + passes
// render scale adapts to the GPU: drops when frames run long, recovers when there is headroom
let renderScale = 1;
const W = () => Math.floor(innerWidth * DPR * renderScale), H = () => Math.floor(innerHeight * DPR * renderScale);
const hdr = { type: THREE.HalfFloatType };
const sceneRT = new THREE.WebGLRenderTarget(W(), H(), { ...hdr, samples: LOW ? 0 : 4, depthTexture: new THREE.DepthTexture(W(), H()) });
const compRT = new THREE.WebGLRenderTarget(W(), H(), hdr);
const volRT = new THREE.WebGLRenderTarget(W() >> 1, H() >> 1, hdr);
const volRT2 = new THREE.WebGLRenderTarget(W() >> 1, H() >> 1, hdr);

const volMat = volumeAOMaterial(LOW ? 16 : 32);
volMat.uniforms.maxDist.value = 22;
const blurMat = blurMaterial();
const compMat = compositeMaterial(LOW ? 6 : 12);
const lensMat = lensMaterial(LOW ? 16 : 40);
const volQuad = new FullScreenQuad(volMat), blurQuad = new FullScreenQuad(blurMat);
const compQuad = new FullScreenQuad(compMat), lensQuad = new FullScreenQuad(lensMat);
const bloom = new UnrealBloomPass(new THREE.Vector2(W(), H()), 0.14, 0.4, 2.5);

for (const m of [blurMat, lensMat]) { m.uniforms.near.value = camera.near; m.uniforms.far.value = camera.far; }

function onResize() {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setPixelRatio(DPR * renderScale);
  renderer.setSize(innerWidth, innerHeight);
  sceneRT.setSize(W(), H());
  compRT.setSize(W(), H());
  volRT.setSize(W() >> 1, H() >> 1);
  volRT2.setSize(W() >> 1, H() >> 1);
  bloom.setSize(W(), H());
  volMat.uniforms.resolution.value.set(W() >> 1, H() >> 1);
  lensMat.uniforms.resolution.value.set(W(), H());
}
addEventListener('resize', onResize);
onResize();

// ------------------------------------------------------------------ sun / time of day
const params = {
  time: 0.35, playing: true, speed: 1 / 160,
  rays: 1, aperture: 3, motionBlur: 1, dust: 1, vignette: 0.45,
};
let EXPOSURE = 1.45;
const sunDir = new THREE.Vector3();
const sunCol = new THREE.Color();
const skyCol = new THREE.Color();
let lastEnvEl = 999;
const elevationAt = (t) => THREE.MathUtils.lerp(58, -5, t);

function sunState(t) {
  const el = elevationAt(t);                              // degrees above horizon
  const az = THREE.MathUtils.lerp(48, 18, t);             // swings toward due west (-x) as it sets
  const e = THREE.MathUtils.degToRad(el), a = THREE.MathUtils.degToRad(az);
  sunDir.set(-Math.cos(a) * Math.cos(e), Math.sin(e), Math.sin(a) * Math.cos(e)).normalize();
  // Kasten–Young air mass → per-channel extinction gives the white→gold→red ramp
  const m = 1 / (Math.sin(Math.max(e, 0.004)) + 0.50572 * Math.pow(Math.max(el, 0) + 6.07995, -1.6364));
  sunCol.setRGB(Math.exp(-0.03 * m), Math.exp(-0.095 * m), Math.exp(-0.25 * m));
  const above = THREE.MathUtils.smoothstep(el, -2.5, 1.5);
  return { el, above };
}

function applySun(t) {
  const { el, above } = sunState(t);
  for (const s of [sky, envSky]) {
    const u = s.material.uniforms;
    u.sunPosition.value.copy(sunDir);
    u.turbidity.value = THREE.MathUtils.lerp(2.6, 6.5, t);
    u.rayleigh.value = THREE.MathUtils.lerp(1.4, 4.0, t);
    u.mieCoefficient.value = 0.005;
    u.mieDirectionalG.value = 0.8;
  }
  skyGain.value = THREE.MathUtils.lerp(0.5, 2.2, THREE.MathUtils.smoothstep(t, 0.45, 1.0));

  const dusk = THREE.MathUtils.smoothstep(t, 0.78, 1.0);
  sun.intensity = 4.2 * above;
  sun.color.copy(sunCol);
  sun.position.copy(sunTarget.position).addScaledVector(sunDir, 35);

  skyCol.setRGB(0.55, 0.66, 0.86).lerp(new THREE.Color(0.85, 0.55, 0.42), t).multiplyScalar(THREE.MathUtils.lerp(1, 0.25, dusk));
  const day = THREE.MathUtils.lerp(1.0, 0.25, dusk);
  for (const l of openingLights) {
    l.color.copy(skyCol).lerp(sunCol, 0.45);
    l.intensity = 1.1 * day;
  }
  hemi.color.copy(skyCol).lerp(sunCol, 0.4);
  hemi.intensity = THREE.MathUtils.lerp(0.05, 0.02, dusk);

  const lightBoost = roomLightsOn ? 3.5 : 0;
  for (const l of roomLights) l.intensity = Math.max(THREE.MathUtils.lerp(0, 3.0, dusk), lightBoost);
  for (const m of emissiveMats.lamp) m.emissiveIntensity = Math.max(dusk * 0.9, roomLightsOn ? 1.5 : 0);
  for (const m of emissiveMats.cove) m.emissiveIntensity = Math.max(dusk * 2.2, roomLightsOn ? 2.8 : 0);

  cloudMat.uniforms.sunDir.value.copy(sunDir);
  cloudMat.uniforms.sunColor.value.copy(sunCol).multiplyScalar(4.5 * Math.max(above, 0.15));
  cloudMat.uniforms.skyColor.value.copy(skyCol).multiplyScalar(1.6);
  scene.fog.color.copy(skyCol).lerp(sunCol, 0.5).multiplyScalar(1.2);

  const shaft = new THREE.Color().copy(sunCol).multiplyScalar(sun.intensity);
  compMat.uniforms.sunColor.value.copy(shaft);
  dustMat.uniforms.sunColor.value.copy(shaft).multiplyScalar(0.55);
  dustMat.uniforms.sunDir.value.copy(sunDir);
  volMat.uniforms.sunDir.value.copy(sunDir);

  if (Math.abs(el - lastEnvEl) > 0.4) {
    lastEnvEl = el;
    const next = pmrem.fromScene(envScene, 0, 0.1, 200);
    scene.environment = next.texture;
    if (envRT) envRT.dispose();
    envRT = next;
  }
}

// ------------------------------------------------------------------ first-person walking
const keys = {};
let yaw = -0.35, pitch = -0.05, tYaw = yaw, tPitch = pitch;
const pos = new THREE.Vector3(-1.9, 0, 3.0);
const vel = new THREE.Vector3();
let bobPhase = 0;
let EYE = 1.62;
const R = 0.22;
const [WX0, WX1, WZ0, WZ1] = colliders.walk;
function free(x, z) {
  if (x < WX0 || x > WX1 || z < WZ0 || z > WZ1) return false;
  for (const [x0, x1, z0, z1] of colliders.boxes) if (x > x0 - R && x < x1 + R && z > z0 - R && z < z1 + R) return false;
  return true;
}
// nudge the start point out of any collider
for (let i = 0; i < 40 && !free(pos.x, pos.z); i++) pos.x += 0.1;

addEventListener('keydown', (e) => {
  keys[e.code] = true;
  if (e.code === 'KeyT') setPlaying(!params.playing);
  if (e.code === 'KeyH') document.body.classList.toggle('hide-ui');
});
addEventListener('keyup', (e) => { keys[e.code] = false; });
let dragging = false;
canvas.addEventListener('pointerdown', (e) => {
  if (document.pointerLockElement !== canvas) {
    canvas.requestPointerLock?.();
    dragging = true;
    canvas.setPointerCapture(e.pointerId);
  }
});
canvas.addEventListener('pointerup', () => { dragging = false; });
document.addEventListener('pointerlockchange', () => {
  document.body.classList.toggle('locked', document.pointerLockElement === canvas);
});
addEventListener('mousemove', (e) => {
  if (document.pointerLockElement !== canvas && !dragging) return;
  tYaw -= e.movementX * 0.0021;
  tPitch = THREE.MathUtils.clamp(tPitch - e.movementY * 0.0021, -1.45, 1.45);
});

function updatePlayer(dt) {
  const k = 1 - Math.exp(-dt * 12);
  yaw += (tYaw - yaw) * k;
  pitch += (tPitch - pitch) * k;
  const f = (keys.KeyW || keys.ArrowUp ? 1 : 0) - (keys.KeyS || keys.ArrowDown ? 1 : 0);
  const s = (keys.KeyD || keys.ArrowRight ? 1 : 0) - (keys.KeyA || keys.ArrowLeft ? 1 : 0);
  const speed = keys.ShiftLeft || keys.ShiftRight ? 2.8 : 1.5;
  const want = new THREE.Vector3(s, 0, -f);
  if (want.lengthSq() > 0) want.normalize().multiplyScalar(speed).applyAxisAngle(THREE.Object3D.DEFAULT_UP, yaw);
  vel.lerp(want, 1 - Math.exp(-dt * 7));
  const nx = pos.x + vel.x * dt, nz = pos.z + vel.z * dt;
  if (free(nx, pos.z)) pos.x = nx; else vel.x = 0;
  if (free(pos.x, nz)) pos.z = nz; else vel.z = 0;
  const sp = Math.hypot(vel.x, vel.z);
  bobPhase += sp * dt * 5.2;
  camera.position.set(pos.x, 0.05 + EYE + Math.sin(bobPhase * 2) * 0.018 * Math.min(sp, 1), pos.z);
  camera.rotation.set(pitch, yaw, Math.sin(bobPhase) * 0.004 * Math.min(sp, 1), 'YXZ');
}

// ------------------------------------------------------------------ autofocus
const ray = new THREE.Raycaster();
let focus = 3, focusTarget = 3, frame = 0;
function updateFocus(dt) {
  if (frame % 6 === 0) {
    ray.setFromCamera({ x: 0, y: 0 }, camera);
    ray.far = 80;
    const hit = ray.intersectObjects(focusTargets, false)[0];
    focusTarget = hit ? hit.distance : 80;
  }
  focus += (focusTarget - focus) * (1 - Math.exp(-dt * 3.5));
}

// ------------------------------------------------------------------ UI
function bindRange(id, key, fmt) {
  const el = $(id), out = $(id + '-v');
  const show = () => { if (out) out.textContent = fmt(params[key]); };
  el.value = params[key];
  el.addEventListener('input', () => { params[key] = parseFloat(el.value); show(); });
  show();
  return { el, show };
}
const timeCtl = bindRange('time', 'time', (v) => {
  const el = elevationAt(v);
  return el > 35 ? 'Afternoon' : el > 12 ? 'Late afternoon' : el > 3 ? 'Golden hour' : el > -1.5 ? 'Sunset' : 'Dusk';
});
bindRange('rays', 'rays', (v) => Math.round(v * 100) + '%');
bindRange('aperture', 'aperture', (v) => v < 0.5 ? 'off' : 'f/' + (22 / Math.sqrt(v * 1.6)).toFixed(1));
bindRange('mblur', 'motionBlur', (v) => Math.round(v * 100) + '%');
bindRange('dust', 'dust', (v) => Math.round(v * 100) + '%');
bindRange('vignette', 'vignette', (v) => Math.round(v * 100) + '%');
function setPlaying(p) {
  params.playing = p;
  $('play').textContent = p ? 'Pause sun' : 'Play sun';
}
$('play').addEventListener('click', () => setPlaying(!params.playing));
setPlaying(true);
let roomLightsOn = false;

const floorPicker = $('floor-picker');
const wallPicker = $('wall-picker');

function setFloorStyle(style) {
  const hexMap = {
    terracotta: '#c45a30',
    marble: '#f2f2f0',
    beige: '#e8dcce',
    wood: '#b8642c',
    slate: '#35383d',
  };
  if (floorPicker && hexMap[style]) floorPicker.value = hexMap[style];
  for (const m of floorMaterials) {
    if (style === 'terracotta') {
      m.map = TX.terracotta;
      m.roughnessMap = TX.terracottaRough;
      m.color.setHex(0xffffff);
      m.roughness = 0.9;
    } else if (style === 'marble') {
      m.map = TX.marble;
      m.roughnessMap = TX.marbleRough;
      m.color.setHex(0xffffff);
      m.roughness = 0.18;
    } else if (style === 'beige') {
      m.map = TX.floor;
      m.roughnessMap = TX.floorRough;
      m.color.setHex(0xffffff);
      m.roughness = 0.35;
    } else if (style === 'wood') {
      m.map = TX.wood;
      m.roughnessMap = TX.woodRough;
      m.color.setHex(0xb8642c);
      m.roughness = 0.45;
    } else if (style === 'slate') {
      m.map = TX.concrete;
      m.roughnessMap = null;
      m.color.setHex(0x35383d);
      m.roughness = 0.65;
    }
    m.needsUpdate = true;
  }
}

function setWallColor(colorKey) {
  const colors = {
    cream: '#f0dfc4',
    white: '#f5f5f5',
    sage: '#8fa88c',
    sand: '#d6c0a0',
    charcoal: '#3e4042',
  };
  const hex = colors[colorKey] || '#f0dfc4';
  if (wallPicker) wallPicker.value = hex;
  for (const m of wallMaterials) {
    m.color.set(hex);
    m.needsUpdate = true;
  }
}

if (floorPicker) {
  floorPicker.addEventListener('input', (e) => {
    for (const m of floorMaterials) {
      m.color.set(e.target.value);
      m.needsUpdate = true;
    }
  });
}

if (wallPicker) {
  wallPicker.addEventListener('input', (e) => {
    for (const m of wallMaterials) {
      m.color.set(e.target.value);
      m.needsUpdate = true;
    }
  });
}

const btnLights = $('btn-lights');
if (btnLights) {
  btnLights.addEventListener('click', () => {
    roomLightsOn = !roomLightsOn;
    btnLights.textContent = roomLightsOn ? '💡 Lights: ON' : '💡 Lights: OFF';
    btnLights.style.background = roomLightsOn ? 'rgba(233,180,106,.45)' : 'rgba(233,180,106,.14)';
    applySun(params.time);
  });
}

const floorSelect = $('floor-select');
if (floorSelect) {
  floorSelect.addEventListener('change', (e) => setFloorStyle(e.target.value));
}

const wallSelect = $('wall-select');
if (wallSelect) {
  wallSelect.addEventListener('change', (e) => setWallColor(e.target.value));
}

$('enter').addEventListener('click', () => {
  document.body.classList.add('started');
  canvas.requestPointerLock?.();
});

// room teleports
const SPOTS = {
  court: [-1.9, 3.0, -0.35, -0.05], hall: [-2.6, -2.4, 0.1, -0.08], room1: [1.2, -2.2, -0.75, -0.1],
  room2: [1.8, 1.9, -1.9, -0.1], room3: [1.7, 3.6, -1.9, -0.1], wash: [-4.3, 1.9, 1.2, -0.15],
};
document.querySelectorAll('[data-spot]').forEach((b) => b.addEventListener('click', () => {
  const [x, z, yw, pt] = SPOTS[b.dataset.spot];
  pos.set(x, 0, z); vel.set(0, 0, 0);
  yaw = tYaw = yw; pitch = tPitch = pt;
}));

if (URLP.has('shot')) {
  document.body.classList.add('started', 'hide-ui');
  setPlaying(false);
  if (URLP.has('t')) params.time = parseFloat(URLP.get('t'));
  if (URLP.has('pos')) { const [x, z] = URLP.get('pos').split(',').map(Number); pos.set(x, 0, z); }
  if (URLP.has('yaw')) yaw = tYaw = parseFloat(URLP.get('yaw'));
  if (URLP.has('pitch')) pitch = tPitch = parseFloat(URLP.get('pitch'));
  if (URLP.has('eye')) EYE = parseFloat(URLP.get('eye'));
  for (const k of Object.keys(params)) if (URLP.has(k) && k !== 'time') params[k] = parseFloat(URLP.get(k));
  if (URLP.has('exp')) EXPOSURE = parseFloat(URLP.get('exp'));
}

// ------------------------------------------------------------------ frame loop
const clock = new THREE.Clock();
const prevVP = new THREE.Matrix4();
let dir = 1;
applySun(params.time);

function render() {
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  frame++;

  if (params.playing) {
    params.time += dir * dt * params.speed;
    if (params.time > 1) { params.time = 1; dir = -1; }
    if (params.time < 0.2) { params.time = 0.2; dir = 1; }
    timeCtl.el.value = params.time;
    if (frame % 10 === 0) timeCtl.show();
  }
  applySun(params.time);
  updatePlayer(dt);
  updateFocus(dt);
  camera.updateMatrixWorld();
  for (const f of fans) f.rotation.y += dt * 9;

  cloudMat.uniforms.time.value = t;
  dustMat.uniforms.time.value = t;
  dustMat.uniforms.amount.value = params.dust;

  // 1. light-space depth (layer 0 = house geometry only)
  lightCam.position.copy(sun.position);
  lightCam.lookAt(sunTarget.position);
  lightCam.updateMatrixWorld();
  lightVP.multiplyMatrices(lightCam.projectionMatrix, lightCam.matrixWorldInverse);
  scene.overrideMaterial = depthOverride;
  renderer.setRenderTarget(lightRT);
  renderer.clear();
  renderer.render(scene, lightCam);
  scene.overrideMaterial = null;

  // 2. HDR scene
  renderer.shadowMap.needsUpdate = true;
  renderer.setRenderTarget(sceneRT);
  renderer.clear();
  renderer.render(scene, camera);

  // 3. sun shafts + AO at half res, then depth-aware blur
  const vu = volMat.uniforms;
  vu.tDepth.value = sceneRT.depthTexture;
  vu.tLightDepth.value = lightRT.depthTexture;
  vu.projInv.value.copy(camera.projectionMatrixInverse);
  vu.viewInv.value.copy(camera.matrixWorld);
  vu.proj.value.copy(camera.projectionMatrix);
  vu.lightVP.value.copy(lightVP);
  vu.camPos.value.copy(camera.position);
  vu.frame.value = frame % 64;
  renderer.setRenderTarget(volRT); volQuad.render(renderer);
  const bu = blurMat.uniforms;
  bu.tDepth.value = sceneRT.depthTexture;
  bu.tInput.value = volRT.texture; bu.dir.value.set(1.6 / volRT.width, 0);
  renderer.setRenderTarget(volRT2); blurQuad.render(renderer);
  bu.tInput.value = volRT2.texture; bu.dir.value.set(0, 1.6 / volRT.height);
  renderer.setRenderTarget(volRT); blurQuad.render(renderer);

  // 4. composite + camera motion blur
  const cu = compMat.uniforms;
  cu.tScene.value = sceneRT.texture;
  cu.tVol.value = volRT.texture;
  cu.tDepth.value = sceneRT.depthTexture;
  cu.projInv.value.copy(camera.projectionMatrixInverse);
  cu.viewInv.value.copy(camera.matrixWorld);
  cu.prevVP.value.copy(prevVP);
  cu.volStrength.value = 0.016 * params.rays;
  cu.mbStrength.value = params.motionBlur;
  renderer.setRenderTarget(compRT); compQuad.render(renderer);
  prevVP.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);

  // 5. bloom (adds into compRT)
  bloom.render(renderer, null, compRT, dt, false);

  // 6. lens: DOF, tonemap, vignette, grain
  const lu = lensMat.uniforms;
  lu.tColor.value = compRT.texture;
  lu.tDepth.value = sceneRT.depthTexture;
  lu.focus.value = focus;
  lu.aperture.value = params.aperture;
  lu.vignette.value = params.vignette;
  lu.exposure.value = EXPOSURE;
  lu.time.value = t;
  renderer.setRenderTarget(null);
  lensQuad.render(renderer);

  adaptQuality(dt);
  requestAnimationFrame(render);
}

let ftAcc = 0, ftN = 0;
function adaptQuality(dt) {
  if (URLP.has('shot') || frame < 60) return;
  ftAcc += dt; ftN++;
  if (ftN < 60) return;
  const avg = ftAcc / ftN;
  ftAcc = ftN = 0;
  const next = avg > 1 / 40 ? Math.max(0.6, renderScale - 0.1) : avg < 1 / 58 ? Math.min(1, renderScale + 0.05) : renderScale;
  if (next !== renderScale) { renderScale = next; onResize(); }
}

document.body.classList.add('ready');
setStatus('Ready');
requestAnimationFrame(render);
window.__debug = { THREE, scene, camera, params, renderer, sun, matCache };
