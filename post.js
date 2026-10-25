// Post-processing shaders: volumetric sun shafts + AO (half res), bilateral blur,
// composite with camera motion blur, and final lens (DOF, tonemap, vignette, grain).
import * as THREE from 'three';

const VERT = /* glsl */`
varying vec2 vUv;
void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

const COMMON = /* glsl */`
uniform mat4 projInv;
uniform mat4 viewInv;
vec3 viewPos(vec2 uv, float d){
  vec4 v = projInv * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
  return v.xyz / v.w;
}
float ign(vec2 p){ return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }
`;

export function volumeAOMaterial(steps = 32) {
  return new THREE.ShaderMaterial({
    defines: { STEPS: steps },
    vertexShader: VERT,
    uniforms: {
      tDepth: { value: null }, tLightDepth: { value: null },
      projInv: { value: new THREE.Matrix4() }, viewInv: { value: new THREE.Matrix4() },
      proj: { value: new THREE.Matrix4() }, lightVP: { value: new THREE.Matrix4() },
      camPos: { value: new THREE.Vector3() }, sunDir: { value: new THREE.Vector3() },
      frame: { value: 0 }, maxDist: { value: 16 }, resolution: { value: new THREE.Vector2() },
    },
    fragmentShader: COMMON + /* glsl */`
uniform sampler2D tDepth, tLightDepth;
uniform mat4 proj, lightVP;
uniform vec3 camPos, sunDir;
uniform float frame, maxDist;
uniform vec2 resolution;
varying vec2 vUv;

float hg(float c, float g){ float g2 = g * g; return (1.0 - g2) / pow(1.0 + g2 - 2.0 * g * c, 1.5); }

float sunVis(vec3 p){
  vec4 lc = lightVP * vec4(p, 1.0);
  vec3 l = lc.xyz / lc.w * 0.5 + 0.5;
  if (any(lessThan(l.xy, vec2(0.0))) || any(greaterThan(l.xy, vec2(1.0)))) return 1.0;
  return step(l.z - 0.0015, texture2D(tLightDepth, l.xy).x);
}

void main(){
  float d = texture2D(tDepth, vUv).x;
  vec3 vp = viewPos(vUv, d);
  vec3 wp = (viewInv * vec4(vp, 1.0)).xyz;
  vec3 ray = wp - camPos;
  float dist = length(ray);
  vec3 rd = ray / dist;
  float L = min(dist, maxDist);
  const int N = STEPS;
  float stepL = L / float(N);
  float j = ign(gl_FragCoord.xy + frame * 5.588238);
  float acc = 0.0;
  for (int i = 0; i < N; i++) {
    vec3 p = camPos + rd * ((float(i) + j) * stepL);
    // dusty air inside the house footprint (rooms + open court), thin haze outside
    float dens = (abs(p.x) < 6.1 && abs(p.z) < 6.6 && p.y > 0.0 && p.y < 3.4) ? 1.0 : 0.05;
    acc += sunVis(p) * dens;
  }
  float c = dot(rd, sunDir);
  float phase = 0.55 * hg(c, 0.72) * 0.08 + 0.45 * hg(c, 0.2);
  float vol = acc * stepL * phase;

  // depth-only AO
  float ao = 1.0;
  if (d < 1.0) {
    vec3 N3 = normalize(cross(dFdx(vp), dFdy(vp)));
    float r = 0.32;
    float sr = r * proj[1][1] / (-vp.z) * 0.5;
    float occ = 0.0;
    for (int i = 0; i < 12; i++) {
      float a = (float(i) + j) * 2.39996 + j * 6.283;
      float rr = sqrt((float(i) + 0.5) / 12.0) * sr;
      vec2 suv = vUv + vec2(cos(a), sin(a)) * rr * vec2(resolution.y / resolution.x, 1.0);
      vec3 sp = viewPos(suv, texture2D(tDepth, suv).x);
      vec3 v = sp - vp;
      float vl = length(v);
      occ += max(0.0, dot(v / max(vl, 1e-4), N3) - 0.12) * (1.0 - clamp(vl / r, 0.0, 1.0));
    }
    ao = clamp(1.0 - occ / 12.0 * 2.2, 0.0, 1.0);
  }
  gl_FragColor = vec4(vol, ao, 0.0, 1.0);
}`,
  });
}

export function blurMaterial() {
  return new THREE.ShaderMaterial({
    vertexShader: VERT,
    uniforms: {
      tInput: { value: null }, tDepth: { value: null }, dir: { value: new THREE.Vector2() },
      near: { value: 0.05 }, far: { value: 1000 },
    },
    fragmentShader: /* glsl */`
