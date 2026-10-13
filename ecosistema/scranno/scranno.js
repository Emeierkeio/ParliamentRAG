/*
 * Scranno: la pianta dell'Aula di Montecitorio, seggio per seggio.
 *
 * Dati: window.AULA (seggi reali, gruppi, fiducia del 7/10/2026 come voto di riserva),
 * le votazioni da /api (vedi «Voti») e
 * window.DEPUTATI (commissioni in corso e contatori, estratti dai dati di Scranno).
 * Due viste: «In Aula» (3D in prima persona, aula3d.js, motore di Scranno) e «Pianta»
 * (SVG: ingrandimento e spostamento cambiano il viewBox). Modalità, ricerca e scheda
 * del deputato valgono per entrambe.
 */
(function () {
  "use strict";

  var A = window.AULA;
  var DD = window.DEPUTATI || { deputati: {}, organi: [] };
  var NS = "http://www.w3.org/2000/svg";
  var esc = window.esc;
  var ridotto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var senzaHover = window.matchMedia("(hover: none)");

  /* Centro geometrico dell'emiciclo (seats.json, plan.centerX/centerY) */
  var CX = 1276.24, CY = 1290.75;
  var BASE = { x: -10, y: -40, w: 2580, h: 1860 };
  var R = 17;
  var ZOOM_MAX = 7;

  var svg = document.getElementById("aula");
  var scena = document.getElementById("scena");
  var blocco = document.getElementById("aula-blocco");
  var fumetto = document.getElementById("fumetto");
  var avviso = document.getElementById("avviso");

  /* ---------- Testi ---------- */

  var GRUPPI = {};
  A.groups.forEach(function (g) { GRUPPI[g.acronym] = g.name; });
  function gruppoBreve(acr) {
    return (GRUPPI[acr] || acr).split(" - ")[0];
  }
  var VOTO = {
    favor: { parola: "Voto favorevole", plurale: "Favorevoli" },
    against: { parola: "Voto contrario", plurale: "Contrari" },
    abstain: { parola: "Astensione", plurale: "Astenuti" },
    absent: { parola: "Assente al voto", plurale: "Assenti" },
    "n.d.": { parola: "Voto non associato al seggio", plurale: "Non associati" },
    segreto: { parola: "Voto segreto", plurale: "Voto segreto" },
  };
  var AREE = { g: "Banchi del Governo", p: "Presidenza", c: "Comitato dei nove", a: "Posto aggiuntivo", d: "Settore dei deputati" };

  /* I dati scrivono gli accenti finali con l'apostrofo (Care' → Carè) */
  function accenta(s) {
    var m = { a: "à", e: "è", i: "ì", o: "ò", u: "ù", A: "À", E: "È", I: "Ì", O: "Ò", U: "Ù" };
    return String(s).replace(/([aeiouAEIOU])'(?=\s|$|,)/g, function (_, v) { return m[v]; });
  }
  function piega(s) {
    return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function data(iso, corta) {
    var d = new Date(iso + "T12:00:00");
    return corta
      ? d.toLocaleDateString("it-IT", { day: "numeric", month: "numeric", year: "numeric" })
      : d.toLocaleDateString("it-IT", { day: "numeric", month: "long", year: "numeric" });
  }
  function decimale(n) {
    return String(n).replace(".", ",");
  }

  /* Componenti del Misto: nome esteso dalle schede dei deputati */
  var COMPONENTI = {};

  /* ---------- Modello dei seggi ---------- */

  var seggi = A.seats.map(function (s, i) {
    var a = (Math.atan2(CY - s.y, s.x - CX) * 180) / Math.PI;
    if (a < -90) a += 360; // da -23° (destra) a 203° (sinistra)
    var o = {
      i: i, p: s.p, x: s.x, y: s.y, k: s.k,
      a: a, r: Math.hypot(s.x - CX, s.y - CY),
      id: s.id || null, n: s.n ? accenta(s.n) : null, g: s.g || null, c: s.c || null, v: s.v || null,
    };
    o.det = o.id ? DD.deputati[o.id] || null : null;
    if (o.c && o.det && o.det.cm) COMPONENTI[o.c] = o.det.cm;
    return o;
  });
  var occupati = seggi.filter(function (s) { return s.id; });
  /* Ordine da sinistra a destra, poi dalla prima fila in su */
  var ordinati = occupati.slice().sort(function (a, b) { return b.a - a.a || a.r - b.r; });

  function nomeGruppoSeggio(s) {
    var g = gruppoBreve(s.g);
    if (s.g === "Misto" && s.c) g += ", " + (COMPONENTI[s.c] || s.c);
    return g;
  }
  function etichettaSeggio(s) {
    return (s.p ? "Seggio " + s.p : "Seggio") + ", " + s.n + ", " + nomeGruppoSeggio(s) +
      (modo === "voto" && s.v ? ", " + VOTO[s.v].parola.toLowerCase() : "");
  }

  /* ---------- Disegno della pianta ---------- */

  function el(nome, attr) {
    var e = document.createElementNS(NS, nome);
    for (var k in attr) e.setAttribute(k, attr[k]);
    return e;
  }
  function punto(a, r) {
    var t = (a * Math.PI) / 180;
    return [CX + r * Math.cos(t), CY - r * Math.sin(t)];
  }
  function arco(r, a0, a1) {
    var p0 = punto(a0, r), p1 = punto(a1, r);
    return "M" + p0[0].toFixed(1) + " " + p0[1].toFixed(1) + " A" + r + " " + r + " 0 1 0 " + p1[0].toFixed(1) + " " + p1[1].toFixed(1);
  }

  var pianta = el("g", { class: "pianta", "aria-hidden": "true" });
  var dep = seggi.filter(function (s) { return s.k === "d"; });
  var aMin = Math.min.apply(null, dep.map(function (s) { return s.a; }));
  var aMax = Math.max.apply(null, dep.map(function (s) { return s.a; }));
  var rMin = Math.min.apply(null, dep.map(function (s) { return s.r; }));
  var rMax = Math.max.apply(null, dep.map(function (s) { return s.r; }));
  /* Muri: davanti alla prima fila e dietro l'ultima */
  pianta.appendChild(el("path", { class: "muro", d: arco(rMax + 34, aMin - 1.6, aMax + 1.6) }));
  pianta.appendChild(el("path", { class: "muro", d: arco(rMin - 34, aMin - 1.6, aMax + 1.6) }));
  /* Corsie: dove tra due seggi vicini per angolo c'è un vuoto largo */
  var angoli = dep.map(function (s) { return s.a; }).sort(function (a, b) { return a - b; });
  for (var j = 1; j < angoli.length; j++) {
    if (angoli[j] - angoli[j - 1] > 2.6) {
      var am = (angoli[j] + angoli[j - 1]) / 2;
      var q0 = punto(am, rMin - 20), q1 = punto(am, rMax + 20);
      pianta.appendChild(el("line", { class: "corsia", x1: q0[0], y1: q0[1], x2: q1[0], y2: q1[1] }));
    }
  }
  /* Etichette delle aree speciali, sotto o sopra i loro seggi */
  function area(k, testo, dy, piccola, filtro) {
    var ss = seggi.filter(function (s) { return s.k === k && (!filtro || filtro(s)); });
    if (!ss.length) return;
    var x = ss.reduce(function (t, s) { return t + s.x; }, 0) / ss.length;
    var y = dy > 0 ? Math.max.apply(null, ss.map(function (s) { return s.y; })) + dy : Math.min.apply(null, ss.map(function (s) { return s.y; })) + dy;
    var t = el("text", { class: "area" + (piccola ? " area--piccola" : ""), x: x.toFixed(1), y: y.toFixed(1) });
    t.textContent = testo;
    pianta.appendChild(t);
  }
  area("c", "COMITATO DEI NOVE", 92);
  area("g", "GOVERNO", -40);
  area("p", "PRESIDENZA", 66);
  area("a", "AGGIUNTIVI", 62, true, function (s) { return s.x < CX; });
  area("a", "AGGIUNTIVI", 62, true, function (s) { return s.x > CX; });
  svg.appendChild(pianta);

  var gSeggi = el("g", { class: "seggi" });
  seggi.forEach(function (s) {
    var c = el("circle", { class: "seggio", cx: s.x, cy: s.y, r: R, "data-k": s.k, "data-i": s.i });
    if (s.id) {
      c.setAttribute("data-occ", "");
      c.setAttribute("role", "button");
      c.setAttribute("tabindex", "-1");
    } else {
      c.setAttribute("data-vuoto", "");
      c.setAttribute("aria-hidden", "true");
    }
    /* Ritardi: comparsa dal centro verso l'esterno, spazzata da sinistra a destra */
    c.style.setProperty("--rit", Math.round(((s.r - 230) / 1060) * 620 + ((203 - s.a) / 226) * 90) + "ms");
    c.style.setProperty("--sw", Math.round(((203 - s.a) / 226) * 380) + "ms");
    s.el = c;
    gSeggi.appendChild(c);
  });
  svg.appendChild(gSeggi);
  var anello = el("circle", { class: "anello", r: R + 13, cx: -100, cy: -100, "aria-hidden": "true" });
  anello.style.display = "none";
  svg.appendChild(anello);
  svg.setAttribute("viewBox", BASE.x + " " + BASE.y + " " + BASE.w + " " + BASE.h);
  svg.setAttribute("aria-label", "Pianta dell'Aula di Montecitorio: " + occupati.length + " deputati nei loro seggi");

  /* Comparsa iniziale */
  if (!ridotto) {
    svg.setAttribute("data-entra", "");
    setTimeout(function () { svg.removeAttribute("data-entra"); }, 1500);
  }

  /* Accessibilità: un solo seggio nel giro del Tab, le frecce fanno il resto */
  var corrente = ordinati[0];
  function etichetteSeggi() {
    occupati.forEach(function (s) { s.el.setAttribute("aria-label", etichettaSeggio(s)); });
  }
  corrente.el.setAttribute("tabindex", "0");

  /* ---------- Vista: viewBox, ingrandimento, spostamento ---------- */

  var vb = { x: BASE.x, y: BASE.y, w: BASE.w, h: BASE.h };
  var rafVista = 0, animVista = 0;
  var btnRiadatta = document.getElementById("zoom-riadatta");
  var btnPiu = document.getElementById("zoom-piu");
  var btnMeno = document.getElementById("zoom-meno");

  function scala() { return BASE.w / vb.w; }
  function limita(v) {
    var w = Math.min(BASE.w, Math.max(BASE.w / ZOOM_MAX, v.w));
    var h = (w * BASE.h) / BASE.w;
    var x = Math.min(BASE.x + BASE.w - w, Math.max(BASE.x, v.x));
    var y = Math.min(BASE.y + BASE.h - h, Math.max(BASE.y, v.y));
    return { x: x, y: y, w: w, h: h };
  }
  function disegnaVista() {
    rafVista = 0;
    svg.setAttribute("viewBox", vb.x.toFixed(2) + " " + vb.y.toFixed(2) + " " + vb.w.toFixed(2) + " " + vb.h.toFixed(2));
    var z = scala() > 1.01;
    scena.setAttribute("data-zoom", z ? "si" : "no");
    btnRiadatta.hidden = !z;
    btnMeno.disabled = !z;
    btnPiu.disabled = scala() >= ZOOM_MAX - 0.01;
    if (fumettoSu && fumettoSu.daTastiera) mostraFumettoSeggio(fumettoSu.s, true);
  }
  function pianifica() {
    if (!rafVista) rafVista = requestAnimationFrame(disegnaVista);
  }
  function vaiA(t, dur) {
    t = limita(t);
    cancelAnimationFrame(animVista);
    if (ridotto || dur === 0) {
      vb = t;
      pianifica();
      return;
    }
    var da = { x: vb.x, y: vb.y, w: vb.w, h: vb.h };
    var t0 = performance.now();
    dur = dur || 380;
    (function passo(ora) {
      var k = Math.min(1, (ora - t0) / dur);
      var e = 1 - Math.pow(1 - k, 3);
      vb = { x: da.x + (t.x - da.x) * e, y: da.y + (t.y - da.y) * e, w: da.w + (t.w - da.w) * e, h: da.h + (t.h - da.h) * e };
      disegnaVista();
      if (k < 1) animVista = requestAnimationFrame(passo);
    })(t0);
  }
  /* Da coordinate dello schermo a coordinate della pianta (l'SVG ha lo stesso rapporto del viewBox) */
  function aPianta(cx, cy, v) {
    v = v || vb;
    var r = svg.getBoundingClientRect();
    return { x: v.x + ((cx - r.left) / r.width) * v.w, y: v.y + ((cy - r.top) / r.height) * v.h };
  }
  function aSchermo(x, y) {
    var r = svg.getBoundingClientRect();
    return { x: r.left + ((x - vb.x) / vb.w) * r.width, y: r.top + ((y - vb.y) / vb.h) * r.height };
  }
  function ingrandisci(f, px, py, anima) {
    if (px == null) { px = vb.x + vb.w / 2; py = vb.y + vb.h / 2; }
    var w = Math.min(BASE.w, Math.max(BASE.w / ZOOM_MAX, vb.w / f));
    var t = { w: w, h: (w * BASE.h) / BASE.w, x: px - (px - vb.x) * (w / vb.w), y: py - (py - vb.y) * (w / vb.w) };
    if (anima) vaiA(t, 280);
    else { cancelAnimationFrame(animVista); vb = limita(t); pianifica(); }
  }
  function centraSu(s, sc) {
    var w = BASE.w / Math.max(scala(), sc || 1);
    var h = (w * BASE.h) / BASE.w;
    vaiA({ x: s.x - w / 2, y: s.y - h / 2, w: w, h: h }, 460);
  }
  function inVista(s) {
    var m = R * 3;
    return s.x > vb.x + m && s.x < vb.x + vb.w - m && s.y > vb.y + m && s.y < vb.y + vb.h - m;
  }

  btnPiu.addEventListener("click", function () { ingrandisci(1.6, null, null, true); });
  btnMeno.addEventListener("click", function () { ingrandisci(1 / 1.6, null, null, true); });
  btnRiadatta.addEventListener("click", function () { vaiA(BASE, 420); });
  disegnaVista();

  /* Rotella: con Ctrl o ⌘ (o il pizzico del trackpad) sempre; senza, solo se già ingrandita */
  var timerAvviso;
  function mostraAvviso(t) {
    avviso.textContent = t;
    avviso.setAttribute("data-mostra", "");
    clearTimeout(timerAvviso);
    timerAvviso = setTimeout(function () { avviso.removeAttribute("data-mostra"); }, 1300);
  }
  svg.addEventListener("wheel", function (e) {
    if (!(e.ctrlKey || e.metaKey || scala() > 1.01)) {
      mostraAvviso("Per ingrandire: Ctrl o ⌘ con la rotella, o i pulsanti +");
      return;
    }
    e.preventDefault();
    var d = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
    /* Pizzico del trackpad: passi piccoli e fitti; rotella: scatti grandi */
    var k = Math.abs(d) < 40 ? 0.012 : 0.0025;
    var f = Math.exp(Math.max(-0.35, Math.min(0.35, -d * k)));
    var p = aPianta(e.clientX, e.clientY);
    ingrandisci(f, p.x, p.y, false);
  }, { passive: false });

  /* ---------- Puntatore: passaggio, tocco, trascinamento, pizzico ---------- */

  var punti = new Map();
  var gesto = null;
  var sopra = null;
  var rafSopra = 0, ultimoMove = null;

  function vicino(px, py, sogliaPx) {
    var r = svg.getBoundingClientRect();
    var soglia = Math.max(R + 4, (sogliaPx * vb.w) / r.width);
    var best = null, bd = soglia * soglia;
    for (var i = 0; i < seggi.length; i++) {
      var s = seggi[i], dx = s.x - px, dy = s.y - py, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = s; }
    }
    return best;
  }
  function segnaSopra(s) {
    if (sopra === s) return;
    if (sopra) sopra.el.removeAttribute("data-sopra");
    sopra = s;
    if (s) s.el.setAttribute("data-sopra", "");
  }

  svg.addEventListener("pointerdown", function (e) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    punti.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (punti.size === 1) {
      gesto = { tipo: "tocco", x0: e.clientX, y0: e.clientY, vb0: { x: vb.x, y: vb.y, w: vb.w, h: vb.h }, mosso: false, tipoPuntatore: e.pointerType };
    } else if (punti.size === 2) {
      var pp = Array.from(punti.values());
      gesto = { tipo: "pizzico", d0: Math.hypot(pp[0].x - pp[1].x, pp[0].y - pp[1].y), vb0: { x: vb.x, y: vb.y, w: vb.w, h: vb.h }, m0: { x: (pp[0].x + pp[1].x) / 2, y: (pp[0].y + pp[1].y) / 2 } };
      nascondiFumetto();
    }
  });
  svg.addEventListener("pointermove", function (e) {
    if (punti.has(e.pointerId)) punti.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (gesto && gesto.tipo === "pizzico" && punti.size === 2) {
      var pp = Array.from(punti.values());
      var d = Math.hypot(pp[0].x - pp[1].x, pp[0].y - pp[1].y);
      var m = { x: (pp[0].x + pp[1].x) / 2, y: (pp[0].y + pp[1].y) / 2 };
      var p0 = aPianta(gesto.m0.x, gesto.m0.y, gesto.vb0);
      var w = gesto.vb0.w / (d / gesto.d0);
      w = Math.min(BASE.w, Math.max(BASE.w / ZOOM_MAX, w));
      var h = (w * BASE.h) / BASE.w;
      var r = svg.getBoundingClientRect();
      cancelAnimationFrame(animVista);
      vb = limita({ w: w, h: h, x: p0.x - ((m.x - r.left) / r.width) * w, y: p0.y - ((m.y - r.top) / r.height) * h });
      pianifica();
      return;
    }
    if (gesto && (gesto.tipo === "tocco" || gesto.tipo === "sposta") && punti.has(e.pointerId)) {
      var dx = e.clientX - gesto.x0, dy = e.clientY - gesto.y0;
      if (!gesto.mosso && Math.hypot(dx, dy) > 5) {
        gesto.mosso = true;
        if (scala() > 1.01) {
          gesto.tipo = "sposta";
          svg.setAttribute("data-trascina", "");
          try { svg.setPointerCapture(e.pointerId); } catch (err) {}
          nascondiFumetto();
        }
      }
      if (gesto.tipo === "sposta") {
        var rr = svg.getBoundingClientRect();
        cancelAnimationFrame(animVista);
        vb = limita({ x: gesto.vb0.x - (dx / rr.width) * gesto.vb0.w, y: gesto.vb0.y - (dy / rr.height) * gesto.vb0.h, w: gesto.vb0.w, h: gesto.vb0.h });
        pianifica();
        return;
      }
    }
    if (e.pointerType === "touch" || senzaHover.matches) return;
    ultimoMove = e;
    if (!rafSopra) rafSopra = requestAnimationFrame(function () {
      rafSopra = 0;
      if (!ultimoMove) return;
      var p = aPianta(ultimoMove.clientX, ultimoMove.clientY);
      var s = vicino(p.x, p.y, 10);
      segnaSopra(s);
      svg.style.cursor = s && s.id ? "pointer" : "";
      if (s) mostraFumetto(s, ultimoMove.clientX, ultimoMove.clientY);
      else nascondiFumetto();
    });
  });
  function fine(e) {
    var g = gesto;
    punti.delete(e.pointerId);
    if (g && g.tipo === "tocco" && !g.mosso && e.type === "pointerup") {
      var p = aPianta(e.clientX, e.clientY);
      var s = vicino(p.x, p.y, g.tipoPuntatore === "touch" ? 22 : 10);
      if (s && s.id) apri(s, { focus: false });
      else if (s && g.tipoPuntatore === "touch") {
        mostraFumetto(s, e.clientX, e.clientY);
        clearTimeout(timerFumetto);
        timerFumetto = setTimeout(nascondiFumetto, 1600);
      }
    }
    if (punti.size === 1 && g && g.tipo === "pizzico") {
      var rest = Array.from(punti.values())[0];
      gesto = { tipo: "sposta", x0: rest.x, y0: rest.y, vb0: { x: vb.x, y: vb.y, w: vb.w, h: vb.h }, mosso: true };
    } else if (punti.size === 0) {
      gesto = null;
      svg.removeAttribute("data-trascina");
    }
  }
  svg.addEventListener("pointerup", fine);
  svg.addEventListener("pointercancel", fine);
  svg.addEventListener("pointerleave", function (e) {
    if (e.pointerType === "touch") return;
    ultimoMove = null;
    segnaSopra(null);
    if (!(fumettoSu && fumettoSu.daTastiera)) nascondiFumetto();
  });

  /* ---------- Fumetto ---------- */

  var fumettoSu = null, timerFumetto;
  function testoFumetto(s) {
    if (!s.id) {
      var dove = AREE[s.k];
      return s.k === "d"
        ? "<strong>" + (s.p ? "Seggio " + s.p : "Seggio") + "</strong><span>Nessun deputato assegnato</span>"
        : "<strong>" + dove + "</strong><span>" + (s.p ? "Seggio " + s.p + " · " : "") + "nessun deputato assegnato</span>";
    }
    var t = "<strong>" + esc(s.n) + "</strong><span>" + esc(nomeGruppoSeggio(s)) + (s.p ? " · seggio " + s.p : "") + "</span>";
    if (modo === "voto" && s.v) t += '<span class="fumetto__voto"><i class="pallino" data-v="' + s.v + '"></i>' + VOTO[s.v].parola + "</span>";
    return t;
  }
  function piazza(x, y, sopraPunto) {
    var w = fumetto.offsetWidth, h = fumetto.offsetHeight;
    var left = Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2));
    var top = sopraPunto ? y - h - 14 : y + 18;
    if (top < 8) top = y + 18;
    if (top + h > window.innerHeight - 8) top = y - h - 14;
    fumetto.style.transform = "translate(" + Math.round(left) + "px," + Math.round(top) + "px)";
  }
  function mostraFumetto(s, x, y) {
    fumettoSu = { s: s, daTastiera: false };
    fumetto.innerHTML = testoFumetto(s);
    fumetto.hidden = false;
    piazza(x, y, true);
  }
  function mostraFumettoSeggio(s, ancora) {
    fumettoSu = { s: s, daTastiera: true };
    if (!ancora) fumetto.innerHTML = testoFumetto(s);
    fumetto.hidden = false;
    var q = aSchermo(s.x, s.y);
    var r = svg.getBoundingClientRect();
    if (q.x < r.left || q.x > r.right || q.y < r.top || q.y > r.bottom) { fumetto.hidden = true; return; }
    piazza(q.x, q.y - (R * r.width) / vb.w, true);
  }
  function nascondiFumetto() {
    fumettoSu = null;
    fumetto.hidden = true;
  }
  window.addEventListener("scroll", function () {
    if (fumettoSu && !fumettoSu.daTastiera) nascondiFumetto();
    else if (fumettoSu) mostraFumettoSeggio(fumettoSu.s, true);
  }, { passive: true });

  /* ---------- Tastiera sulla pianta ---------- */

  function rendiCorrente(s, focus) {
    if (corrente && corrente !== s) corrente.el.setAttribute("tabindex", "-1");
    corrente = s;
    s.el.setAttribute("tabindex", "0");
    if (focus) s.el.focus({ preventScroll: true });
  }
  function prossimo(s, dir) {
    var best = null, bv = Infinity;
    occupati.forEach(function (t) {
      if (t === s) return;
      var da = t.a - s.a, dr = t.r - s.r, v;
      if (dir === "sinistra" || dir === "destra") {
        if (Math.abs(dr) > 34) return;
        if (dir === "sinistra" ? da <= 0 : da >= 0) return;
        v = Math.abs(da) + Math.abs(dr) * 0.01;
      } else {
        if (dir === "su" ? dr < 20 : dr > -20) return;
        v = Math.abs(dr) + Math.abs(da) * 20;
      }
      if (v < bv) { bv = v; best = t; }
    });
    return best;
  }
  svg.addEventListener("keydown", function (e) {
    var s = e.target && e.target.classList && e.target.classList.contains("seggio") ? seggi[+e.target.getAttribute("data-i")] : null;
    var mappa = { ArrowLeft: "sinistra", ArrowRight: "destra", ArrowUp: "su", ArrowDown: "giu" };
    var n = null;
    if (s && mappa[e.key]) n = prossimo(s, mappa[e.key]);
    else if (s && e.key === "Home") n = ordinati[0];
    else if (s && e.key === "End") n = ordinati[ordinati.length - 1];
    else if (s && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      apri(s, { focus: true });
      return;
    } else if (e.key === "+" || e.key === "=") { e.preventDefault(); ingrandisci(1.6, null, null, true); return; }
    else if (e.key === "-") { e.preventDefault(); ingrandisci(1 / 1.6, null, null, true); return; }
    else if (e.key === "0") { e.preventDefault(); vaiA(BASE, 420); return; }
    else return;
    e.preventDefault();
    if (n) rendiCorrente(n, true);
  });
  svg.addEventListener("focusin", function (e) {
    var t = e.target;
    if (!t.classList || !t.classList.contains("seggio")) return;
    var s = seggi[+t.getAttribute("data-i")];
    if (s !== corrente) rendiCorrente(s, false);
    var tastiera = false;
    try { tastiera = t.matches(":focus-visible"); } catch (err) {}
    if (!tastiera) return;
    if (!inVista(s)) centraSu(s, scala());
    requestAnimationFrame(function () { mostraFumettoSeggio(s); });
  });
  svg.addEventListener("focusout", function () {
    if (fumettoSu && fumettoSu.daTastiera) nascondiFumetto();
  });

  /* ---------- Modalità: gruppi o voto ---------- */

  var modo = "gruppi";
  var scelto = null; // { g: "PD" } oppure { g: "Misto", c: "+Europa" }
  var filtroVoto = null;
  var schede = document.querySelectorAll(".comandi .schede [role=tab]");
  var strisciaGruppi = document.getElementById("striscia-gruppi");
  var strisciaVoto = document.getElementById("striscia-voto");

  function luce(sel) {
    /* sel: funzione(seggio) → acceso; null = tutto neutro */
    if (sel) svg.setAttribute("data-luce", "");
    else svg.removeAttribute("data-luce");
    occupati.forEach(function (s) {
      if (sel && sel(s)) s.el.setAttribute("data-on", "");
      else s.el.removeAttribute("data-on");
    });
    pianifica3d();
  }
  function filtroGruppo(f) {
    if (!f) return null;
    return function (s) { return s.g === f.g && (f.c === undefined || s.c === f.c); };
  }

  function impostaModo(m, daHash) {
    if (m === modo && !daHash) return;
    modo = m;
    schede.forEach(function (b) { b.setAttribute("aria-selected", b.dataset.modo === m ? "true" : "false"); b.tabIndex = b.dataset.modo === m ? 0 : -1; });
    strisciaGruppi.hidden = m !== "gruppi";
    strisciaVoto.hidden = m !== "voto";
    svg.setAttribute("data-modo", m);
    if (!ridotto) {
      svg.setAttribute("data-spazza", "");
      setTimeout(function () { svg.removeAttribute("data-spazza"); }, 950);
    }
    coloraSeggi();
    if (m === "voto") {
      svg.removeAttribute("data-luce");
      applicaFiltroVoto();
    } else {
      svg.removeAttribute("data-filtro");
      luce(filtroGruppo(scelto));
    }
    etichetteSeggi();
    pianifica3d();
    if (aperto) riempiCassetto(aperto);
    testaVoto.hidden = m !== "voto";
    if (m !== "voto") chiudiScegli(false);
    collocaCassetto();
    try {
      history.replaceState(null, "", m === "voto" ? (V.id ? "#voto=" + V.id : "#voto") : location.pathname + location.search);
    } catch (err) {}
    if (m === "voto") avviaVoti(daHash && typeof daHash === "string" ? daHash : null);
  }
  schede.forEach(function (b) {
    b.addEventListener("click", function () { impostaModo(b.dataset.modo); });
    b.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      var altro = b.dataset.modo === "gruppi" ? "voto" : "gruppi";
      impostaModo(altro);
      document.querySelector('.comandi .schede [data-modo="' + altro + '"]').focus();
    });
  });

  /* Gruppi */
  var conta = {}, contaC = {};
  occupati.forEach(function (s) {
    conta[s.g] = (conta[s.g] || 0) + 1;
    if (s.g === "Misto") contaC[s.c || ""] = (contaC[s.c || ""] || 0) + 1;
  });
  var boxGruppi = document.getElementById("gruppi");
  var info = document.getElementById("gruppo-info");
  boxGruppi.innerHTML = A.groups.map(function (g) {
    return '<button type="button" aria-pressed="false" data-g="' + esc(g.acronym) + '" aria-label="' + esc(g.name) + ", " + (conta[g.acronym] || 0) + ' seggi">' +
      '<span class="g-sigla">' + esc(g.acronym) + '</span><span class="g-n">' + (conta[g.acronym] || 0) + "</span></button>";
  }).join("");
  var INFO_VUOTA = "Scegli un gruppo per accenderne i seggi. I gruppi non hanno un colore: si guardano uno alla volta.";

  function scriviInfo() {
    if (!scelto) { info.innerHTML = '<span class="tenue">' + INFO_VUOTA + "</span>"; return; }
    var g = scelto.g;
    var t = "<strong>" + esc(GRUPPI[g]) + "</strong> · " + conta[g] + " seggi in Aula.";
    if (g === "Misto") {
      t += " Nel Misto ogni deputato si attribuisce alla sua componente." +
        '<div class="componenti" role="group" aria-label="Componenti del Gruppo Misto">' +
        Object.keys(contaC).sort(function (a, b) { return contaC[b] - contaC[a] || (a ? 0 : 1); }).filter(function (c) { return c; }).concat(contaC[""] ? [""] : [])
          .map(function (c) {
            var on = scelto.c !== undefined && scelto.c === (c || null);
            return '<button type="button" aria-pressed="' + on + '" data-c="' + esc(c) + '">' + esc(c ? COMPONENTI[c] || c : "Senza componente") + ' <span class="n">' + contaC[c] + "</span></button>";
          }).join("") + "</div>";
    }
    info.innerHTML = t;
  }
  function scegliGruppo(g, c) {
    if (g && scelto && scelto.g === g && c === undefined && scelto.c === undefined) g = null;
    scelto = g ? { g: g } : null;
    if (scelto && c !== undefined) scelto.c = c;
    boxGruppi.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", scelto && b.dataset.g === scelto.g ? "true" : "false"); });
    luce(filtroGruppo(scelto));
    scriviInfo();
    if (scelto && vista === "aula" && aula3d) {
      var f = filtroGruppo(scelto);
      aula3d.orienta(occupati.filter(f).map(function (s) { return s.i; }));
      mostraRiadatta(true);
    }
  }
  boxGruppi.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (b) scegliGruppo(b.dataset.g);
  });
  info.addEventListener("click", function (e) {
    var b = e.target.closest("[data-c]");
    if (!b) return;
    var c = b.dataset.c || null;
    if (scelto && scelto.c === c) scegliGruppo("Misto"); // seconda pressione: tutto il Misto
    else scegliGruppo("Misto", c);
    var dopo = info.querySelector('[data-c="' + (c || "") + '"]');
    if (dopo) dopo.focus();
  });
  /* Anteprima al passaggio, senza cambiare la scelta */
  function anteprima(g) {
    if (modo !== "gruppi") return;
    luce(g ? filtroGruppo({ g: g }) : filtroGruppo(scelto));
  }
  boxGruppi.addEventListener("pointerover", function (e) {
    var b = e.target.closest("button");
    if (b && e.pointerType !== "touch") anteprima(b.dataset.g);
  });
  boxGruppi.addEventListener("pointerleave", function () { anteprima(null); });
  boxGruppi.addEventListener("focusin", function (e) {
    var b = e.target.closest("button");
    if (b && b.matches(":focus-visible")) anteprima(b.dataset.g);
  });
  boxGruppi.addEventListener("focusout", function () { anteprima(null); });
  scriviInfo();

  /* ---------- Voti: qualsiasi votazione elettronica della legislatura ----------
   *
   * Sedute e votazioni arrivano da /api (stesso indirizzo della pagina, inoltrato al
   * backend da serve.py). Se /api non risponde al primo accesso, resta la fiducia del
   * 7/10/2026 salvata in AULA.vote e nei campi `v` dei seggi.
   */

  var API = "/api/timeline";
  var ORDINE_V = ["favor", "against", "abstain", "absent", "n.d."];
  var ORDINE_SEGRETO = ["abstain", "segreto", "n.d."];
  var boxVoti = document.getElementById("voti");
  var testaVoto = document.getElementById("voto-testa");
  var elMeta = document.getElementById("voto-meta");
  var elTitolo = document.getElementById("voto-titolo");
  var elEsito = document.getElementById("esito-voto");
  var elUfficiale = document.getElementById("voto-ufficiale");
  var elNd = document.getElementById("voto-nd");
  var elLink = document.getElementById("voto-link");
  var elAvviso = document.getElementById("voto-avviso");
  var annuncio = document.getElementById("voto-annuncio");
  var btnCambia = document.getElementById("voto-cambia");
  var scegliBox = document.getElementById("scegli-voto");
  var listaSedute = document.getElementById("lista-sedute");
  var listaVoti = document.getElementById("lista-voti");
  var statoSedute = document.getElementById("sedute-stato");
  var statoVoti = document.getElementById("voti-stato");
  var btnAltre = document.getElementById("sedute-altre");
  var cercaSedute = document.getElementById("cerca-sedute");
  var votiTitolo = document.getElementById("voti-titolo");
  var FRECCIA_NE = '<svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg>';

  var V = {
    sedute: [], cursore: null, altre: false, cerca: "", erroreSedute: false,
    seduta: null, voti: [], erroreVoti: false,
    id: null, det: null, carica: false, errore: null,
    inLinea: false, avviato: false,
  };
  var turno = { sedute: 0, voti: 0, voto: 0 };
  var ctrl = {};
  var cache = new Map();

  function abortito(err) { return err && err.name === "AbortError"; }
  /* Una richiesta per tipo alla volta: la nuova interrompe la precedente */
  function prendi(url, quale) {
    if (quale && ctrl[quale]) ctrl[quale].abort();
    if (cache.has(url)) return Promise.resolve(cache.get(url));
    var c = quale ? (ctrl[quale] = new AbortController()) : null;
    return fetch(url, { signal: c ? c.signal : undefined, headers: { Accept: "application/json" } }).then(function (r) {
      var tipo = r.headers.get("content-type") || "";
      if (!r.ok || tipo.indexOf("json") < 0) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (j) {
      V.inLinea = true;
      if (cache.size > 150) cache.delete(cache.keys().next().value);
      cache.set(url, j);
      return j;
    });
  }

  /* Testi delle votazioni */
  function pulisci(t) {
    return String(t || "").replace(/ /g, " ").replace(/\s*\(ore \d+[,.]\d+\)\.?/g, "").replace(/\s+/g, " ").trim();
  }
  function accorcia(t, n) {
    t = pulisci(t);
    if (t.length <= n) return t;
    return t.slice(0, n).replace(/[\s,;:.(-]+[^\s]*$/, "") + "…";
  }
  function maiuscola(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function finale(v) { return !!(v.final_vote || /finale/i.test(v.vote_type || "") || /^votazione finale$/i.test(pulisci(v.subject))); }
  /* { t: titolo, tag: sigla ufficiale da mostrare accanto, se aggiunge qualcosa } */
  function titoloVoto(v, perLista) {
    var sub = pulisci(v.subject), desc = pulisci(v.description);
    var resto = sub.replace(/^votazione\b\s*/i, "");
    if (finale(v)) {
      var cosa = desc.replace(/\s*-?\s*voto finale$/i, "");
      return perLista ? { t: cosa || "Voto finale", tag: "" } : { t: "Voto finale" + (cosa ? " · " + cosa : ""), tag: "" };
    }
    if (resto) return { t: maiuscola(resto), tag: piega(desc) === piega(resto) ? "" : desc };
    return { t: desc || "Votazione " + v.number, tag: "" };
  }
  function parti(id) {
    var m = /^camera_(leg19_sed(\d+))_v(\d+)$/.exec(id || "");
    return m ? { seduta: m[1], numero: +m[2], voto: +m[3] } : null;
  }
  function sedutaDi(id) {
    var p = parti(id);
    if (!p) return null;
    if (V.seduta && V.seduta.id === p.seduta) return V.seduta;
    for (var i = 0; i < V.sedute.length; i++) if (V.sedute[i].id === p.seduta) return V.sedute[i];
    return null;
  }
  function metaVoto() {
    var p = parti(V.id), s = sedutaDi(V.id);
    if (!p) return "";
    return "Seduta " + p.numero + (s && s.date ? " · " + data(s.date) : "") + " · votazione " + p.voto;
  }
  function etichettaVotoBreve() {
    var p = parti(V.id), s = sedutaDi(V.id);
    if (!p) return "Votazione";
    return "Votazione " + p.voto + " · seduta " + p.numero + (s && s.date ? " del " + data(s.date) : "");
  }
  function esitoParola(o) { return o === "approved" ? "Approvata" : o === "rejected" ? "Respinta" : ""; }
  function num(x) { return x == null ? "n.d." : window.numero(x); }

  /* Fiducia del 7/10/2026, salvata nella pagina */
  occupati.forEach(function (s) { s.v0 = s.v; s.v = null; });
  function votoSalvato() {
    var p = parti(A.vote.id);
    return {
      id: A.vote.id, number: p.voto, subject: A.vote.subject, description: A.vote.description,
      outcome: A.vote.outcome, secret_vote: false, in_favor: A.vote.in_favor, against: A.vote.against,
      abstained: A.vote.abstained, present: A.vote.present, majority: A.vote.majority,
      acts: [{ title: "Pdl C. 2822-B", url: "https://www.camera.it/leg19/126?tab=1&leg=19&idDocumento=2822" }],
      session_annex_url: null, salvato: true,
    };
  }

  /* ---------- Applicazione ai seggi ---------- */

  function contaVoti() {
    var c = {};
    occupati.forEach(function (s) { if (s.v) c[s.v] = (c[s.v] || 0) + 1; });
    return c;
  }
  function coloraSeggi() {
    occupati.forEach(function (s) {
      if (modo === "voto" && s.v) s.el.setAttribute("data-v", s.v);
      else s.el.removeAttribute("data-v");
    });
    if (modo === "voto") svg.toggleAttribute("data-carica", V.carica);
    else svg.removeAttribute("data-carica");
  }
  function applicaVoto(det) {
    var mappa = {};
    (det.participants || []).forEach(function (p) {
      var m = /\/p(\d+)$/.exec(p.id || "");
      if (m) mappa[m[1]] = p.outcome;
    });
    occupati.forEach(function (s) {
      if (det.salvato) { s.v = s.v0; return; }
      var o = mappa[s.id];
      if (!o) s.v = "n.d.";
      else if (det.secret_vote) s.v = o === "abstain" ? "abstain" : "segreto";
      else if (o === "secret") s.v = "segreto";
      else s.v = VOTO[o] ? o : "n.d.";
    });
    V.det = det;
    V.carica = false;
    V.errore = null;
    filtroVoto = null;
    scriviVoto();
    coloraSeggi();
    applicaFiltroVoto();
    etichetteSeggi();
    if (aperto) riempiCassetto(aperto);
    var c = contaVoti();
    annuncia(etichettaVotoBreve() + (esitoParola(det.outcome) ? ": " + esitoParola(det.outcome).toLowerCase() : "") +
      (det.secret_vote ? ", scrutinio segreto" : ", " + (c.favor || 0) + " favorevoli, " + (c.against || 0) + " contrari sui seggi"));
  }
  var timerAnnuncio;
  function annuncia(t) {
    clearTimeout(timerAnnuncio);
    annuncio.textContent = "";
    timerAnnuncio = setTimeout(function () { annuncio.textContent = t; }, 60);
  }

  /* ---------- Testata, legenda, note ---------- */

  function bottoneRiprova(azione, testo) {
    return '<button class="btn btn--linea btn--piccolo" type="button" data-riprova="' + azione + '">' + (testo || "Riprova") + "</button>";
  }
  function scriviVoto() {
    var d = V.det;
    testaVoto.setAttribute("aria-busy", V.carica ? "true" : "false");
    testaVoto.toggleAttribute("data-carica", V.carica);
    if (V.errore) {
      elMeta.textContent = metaVoto() || "Votazione";
      elTitolo.innerHTML = '<span class="voto-errore">' + esc(V.errore) + "</span>";
      elTitolo.removeAttribute("title");
      elEsito.innerHTML = bottoneRiprova("voto");
    } else if (V.carica || !d) {
      elMeta.textContent = metaVoto() || "Votazione";
      elTitolo.innerHTML = '<span class="riga-attesa" aria-hidden="true"></span><span class="sr">Carico la votazione…</span>';
      elTitolo.removeAttribute("title");
      elEsito.innerHTML = '<span class="tenue">Carico la votazione…</span>';
    } else {
      var t = titoloVoto(d);
      elMeta.textContent = metaVoto();
      elTitolo.innerHTML = esc(accorcia(t.t, 160)) + (t.tag ? ' <span class="mono tenue">' + esc(t.tag) + "</span>" : "");
      elTitolo.title = pulisci(t.t + (t.tag ? " · " + t.tag : ""));
      var es = esitoParola(d.outcome);
      elEsito.innerHTML = es ? '<i class="pallino" data-v="' + (d.outcome === "approved" ? "favor" : "against") + '"></i>' + es : "";
    }

    /* Legenda: conteggi dai seggi */
    var ordine = d && d.secret_vote && !V.carica ? ORDINE_SEGRETO : ORDINE_V;
    var vuota = V.carica || V.errore || !d;
    var c = vuota ? {} : contaVoti();
    boxVoti.setAttribute("data-n", ordine.length);
    boxVoti.innerHTML = ordine.map(function (v) {
      return '<button type="button" aria-pressed="' + (filtroVoto === v) + '" data-v="' + v + '"' + (vuota ? " disabled" : "") + '><i class="pallino v-p" data-v="' + v + '"></i>' +
        '<span class="v-n">' + (V.errore ? "–" : vuota ? '<span class="riga-attesa riga-attesa--n" aria-hidden="true"></span>' : c[v] || 0) + '</span><span class="v-l">' + VOTO[v].plurale + "</span></button>";
    }).join("");

    /* Avvisi */
    var avvisi = [];
    if (d && d.salvato && !V.carica) avvisi.push('<p>Backend non raggiungibile: mostro l\'ultimo voto salvato.</p><p>' + bottoneRiprova("collega", "Riprova a collegarti") + "</p>");
    if (d && d.secret_vote && !V.carica) avvisi.push("<p><strong>Scrutinio segreto: i voti dei singoli non sono pubblici.</strong> Sui seggi restano solo le astensioni registrate.</p>");
    elAvviso.innerHTML = avvisi.join("");
    elAvviso.hidden = !avvisi.length;

    if (!d || V.carica || V.errore) {
      elUfficiale.textContent = "";
      elNd.textContent = "";
      elLink.innerHTML = "";
      return;
    }
    elUfficiale.innerHTML = d.in_favor == null ? "Totali ufficiali non disponibili." :
      "Totali ufficiali: <strong>" + num(d.in_favor) + "</strong> favorevoli, <strong>" + num(d.against) + "</strong> contrari, <strong>" + num(d.abstained) +
      "</strong> astenuti." + (d.present != null ? " Presenti " + num(d.present) + (d.majority != null ? ", maggioranza richiesta " + num(d.majority) : "") + "." : "");

    var nota = "I numeri qui sopra contano i seggi di oggi. «Non associato» indica un voto che i dati non collegano a un seggio: per esempio i deputati che siedono ai banchi del Governo, o chi è entrato alla Camera dopo questa votazione.";
    if (!d.secret_vote && d.in_favor != null) {
      var diff = [];
      [["favor", d.in_favor, "favorevoli"], ["against", d.against, "contrari"], ["abstain", d.abstained, "astenuti"]].forEach(function (x) {
        if (x[1] != null && (c[x[0]] || 0) !== x[1]) diff.push((c[x[0]] || 0) + " " + x[2] + " e non " + x[1]);
      });
      if (diff.length) nota += " Per questo sui seggi risultano " + diff.join(", ") + ".";
    }
    elNd.textContent = nota;

    var p = parti(d.id), link = [];
    if (p) link.push('<a class="collegamento" href="https://www.camera.it/leg19/410?idSeduta=' + String(p.numero).padStart(4, "0") + '&amp;tipo=stenografico" rel="noopener">Resoconto della seduta ' + p.numero + FRECCIA_NE + "</a>");
    (d.acts || []).slice(0, 3).forEach(function (a) {
      if (!a.url) return;
      link.push('<a class="collegamento" href="' + esc(a.url) + '" rel="noopener" title="' + esc(pulisci(a.title)) + '">' + esc(accorcia(a.title || "L'atto sul sito della Camera", 70)) + FRECCIA_NE + "</a>");
    });
    if (d.session_annex_url) link.push('<a class="collegamento" href="' + esc(d.session_annex_url) + '" rel="noopener">Testo votato <span class="tenue">(Allegato A)</span>' + FRECCIA_NE + "</a>");
    elLink.innerHTML = link.join("");
  }

  function applicaFiltroVoto() {
    boxVoti.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.v === filtroVoto ? "true" : "false"); });
    if (filtroVoto) {
      boxVoti.setAttribute("data-filtro", "");
      svg.setAttribute("data-filtro", "");
      occupati.forEach(function (s) {
        if (s.v === filtroVoto) s.el.setAttribute("data-on", ""); else s.el.removeAttribute("data-on");
      });
    } else {
      boxVoti.removeAttribute("data-filtro");
      svg.removeAttribute("data-filtro");
      occupati.forEach(function (s) { s.el.removeAttribute("data-on"); });
    }
    pianifica3d();
  }
  boxVoti.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b || b.disabled) return;
    filtroVoto = filtroVoto === b.dataset.v ? null : b.dataset.v;
    applicaFiltroVoto();
  });

  /* ---------- Caricamento di una votazione ---------- */

  function scriviHash() {
    if (modo !== "voto") return;
    try { history.replaceState(null, "", V.id ? "#voto=" + V.id : "#voto"); } catch (err) {}
  }
  function apriVoto(id, opz) {
    opz = opz || {};
    var mio = ++turno.voto;
    V.id = id;
    V.det = null;
    V.carica = true;
    V.errore = null;
    filtroVoto = null;
    occupati.forEach(function (s) { s.v = null; });
    scriviHash();
    scriviVoto();
    coloraSeggi();
    applicaFiltroVoto();
    etichetteSeggi();
    if (aperto) riempiCassetto(aperto);
    segnaVotoCorrente();
    annuncia("Carico la votazione…");
    if (!opz.senzaSeduta) assicuraSeduta(id);
    return prendi(API + "/votes/" + encodeURIComponent(id), "voto").then(function (det) {
      if (mio !== turno.voto) return;
      if (!det || (!det.outcome && !(det.participants || []).length)) {
        V.carica = false;
        V.errore = "Votazione non trovata nei dati.";
        scriviVoto();
        coloraSeggi();
        annuncia(V.errore);
        return;
      }
      applicaVoto(det);
    }).catch(function (err) {
      if (abortito(err) || mio !== turno.voto) return;
      if (!V.inLinea) { usaSalvato(); return; }
      V.carica = false;
      V.errore = "Non riesco a caricare la votazione.";
      scriviVoto();
      coloraSeggi();
      if (aperto) riempiCassetto(aperto);
      annuncia(V.errore);
    });
  }
  function usaSalvato() {
    turno.voto++;
    if (ctrl.voto) ctrl.voto.abort();
    V.id = A.vote.id;
    V.seduta = V.seduta && V.seduta.id === "leg19_sed722" ? V.seduta : { id: "leg19_sed722", number: 722, date: A.date, vote_count: null, salvata: true };
    scriviHash();
    applicaVoto(votoSalvato());
    if (!V.sedute.length && V.erroreSedute) scriviSedute();
    if (!V.inLinea) {
      turno.voti++;
      votiTitolo.textContent = "Seduta 722 · " + data(A.date);
      listaVoti.innerHTML = "";
      listaVoti.setAttribute("aria-busy", "false");
      statoVoti.innerHTML = '<p class="nota">Senza collegamento al backend l\'elenco delle votazioni non è disponibile.</p>';
    }
  }

  /* ---------- Elenco delle sedute ---------- */

  function sheet() { return window.matchMedia("(max-width: 720px)").matches; }
  /* A passi (prima la seduta, poi la votazione) sotto i 960px e nella colonna accanto all'Aula da 1100px */
  function aPassi() { return window.matchMedia("(max-width: 960px), (min-width: 1100px)").matches; }

  function righeAttesa(k) {
    var r = "";
    for (var i = 0; i < k; i++) r += '<li class="scegli__attesa" aria-hidden="true"><span class="riga-attesa"></span><span class="riga-attesa riga-attesa--corta"></span></li>';
    return r;
  }
  function temaTrovato(s) {
    if (!V.cerca) return "";
    var q = piega(V.cerca);
    var d = (s.debates || []).filter(function (x) { return piega(x.title).indexOf(q) >= 0; })[0];
    return d ? accorcia(d.title, 120) : "";
  }
  function scriviSedute(caricando) {
    var conVoti = V.sedute;
    var h = conVoti.map(function (s) {
      var on = V.seduta && V.seduta.id === s.id;
      var tema = temaTrovato(s);
      return '<li><button type="button" class="voce voce--seduta" data-id="' + esc(s.id) + '"' + (on ? ' aria-current="true"' : "") + ' tabindex="-1">' +
        '<span class="voce__t">' + esc(data(s.date)) + "</span>" +
        '<span class="voce__d">Seduta ' + s.number + " · " + s.vote_count + (s.vote_count === 1 ? " votazione" : " votazioni") + "</span>" +
        (tema ? '<span class="voce__tema">' + esc(tema) + "</span>" : "") + "</button></li>";
    }).join("");
    if (caricando) h += righeAttesa(conVoti.length ? 2 : 7);
    listaSedute.innerHTML = h;
    listaSedute.setAttribute("aria-busy", caricando ? "true" : "false");
    roving(listaSedute);
    btnAltre.hidden = caricando || !V.altre || V.erroreSedute;
    if (V.erroreSedute) {
      statoSedute.innerHTML = '<p class="messaggio" data-tipo="errore">' + (V.inLinea ? "Non riesco a caricare le sedute." : "Backend non raggiungibile: l'elenco delle sedute non è disponibile.") + "</p>" + bottoneRiprova("sedute");
    } else if (!caricando && !conVoti.length) {
      statoSedute.innerHTML = '<p class="nota">' + (V.cerca ? "Nessuna seduta con votazioni per «" + esc(V.cerca) + "»." : "Nessuna seduta con votazioni.") + "</p>";
    } else statoSedute.innerHTML = caricando ? '<span class="sr">Carico le sedute…</span>' : "";
  }
  /* Carica una pagina di sedute; salta da sola le pagine senza votazioni */
  function caricaSedute(daCapo) {
    var mio = ++turno.sedute;
    if (daCapo) { V.sedute = []; V.cursore = null; V.altre = false; }
    V.erroreSedute = false;
    scriviSedute(true);
    var giri = 0;
    function pagina() {
      var url = API + "?limit=30" + (V.cursore ? "&before=" + encodeURIComponent(V.cursore) : "") + (V.cerca ? "&search=" + encodeURIComponent(V.cerca) : "");
      return prendi(url, "sedute").then(function (j) {
        if (mio !== turno.sedute) return;
        var nuove = (j.sessions || []).filter(function (s) { return s.vote_count > 0; });
        var visti = {};
        V.sedute.forEach(function (s) { visti[s.id] = 1; });
        nuove.forEach(function (s) { if (!visti[s.id]) V.sedute.push(s); });
        V.cursore = j.next_cursor || null;
        V.altre = !!(j.has_more && j.next_cursor);
        if (!nuove.length && V.altre && ++giri < 6) return pagina();
        scriviSedute(false);
      });
    }
    return pagina().catch(function (err) {
      if (abortito(err) || mio !== turno.sedute) throw err;
      V.erroreSedute = true;
      scriviSedute(false);
      throw err;
    });
  }

  /* ---------- Votazioni di una seduta ---------- */

  function segnaVotoCorrente() {
    listaVoti.querySelectorAll(".voce").forEach(function (b) {
      if (b.dataset.id === V.id) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
    });
  }
  function scriviVoti(caricando) {
    var s = V.seduta;
    votiTitolo.textContent = s ? "Seduta " + s.number + (s.date ? " · " + data(s.date) : "") : "Votazioni";
    if (caricando) {
      listaVoti.innerHTML = righeAttesa(6);
      listaVoti.setAttribute("aria-busy", "true");
      statoVoti.innerHTML = '<span class="sr">Carico le votazioni della seduta…</span>';
      return;
    }
    listaVoti.setAttribute("aria-busy", "false");
    if (V.erroreVoti) {
      listaVoti.innerHTML = "";
      statoVoti.innerHTML = '<p class="messaggio" data-tipo="errore">Non riesco a caricare le votazioni di questa seduta.</p>' + bottoneRiprova("voti");
      return;
    }
    if (!s) { listaVoti.innerHTML = ""; statoVoti.innerHTML = '<p class="nota">Scegli una seduta.</p>'; return; }
    listaVoti.innerHTML = V.voti.map(function (v) {
      var t = titoloVoto(v, true);
      var es = esitoParola(v.outcome);
      return '<li><button type="button" class="voce voce--voto" data-id="' + esc(v.id) + '"' + (v.id === V.id ? ' aria-current="true"' : "") + ' tabindex="-1">' +
        '<span class="voce__n">' + v.number + "</span>" +
        '<span class="voce__corpo"><span class="voce__t">' + esc(accorcia(t.t, 110)) + "</span>" +
        '<span class="voce__d">' + (finale(v) ? '<span class="voce__finale">Voto finale</span>' : "") +
        (es ? '<span class="voce__esito"><i class="pallino" data-v="' + (v.outcome === "approved" ? "favor" : "against") + '"></i>' + es + "</span>" : "") +
        (v.in_favor != null ? '<span class="voce__conti" aria-label="' + v.in_favor + " favorevoli, " + v.against + " contrari, " + v.abstained + ' astenuti">' + v.in_favor + " sì · " + v.against + " no · " + v.abstained + " ast.</span>" : "") +
        "</span></span></button></li>";
    }).join("");
    statoVoti.innerHTML = V.voti.length ? "" : '<p class="nota">Nessuna votazione elettronica in questa seduta.</p>';
    roving(listaVoti);
    /* Porta in vista la votazione scelta, solo dentro l'elenco */
    var cur = listaVoti.querySelector('[aria-current="true"]');
    if (cur) {
      var li = cur.parentNode;
      if (li.offsetTop < listaVoti.scrollTop || li.offsetTop + li.offsetHeight > listaVoti.scrollTop + listaVoti.clientHeight) listaVoti.scrollTop = Math.max(0, li.offsetTop - listaVoti.clientHeight / 3);
    } else listaVoti.scrollTop = 0;
  }
  function votoPredefinito(lista) {
    var finali = lista.filter(finale);
    return finali.length ? finali[finali.length - 1] : lista[lista.length - 1];
  }
  /* All'ingresso apre l'ultimo voto palese: uno scrutinio segreto mostrerebbe un'Aula grigia.
     Prova le sedute più recenti, prima i voti finali e poi gli altri, dal più recente. */
  function primoPalese(sedute) {
    var i = 0;
    function prossima() {
      if (V.id) return; // nel frattempo l'utente ha scelto
      if (i >= sedute.length) { scegliSeduta(sedute[0], { predefinito: true, passo: false }); return; }
      var s = sedute[i++];
      prendi(API + "/sessions/" + encodeURIComponent(s.id) + "/votes").then(function (lista) {
        lista = (lista || []).slice().sort(function (a, b) { return b.number - a.number; });
        var candidati = lista.filter(finale).concat(lista.filter(function (v) { return !finale(v); })).slice(0, 4);
        var j = 0;
        (function prova() {
          if (V.id) return;
          if (j >= candidati.length) return prossima();
          var v = candidati[j++];
          prendi(API + "/votes/" + encodeURIComponent(v.id)).then(function (d) {
            if (d && !d.secret_vote) {
              scegliSeduta(s);
              apriVoto(v.id, { senzaSeduta: true });
            } else prova();
          }, prova);
        })();
      }, prossima);
    }
    prossima();
  }
  function scegliSeduta(s, opz) {
    opz = opz || {};
    var mio = ++turno.voti;
    V.seduta = s;
    V.voti = [];
    V.erroreVoti = false;
    listaSedute.querySelectorAll(".voce").forEach(function (b) {
      if (b.dataset.id === s.id) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
    });
    if (opz.passo !== false) scegliBox.setAttribute("data-passo", "voti");
    scriviVoti(true);
    return prendi(API + "/sessions/" + encodeURIComponent(s.id) + "/votes", "voti").then(function (lista) {
      if (mio !== turno.voti) return;
      V.voti = (lista || []).slice().sort(function (a, b) { return a.number - b.number; });
      scriviVoti(false);
      if (opz.focus) {
        var b = listaVoti.querySelector('[tabindex="0"]');
        if (b) b.focus({ preventScroll: true });
      }
      if (opz.predefinito && V.voti.length) apriVoto(votoPredefinito(V.voti).id, { senzaSeduta: true });
    }).catch(function (err) {
      if (abortito(err) || mio !== turno.voti) return;
      V.erroreVoti = true;
      scriviVoti(false);
      if (opz.predefinito && !V.inLinea) usaSalvato();
    });
  }
  /* La seduta di una votazione aperta da link: dall'elenco, o cercata per data */
  function assicuraSeduta(id) {
    var p = parti(id);
    if (!p) return;
    if (V.seduta && V.seduta.id === p.seduta) return;
    var s = sedutaDi(id);
    if (s) { scegliSeduta(s, { passo: false }); return; }
    s = { id: p.seduta, number: p.numero, date: null, vote_count: null };
    scegliSeduta(s, { passo: false });
    trovaSeduta(p.numero).then(function (t) {
      if (!t || V.seduta !== s) return;
      s.date = t.date;
      s.vote_count = t.vote_count;
      scriviVoti(false);
      aggiornaTesta();
    }).catch(function () {});
  }
  /* La data della seduta può arrivare dopo la votazione */
  function aggiornaTesta() {
    if (V.det && !V.carica && !V.errore) scriviVoto(); else elMeta.textContent = metaVoto() || "Votazione";
    if (aperto) riempiCassetto(aperto);
  }
  /* L'API non ha un indirizzo per seduta: ricerca per data sulle sedute (to_date, limit=1) */
  function trovaSeduta(num) {
    var giorno = 864e5;
    var lo = new Date("2022-10-13T12:00:00").getTime(), hi = Date.now(), giri = 0;
    function iso(t) { return new Date(t).toISOString().slice(0, 10); }
    function passo() {
      if (giri++ > 16 || lo > hi) return Promise.resolve(null);
      var mid = lo + Math.floor((hi - lo) / 2 / giorno) * giorno;
      return prendi(API + "?limit=1&to_date=" + iso(mid)).then(function (j) {
        var s = j.sessions && j.sessions[0];
        if (!s) { lo = mid + giorno; return passo(); }
        if (s.number === num) return s;
        if (s.number < num) lo = mid + giorno;
        else hi = new Date(s.date + "T12:00:00").getTime() - giorno;
        return passo();
      });
    }
    return passo();
  }

  /* ---------- Avvio della modalità Voti ---------- */

  function avviaVoti(id) {
    if (id && id === V.id && (V.det || V.carica)) return;
    if (id) {
      apriVoto(id, { senzaSeduta: true });
      if (V.avviato) { assicuraSeduta(id); return; }
    }
    if (V.avviato) return;
    V.avviato = true;
    if (!id) {
      /* Testata in attesa finché non arriva la prima seduta */
      V.carica = true;
      scriviVoto();
      coloraSeggi();
    }
    caricaSedute(true).then(function () {
      if (id) { assicuraSeduta(id); aggiornaTesta(); return; }
      if (V.id) return; // nel frattempo l'utente ha scelto
      if (V.sedute[0]) primoPalese(V.sedute.slice(0, 4));
      else usaSalvato();
    }).catch(function (err) {
      if (abortito(err)) return;
      if (!id && !V.inLinea) usaSalvato();
    });
  }
  function riprova(azione) {
    if (azione === "voto" && V.id) apriVoto(V.id, { senzaSeduta: true });
    else if (azione === "sedute") caricaSedute(V.sedute.length === 0).catch(function () {});
    else if (azione === "voti" && V.seduta) scegliSeduta(V.seduta, { passo: false });
    else if (azione === "collega") {
      cache.clear();
      V.avviato = false;
      V.id = null;
      V.det = null;
      V.seduta = null;
      avviaVoti();
    }
  }
  document.getElementById("striscia-voto").addEventListener("click", function (e) {
    var b = e.target.closest("[data-riprova]");
    if (b) riprova(b.dataset.riprova);
  });
  testaVoto.addEventListener("click", function (e) {
    var b = e.target.closest("[data-riprova]");
    if (b) riprova(b.dataset.riprova);
  });

  /* ---------- Interazione con l'elenco ---------- */

  /* Un solo elemento per elenco nel giro del Tab; frecce, Home e Fine per muoversi */
  function roving(ul) {
    var voci = ul.querySelectorAll(".voce");
    if (!voci.length) return;
    var cur = ul.querySelector('.voce[aria-current="true"]') || voci[0];
    voci.forEach(function (b) { b.tabIndex = b === cur ? 0 : -1; });
  }
  function tastiLista(e) {
    var b = e.target.closest(".voce");
    if (!b) return;
    var voci = Array.prototype.slice.call(this.querySelectorAll(".voce"));
    var i = voci.indexOf(b), j = -1;
    if (e.key === "ArrowDown") j = Math.min(voci.length - 1, i + 1);
    else if (e.key === "ArrowUp") j = Math.max(0, i - 1);
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = voci.length - 1;
    else if (e.key === "ArrowLeft" && this === listaVoti && aPassi()) { e.preventDefault(); indietro(); return; }
    else return;
    e.preventDefault();
    voci.forEach(function (x, k) { x.tabIndex = k === j ? 0 : -1; });
    voci[j].focus({ preventScroll: true });
    var li = voci[j].parentNode, ul = this;
    if (li.offsetTop < ul.scrollTop) ul.scrollTop = li.offsetTop - 4;
    else if (li.offsetTop + li.offsetHeight > ul.scrollTop + ul.clientHeight) ul.scrollTop = li.offsetTop + li.offsetHeight - ul.clientHeight + 4;
  }
  listaSedute.addEventListener("keydown", tastiLista);
  listaVoti.addEventListener("keydown", tastiLista);
  listaSedute.addEventListener("click", function (e) {
    var b = e.target.closest(".voce");
    if (!b) return;
    var s = V.sedute.filter(function (x) { return x.id === b.dataset.id; })[0];
    if (s) scegliSeduta(s, { focus: aPassi() });
  });
  listaVoti.addEventListener("click", function (e) {
    var b = e.target.closest(".voce");
    if (!b) return;
    if (b.dataset.id !== V.id || V.errore) apriVoto(b.dataset.id, { senzaSeduta: true });
    if (sheet() && scegliBox.hasAttribute("data-aperto")) chiudiScegli(false);
  });
  function indietro() {
    scegliBox.setAttribute("data-passo", "sedute");
    var b = listaSedute.querySelector('[tabindex="0"]');
    if (b) b.focus({ preventScroll: true });
  }
  document.getElementById("scegli-indietro").addEventListener("click", indietro);
  btnAltre.addEventListener("click", function () {
    var primo = V.sedute.length;
    caricaSedute(false).then(function () {
      var b = listaSedute.querySelectorAll(".voce")[primo];
      if (b) { listaSedute.querySelectorAll(".voce").forEach(function (x) { x.tabIndex = x === b ? 0 : -1; }); b.focus({ preventScroll: true }); }
    }).catch(function () {});
  });

  /* Ricerca per tema: titoli dei dibattiti (e riassunti delle sedute, lato backend) */
  var timerCerca;
  function avviaRicerca() {
    clearTimeout(timerCerca);
    var q = cercaSedute.value.trim();
    if (q === V.cerca) return;
    if (q && q.length < 3) return;
    V.cerca = q;
    scegliBox.setAttribute("data-passo", "sedute");
    caricaSedute(true).catch(function () {});
  }
  cercaSedute.addEventListener("input", function () {
    clearTimeout(timerCerca);
    timerCerca = setTimeout(avviaRicerca, 450);
  });
  document.getElementById("scegli-cerca").addEventListener("submit", function (e) {
    e.preventDefault();
    avviaRicerca();
  });

  /* Su telefono l'elenco è un foglio dal basso; su schermi larghi sta sotto l'Aula */
  function apriScegli() {
    if (sheet()) {
      if (aperto) chiudi();
      scegliBox.hidden = false;
      requestAnimationFrame(function () { scegliBox.setAttribute("data-aperto", ""); });
      btnCambia.setAttribute("aria-expanded", "true");
      setTimeout(function () {
        var b = scegliBox.querySelector(scegliBox.getAttribute("data-passo") === "voti" ? "#lista-voti [tabindex='0']" : "#lista-sedute [tabindex='0']");
        (b || cercaSedute).focus({ preventScroll: true });
      }, ridotto ? 0 : 200);
      return;
    }
    var r = scegliBox.getBoundingClientRect();
    window.scrollBy({ top: r.top - 88, behavior: ridotto ? "auto" : "smooth" });
    var b2 = scegliBox.querySelector(aPassi() && scegliBox.getAttribute("data-passo") === "voti" ? "#lista-voti [tabindex='0']" : "#lista-voti [tabindex='0'], #lista-sedute [tabindex='0']");
    if (b2) b2.focus({ preventScroll: true });
  }
  function chiudiScegli(focus) {
    if (!scegliBox.hasAttribute("data-aperto")) return;
    scegliBox.removeAttribute("data-aperto");
    btnCambia.setAttribute("aria-expanded", "false");
    if (focus !== false) btnCambia.focus({ preventScroll: true });
  }
  btnCambia.addEventListener("click", function () {
    if (scegliBox.hasAttribute("data-aperto")) chiudiScegli();
    else apriScegli();
  });
  document.getElementById("scegli-chiudi").addEventListener("click", function () { chiudiScegli(); });
  scegliBox.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && scegliBox.hasAttribute("data-aperto")) { e.preventDefault(); e.stopPropagation(); chiudiScegli(); }
  });
  window.matchMedia("(max-width: 720px)").addEventListener("change", function (m) {
    if (!m.matches) chiudiScegli(false);
    btnCambia.toggleAttribute("aria-expanded", m.matches);
    if (m.matches) btnCambia.setAttribute("aria-expanded", "false");
  });
  if (sheet()) btnCambia.setAttribute("aria-expanded", "false");

  /* ---------- Cassetto del deputato ---------- */

  var cassetto = document.getElementById("cassetto");
  /* Dove sta la scheda del deputato:
     - telefono: foglio dal basso, figlio di <body>;
     - da 1100px in modalità Partiti: colonna a destra dell'Aula, come l'elenco delle votazioni;
     - altrimenti da 721px: dentro il riquadro dell'Aula, appoggiata in basso. */
  var mqRiquadro = window.matchMedia("(min-width: 721px)");
  var mqColonna = window.matchMedia("(min-width: 1100px)");
  function collocaCassetto() {
    if (!cassetto || !mqRiquadro) return;
    var scena = document.getElementById("scena");
    var dest = !mqRiquadro.matches ? document.body : (mqColonna.matches && modo !== "voto" ? blocco : scena);
    if (cassetto.parentNode !== dest) dest.appendChild(cassetto);
    if (typeof spostaScena === "function" && aperto) spostaScena();
  }
  mqRiquadro.addEventListener("change", collocaCassetto);
  mqColonna.addEventListener("change", collocaCassetto);
  collocaCassetto();
  var corpo = document.getElementById("cassetto-corpo");
  var etSeggio = document.getElementById("dep-seggio");
  var aperto = null;
  var ORGANI_VISIBILI = 6;

  function iniziali(n) {
    var p = n.split(/\s+/);
    return (p[0][0] + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase();
  }
  function riempiCassetto(s) {
    var d = s.det;
    etSeggio.textContent = (s.p ? "Seggio " + s.p : "Seggio") + " · " + AREE[s.k];
    var h = "";
    h += '<div class="dep-chi"><div class="dep-foto" id="dep-foto">' +
      '<img src="https://documenti.camera.it/_dati/leg19/schededeputatinuovosito/fotoDefinitivo/big/d' + esc(s.id) + '.jpg" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">' +
      "</div><div>" +
      '<h2 class="dep-nome" id="dep-nome" tabindex="-1">' + esc(s.n) + "</h2>" +
      '<p class="dep-gruppo"><span class="sigla">' + esc(s.g) + "</span>" + esc(s.g === "Misto" ? "Gruppo Misto" : GRUPPI[s.g] || s.g) + "</p>";
    if (s.g === "Misto") {
      h += '<p class="dep-ruolo">' + (s.c ? "Componente: " + esc(COMPONENTI[s.c] || s.c) : "Nessuna componente del Misto nei dati") + "</p>";
    }
    if (d && d.ri) h += '<p class="dep-ruolo">' + esc(d.ri) + "</p>";
    if (d && d.rg) h += '<p class="dep-ruolo">' + esc(d.rg) + "</p>";
    h += "</div></div>";

    /* Voto nella votazione scelta */
    if (V.id) {
      h += '<div class="dep-blocco"><span class="etichetta">' + esc(etichettaVotoBreve()) + "</span>";
      if (V.det && !V.carica && !V.errore) h += '<p class="dep-voto-cosa">' + esc(accorcia(titoloVoto(V.det).t, 90)) + "</p>";
      if (V.carica) {
        h += '<p class="nota">Carico la votazione…</p>';
      } else if (V.errore || !V.det) {
        h += '<p class="nota">Voto non disponibile.</p>';
      } else if (s.v === "segreto") {
        h += '<p class="dep-voto"><i class="pallino" data-v="segreto"></i>Voto segreto</p><p class="nota dep-voto-nota">Scrutinio segreto: i voti dei singoli non sono pubblici.</p>';
      } else if (s.v) {
        h += '<p class="dep-voto"><i class="pallino" data-v="' + s.v + '"></i>' + VOTO[s.v].parola + "</p>";
        if (s.v === "n.d.") h += '<p class="nota dep-voto-nota">I dati della votazione non collegano questo voto al seggio: per esempio il deputato siede ai banchi del Governo, o è entrato alla Camera dopo questa votazione.</p>';
      } else {
        h += '<p class="nota">Voto non disponibile.</p>';
      }
      if (modo !== "voto") h += '<button class="organi-altri" type="button" id="dep-vai-voti">Mostra la votazione sui seggi</button>';
      h += "</div>";
    }

    if (d) {
      /* Attività in cifre */
      var cifre = [];
      if (d.sp != null) cifre.push([window.numero(d.sp), d.sp === 1 ? "intervento in Aula" : "interventi in Aula"]);
      if (d.ap != null) cifre.push([window.numero(d.ap), "atti da primo firmatario"]);
      if (d.pp != null) cifre.push([decimale(d.pp) + "%", "presenza alle votazioni"]);
      if (cifre.length) {
        h += '<div class="dep-blocco"><span class="etichetta">Nella legislatura, al ' + data(DD.dataAsOf) + '</span><div class="dep-cifre">' +
          cifre.map(function (c) { return '<div class="cifra"><p class="cifra__n">' + c[0] + '</p><p class="cifra__l">' + c[1] + "</p></div>"; }).join("") +
          "</div>" + (d.ac ? '<p class="nota" style="margin-top:var(--s-2)">Ha firmato anche ' + window.numero(d.ac) + " atti come cofirmatario.</p>" : "") + "</div>";
      }
      /* Commissioni e organi */
      if (d.co && d.co.length) {
        var voci = d.co.map(function (o) {
          var n = Array.isArray(o) ? DD.organi[o[0]] : DD.organi[o];
          var r = Array.isArray(o) ? o[1] : null;
          return "<li>" + (r ? '<span class="ruolo">' + esc(r) + "</span>" : "") + "<span>" + esc(n) + "</span></li>";
        });
        h += '<div class="dep-blocco"><span class="etichetta">Commissioni e organi in corso</span><ul class="organi" id="organi">' +
          voci.slice(0, ORGANI_VISIBILI).join("") + "</ul>" +
          (voci.length > ORGANI_VISIBILI ? '<button class="organi-altri" type="button" id="organi-altri">Mostra gli altri ' + (voci.length - ORGANI_VISIBILI) + "</button>" : "") +
          "</div>";
        corpo._voci = voci;
      }
      /* Gruppi nella legislatura */
      if (d.gh && d.gh.length > 1) {
        h += '<div class="dep-blocco"><span class="etichetta">Gruppi nella legislatura</span><ul class="storia">' +
          d.gh.map(function (g) {
            return '<li><span class="sigla">' + esc(g[0]) + "</span><span>" + (g[2] ? "dal " + data(g[1], true) + " al " + data(g[2], true) : "dal " + data(g[1], true)) + "</span></li>";
          }).join("") + "</ul></div>";
      }
    }

    /* Azioni */
    h += '<div class="dep-azioni">' +
      (vista === "aula" && aula3d ? '<button class="btn btn--linea dep-siediti" type="button" id="dep-siediti">Guarda l\'Aula dal suo seggio</button>' : "") +
      '<a class="btn btn--accento" href="../stenografo/index.html?chi=' + encodeURIComponent(s.n) + '">Chiedi a Stenografo cosa ha detto ' + window.ICONE.freccia + "</a>" +
      '<a class="btn btn--linea" href="http://dati.camera.it/ocd/persona.rdf/p' + esc(s.id) + '" rel="noopener">Scheda open data ' + window.ICONE.esterno + "</a>" +
      "</div>" +
      '<p class="nota dep-fonte">Seggi da camera.it, voto da dati.camera.it' + (d ? ", commissioni e cifre dal grafo ParliamentRAG" : "") + ". " +
      '<a class="collegamento" href="https://www.camera.it/deputati/elenco/19-' + esc(s.id) + '" rel="noopener">Scheda su camera.it</a></p>';

    corpo.innerHTML = h;
    corpo.scrollTop = 0;
    var img = corpo.querySelector("#dep-foto img");
    img.addEventListener("error", function () {
      img.parentNode.innerHTML = '<span class="iniziali" aria-hidden="true">' + esc(iniziali(s.n)) + "</span>";
    });
    var siediti = corpo.querySelector("#dep-siediti");
    if (siediti) siediti.addEventListener("click", function () {
      aula3d.siediti(s.i);
      scriviDove("Dal seggio di " + s.n);
      if (!largo()) chiudi();
    });
    var vaiVoti = corpo.querySelector("#dep-vai-voti");
    if (vaiVoti) vaiVoti.addEventListener("click", function () { impostaModo("voto"); });
    var altri = corpo.querySelector("#organi-altri");
    if (altri) altri.addEventListener("click", function () {
      corpo.querySelector("#organi").innerHTML = corpo._voci.join("");
      altri.remove();
    });
  }

  /* La scheda del deputato è sempre una barra in basso: nessuno spostamento laterale */
  function largo() { return false; }
  function spostaScena() {
    /* Su schermi larghi l'Aula si sposta a sinistra quanto basta per non finire sotto il cassetto */
    if (vista === "aula") {
      blocco.style.transform = "";
      if (!aula3d) return;
      if (!aperto) { aula3d.sposta(0); return; }
      /* Scheda nella colonna a destra: non copre l'Aula */
      if (cassetto.parentNode === blocco) { aula3d.sposta(0); return; }
      if (!largo()) {
        /* Il foglio copre il fondo: il centro della vista sale nella parte libera */
        var rr = host3d.getBoundingClientRect();
        /* Scheda dentro il riquadro: copre la sua altezza; foglio su telefono: copre il fondo dello schermo */
        var sotto = cassetto.parentNode !== document.body
          ? cassetto.offsetHeight + 12
          : Math.max(0, rr.bottom - (window.innerHeight - cassetto.offsetHeight));
        aula3d.sposta(0, Math.min(sotto, rr.height * 0.6) / 2);
        return;
      }
      var r3 = host3d.getBoundingClientRect();
      var copre = Math.max(0, r3.right - (window.innerWidth - cassetto.offsetWidth));
      aula3d.sposta(Math.min(copre, r3.width * 0.4) / 2);
      return;
    }
    if (!aperto || !largo()) { blocco.style.transform = ""; return; }
    blocco.style.transform = "";
    var r = blocco.getBoundingClientRect();
    var spazio = window.innerWidth - cassetto.offsetWidth - 24;
    var d = Math.max(0, r.right - spazio);
    d = Math.min(d, Math.max(0, r.left - 16));
    blocco.style.transform = d ? "translateX(" + -Math.round(d) + "px)" : "";
  }

  function apri(s, opz) {
    opz = opz || {};
    chiudiScegli(false);
    if (aperto && aperto !== s) aperto.el.removeAttribute("data-sel");
    aperto = s;
    s.el.setAttribute("data-sel", "");
    s.el.setAttribute("aria-expanded", "true");
    rendiCorrente(s, false);
    anello.style.display = "";
    anello.setAttribute("cx", s.x);
    anello.setAttribute("cy", s.y);
    anello.removeAttribute("data-pulsa");
    if (!ridotto) requestAnimationFrame(function () { anello.setAttribute("data-pulsa", ""); });
    riempiCassetto(s);
    cassetto.hidden = false;
    requestAnimationFrame(function () {
      cassetto.setAttribute("data-aperto", "");
      spostaScena();
      if (!largo() && vista === "pianta") {
        /* Il foglio copre la parte bassa: porto il seggio nella parte alta dello schermo */
        var q = aSchermo(s.x, s.y);
        var alto = window.innerHeight - cassetto.offsetHeight;
        if (q.y > alto - 24 || q.y < 80) window.scrollBy({ top: q.y - Math.max(90, alto * 0.5), behavior: ridotto ? "auto" : "smooth" });
      }
      if (opz.focus) document.getElementById("dep-nome").focus({ preventScroll: true });
    });
    if (vista === "pianta" && !inVista(s)) centraSu(s, scala());
    if (aula3d) aula3d.seleziona(s.i);
    nascondiFumetto();
  }
  function chiudi() {
    if (!aperto) return;
    cassetto.removeAttribute("data-esteso");
    btnDettagli.setAttribute("aria-expanded", "false");
    btnDettagli.textContent = "Dettagli";
    var s = aperto;
    s.el.removeAttribute("data-sel");
    s.el.removeAttribute("aria-expanded");
    aperto = null;
    anello.style.display = "none";
    cassetto.removeAttribute("data-aperto");
    blocco.style.transform = "";
    setTimeout(function () { if (!aperto) cassetto.hidden = true; }, ridotto ? 0 : 480);
    if (aula3d) { aula3d.seleziona(null); aula3d.sposta(0); }
    if (vista === "aula") host3d.focus({ preventScroll: true });
    else rendiCorrente(s, true);
  }
  document.getElementById("cassetto-chiudi").addEventListener("click", chiudi);
  /* Nel riquadro dell'Aula la scheda è compatta: «Dettagli» apre numeri e commissioni */
  var btnDettagli = document.getElementById("cassetto-dettagli");
  btnDettagli.addEventListener("click", function () {
    var esteso = !cassetto.hasAttribute("data-esteso");
    cassetto.toggleAttribute("data-esteso", esteso);
    btnDettagli.setAttribute("aria-expanded", esteso ? "true" : "false");
    btnDettagli.textContent = esteso ? "Meno dettagli" : "Dettagli";
    spostaScena();
  });
  window.addEventListener("resize", function () { spostaScena(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && aperto && !(document.activeElement === input && !lista.hidden)) {
      e.preventDefault();
      chiudi();
    }
    /* «/» porta alla ricerca */
    if (e.key === "/" && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) {
      e.preventDefault();
      input.focus();
    }
  });

  /* ---------- Ricerca ---------- */

  var input = document.getElementById("cerca");
  var lista = document.getElementById("proposte");
  var risultati = [], attivo = -1;
  var indice = occupati.map(function (s) {
    return { s: s, t: piega(s.n), parole: piega(s.n).split(/[\s'-]+/) };
  });

  function evidenzia(nome, q) {
    if (!q) return esc(nome);
    var f = piega(nome), i = f.indexOf(q);
    if (i < 0) return esc(nome);
    return esc(nome.slice(0, i)) + "<mark>" + esc(nome.slice(i, i + q.length)) + "</mark>" + esc(nome.slice(i + q.length));
  }
  function cerca() {
    var q = piega(input.value.trim()).replace(/\s+/g, " ");
    if (!q) { chiudiLista(); return; }
    var pezzi = q.split(" ");
    risultati = indice.map(function (x) {
      var punti = 0;
      var ok = pezzi.every(function (p) {
        if (x.parole.indexOf(p) >= 0) { punti += 4; return true; }
        if (x.parole.some(function (w) { return w.indexOf(p) === 0; })) { punti += 2; return true; }
        if (x.t.indexOf(p) >= 0) { punti += 1; return true; }
        return false;
      });
      if (!ok) return null;
      if (x.t.indexOf(q) === 0) punti += 1;
      if (x.parole[x.parole.length - 1].indexOf(pezzi[pezzi.length - 1]) === 0) punti += 1;
      return { s: x.s, punti: punti };
    }).filter(Boolean).sort(function (a, b) { return b.punti - a.punti || a.s.n.localeCompare(b.s.n, "it"); }).slice(0, 8).map(function (x) { return x.s; });
    attivo = risultati.length ? 0 : -1;
    disegnaLista(q);
  }
  function disegnaLista(q) {
    if (!risultati.length) {
      lista.innerHTML = '<li class="vuoto" role="presentation">Nessun deputato con questo nome nell\'Aula di oggi.</li>';
    } else {
      lista.innerHTML = risultati.map(function (s, i) {
        return '<li role="option" id="proposta-' + i + '" aria-selected="' + (i === attivo) + '" data-i="' + i + '">' +
          "<span>" + evidenzia(s.n, q) + '</span><span class="chi-g">' + esc(s.g === "Misto" && s.c ? s.c : s.g) + (s.p ? " · " + s.p : "") + "</span></li>";
      }).join("");
    }
    lista.hidden = false;
    input.setAttribute("aria-expanded", "true");
    if (attivo >= 0) input.setAttribute("aria-activedescendant", "proposta-" + attivo);
    else input.removeAttribute("aria-activedescendant");
  }
  function muovi(d) {
    if (!risultati.length) return;
    attivo = (attivo + d + risultati.length) % risultati.length;
    lista.querySelectorAll("[role=option]").forEach(function (li, i) { li.setAttribute("aria-selected", i === attivo ? "true" : "false"); });
    input.setAttribute("aria-activedescendant", "proposta-" + attivo);
    var li = lista.querySelector("#proposta-" + attivo);
    if (li) {
      if (li.offsetTop < lista.scrollTop) lista.scrollTop = li.offsetTop - 4;
      else if (li.offsetTop + li.offsetHeight > lista.scrollTop + lista.clientHeight) lista.scrollTop = li.offsetTop + li.offsetHeight - lista.clientHeight + 4;
    }
  }
  function chiudiLista() {
    lista.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }
  function scegli(s) {
    chiudiLista();
    input.value = s.n;
    if (vista === "aula" && aula3d) {
      aula3d.vaiA(s.i);
      scriviDove("Davanti al seggio di " + s.n);
      /* Su telefono la scheda sale dal basso: l'Aula va in cima allo schermo */
      setTimeout(function () {
        var rb = (largo() ? blocco : host3d).getBoundingClientRect();
        var cima = largo() ? 72 : 60;
        if (!largo() || rb.top < 0 || rb.top > window.innerHeight * 0.35) window.scrollBy({ top: rb.top - cima, behavior: ridotto || !largo() ? "auto" : "smooth" });
        setTimeout(spostaScena, 520);
      }, 60);
      mostraRiadatta(true);
    } else centraSu(s, 2.6);
    apri(s, { focus: true });
  }
  input.addEventListener("input", cerca);
  input.addEventListener("focus", function () { if (input.value.trim()) cerca(); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); if (lista.hidden) cerca(); else muovi(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); muovi(-1); }
    else if (e.key === "Enter") {
      if (!lista.hidden && risultati[attivo]) { e.preventDefault(); scegli(risultati[attivo]); }
    } else if (e.key === "Escape") {
      if (!lista.hidden) { e.preventDefault(); e.stopPropagation(); chiudiLista(); }
      else if (input.value) { e.preventDefault(); input.value = ""; }
    }
  });
  lista.addEventListener("pointerdown", function (e) { e.preventDefault(); });
  lista.addEventListener("click", function (e) {
    var li = e.target.closest("[role=option]");
    if (li) scegli(risultati[+li.dataset.i]);
  });
  input.addEventListener("blur", function () { setTimeout(chiudiLista, 120); });

  /* ---------- Sezione sotto: numeri e marchi ---------- */

  document.getElementById("n-posti").textContent = window.numero(dep.length);
  document.getElementById("dati-seggi").textContent = occupati.length + " deputati nei loro posti, dati al " + data(A.dataAsOf);
  document.getElementById("dati-dep").textContent = data(DD.dataAsOf || A.dataAsOf);
  document.querySelectorAll("[data-marchio]").forEach(function (e) { e.innerHTML = window.MARCHI[e.dataset.marchio](false); });

  /* ---------- In Aula: la vista 3D ---------- */

  var vista = "aula";
  document.body.setAttribute("data-vista", vista);
  var aula3d = null;
  var host3d = document.getElementById("aula3d");
  var attesa = document.getElementById("aula3d-attesa");
  var guida = document.getElementById("aula3d-guida");
  var dove = document.getElementById("vista-dove");
  var btnRiadatta3d = document.getElementById("aula3d-riadatta");
  var schedeVista = document.querySelectorAll(".vista-barra [role=tab]");
  var DOVE_INIZIO = "Dal banco della Presidenza";
  var raf3d = 0;

  function scriviDove(t) { dove.textContent = t; }
  function mostraRiadatta(on) { btnRiadatta3d.hidden = !on; }

  /* Stato di ogni seggio, letto dagli stessi attributi della pianta */
  function stati3d() {
    var luceOn = svg.hasAttribute("data-luce");
    var filtro = svg.hasAttribute("data-filtro");
    return seggi.map(function (s) {
      if (!s.id) return modo === "voto" ? "vuotoVoto" : "vuoto";
      var on = s.el.hasAttribute("data-on");
      if (modo === "voto") {
        if (filtro && !on) return "spento";
        return s.v ? (s.v === "n.d." ? "nd" : s.v === "segreto" ? "neutro" : s.v) : "neutro";
      }
      if (luceOn) return on ? "acceso" : "spento";
      return "neutro";
    });
  }
  function pianifica3d() {
    if (!aula3d || raf3d) return;
    raf3d = requestAnimationFrame(function () {
      raf3d = 0;
      aula3d.colora(stati3d());
    });
  }

  function impostaVista(v, focus) {
    if (v === "aula" && !aula3d && !attesa) return;
    vista = v;
    blocco.setAttribute("data-vista", v);
    document.body.setAttribute("data-vista", v);
    schedeVista.forEach(function (b) {
      var on = b.dataset.vista === v;
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    });
    nascondiFumetto();
    if (aula3d) aula3d.attiva(v === "aula");
    blocco.style.transform = "";
    if (aperto) { riempiCassetto(aperto); spostaScena(); }
    if (focus) document.getElementById(v === "aula" ? "vista-aula" : "vista-pianta").focus();
  }
  schedeVista.forEach(function (b) {
    b.addEventListener("click", function () { impostaVista(b.dataset.vista); });
    b.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      if (b.disabled) return;
      var altro = b.dataset.vista === "aula" ? "pianta" : "aula";
      if (altro === "aula" && document.getElementById("vista-aula").disabled) return;
      impostaVista(altro, true);
    });
  });

  function senza3d(motivo) {
    if (motivo) console.warn("Scranno 3D:", motivo);
    aula3d = null;
    attesa = null;
    var b = document.getElementById("vista-aula");
    b.disabled = true;
    b.setAttribute("aria-disabled", "true");
    document.getElementById("aula3d-fallback").hidden = false;
    impostaVista("pianta");
  }

  guida.querySelector("#aula3d-guida-chiudi").addEventListener("click", function () {
    guida.hidden = true;
    try { localStorage.setItem("scranno-guida-3d", "vista"); } catch (err) {}
    host3d.focus({ preventScroll: true });
  });
  btnRiadatta3d.addEventListener("click", function () {
    if (!aula3d) return;
    aula3d.riadatta();
    scriviDove(DOVE_INIZIO);
    mostraRiadatta(false);
  });
  document.getElementById("aula3d-piu").addEventListener("click", function () { if (aula3d) aula3d.zoom(0.84); });
  document.getElementById("aula3d-meno").addEventListener("click", function () { if (aula3d) aula3d.zoom(1 / 0.84); });

  function avvia3d() {
    if (!window.Aula3D || !window.SEGGI3D || !window.Aula3D.supported()) {
      senza3d();
      return;
    }
    var timerTocco;
    window.Aula3D.mount(host3d, {
      seggi: A.seats,
      piano: window.SEGGI3D,
      ridotto: ridotto,
      onHover: function (i, x, y) {
        if (i === null) { if (!(fumettoSu && fumettoSu.daTastiera)) nascondiFumetto(); return; }
        mostraFumetto(seggi[i], x, y);
        if (senzaHover.matches) {
          clearTimeout(timerTocco);
          timerTocco = setTimeout(nascondiFumetto, 1600);
        }
      },
      onPick: function (i) { apri(seggi[i], { focus: false }); },
      onAvviso: mostraAvviso,
      onVista: function (cambiata) {
        if (!cambiata) return;
        mostraRiadatta(true);
        if (dove.textContent === DOVE_INIZIO) scriviDove("In giro per l'Aula");
      },
    }).then(function (c) {
      aula3d = c;
      aula3d.colora(stati3d());
      aula3d.attiva(vista === "aula");
      if (aperto) { aula3d.seleziona(aperto.i); spostaScena(); }
      attesa.setAttribute("data-fatto", "");
      var vista1 = null;
      try { vista1 = localStorage.getItem("scranno-guida-3d"); } catch (err) {}
      if (!vista1) guida.hidden = false;
      document.addEventListener("tema", function () { aula3d.tema(); });
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { aula3d.tema(); });
    }).catch(function (err) {
      senza3d(err && err.message);
    });
  }

  /* ---------- Avvio ---------- */

  /* #voto apre la modalità Voti sulla votazione più recente, #voto=<id> su quella votazione */
  function votoDaHash() {
    var m = /^#voto(?:=([\w.-]+))?$/.exec(location.hash);
    if (!m) return null;
    return m[1] ? decodeURIComponent(m[1]) : true;
  }
  etichetteSeggi();
  var daHash = votoDaHash();
  if (daHash) impostaModo("voto", daHash);
  avvia3d();
  window.addEventListener("hashchange", function () {
    var h = votoDaHash();
    if (!h) return;
    if (modo !== "voto") impostaModo("voto", h);
    else if (typeof h === "string") avviaVoti(h);
  });
})();
