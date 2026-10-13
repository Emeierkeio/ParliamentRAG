/*
 * Guscio comune della famiglia: barra di famiglia, testata del sito, piede,
 * tema, comparse allo scorrimento e pulsanti «copia».
 *
 * Ogni pagina dichiara su <html>:
 *   data-sito="parliamentrag|stenografo|fascicoli|scranno"
 *   data-pagina="<chiave della voce di menu>"
 * e mette tre segnaposto: [data-famiglia], [data-testata], [data-piede].
 * Tutte le pagine stanno a un livello di profondità, quindi «../» porta alla radice.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  root.classList.remove("no-js");
  var SITO = root.dataset.sito || "parliamentrag";
  var PAGINA = root.dataset.pagina || "";

  /* ---------- Marchi (stessi tracciati dei siti in produzione) ---------- */

  var MARCHI = {
    parliamentrag: function (anima) {
      return (
        '<svg viewBox="15 15 194 153" aria-hidden="true" focusable="false">' +
        '<path ' + (anima ? 'class="penna" pathLength="1" ' : "") + 'd="M 35.91 139.73 A 81 81 0 1 1 188.09 139.73" fill="none" stroke="currentColor" stroke-width="32" stroke-linecap="round"/>' +
        '<circle ' + (anima ? 'class="penna-punto" ' : "") + 'cx="112" cy="146" r="22" fill="#2D5F8F"/></svg>'
      );
    },
    stenografo: function (anima) {
      return (
        '<svg viewBox="6 8.5 50.5 48" aria-hidden="true" focusable="false">' +
        '<path ' + (anima ? 'class="penna" pathLength="1" ' : "") + 'd="M10 42C12 23 29 16 33.5 27C37 36 24 42 27.5 49.5C31 56.5 46 52 48.5 28" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>' +
        '<circle ' + (anima ? 'class="penna-punto" ' : "") + 'cx="50" cy="15" r="6.6" fill="#167A68"/></svg>'
      );
    },
    fascicoli: function (anima) {
      return (
        '<svg viewBox="-5.8 5.5 57.8 55" aria-hidden="true" focusable="false"><g transform="rotate(-30 28 32)">' +
        '<path ' + (anima ? 'class="penna" pathLength="1" ' : "") + 'd="M14 14V44a14 14 0 0 0 28 0V18a7 7 0 0 0-14 0V40" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>' +
        '<circle ' + (anima ? 'class="penna-punto" ' : "") + 'cx="14" cy="2" r="6.6" fill="#167A68"/></g></svg>'
      );
    },
    scranno: function (anima) {
      return (
        '<svg viewBox="14.3 8.3 36.5 45.5" aria-hidden="true" focusable="false">' +
        '<path ' + (anima ? 'class="penna" pathLength="1" ' : "") + 'd="M18 12C18 24 18 32 20 36C22 40 30 40 42 40C46 40 47 43 47 50M24 40V50" fill="none" stroke="currentColor" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/>' +
        '<circle ' + (anima ? 'class="penna-punto" ' : "") + 'cx="34" cy="24" r="6.4" fill="#167A68"/></svg>'
      );
    },
  };
  window.MARCHI = MARCHI;

  var FAMIGLIA = [
    { id: "parliamentrag", nome: "ParliamentRAG", href: "../parliamentrag/index.html", ruolo: "Metodo, dati, verifica" },
    { id: "stenografo", nome: "Stenografo", href: "../stenografo/index.html", ruolo: "Domande puntuali" },
    { id: "fascicoli", nome: "Fascicoli", href: "../fascicoli/index.html", ruolo: "Un tema, tutti i gruppi" },
    { id: "scranno", nome: "Scranno", href: "../scranno/index.html", ruolo: "L'Aula, seggio per seggio" },
  ];
  window.FAMIGLIA = FAMIGLIA;

  var NAV = {
    parliamentrag: [
      { k: "metodo", t: "Metodo", h: "metodo.html" },
      { k: "verifica", t: "Verifica", h: "verifica.html" },
      { k: "dati", t: "Dati", h: "dati.html" },
      { k: "ricerca", t: "Ricerca", h: "ricerca.html" },
      { k: "sviluppatori", t: "Sviluppatori", h: "sviluppatori.html" },
      { k: "aggiornamenti", t: "Aggiornamenti", h: "aggiornamenti.html" },
    ],
    stenografo: [
      { k: "chiedi", t: "Chiedi", h: "index.html" },
      { k: "come", t: "Come risponde", h: "../parliamentrag/metodo.html" },
    ],
    fascicoli: [
      { k: "tema", t: "Temi", h: "index.html" },
      { k: "come", t: "Come è composto", h: "../parliamentrag/metodo.html" },
    ],
    scranno: [
      { k: "aula", t: "Aula", h: "index.html" },
      { k: "dati", t: "Da dove vengono i dati", h: "../parliamentrag/dati.html" },
    ],
  };

  var ICONA = {
    sole: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    luna: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
    menu: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M4 8h16M4 16h16"/></svg>',
    chiudi: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  };
  window.ICONE = {
    spunta: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>',
    croce: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.8 5.8l4.4 4.4M10.2 5.8l-4.4 4.4"/></svg>',
    freccia: '<svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg>',
    esterno: '<svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-1px"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg>',
  };

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  window.esc = esc;

  /* La barra di famiglia è stata tolta: i sistemi si collegano dal piede e dai link nelle pagine */
  var barra = document.querySelector("[data-famiglia]");
  if (barra) barra.remove();

  /* ---------- Testata ---------- */

  var testata = document.querySelector("[data-testata]");
  if (testata) {
    var nomeSito = FAMIGLIA.filter(function (f) { return f.id === SITO; })[0];
    testata.className = "sito";
    testata.innerHTML =
      '<div class="pagina sito__in">' +
      '<a class="marchio" href="index.html" aria-label="' + nomeSito.nome + ', pagina iniziale">' +
      MARCHI[SITO](!sessionStorageGet("marchio-" + SITO)) +
      '<span class="marchio__nome">' + nomeSito.nome + "</span></a>" +
      '<nav class="nav" id="nav" aria-label="Sezioni">' +
      NAV[SITO].map(function (v) {
        return '<a href="' + v.h + '"' + (v.k === PAGINA ? ' aria-current="page"' : "") + ">" + v.t + "</a>";
      }).join("") +
      "</nav>" +
      '<div class="sito__azioni">' +
      '<button class="btn btn--linea btn--icona" type="button" data-tema aria-label="Cambia tema"></button>' +
      '<button class="btn btn--linea btn--icona menu-btn" type="button" aria-controls="nav" aria-expanded="false" aria-label="Apri il menu">' + ICONA.menu + "</button>" +
      "</div></div>";
    sessionStorageSet("marchio-" + SITO, "1");

    var menuBtn = testata.querySelector(".menu-btn");
    var nav = testata.querySelector(".nav");
    menuBtn.addEventListener("click", function () {
      var aperto = nav.getAttribute("data-aperto") === "true";
      nav.setAttribute("data-aperto", aperto ? "false" : "true");
      menuBtn.setAttribute("aria-expanded", aperto ? "false" : "true");
      menuBtn.innerHTML = aperto ? ICONA.menu : ICONA.chiudi;
      document.body.style.overflow = aperto ? "" : "hidden";
    });

    var onScroll = function () {
      testata.setAttribute("data-scorre", window.scrollY > 8 ? "true" : "false");
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- Tema ---------- */

  function temaCorrente() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function disegnaTema() {
    document.querySelectorAll("[data-tema]").forEach(function (b) {
      var scuro = temaCorrente() === "dark";
      b.innerHTML = scuro ? ICONA.sole : ICONA.luna;
      b.setAttribute("aria-label", scuro ? "Passa al tema chiaro" : "Passa al tema scuro");
    });
  }
  try {
    var salvato = localStorage.getItem("famiglia-tema");
    if (salvato) root.setAttribute("data-theme", salvato);
  } catch (e) {}
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-tema]");
    if (!b) return;
    var nuovo = temaCorrente() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", nuovo);
    try {
      localStorage.setItem("famiglia-tema", nuovo);
    } catch (err) {}
    disegnaTema();
    document.dispatchEvent(new CustomEvent("tema"));
  });
  disegnaTema();

  /* ---------- Piede ---------- */

  var piede = document.querySelector("[data-piede]");
  if (piede) {
    piede.className = "piede";
    piede.innerHTML =
      '<div class="pagina">' +
      '<div class="piede__griglia">' +
      '<div class="pila" style="--pila:var(--s-4)">' +
      '<a class="marchio" href="../parliamentrag/index.html">' + MARCHI.parliamentrag(false) + '<span class="marchio__nome">ParliamentRAG</span></a>' +
      '<p style="max-width:40ch">Progetto di ricerca per l\'AI sui dibattiti delle istituzioni italiane. Università di Milano-Bicocca.</p>' +
      '<p class="nota">Progetto indipendente: non è affiliato alla Camera dei Deputati e non parla a suo nome.</p>' +
      "</div>" +
      "<div><h2>Sistemi</h2><ul>" +
      FAMIGLIA.slice(1).map(function (f) {
        return '<li><a href="' + f.href + '">' + f.nome + "</a></li>";
      }).join("") +
      "</ul></div>" +
      '<div><h2>Progetto</h2><ul>' +
      '<li><a href="../parliamentrag/metodo.html">Metodo</a></li>' +
      '<li><a href="../parliamentrag/verifica.html">Verifica</a></li>' +
      '<li><a href="../parliamentrag/dati.html">Dati aperti</a></li>' +
      '<li><a href="../parliamentrag/ricerca.html">Ricerca</a></li>' +
      '<li><a href="../parliamentrag/sviluppatori.html">Sviluppatori</a></li>' +
      '<li><a href="../parliamentrag/aggiornamenti.html">Aggiornamenti</a></li>' +
      "</ul></div>" +
      '<div><h2>Note legali</h2><ul>' +
      '<li><a href="../parliamentrag/privacy.html">Privacy</a></li>' +
      '<li><a href="../parliamentrag/termini.html">Termini</a></li>' +
      '<li><a href="https://creativecommons.org/licenses/by-sa/4.0/deed.it" rel="noopener">Licenza dei dati CC BY-SA 4.0</a></li>' +
      '<li><a href="https://dati.camera.it/" rel="noopener">dati.camera.it</a></li>' +
      '<li><a href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a></li>' +
      "</ul></div>" +
      "</div>" +
      '<div class="piede__fondo">' +
      '<p>Con il sostegno del programma EU Horizon Europe, grant <a href="https://doi.org/10.3030/101189771" rel="noopener">101189771</a> (<a href="https://datapact.eu/" rel="noopener">DataPACT</a>)</p>' +
      '<p>Mirko Tritella · <a href="https://emeierkeio.github.io" rel="noopener">emeierkeio.github.io</a></p>' +
      "</div></div>";
  }

  /* ---------- Comparse allo scorrimento ---------- */

  function osserva() {
    var el = document.querySelectorAll(".compare:not([data-visto])");
    if (!("IntersectionObserver" in window)) {
      el.forEach(function (n) { n.setAttribute("data-visto", "true"); });
      return;
    }
    var io = new IntersectionObserver(
      function (voci) {
        voci.forEach(function (v) {
          if (v.isIntersecting) {
            v.target.setAttribute("data-visto", "true");
            io.unobserve(v.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );
    el.forEach(function (n) { io.observe(n); });
  }
  window.osservaComparse = osserva;
  osserva();

  /* ---------- Copia ---------- */

  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copia]");
    if (!b) return;
    var sorgente = document.getElementById(b.getAttribute("data-copia"));
    var testo = sorgente ? sorgente.innerText.trim() : "";
    var fatto = function () {
      var prima = b.textContent;
      b.textContent = "Copiato";
      setTimeout(function () { b.textContent = prima; }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(testo).then(fatto, fatto);
    } else {
      fatto();
    }
  });

  /* ---------- Utilità ---------- */

  function sessionStorageGet(k) {
    try {
      return sessionStorage.getItem(k);
    } catch (e) {
      return null;
    }
  }
  function sessionStorageSet(k, v) {
    try {
      sessionStorage.setItem(k, v);
    } catch (e) {}
  }

  /* Numeri italiani: 47.763 */
  window.numero = function (n) {
    return String(Math.round(Number(n))).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  };
})();