uniform sampler2D tInput, tDepth;
uniform vec2 dir;
uniform float near, far;
varying vec2 vUv;
float lin(float d){ return near * far / (far - d * (far - near)); }
void main(){
  float z0 = lin(texture2D(tDepth, vUv).x);
  vec4 sum = vec4(0.0); float ws = 0.0;
  for (int i = -4; i <= 4; i++) {
    vec2 uv = vUv + dir * float(i);
    float w = exp(-float(i * i) / 10.0);
    float z = lin(texture2D(tDepth, uv).x);
    w *= exp(-abs(z - z0) / (0.05 * z0 + 0.02));
    sum += texture2D(tInput, uv) * w; ws += w;
  }
  gl_FragColor = sum / ws;
}`,
  });
}

export function compositeMaterial(taps = 12) {
  return new THREE.ShaderMaterial({
    defines: { TAPS: taps },
    vertexShader: VERT,
    uniforms: {
      tScene: { value: null }, tVol: { value: null }, tDepth: { value: null },
      projInv: { value: new THREE.Matrix4() }, viewInv: { value: new THREE.Matrix4() },
      prevVP: { value: new THREE.Matrix4() },
      sunColor: { value: new THREE.Color() }, volStrength: { value: 1 },
      aoStrength: { value: 0.85 }, mbStrength: { value: 1 },
    },
    fragmentShader: COMMON + /* glsl */`
uniform sampler2D tScene, tVol, tDepth;
uniform mat4 prevVP;
uniform vec3 sunColor;
uniform float volStrength, aoStrength, mbStrength;
varying vec2 vUv;
vec3 shade(vec2 uv){
  vec3 c = texture2D(tScene, uv).rgb;
  vec2 va = texture2D(tVol, uv).xy;
  c *= mix(1.0, va.y, aoStrength);
  return c + va.x * sunColor * volStrength;
}
void main(){
  float d = texture2D(tDepth, vUv).x;
  vec3 wp = (viewInv * vec4(viewPos(vUv, d), 1.0)).xyz;
  vec4 pc = prevVP * vec4(wp, 1.0);
  vec2 puv = pc.xy / pc.w * 0.5 + 0.5;
  vec2 vel = (vUv - puv) * mbStrength;
  float l = length(vel);
  if (l > 0.06) vel *= 0.06 / l;
  vec3 col;
  if (l * mbStrength < 0.0008) col = shade(vUv);
  else {
    col = vec3(0.0);
    float j = ign(gl_FragCoord.xy);
    for (int i = 0; i < TAPS; i++) col += shade(vUv - vel * ((float(i) + j) / float(TAPS) - 0.5));
    col /= float(TAPS);
  }
  gl_FragColor = vec4(col, 1.0);
}`,
  });
}

export function lensMaterial(taps = 40) {
  return new THREE.ShaderMaterial({
    defines: { TAPS: taps },
    vertexShader: VERT,
    uniforms: {
      tColor: { value: null }, tDepth: { value: null },
      near: { value: 0.05 }, far: { value: 1000 }, focus: { value: 2 }, aperture: { value: 12 },
      exposure: { value: 1 }, vignette: { value: 0.45 }, time: { value: 0 },
      resolution: { value: new THREE.Vector2() },
    },
    fragmentShader: /* glsl */`
uniform sampler2D tColor, tDepth;
uniform float near, far, focus, aperture, exposure, vignette, time;
uniform vec2 resolution;
varying vec2 vUv;
const float MAXC = 16.0;
float lin(float d){ return near * far / (far - d * (far - near)); }
float coc(float z){ return min(aperture * abs(1.0 / focus - 1.0 / z) * resolution.y / 1080.0 * 3.0, MAXC); }
vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
vec3 toSRGB(vec3 c){ return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
float h12(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main(){
  vec2 px = 1.0 / resolution;
  float z0 = lin(texture2D(tDepth, vUv).x);
  float r0 = coc(z0);
  vec3 col = texture2D(tColor, vUv).rgb;
  if (r0 > 0.6) {
    vec3 acc = col; float ws = 1.0;
    for (int i = 0; i < TAPS; i++) {
      float fi = float(i) + 0.5;
      float r = sqrt(fi / float(TAPS)) * r0;
      float a = fi * 2.39996;
      vec2 uv = vUv + vec2(cos(a), sin(a)) * r * px;
      float z = lin(texture2D(tDepth, uv).x);
      float rs = coc(z);
      float w = z >= z0 - 0.05 ? 1.0 : clamp(rs - r + 1.0, 0.0, 1.0);
      vec3 s = texture2D(tColor, uv).rgb;
      w *= 1.0 + 0.6 * smoothstep(1.5, 6.0, dot(s, vec3(0.3, 0.6, 0.1)));  // bokeh highlights
      acc += s * w; ws += w;
    }
    col = acc / ws;
  }
  col *= exposure;
  col = aces(col);
  // grade: a touch of saturation, warm highlights, lifted cool-free blacks
  float luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
  col = max(mix(vec3(luma), col, 1.22), 0.0);
  col *= mix(vec3(1.0), vec3(1.04, 1.0, 0.92), smoothstep(0.2, 0.9, luma));
  col = col * 0.97 + vec3(0.012, 0.009, 0.006);
  vec2 q = (vUv - 0.5) * vec2(resolution.x / resolution.y, 1.0);
  col *= mix(1.0, smoothstep(1.15, 0.25, length(q)), vignette);
  col = toSRGB(col);
  col += (h12(vUv * resolution + fract(time) * 100.0) - 0.5) * 0.018;
  gl_FragColor = vec4(col, 1.0);
}`,
  });
}
