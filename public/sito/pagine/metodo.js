(function () {
  "use strict";
  var D = window.DATI;
  var SPUNTA = window.ICONE.spunta;
  var ridotto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var EN = window.LINGUA === "en";
  var esc = window.esc;
  /* Decimali con la virgola in italiano, con il punto in inglese */
  var virgola = function (n, d) { return EN ? n.toFixed(d) : n.toFixed(d).replace(".", ","); };
  var dataIt = window.dataLunga;
  var sigla = function (g) { return EN && g === "Governo" ? "Government" : g; };

  /* ---------- Indice: segna la sezione che stai leggendo ---------- */
  var voci = document.querySelectorAll("#indice a");
  var capitoli = Array.prototype.map.call(voci, function (a) { return document.querySelector(a.getAttribute("href")); });
  function segna() {
    var soglia = window.innerHeight * 0.3, attivo = 0;
    capitoli.forEach(function (c, i) { if (c.getBoundingClientRect().top <= soglia) attivo = i; });
    voci.forEach(function (a, i) { if (i === attivo) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
  }

  /* ---------- § 1 Condotto: i passaggi si accendono scorrendo ---------- */
  var ordine = ["FdI", "PD", "Lega", "M5S", "FI", "AVS", "Azione", "IV", "NM", "+Europa", "Governo"];
  document.getElementById("ventaglio").innerHTML = ordine.map(function (g, i) {
    return '<span class="sigla" style="--i:' + i + '">' + esc(sigla(g)) + "</span>";
  }).join("");

  var condotto = document.getElementById("condotto");
  var passi = condotto.querySelectorAll(".passo");
  var stretto = window.matchMedia("(max-width: 960px)");
  function accendiPassi() {
    var vh = window.innerHeight, n = 0;
    if (stretto.matches) {
      /* Verticale: acceso ogni passo che ha superato i due terzi dello schermo */
      passi.forEach(function (p, i) { if (p.getBoundingClientRect().top < vh * 0.68) n = i + 1; });
    } else {
      /* Orizzontale: la figura sale da fondo schermo a metà, i passi seguono */
      var r = condotto.getBoundingClientRect();
      var t = (vh * 0.92 - r.top) / (vh * 0.5);
      n = Math.max(0, Math.min(6, Math.floor(t * 6 + 0.4)));
    }
    if (ridotto) n = 6;
    passi.forEach(function (p, i) { if (i < n) p.setAttribute("data-acceso", ""); else p.removeAttribute("data-acceso"); });
    condotto.style.setProperty("--p", n <= 1 ? 0 : (n - 1) / 5);
  }

  var inCoda = false;
  function alloScorrere() {
    if (inCoda) return;
    inCoda = true;
    requestAnimationFrame(function () { inCoda = false; segna(); accendiPassi(); });
  }
  window.addEventListener("scroll", alloScorrere, { passive: true });
  window.addEventListener("resize", alloScorrere);
  alloScorrere();

  /* ---------- § 2 Le voci del tema d'esempio ---------- */
  document.getElementById("fila-voci").innerHTML = D.tema.citazioni.map(function (q) {
    return '<span class="sigla" title="' + esc(sigla(q.groupName)) + '">' + SPUNTA + esc(sigla(q.group)) + "</span>";
  }).join("");

  /* ---------- § 3 Tabella dei pesi ---------- */
  var CRITERI = EN ? [
    { k: "interventi", t: "Floor speeches", p: 0.25, d: "How much, and how recently, they have spoken about the topic on the floor." },
    { k: "commissione", t: "Committee", p: 0.25, d: "How close their committee is to the topic." },
    { k: "atti", t: "Signed acts", p: 0.20, d: "Bills and other acts on the topic that they signed, weighted by recency." },
    { k: "professione", t: "Profession", p: 0.15, d: "Affinity between their work outside Parliament and the topic." },
    { k: "formazione", t: "Education", p: 0.10, d: "Affinity between their degrees and the topic." },
    { k: "ruolo", t: "Institutional role", p: 0.05, d: "Current offices, for example in the Government or in a committee." }
  ] : [
    { k: "interventi", t: "Interventi in Aula", p: 0.25, d: "Quanto, e quanto di recente, ha parlato del tema in Aula." },
    { k: "commissione", t: "Commissione", p: 0.25, d: "Quanto la sua commissione è vicina al tema." },
    { k: "atti", t: "Atti firmati", p: 0.20, d: "Proposte e altri atti sul tema che ha firmato, pesati per recenza." },
    { k: "professione", t: "Professione", p: 0.15, d: "Affinità tra il suo lavoro fuori dall'Aula e il tema." },
    { k: "formazione", t: "Formazione", p: 0.10, d: "Affinità tra i suoi titoli di studio e il tema." },
    { k: "ruolo", t: "Ruolo istituzionale", p: 0.05, d: "Incarichi in corso, per esempio in Governo o in commissione." }
  ];
  /* Sei toni dello stesso accento: i criteri si distinguono, i gruppi no */
  var TONI = [100, 82, 64, 48, 34, 22];
  CRITERI.forEach(function (c, i) {
    c.c = "color-mix(in oklab, var(--accento) " + TONI[i] + "%, var(--carta-2))";
    c.testo = TONI[i] >= 48 ? "var(--su-accento)" : "var(--inchiostro)";
  });
  document.getElementById("tabella-pesi").innerHTML = CRITERI.map(function (c) {
    return "<tr><td>" + esc(c.t) + '</td><td class="num">' + virgola(c.p, 2) + '<span class="barretta" style="--w:' + c.p * 100 + 'px" aria-hidden="true"></span></td><td>' + esc(c.d) + "</td></tr>";
  }).join("");

  /* ---------- § 3 Curva di decadimento, 18 mesi di dimezzamento ---------- */
  (function () {
    var svg = document.getElementById("decadimento");
    var x0 = 40, x1 = 500, y0 = 170, y1 = 20, mesi = 48;
    var X = function (m) { return x0 + (m / mesi) * (x1 - x0); };
    var Y = function (v) { return y0 - v * (y0 - y1); };
    var punti = [];
    for (var m = 0; m <= mesi; m += 1) punti.push(X(m).toFixed(1) + "," + Y(Math.pow(0.5, m / 18)).toFixed(1));
    var h = "";
    h += '<path class="area" d="M' + X(0) + "," + y0 + " L" + punti.join(" L") + " L" + X(mesi) + "," + y0 + ' Z" opacity=".55"/>';
    h += '<line class="assi" x1="' + x0 + '" y1="' + y0 + '" x2="' + x1 + '" y2="' + y0 + '"/>';
    h += '<line class="assi" x1="' + x0 + '" y1="' + y0 + '" x2="' + x0 + '" y2="' + y1 + '"/>';
    [[18, 0.5], [36, 0.25]].forEach(function (g) {
      h += '<line class="guida" x1="' + X(g[0]) + '" y1="' + y0 + '" x2="' + X(g[0]) + '" y2="' + Y(g[1]) + '"/>';
      h += '<line class="guida" x1="' + x0 + '" y1="' + Y(g[1]) + '" x2="' + X(g[0]) + '" y2="' + Y(g[1]) + '"/>';
    });
    h += '<polyline class="curva" id="curva" points="' + punti.join(" ") + '"/>';
    [[0, 1], [18, 0.5], [36, 0.25]].forEach(function (g) {
      h += '<circle class="punto-c" cx="' + X(g[0]) + '" cy="' + Y(g[1]) + '" r="4.5"/>';
    });
    h += '<text x="' + (x0 - 8) + '" y="' + (Y(1) + 4) + '" text-anchor="end">1</text>';
    h += '<text x="' + (x0 - 8) + '" y="' + (Y(0.5) + 4) + '" text-anchor="end">' + virgola(0.5, 1) + '</text>';
    h += '<text x="' + (x0 - 8) + '" y="' + (Y(0.25) + 4) + '" text-anchor="end">' + virgola(0.25, 2) + '</text>';
    [0, 12, 18, 24, 36, 48].forEach(function (m) {
      h += '<text x="' + X(m) + '" y="' + (y0 + 18) + '" text-anchor="middle"' + (m === 18 ? ' class="forte"' : "") + ">" + m + "</text>";
    });
    h += '<text x="' + x1 + '" y="' + (y0 + 36) + '" text-anchor="end">' + (EN ? "months since the speech" : "mesi dall\'intervento") + '</text>';
    h += '<text x="' + (X(18) + 8) + '" y="' + (Y(0.5) - 10) + '" class="forte">' + (EN ? "half the weight at 18 months" : "metà del peso a 18 mesi") + '</text>';
    svg.innerHTML = h;

    /* La curva si disegna quando entra nello schermo */
    var curva = document.getElementById("curva");
    if (!ridotto && "IntersectionObserver" in window) {
      var L = curva.getTotalLength();
      curva.style.strokeDasharray = L;
      curva.style.strokeDashoffset = L;
      new IntersectionObserver(function (v, io) {
        if (v[0].isIntersecting) {
          curva.style.transition = "stroke-dashoffset 1.4s var(--e-std)";
          curva.style.strokeDashoffset = 0;
          io.disconnect();
        }
      }, { threshold: 0.5 }).observe(svg);
    }
  })();

  /* ---------- § 3 Sposta i pesi ---------- */
  var cursori = document.getElementById("cursori");
  cursori.innerHTML = CRITERI.map(function (c) {
    var v = Math.round(c.p * 100);
    return '<div class="cursore"><label for="c-' + c.k + '">' + esc(c.t) + '</label>' +
      '<output for="c-' + c.k + '" id="o-' + c.k + '">' + v + "</output>" +
      '<span class="norm" id="n-' + c.k + '"></span>' +
      '<input type="range" id="c-' + c.k + '" min="0" max="100" step="1" value="' + v + '" aria-describedby="somma"></div>';
  }).join("");

  function pila(el, valori) {
    el.innerHTML = CRITERI.map(function (c, i) {
      var q = valori[i];
      return '<span style="flex:0 0 ' + (q * 100).toFixed(2) + "%;--c:" + c.c + ";--c-testo:" + c.testo + '">' + (q >= 0.07 ? Math.round(q * 100) + "%" : "") + "</span>";
    }).join("");
  }
  pila(document.getElementById("barra-pubblicati"), CRITERI.map(function (c) { return c.p; }));
  var barraTuoi = document.getElementById("barra-tuoi");
  var chiave = document.getElementById("chiave");
  var somma = document.getElementById("somma");
  var scarti = document.getElementById("scarti");

  function ricalcola() {
    var grezzi = CRITERI.map(function (c) { return +document.getElementById("c-" + c.k).value; });
    var tot = grezzi.reduce(function (a, b) { return a + b; }, 0);
    var norm = grezzi.map(function (v) { return tot ? v / tot : 0; });
    CRITERI.forEach(function (c, i) {
      document.getElementById("o-" + c.k).textContent = grezzi[i];
      document.getElementById("n-" + c.k).textContent = tot ? virgola(norm[i], 2) : "–";
    });
    if (!tot) {
      somma.setAttribute("data-zero", "");
      somma.innerHTML = EN ? "<span>Sum of the sliders</span><strong>0</strong><span>At least one criterion must weigh more than zero.</span>" : "<span>Somma dei cursori</span><strong>0</strong><span>Almeno un criterio deve pesare più di zero.</span>";
      barraTuoi.innerHTML = "";
      chiave.innerHTML = "";
      scarti.textContent = "";
      return;
    }
    somma.removeAttribute("data-zero");
    somma.innerHTML = EN
      ? "<span>Sum of the sliders <strong>" + tot + "</strong></span><span>Each weight divided by " + tot + ": the sum is back to <strong>1.00</strong></span>"
      : "<span>Somma dei cursori <strong>" + tot + "</strong></span><span>Ogni peso diviso per " + tot + ": la somma torna <strong>1,00</strong></span>";
    pila(barraTuoi, norm);
    chiave.innerHTML = CRITERI.map(function (c, i) {
      return '<span><i style="--c:' + c.c + '"></i>' + esc(c.t) + "<b>" + virgola(norm[i], 2) + "</b></span>";
    }).join("");

    /* Le due differenze più grandi rispetto ai pesi pubblicati */
    var diff = CRITERI.map(function (c, i) { return { t: c.t, d: norm[i] - c.p }; })
      .filter(function (x) { return Math.abs(x.d) >= 0.005; })
      .sort(function (a, b) { return Math.abs(b.d) - Math.abs(a.d); });
    if (!diff.length) {
      scarti.textContent = EN ? "These are the published weights." : "Sono i pesi pubblicati.";
    } else {
      scarti.innerHTML = (EN ? "Compared with the published weights: " : "Rispetto ai pesi pubblicati: ") + diff.slice(0, 2).map(function (x) {
        return "<strong>" + esc(x.t) + "</strong> " + (x.d > 0 ? "+" : "−") + virgola(Math.abs(x.d), 2);
      }).join(", ") + (diff.length > 2 ? (EN ? ", and " + (diff.length - 2) + " more." : ", e altri " + (diff.length - 2) + ".") : ".");
    }
  }
  cursori.addEventListener("input", ricalcola);
  document.getElementById("pesi-ripristina").addEventListener("click", function () {
    CRITERI.forEach(function (c) { document.getElementById("c-" + c.k).value = Math.round(c.p * 100); });
    ricalcola();
  });
  ricalcola();

  /* ---------- § 4 Una citazione e la sua provenienza ---------- */
  var q = D.tema.citazioni.filter(function (x) { return x.group === "NM"; })[0];
  var parole = q.quote.trim().split(/\s+/).length;
  document.getElementById("cit-esempio").innerHTML =
    '<p class="cit__testo" lang="it">' + esc(q.quote) + "</p>" +
    '<footer class="cit__fonte"><span class="cit__chi">' + esc(q.name) + "</span><span>" + esc(q.groupName) + "</span><span>" + dataIt(q.date) + "</span>" +
    '<a class="bollino" href="' + esc(q.url) + '" rel="noopener">' + SPUNTA + (EN ? "Record" : "Resoconto") + "</a></footer>";
  var riga = function (t, v) { return "<div><dt>" + t + "</dt><dd>" + v + "</dd></div>"; };
  document.getElementById("cit-scheda").innerHTML =
    riga(EN ? "Sitting" : "Seduta", (EN ? "No. " : "n. ") + q.session + ", " + dataIt(q.date)) +
    riga(EN ? "Debate" : "Dibattito", '<span lang="it">' + esc(q.debate) + "</span>") +
    riga(EN ? "Speech" : "Intervento", '<span class="mono">' + esc(q.id) + "</span>") +
    riga(EN ? "Comparison" : "Confronto", EN ? parole + " words out of " + parole + " match" : parole + " parole su " + parole + " coincidono") +
    riga(EN ? "Source" : "Fonte", '<a class="collegamento" href="' + esc(q.url) + '" rel="noopener">' + (EN ? "camera.it, verbatim record" : "camera.it, resoconto stenografico") + "</a>");

  /* ---------- § 5 Piano della bussola (schema) ---------- */
  (function () {
    var g = document.getElementById("piano");
    var c = 150, x0 = 30, r = 120;
    var X = function (v) { return c + x0 + v * r; };
    var Y = function (v) { return c - v * r; };
    var h = "";
    [-0.5, 0.5].forEach(function (v) {
      h += '<line class="griglia-p" x1="' + X(v) + '" y1="' + Y(1) + '" x2="' + X(v) + '" y2="' + Y(-1) + '"/>';
      h += '<line class="griglia-p" x1="' + X(-1) + '" y1="' + Y(v) + '" x2="' + X(1) + '" y2="' + Y(v) + '"/>';
    });
    h += '<rect x="' + X(-1) + '" y="' + Y(1) + '" width="' + 2 * r + '" height="' + 2 * r + '" fill="none" class="griglia-p"/>';
    h += '<line class="asse" x1="' + X(-1) + '" y1="' + Y(0) + '" x2="' + X(1) + '" y2="' + Y(0) + '"/>';
    h += '<line class="asse" x1="' + X(0) + '" y1="' + Y(1) + '" x2="' + X(0) + '" y2="' + Y(-1) + '"/>';
    h += '<text x="' + X(-1) + '" y="' + (Y(0) - 6) + '">−1</text>';
    h += '<text x="' + X(1) + '" y="' + (Y(0) - 6) + '" text-anchor="end">+1</text>';
    h += '<text x="' + (X(0) + 6) + '" y="' + (Y(1) + 12) + '">+1</text>';
    h += '<text x="' + (X(0) + 6) + '" y="' + (Y(-1) - 4) + '">−1</text>';
    h += '<text x="' + X(1) + '" y="' + (Y(-1) + 22) + '" text-anchor="end">' + (EN ? "axis A" : "asse A") + '</text>';
    h += '<text x="' + (X(-1) - 8) + '" y="' + Y(1) + '" text-anchor="end" transform="rotate(-90 ' + (X(-1) - 8) + " " + Y(1) + ')">' + (EN ? "axis B" : "asse B") + '</text>';
    /* Tre interventi di forma: la media cade in alto a destra */
    var pts = [[0.82, 0.58], [0.56, 0.84], [0.72, 0.4]];
    pts.forEach(function (p) { h += '<circle class="intervento" cx="' + X(p[0]) + '" cy="' + Y(p[1]) + '" r="6"/>'; });
    var mx = 0.7, my = 0.6, k = 0.55;
    h += '<circle class="media" cx="' + X(mx) + '" cy="' + Y(my) + '" r="9"/>';
    h += '<line class="freccia-p" x1="' + X(mx * 0.93) + '" y1="' + Y(my * 0.93) + '" x2="' + X(mx * k * 1.12) + '" y2="' + Y(my * k * 1.12) + '" marker-end="url(#punta)"/>';
    h += '<circle class="ristretta" cx="' + X(mx * k) + '" cy="' + Y(my * k) + '" r="7"/>';
    h = '<defs><marker id="punta" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1l5 3-5 3" fill="none" stroke="var(--accento)" stroke-width="1.4"/></marker></defs>' + h;
    g.innerHTML = h;
  })();

  window.osservaComparse();
})();
