/*
 * Scranno, l'Aula in prima persona.
 *
 * Usa il motore di produzione (scranno/src/three e scranno/src/data/layout): la stessa
 * Aula di Basile, le stesse sedie, la stessa vista dal seggio. Qui cambia solo il
 * contorno: niente Transatlantico, niente post-processing, disegno su richiesta,
 * colori dei seggi dalle variabili CSS della famiglia (nessun colore di gruppo).
 *
 * Build: node ecosistema/scranno/3d/build.mjs  →  ecosistema/scranno/aula3d.js
 * API: window.Aula3D.supported(), window.Aula3D.mount(el, opzioni) → Promise<controllo>
 */
import * as THREE from 'three';
import { buildAula } from '../../../../scranno/src/three/aula';
import { createMaterials } from '../../../../scranno/src/three/materials';
import { chairFrame, chairUpholstery, consoleGeometry, micGeometry, tallChairFrame, tallChairUpholstery } from '../../../../scranno/src/three/chair';
import { seatView } from '../../../../scranno/src/three/eye';
import { walkVector } from '../../../../scranno/src/three/walk';
import { DESK, ROOM, buildHemicycle, type Seat } from '../../../../scranno/src/data/layout';

type Stato = 'scelto' | 'vuoto' | 'vuotoVoto' | 'neutro' | 'spento' | 'acceso' | 'favor' | 'against' | 'abstain' | 'absent' | 'nd';

interface SeggioAula { p?: number; k: string; id?: string; g?: string }
interface Seggi3D { rows: number; rowRadii: number[]; settori: string[]; s: [number, number, number, number][] }

interface Opzioni {
  seggi: SeggioAula[];
  piano: Seggi3D;
  onHover?: (i: number | null, x: number, y: number) => void;
  onPick?: (i: number) => void;
  onAvviso?: (testo: string) => void;
  onVista?: (cambiata: boolean) => void;
  ridotto?: boolean;
}

const KIND: Record<string, Seat['kind']> = { d: 'deputato', p: 'presidenza', g: 'governo', c: 'comitato', a: 'aggiuntivo' };
const TALL: Seat['kind'][] = ['presidenza', 'governo'];
const EYE = 1.62;
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const frame = () => new Promise<void>((r) => requestAnimationFrame(() => r()));

/* ---------- colori dalle variabili CSS ---------- */

const sonda = (() => {
  let ctx: CanvasRenderingContext2D | null = null;
  return (css: string, fallback: string): THREE.Color => {
    try {
      if (!ctx) {
        const c = document.createElement('canvas');
        c.width = c.height = 1;
        ctx = c.getContext('2d', { willReadFrequently: true });
      }
      if (!ctx || !css) return new THREE.Color(fallback);
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = fallback;
      ctx.fillStyle = css;
      ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      return new THREE.Color().setRGB(d[0]! / 255, d[1]! / 255, d[2]! / 255, THREE.SRGBColorSpace);
    } catch {
      return new THREE.Color(fallback);
    }
  };
})();

function scuro(): boolean {
  const t = document.documentElement.getAttribute('data-theme');
  if (t) return t === 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function leggiPalette(): Record<Stato, THREE.Color> & { carta: THREE.Color } {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string, f: string) => sonda(cs.getPropertyValue(n).trim(), f);
  const neutro = new THREE.Color('#5b4742');
  return {
    scelto: new THREE.Color('#f6f1e4'),
    vuoto: new THREE.Color(scuro() ? '#6f6a63' : '#bdb8ad'),
    vuotoVoto: new THREE.Color('#3a3230'),
    neutro,
    spento: new THREE.Color('#2f2926'),
    acceso: v('--accento', '#167a68'),
    favor: v('--voto-si', '#1f7a55'),
    against: v('--voto-no', '#b4442c'),
    abstain: v('--voto-ast', '#b88a1e'),
    absent: v('--voto-ass', '#c9c7bf'),
    nd: neutro.clone(),
    carta: v('--carta', '#f6f5f1'),
  };
}

/* ---------- sedie ---------- */

