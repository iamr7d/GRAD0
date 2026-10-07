// PEN News "glass and light" title engine.
// Three.js (MIT). Montserrat Black (SIL OFL 1.1) converted to 3D type at runtime.
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { TTFLoader } from "three/examples/jsm/loaders/TTFLoader.js";
import { Font } from "three/examples/jsm/loaders/FontLoader.js";
import { TextGeometry } from "three/examples/jsm/geometries/TextGeometry.js";
import montserrat from "./montserrat900.ttf";

const clamp01 = x => Math.max(0, Math.min(1, x));
const seg = (t, a, b) => clamp01((t - a) / (b - a));
const outExpo = t => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));
const inOut = t => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const spring = t => 1 - Math.exp(-6.5 * t) * Math.cos(9 * t);   // gentle overshoot that settles
const lerp = THREE.MathUtils.lerp;

let renderer, camera, scene, canvas, running = false, t0 = 0, light;
let letters = [], plates = [], bgMat, logo3d;
const U = { uT: { value: 0 }, uRes: { value: new THREE.Vector2(1, 1) }, uLight: { value: new THREE.Vector3(-.4, .6, .7) } };

// Animated light field, drawn in screen space so the glass can refract the exact same picture.
const BG_FN = `
uniform float uT; uniform vec2 uRes;
float blob(vec2 p, vec2 c, float r){ return exp(-dot(p-c,p-c)/(r*r)); }
vec3 field(vec2 p){
  vec3 col = mix(vec3(.62,.02,.05), vec3(.30,.0,.02), p.y);
  col = mix(col, vec3(1.0,.16,.14), .75*blob(p, vec2(.26+.07*sin(uT*.35), .6+.06*cos(uT*.3)), .2));
  col = mix(col, vec3(.85,.0,.1), .6*blob(p, vec2(.8+.05*cos(uT*.28), .36+.07*sin(uT*.33)), .24));
  col = mix(col, vec3(1.0,.45,.25), .4*blob(p, vec2(.55+.1*sin(uT*.22), .86), .18));
  float d = p.x + p.y*.42;
  col += vec3(1.)*smoothstep(.03,.0,abs(d - (fract(uT*.09)*2.2-.4)))*.42;
  col += vec3(1.)*smoothstep(.01,.0,abs(d - (fract(uT*.09+.4)*2.2-.4)))*.55;
  col += vec3(1.,.9,.92)*smoothstep(.06,.0,abs(d - (fract(uT*.06+.7)*2.2-.4)))*.25;
  return col;
}`;
const BG_VERT = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.9999, 1.); }";
const BG_FRAG = BG_FN + "\nvoid main(){ gl_FragColor = vec4(field(gl_FragCoord.xy/uRes), 1.); }";
const GLASS_VERT = `
varying vec3 vN; varying vec3 vP;
void main(){ vec4 wp = modelMatrix*vec4(position,1.); vP = wp.xyz; vN = normalize(mat3(modelMatrix)*normal); gl_Position = projectionMatrix*viewMatrix*wp; }`;
const GLASS_FRAG = BG_FN + `
uniform float uStrength; uniform float uDisp; uniform vec3 uLight; uniform float uTint; uniform vec3 uCol; uniform float uColAmt;
varying vec3 vN; varying vec3 vP;
void main(){
  vec3 n = normalize(vN); if (!gl_FrontFacing) n = -n;
  vec3 v = normalize(cameraPosition - vP);
  vec2 uv = gl_FragCoord.xy/uRes;
  vec3 rr = refract(-v, n, 1./1.5);
  vec2 off = (rr.xy - (-v).xy) * uStrength;
  vec3 refr = vec3(field(uv + off*(1.-uDisp)).r, field(uv + off).g, field(uv + off*(1.+uDisp)).b);
  float fr = pow(1. - max(dot(n, v), 0.), 2.6);
  vec3 rd = reflect(-v, n);
  vec3 refl = mix(vec3(.78,.82,.9), vec3(1.), smoothstep(-.2, .8, rd.y));
  float spec = pow(max(dot(reflect(-normalize(uLight), n), v), 0.), 90.) * 1.6 + pow(max(dot(reflect(-normalize(uLight), n), v), 0.), 12.) * .12;
  vec3 col = refr * (1. - uTint*fr) + vec3(.03);
  col = mix(col, col*uCol*1.15 + uCol*.42, uColAmt);
  col = mix(col, refl, fr*.75) + vec3(spec);
  gl_FragColor = vec4(col, 1.);
}`;

function makeFont(bin) { const buf = bin.buffer.slice(bin.byteOffset, bin.byteOffset + bin.byteLength); return new Font(new TTFLoader().parse(buf)); }