function instanced(geo: THREE.BufferGeometry, mat: THREE.Material, seats: Seat[], name: string, offset?: () => THREE.Vector3): THREE.InstancedMesh {
  const mesh = new THREE.InstancedMesh(geo, mat, Math.max(1, seats.length));
  mesh.name = name;
  mesh.count = seats.length;
  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const one = new THREE.Vector3(1, 1, 1);
  seats.forEach((s, i) => {
    q.setFromAxisAngle(up, s.yaw);
    const p = new THREE.Vector3(s.x, s.y, s.z);
    if (offset) p.add(offset().applyQuaternion(q));
    mesh.setMatrixAt(i, m.compose(p, q, one));
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.computeBoundingSphere();
  return mesh;
}

class Sedie {
  readonly group = new THREE.Group();
  readonly pick: THREE.InstancedMesh;
  readonly anello: THREE.Mesh;
  readonly sopra: THREE.Mesh;
  private readonly normalIdx: number[] = [];
  private readonly tallIdx: number[] = [];
  private readonly normal: THREE.InstancedMesh;
  private readonly tall: THREE.InstancedMesh;
  private readonly strisce: THREE.InstancedMesh;
  private readonly strisciaSeggio: number[] = [];
  private readonly cur: THREE.Color[];
  private readonly goal: THREE.Color[];
  private fermo = false;

  constructor(readonly seats: Seat[], occupato: (i: number) => boolean) {
    const uph = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.8 });
    const telaio = new THREE.MeshStandardMaterial({ color: '#4a3a30', roughness: 0.5 });
    seats.forEach((s, i) => (TALL.includes(s.kind) ? this.tallIdx : this.normalIdx).push(i));
    const n = this.normalIdx.map((i) => seats[i]!);
    const t = this.tallIdx.map((i) => seats[i]!);
    this.normal = instanced(chairUpholstery(), uph, n, 'sedie');
    this.tall = instanced(tallChairUpholstery(), uph, t, 'sedie-alte');
    this.group.add(this.normal, this.tall, instanced(chairFrame(), telaio, n, 'telai'), instanced(tallChairFrame(), telaio, t, 'telai-alti'));

    const proxy = new THREE.BoxGeometry(0.56, 1.15, 0.56).translate(0, 0.58, 0);
    this.pick = instanced(proxy, new THREE.MeshBasicMaterial({ visible: false }), seats, 'seggi-pick');
    this.pick.castShadow = false;
    this.pick.layers.set(1);
    this.group.add(this.pick);

    const banco = seats.filter((s) => s.kind === 'deputato');
    const cons = instanced(consoleGeometry(), new THREE.MeshStandardMaterial({ color: '#2e302f', roughness: 0.7, metalness: 0.2 }), banco, 'console', () => new THREE.Vector3(-0.08, DESK.top, (DESK.front + DESK.back) / 2 + 0.02));
    const mic = instanced(micGeometry(), new THREE.MeshStandardMaterial({ color: '#6b6f6c', roughness: 0.45, metalness: 0.6 }), banco, 'microfoni', () => new THREE.Vector3(0.14, DESK.top, DESK.back + 0.03));
    cons.castShadow = false;
    this.group.add(cons, mic);
    // striscia sul fronte del banco: lo stato del seggio si legge anche da lontano
    const occ = seats.filter((s) => s.kind === 'deputato' && occupato(s.index));
    occ.forEach((s) => this.strisciaSeggio.push(s.index));
    this.strisce = instanced(new THREE.BoxGeometry(0.42, 0.08, 0.012), new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.6 }), occ, 'strisce', () => new THREE.Vector3(0, DESK.top - 0.09, DESK.front + 0.008));
    this.strisce.castShadow = false;
    this.group.add(this.strisce);

    this.cur = seats.map(() => new THREE.Color('#5b4742'));
    this.goal = this.cur.map((c) => c.clone());

    const ring = new THREE.RingGeometry(0.2, 0.3, 48);
    ring.rotateX(-Math.PI / 2);
    this.anello = new THREE.Mesh(ring, new THREE.MeshBasicMaterial({ color: '#167a68', transparent: true, opacity: 0.95, depthWrite: false, toneMapped: false, side: THREE.DoubleSide }));
    this.anello.renderOrder = 2;
    this.anello.visible = false;
    const ring2 = new THREE.RingGeometry(0.34, 0.4, 40);
    ring2.rotateX(-Math.PI / 2);
    this.sopra = new THREE.Mesh(ring2, new THREE.MeshBasicMaterial({ color: '#12171a', transparent: true, opacity: 0.55, depthWrite: false, toneMapped: false }));
    this.sopra.renderOrder = 2;
    this.sopra.visible = false;
    this.group.add(this.anello, this.sopra);
  }

  imposta(colori: THREE.Color[], subito: boolean): void {
    colori.forEach((c, i) => this.goal[i]!.copy(c));
    if (subito) this.cur.forEach((c, i) => c.copy(this.goal[i]!));
    this.fermo = false;
    this.scrivi();
  }

  segna(mesh: THREE.Mesh, i: number | null, alto = 0.02): void {
    const s = i === null ? undefined : this.seats[i];
    mesh.visible = !!s;
    if (s) mesh.position.set(s.x, s.y + alto, s.z);
  }

  /** true finché i colori stanno ancora sfumando */
  update(dt: number): boolean {
    if (this.fermo) return false;
    const k = 1 - Math.exp(-dt * 12);
    let muove = false;
    for (let i = 0; i < this.cur.length; i++) {
      const c = this.cur[i]!;
      const t = this.goal[i]!;
      if (Math.abs(c.r - t.r) + Math.abs(c.g - t.g) + Math.abs(c.b - t.b) > 0.003) {
        c.lerp(t, k);
        muove = true;
      } else c.copy(t);
    }
    this.scrivi();
    this.fermo = !muove;
    return muove;
  }

  private scrivi(): void {
    this.normalIdx.forEach((s, i) => this.normal.setColorAt(i, this.cur[s]!));
    this.tallIdx.forEach((s, i) => this.tall.setColorAt(i, this.cur[s]!));
    this.strisciaSeggio.forEach((s, i) => this.strisce.setColorAt(i, this.cur[s]!));
    for (const m of [this.normal, this.tall, this.strisce]) if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }
}