function build() {
  scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), .03).texture;
  scene.environmentIntensity = .55;

  bgMat = new THREE.ShaderMaterial({ uniforms: U, vertexShader: BG_VERT, fragmentShader: BG_FRAG, depthWrite: false, depthTest: false });
  const bg = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), bgMat); bg.frustumCulled = false; bg.renderOrder = -1; scene.add(bg);

  light = new THREE.DirectionalLight("#ffffff", 1.4); light.position.set(-3, 5, 6); scene.add(light);
  scene.add(new THREE.AmbientLight("#ffffff", .9));

  const glass = new THREE.ShaderMaterial({ uniforms: { ...U, uStrength: { value: .22 }, uDisp: { value: .12 }, uTint: { value: .35 }, uCol: { value: new THREE.Color(1, .02, .03) }, uColAmt: { value: .9 } }, vertexShader: GLASS_VERT, fragmentShader: GLASS_FRAG });

  // the Prime Earth News logo: a red glass block carrying the three lines of type
  const font = makeFont(montserrat);
  const W = 4.4, H = W * 432 / 604, D = .55;
  const logoG = new THREE.Group(); scene.add(logoG);
  const slab = new THREE.Mesh(new RoundedBoxGeometry(W, H, D, 8, .09), glass); logoG.add(slab);
  const white = new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: .28, metalness: 0, envMapIntensity: .7 });
  const black = new THREE.MeshStandardMaterial({ color: "#0d0d0f", roughness: .32, metalness: .1, envMapIntensity: .6 });
  const dark = new THREE.MeshStandardMaterial({ color: "#a10008", roughness: .3, metalness: .05, envMapIntensity: .6 });
  const px = v => v / 604 * W;                       // logo artwork pixels -> scene units
    const size = px(108);                              // em size giving ~100px caps like the artwork
  const mk = (str, mat, sz) => { const g = new TextGeometry(str, { font, size: sz, depth: .12, curveSegments: 12, bevelEnabled: true, bevelThickness: .02, bevelSize: .012, bevelSegments: 3 }); g.computeBoundingBox(); return new THREE.Mesh(g, mat); };
  // fit each line to the artwork's measurements so nothing leaves the red block
  const left = px(32), right = px(32), inner = W - left - right;
  const fit = (m, width) => { const bb = m.geometry.boundingBox, k = width / (bb.max.x - bb.min.x); m.geometry.translate(-bb.min.x, 0, 0); m.geometry.scale(k, k, 1); m.geometry.computeBoundingBox(); return m; };
  const ai = mk(".AI", dark, px(46));
  const aiW = ai.geometry.boundingBox.max.x - ai.geometry.boundingBox.min.x, gap = px(8);
  const lines = [["PRIME", white, 152, inner * .9], ["EARTH", white, 270, inner * .93], ["NEWS", black, 393, inner - aiW - gap]].map(([str, mat, base, w]) => {
    const m = fit(mk(str, mat, size), w); m.position.set(-W / 2 + left, H / 2 - px(base), D / 2 + .005); logoG.add(m); return m;
  });
  ai.geometry.translate(-ai.geometry.boundingBox.min.x, 0, 0);
  ai.position.set(-W / 2 + left + lines[2].geometry.boundingBox.max.x + gap, lines[2].position.y, D / 2 + .005); logoG.add(ai);
  lines.push(ai);
  logoG.position.set(0, .9, 0);
  letters = lines; letters.forEach(m => (m.userData.home = m.position.clone()));
  logo3d = logoG;
  // floating glass layers behind the logo
  const pane = new THREE.ShaderMaterial({ uniforms: { ...U, uStrength: { value: .07 }, uDisp: { value: .06 }, uTint: { value: .1 }, uCol: { value: new THREE.Color(1, 1, 1) }, uColAmt: { value: 0 } }, vertexShader: GLASS_VERT, fragmentShader: GLASS_FRAG });
  [[-4.6, 1.6, -2.4, 4.2, 2.6, .35], [4.3, -1.2, -2.0, 4.6, 2.8, -.3], [.6, 2.6, -3.4, 5.2, 2.2, .12], [-2.2, -2.4, -2.8, 3.6, 2.2, -.2]].forEach(([px, py, pz, w, h, rz], i) => {
    const p = new THREE.Mesh(new RoundedBoxGeometry(w, h, .12, 6, .22), pane);
    p.position.set(px, py, pz); p.rotation.set(.08, -.25 + i * .14, rz); p.userData.base = p.position.clone(); p.userData.rz = rz;
    scene.add(p); plates.push(p);
  });

  camera = new THREE.PerspectiveCamera(28, 16 / 9, .1, 100);
}

function frame(now) {
  if (!running) return;
  requestAnimationFrame(frame);
  const t = (now - t0) / 1000;
  U.uT.value = t + 4;
  // camera: gentle arc from the side to the front, then a slow push
  const a = outExpo(seg(t, 0, 3.2));
  camera.position.set(lerp(4.5, 0, a), lerp(-1.2, .25, a), lerp(13, 11.2, a) - t * .08);
  camera.lookAt(0, .45, 0);
  const sIn = spring(seg(t, .1, 1.9));
  logo3d.rotation.y = lerp(-1.05, 0, sIn) + Math.sin(t * .55) * .05 * seg(t, 2.6, 3.6);
  logo3d.rotation.x = lerp(.45, 0, sIn);
  logo3d.position.z = lerp(-6, 0, outExpo(seg(t, .05, 1.8)));
  letters.forEach((m, i) => {
    const p = seg(t, .8 + i * .16, 1.9 + i * .16), e = outExpo(p);
    m.position.x = m.userData.home.x + lerp(-1.2, 0, e);
    m.position.z = m.userData.home.z + lerp(-.6, 0, e);
    m.visible = p > 0; m.scale.setScalar(lerp(.92, 1, e));
  });
  plates.forEach((p, i) => {
    const e = outExpo(seg(t, .1 + i * .12, 2.4 + i * .12));
    p.position.x = p.userData.base.x * lerp(1.8, 1, e); p.position.y = p.userData.base.y + Math.sin(t * .5 + i) * .08;
    p.rotation.z = p.userData.rz + Math.sin(t * .3 + i) * .04;
  });
  U.uLight.value.set(lerp(-.9, .9, inOut(seg(t, 1.8, 5.2))), .55, .75);
  renderer.render(scene, camera);
}

function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight; if (!w || !h) return;
  renderer.setSize(w, h, false); renderer.getDrawingBufferSize(U.uRes.value); camera.aspect = w / h; camera.updateProjectionMatrix();
}

export function init(el) {
  canvas = el;
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
  build();
  new ResizeObserver(resize).observe(canvas); resize();
  return true;
}
export function play() { t0 = performance.now(); if (!running) { running = true; requestAnimationFrame(frame); } }
export function stop() { running = false; }