/* ---------- supporto ---------- */

function supported(): boolean {
  try {
    const c = document.createElement('canvas');
    const gl = window.WebGL2RenderingContext ? c.getContext('webgl2') : null;
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
    return !!gl;
  } catch {
    return false;
  }
}

/* ---------- montaggio ---------- */

async function mount(host: HTMLElement, o: Opzioni) {
  const ridotto = !!o.ridotto;
  const canvas = document.createElement('canvas');
  canvas.className = 'aula3d__tela';
  host.prepend(canvas);
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  } catch (e) {
    canvas.remove();
    throw e;
  }
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.shadowMap.autoUpdate = false;
  const dpr = () => Math.min(window.devicePixelRatio || 1, 2);
  renderer.setPixelRatio(dpr());

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, 1.6, 0.05, 200);
  await frame();

  // ---- costruzione: materiali di produzione, desaturati verso carta e inchiostro
  const mat = createMaterials();
  const hsl = { h: 0, s: 0, l: 0 };
  for (const m of Object.values(mat)) {
    const sm = m as THREE.MeshStandardMaterial;
    if (sm.color) {
      sm.color.getHSL(hsl);
      sm.color.setHSL(hsl.h, hsl.s * 0.55, hsl.l);
    }
  }
  const occupato = (i: number) => !!o.seggi[i]?.id;
  const plan = {
    plan: { rows: o.piano.rows },
    rowRadii: o.piano.rowRadii,
    seats: o.piano.s.map((r, i) => ({
      id: String(i + 1),
      posto: o.seggi[i]?.p ?? null,
      kind: KIND[o.seggi[i]?.k ?? 'd'] ?? 'deputato',
      sector: o.piano.settori[r[0]]!,
      row: r[1] < 0 ? null : r[1],
      x: r[2],
      z: r[3],
    })),
  };
  const deputati = o.seggi.filter((s) => s.id && s.p).map((s) => ({ id: s.id, group: s.g, seat: s.p }));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hemi = buildHemicycle(plan as any, deputati as any);
  await frame();
  const aula = buildAula(mat, hemi);
  await frame();
  const sedie = new Sedie(hemi.seats, occupato);
  scene.add(aula.root, sedie.group);
  aula.doorPick.forEach((p) => (p.visible = false));

  // calpestabile: pavimento, gradoni, tappeti della Presidenza e del Governo
  const pavimento: THREE.Object3D[] = [];
  aula.root.traverse((ob) => {
    const m = ob as THREE.Mesh;
    if (m.isMesh && (m.material === mat.emicicloFloor || m.material === mat.carpet)) pavimento.push(m);
  });

  // ---- luce: la stessa di produzione, senza il cortile
  const cielo = new THREE.HemisphereLight('#fff4e4', '#5a3a26', 1);
  const sole = new THREE.DirectionalLight('#fff3e2', 2.4);
  sole.position.set(14, 48, -4);
  sole.target.position.set(0, 0, -16);
  sole.castShadow = true;
  sole.shadow.mapSize.setScalar(2048);
  Object.assign(sole.shadow.camera, { left: -34, right: 34, top: 38, bottom: -38, near: 10, far: 90 });
  sole.shadow.bias = -0.0004;
  sole.shadow.normalBias = 0.035;
  scene.add(cielo, sole, sole.target);
  renderer.shadowMap.needsUpdate = true;

  // ---- palette
  let palette = leggiPalette();
  let stati: Stato[] = hemi.seats.map((_, i) => (occupato(i) ? 'neutro' : 'vuoto'));
  const applicaTema = () => {
    palette = leggiPalette();
    scene.background = palette.carta.clone();
    renderer.toneMappingExposure = scuro() ? 0.82 : 1;
    (sedie.anello.material as THREE.MeshBasicMaterial).color.copy(palette.acceso);
    (sedie.sopra.material as THREE.MeshBasicMaterial).color.set(scuro() ? '#eceae4' : '#12171a');
    sedie.imposta(coloriSedie(), true);
    sveglia();
  };

  let selezionato: number | null = null;
  const coloriSedie = () => stati.map((s, i) => (i === selezionato ? palette.scelto : (palette[s] ?? palette.neutro)));

  /* ---------- camera in prima persona ---------- */

  const R = ROOM.wallRadius;
  const presidente = hemi.seats.find((s) => s.kind === 'presidenza' && s.sector === 'Presidenza') ?? hemi.seats.find((s) => s.kind === 'presidenza')!;
  const pos = new THREE.Vector3();
  const look = { yaw: 0, pitch: 0, fov: 62, yawG: 0, pitchG: 0, fovG: 62 };
  let yGoal = 0;
  let volo: { t0: number; dur: number; da: { p: THREE.Vector3; yaw: number; pitch: number; fov: number }; a: { p: THREE.Vector3; yaw: number; pitch: number; fov: number }; lift: number; fine: () => void } | null = null;
  const vel = new THREE.Vector2();
  const input = { x: 0, z: 0, turn: 0, corsa: false };
  const joy = { x: 0, z: 0 };
  let aspect = 1.6;
  let mosso = false;

  const ray = new THREE.Raycaster();
  ray.layers.enableAll();
  const giu = new THREE.Vector3(0, -1, 0);
  const tmp = new THREE.Vector3();
  function suolo(x: number, z: number): number | null {
    ray.set(tmp.set(x, ROOM.galleryY - 0.6, z), giu);
    ray.far = 20;
    const h = ray.intersectObjects(pavimento, false)[0];
    return h ? h.point.y : null;
  }
  function dentro(x: number, z: number): boolean {
    if (z >= 0) return Math.hypot(x, z) < R - 1.0;
    return z > ROOM.backZ + 0.7 && Math.abs(x) < R - 1.0;
  }
  const fovMin = () => (aspect < 0.9 ? 44 : 30);
  const fovMax = () => (aspect < 0.9 ? 92 : 80);
  /** campo verticale che lascia almeno ~70 gradi in orizzontale anche sugli schermi stretti */
  function fovBase(): number {
    const want = (88 * Math.PI) / 180;
    const v = (2 * Math.atan(Math.tan(want / 2) / aspect) * 180) / Math.PI;
    return clamp(v, 56, 88);
  }
  function direzione(yaw: number, pitch: number, out = new THREE.Vector3()) {
    return out.set(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch));
  }
  function guarda(p: THREE.Vector3, target: THREE.Vector3) {
    const d = target.clone().sub(p).normalize();
    return { yaw: Math.atan2(d.x, d.z), pitch: Math.asin(clamp(d.y, -1, 1)) };
  }
  function applica() {
    camera.position.copy(pos);
    camera.lookAt(tmp.copy(pos).add(direzione(look.yaw, look.pitch)));
    if (Math.abs(camera.fov - look.fov) > 1e-4) {
      camera.fov = look.fov;
      camera.updateProjectionMatrix();
    }
  }

  /** Il punto di partenza: in piedi sul banco della Presidenza, lo sguardo sull'emiciclo. */
  function posaIniziale() {
    const p = new THREE.Vector3(0, presidente.y + 2.15, presidente.z + 1.4);
    const g = guarda(p, new THREE.Vector3(0, 0.9, 10));
    return { p, yaw: g.yaw, pitch: g.pitch, fov: fovBase() };
  }
  /** Davanti al seggio, un po' in alto, guardando la sedia: si vedono i vicini. */
  function posaDavanti(i: number) {
    const s = hemi.seats[i]!;
    const f = new THREE.Vector3(Math.sin(s.yaw), 0, Math.cos(s.yaw));
    let dist = 3.4;
    let p = new THREE.Vector3(s.x, s.y + 2.1, s.z).addScaledVector(f, dist);
    while (!dentro(p.x, p.z) && dist > 1.2) {
      dist -= 0.3;
      p = new THREE.Vector3(s.x, s.y + 2.1, s.z).addScaledVector(f, dist);
    }
    const g = guarda(p, new THREE.Vector3(s.x, s.y + 0.6, s.z));
    return { p, yaw: g.yaw, pitch: g.pitch, fov: Math.min(fovBase(), 64) };
  }
  function posaSeduta(i: number) {
    const s = hemi.seats[i]!;
    const v = seatView(s, [aula.root, sedie.group]);
    const g = guarda(v.eye, v.look);
    return { p: v.eye.clone(), yaw: g.yaw, pitch: g.pitch, fov: Math.max(fovBase(), 62) };
  }

  function salta(a: { p: THREE.Vector3; yaw: number; pitch: number; fov: number }) {
    volo = null;
    pos.copy(a.p);
    yGoal = a.p.y;
    look.yaw = look.yawG = a.yaw;
    look.pitch = look.pitchG = a.pitch;
    look.fov = look.fovG = a.fov;
    vel.set(0, 0);
    applica();
    sveglia();
  }
  function vola(a: { p: THREE.Vector3; yaw: number; pitch: number; fov: number }): Promise<void> {
    if (ridotto) {
      salta(a);
      return Promise.resolve();
    }
    return new Promise((fine) => {
      let dy = a.yaw - look.yaw;
      dy = Math.atan2(Math.sin(dy), Math.cos(dy));
      const dist = pos.distanceTo(a.p);
      volo = {
        t0: performance.now(),
        dur: clamp(700 + dist * 70, 800, 2200),
        da: { p: pos.clone(), yaw: look.yaw, pitch: look.pitch, fov: look.fov },
        a: { ...a, yaw: look.yaw + dy },
        lift: clamp(dist * 0.12, 0, 2.5),
        fine: () => fine(),
      };
      vel.set(0, 0);
      sveglia();
    });
  }

  /* ---------- disegno su richiesta ---------- */

  let raf = 0;
  let attivo = true;
  let ultimo = 0;
  let hoverCoda: { x: number; y: number } | null = null;
  let hoverI: number | null = null;
  function sveglia() {
    if (!raf && attivo && !document.hidden) raf = requestAnimationFrame(passo);
  }
  const easeIO = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  function passo(t: number) {
    raf = 0;
    const dt = ultimo ? Math.min((t - ultimo) / 1000, 0.1) : 1 / 60;
    ultimo = t;
    let busy = false;

    if (volo) {
      const k = clamp((performance.now() - volo.t0) / volo.dur, 0, 1);
      const e = easeIO(k);
      pos.lerpVectors(volo.da.p, volo.a.p, e);
      pos.y += Math.sin(Math.PI * e) * volo.lift;
      look.yaw = look.yawG = volo.da.yaw + (volo.a.yaw - volo.da.yaw) * e;
      look.pitch = look.pitchG = volo.da.pitch + (volo.a.pitch - volo.da.pitch) * e;
      look.fov = look.fovG = volo.da.fov + (volo.a.fov - volo.da.fov) * e;
      yGoal = pos.y;
      busy = true;
      if (k >= 1) {
        const f = volo.fine;
        volo = null;
        f();
      }
    } else {
      // camminare
      const ix = clamp(input.x + joy.x, -1, 1);
      const iz = clamp(input.z + joy.z, -1, 1);
      if (input.turn) {
        look.yawG += input.turn * dt * 1.6;
        busy = true;
      }
      const v = walkVector(look.yaw, -ix, iz);
      const vmax = input.corsa ? 6 : 3.2;
      vel.lerp(new THREE.Vector2(v.x * vmax, v.z * vmax), 1 - Math.exp(-dt * 10));
      if (vel.lengthSq() > 1e-4) {
        busy = true;
        mosso = true;
        let nx = pos.x + vel.x * dt;
        let nz = pos.z + vel.y * dt;
        if (!dentro(nx, nz)) {
          if (dentro(nx, pos.z)) nz = pos.z;
          else if (dentro(pos.x, nz)) nx = pos.x;
          else {
            nx = pos.x;
            nz = pos.z;
          }
        }
        pos.x = nx;
        pos.z = nz;
        const y = suolo(nx, nz);
        if (y !== null) yGoal = y + EYE;
      } else vel.set(0, 0);
      if (Math.abs(pos.y - yGoal) > 0.002) {
        pos.y += (yGoal - pos.y) * (1 - Math.exp(-dt * 9));
        busy = true;
      }
      const k = 1 - Math.exp(-dt * 12);
      for (const [a, g] of [['yaw', 'yawG'], ['pitch', 'pitchG'], ['fov', 'fovG']] as const) {
        const d = look[g] - look[a];
        if (Math.abs(d) > 1e-4) {
          look[a] += d * k;
          busy = true;
        } else look[a] = look[g];
      }
    }
    applica();
    if (sedie.update(dt)) busy = true;
    if (hoverCoda) {
      const { x, y } = hoverCoda;
      hoverCoda = null;
      const i = volo ? null : scegli(x, y);
      if (i !== hoverI) {
        hoverI = i;
        sedie.segna(sedie.sopra, i !== null && i !== selezionato ? i : null);
        canvas.style.cursor = i !== null && occupato_(i) ? 'pointer' : '';
      }
      o.onHover?.(i, x, y);
    }
    renderer.render(scene, camera);
    if (mosso) {
      mosso = false;
      o.onVista?.(true);
    }
    if (busy) sveglia();
    else ultimo = 0;
  }
  const occupato_ = occupato;

  const ndc = new THREE.Vector2();
  function scegli(cx: number, cy: number): number | null {
    const r = canvas.getBoundingClientRect();
    ndc.set(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    ray.far = 200;
    const h = ray.intersectObject(sedie.pick, false)[0];
    return h && h.instanceId !== undefined ? h.instanceId : null;
  }

  /* ---------- dimensioni ---------- */

  let spostamento = 0;
  let spostamentoY = 0;
  function dimensiona() {
    const w = Math.max(1, host.clientWidth);
    const h = Math.max(1, host.clientHeight);
    renderer.setPixelRatio(dpr());
    renderer.setSize(w, h, false);
    const prima = fovBase();
    aspect = w / h;
    camera.aspect = aspect;
    if (spostamento || spostamentoY) camera.setViewOffset(w, h, spostamento, spostamentoY, w, h);
    else camera.clearViewOffset();
    // il campo segue il rapporto dello schermo, mantenendo lo zoom scelto
    const k = look.fovG / prima;
    look.fovG = look.fov = clamp(fovBase() * k, fovMin(), fovMax());
    camera.fov = look.fov;
    camera.updateProjectionMatrix();
    sveglia();
  }
  const ro = new ResizeObserver(() => dimensiona());
  ro.observe(host);

  /* ---------- puntatore ---------- */

  const punti = new Map<number, { x: number; y: number }>();
  let giuP: { x: number; y: number; t: number; mosso: number; tipo: string } | null = null;
  let pizzico = 0;
  const dist2 = () => {
    const p = [...punti.values()];
    return p.length >= 2 ? Math.hypot(p[0]!.x - p[1]!.x, p[0]!.y - p[1]!.y) : 0;
  };
  function trascina(dx: number, dy: number) {
    const k = (0.0034 * look.fov) / 62;
    look.yawG -= dx * k;
    look.pitchG = clamp(look.pitchG - dy * k, -1.1, 0.9);
    mosso = true;
    sveglia();
  }
  function zoom(f: number) {
    look.fovG = clamp(look.fovG * f, fovMin(), fovMax());
    mosso = true;
    sveglia();
  }
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  canvas.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    try {
      canvas.setPointerCapture(e.pointerId);
    } catch {
      /* niente */
    }
    punti.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (punti.size === 1) giuP = { x: e.clientX, y: e.clientY, t: performance.now(), mosso: 0, tipo: e.pointerType };
    else {
      giuP = null;
      pizzico = dist2();
    }
    host.focus({ preventScroll: true });
  });
  canvas.addEventListener('pointermove', (e) => {
    const prev = punti.get(e.pointerId);
    if (!prev) {
      if (e.pointerType === 'mouse') {
        hoverCoda = { x: e.clientX, y: e.clientY };
        sveglia();
      }
      return;
    }
    const dx = e.clientX - prev.x;
    const dy = e.clientY - prev.y;
    prev.x = e.clientX;
    prev.y = e.clientY;
    if (punti.size >= 2) {
      const d = dist2();
      if (pizzico > 0 && d > 0) zoom(pizzico / d);
      pizzico = d;
      return;
    }
    if (giuP) {
      giuP.mosso = Math.max(giuP.mosso, Math.hypot(e.clientX - giuP.x, e.clientY - giuP.y));
      if (giuP.mosso > 6) {
        if (volo) return;
        trascina(dx, dy);
        canvas.dataset.trascina = '';
        if (hoverI !== null) {
          hoverI = null;
          sedie.segna(sedie.sopra, null);
          o.onHover?.(null, 0, 0);
        }
      }
    }
  });
  const su = (e: PointerEvent) => {
    const tap = giuP && punti.size === 1 && giuP.mosso <= 6 && performance.now() - giuP.t < 600;
    punti.delete(e.pointerId);
    if (punti.size === 0) {
      giuP = null;
      delete canvas.dataset.trascina;
    }
    if (tap && e.type === 'pointerup' && !volo) {
      const i = scegli(e.clientX, e.clientY);
      if (i !== null && occupato(i)) o.onPick?.(i);
      else if (i !== null && e.pointerType === 'touch') o.onHover?.(i, e.clientX, e.clientY);
    }
    if (e.pointerType === 'mouse') {
      hoverCoda = { x: e.clientX, y: e.clientY };
      sveglia();
    }
  };
  canvas.addEventListener('pointerup', su);
  canvas.addEventListener('pointercancel', su);
  canvas.addEventListener('pointerleave', (e) => {
    if (e.pointerType !== 'mouse' || punti.size) return;
    hoverCoda = null;
    if (hoverI !== null) {
      hoverI = null;
      sedie.segna(sedie.sopra, null);
      canvas.style.cursor = '';
      sveglia();
    }
    o.onHover?.(null, 0, 0);
  });
  canvas.addEventListener(
    'wheel',
    (e) => {
      if (!(e.ctrlKey || e.metaKey)) {
        o.onAvviso?.('Per lo zoom: Ctrl o ⌘ con la rotella');
        return;
      }
      e.preventDefault();
      const d = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      zoom(Math.exp(clamp(d, -120, 120) * (Math.abs(d) < 40 ? 0.01 : 0.0015)));
    },
    { passive: false },
  );

  /* ---------- tastiera (solo con l'Aula a fuoco) ---------- */

  const tasti = new Set<string>();
  const leggiTasti = () => {
    input.z = (tasti.has('KeyW') || tasti.has('ArrowUp') ? 1 : 0) - (tasti.has('KeyS') || tasti.has('ArrowDown') ? 1 : 0);
    input.x = (tasti.has('KeyD') ? 1 : 0) - (tasti.has('KeyA') ? 1 : 0);
    input.turn = (tasti.has('ArrowLeft') ? 1 : 0) - (tasti.has('ArrowRight') ? 1 : 0);
    input.corsa = tasti.has('ShiftLeft') || tasti.has('ShiftRight');
    sveglia();
  };
  const MUOVE = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight']);
  host.addEventListener('keydown', (e) => {
    if (e.target !== host || e.altKey || e.metaKey || e.ctrlKey) return;
    if (MUOVE.has(e.code)) {
      e.preventDefault();
      if (volo) return;
      tasti.add(e.code);
      leggiTasti();
      mosso = true;
    } else if (e.key === '+' || e.key === '=') {
      e.preventDefault();
      zoom(0.88);
    } else if (e.key === '-') {
      e.preventDefault();
      zoom(1 / 0.88);
    }
  });
  const libera = () => {
    tasti.clear();
    leggiTasti();
  };
  host.addEventListener('keyup', (e) => {
    tasti.delete(e.code);
    leggiTasti();
  });
  host.addEventListener('blur', libera);
  window.addEventListener('blur', libera);

  /* ---------- joystick sul tocco ---------- */

  let joyEl: HTMLElement | null = null;
  if (window.matchMedia('(pointer: coarse)').matches) {
    const knob = document.createElement('span');
    knob.className = 'joy__pomo';
    joyEl = document.createElement('div');
    joyEl.className = 'joy';
    joyEl.setAttribute('aria-hidden', 'true');
    joyEl.append(knob);
    host.append(joyEl);
    let id: number | null = null;
    let cx = 0;
    let cy = 0;
    const RJ = 34;
    const set = (dx: number, dy: number) => {
      const d = Math.hypot(dx, dy);
      const k = d > RJ ? RJ / d : 1;
      knob.style.transform = `translate(${dx * k}px, ${dy * k}px)`;
      joy.x = (dx * k) / RJ;
      joy.z = -(dy * k) / RJ;
      if (joy.x || joy.z) mosso = true;
      sveglia();
    };
    joyEl.addEventListener('pointerdown', (e) => {
      id = e.pointerId;
      joyEl!.setPointerCapture(id);
      const r = joyEl!.getBoundingClientRect();
      cx = r.left + r.width / 2;
      cy = r.top + r.height / 2;
      set(e.clientX - cx, e.clientY - cy);
      e.stopPropagation();
    });
    joyEl.addEventListener('pointermove', (e) => {
      if (e.pointerId === id) set(e.clientX - cx, e.clientY - cy);
    });
    const fine = (e: PointerEvent) => {
      if (e.pointerId !== id) return;
      id = null;
      set(0, 0);
    };
    joyEl.addEventListener('pointerup', fine);
    joyEl.addEventListener('pointercancel', fine);
  }

  /* ---------- pausa con la scheda nascosta ---------- */

  const vis = () => {
    if (document.hidden) {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      ultimo = 0;
      libera();
    } else sveglia();
  };
  document.addEventListener('visibilitychange', vis);

  /* ---------- avvio ---------- */

  dimensiona();
  salta(posaIniziale());
  applicaTema();
  renderer.compile(scene, camera);
  await frame();
  renderer.render(scene, camera);

  return {
    /** stati per seggio, nello stesso ordine di AULA.seats */
    colora(nuovi: Stato[]) {
      stati = nuovi.slice();
      sedie.imposta(coloriSedie(), ridotto);
      sveglia();
    },
    seleziona(i: number | null) {
      selezionato = i;
      // l'anello galleggia sopra lo schienale: si vede anche dietro i banchi
      sedie.segna(sedie.anello, i, 1.45);
      sedie.imposta(coloriSedie(), ridotto);
      if (i !== null && hoverI === i) sedie.segna(sedie.sopra, null);
      sveglia();
    },
    /** vola davanti al seggio */
    vaiA(i: number) {
      return vola(posaDavanti(i));
    },
    /** vola dentro il seggio: la vista di chi ci siede */
    siediti(i: number) {
      return vola(posaSeduta(i));
    },
    /** gira lo sguardo verso un insieme di seggi (un gruppo), senza spostarsi */
    orienta(indici: number[]) {
      if (!indici.length || volo) return;
      const c = new THREE.Vector3();
      indici.forEach((i) => {
        const s = hemi.seats[i]!;
        c.add(tmp.set(s.x, s.y + 0.5, s.z));
      });
      c.divideScalar(indici.length);
      const g = guarda(pos, c);
      let dy = g.yaw - look.yawG;
      dy = Math.atan2(Math.sin(dy), Math.cos(dy));
      look.yawG += dy;
      look.pitchG = clamp(g.pitch, -1.1, 0.9);
      if (ridotto) {
        look.yaw = look.yawG;
        look.pitch = look.pitchG;
      }
      sveglia();
    },
    riadatta() {
      o.onVista?.(false);
      return vola(posaIniziale());
    },
    zoom,
    attiva(on: boolean) {
      attivo = on;
      if (!on) {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
        ultimo = 0;
        libera();
      } else {
        dimensiona();
      }
    },
    sposta(px: number, py = 0) {
      spostamento = Math.round(px);
      spostamentoY = Math.round(py);
      dimensiona();
    },
    tema: applicaTema,
    distruggi() {
      ro.disconnect();
      document.removeEventListener('visibilitychange', vis);
      window.removeEventListener('blur', libera);
      if (raf) cancelAnimationFrame(raf);
      renderer.dispose();
      canvas.remove();
      joyEl?.remove();
    },
  };
}

(window as unknown as { Aula3D: unknown }).Aula3D = { supported, mount };
