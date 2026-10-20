/*
 * Guscio comune del sito: comportamento di testata (menu, ombra allo
 * scorrimento), tema, comparse allo scorrimento e pulsanti «copia».
 * Testata e piede arrivano già scritti dal server (src/sito/guscio.ts).
 *
 * Espone window.MARCHI, window.ICONE, window.esc, window.numero,
 * window.osservaComparse, window.LINGUA: li usano gli script delle pagine.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  root.classList.remove("no-js");
  var EN = root.lang === "en";
  window.LINGUA = EN ? "en" : "it";

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

  var ICONA = {
    sole: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    luna: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
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

  /* ---------- Testata ---------- */

  var testata = document.querySelector("[data-testata]");
  if (testata) {
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
      b.setAttribute("aria-label", scuro ? (EN ? "Switch to light theme" : "Passa al tema chiaro") : (EN ? "Switch to dark theme" : "Passa al tema scuro"));
    });
  }
  try {
    var salvato = localStorage.getItem("famiglia-tema");
    if (salvato) root.setAttribute("data-theme", salvato);
  } catch { /* memoria bloccata */ }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-tema]");
    if (!b) return;
    var nuovo = temaCorrente() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", nuovo);
    try {
      localStorage.setItem("famiglia-tema", nuovo);
    } catch { /* memoria bloccata */ }
    disegnaTema();
    document.dispatchEvent(new CustomEvent("tema"));
  });
  disegnaTema();

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
      b.textContent = EN ? "Copied" : "Copiato";
      setTimeout(function () { b.textContent = prima; }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(testo).then(fatto, fatto);
    } else {
      fatto();
    }
  });

  /* ---------- Utilità ---------- */

  /* Numeri con il separatore delle migliaia della lingua: 47.763 / 47,763 */
  window.numero = function (n) {
    return String(Math.round(Number(n))).replace(/\B(?=(\d{3})+(?!\d))/g, EN ? "," : ".");
  };
  /* Data lunga nella lingua della pagina, da «AAAA-MM-GG» senza fusi orari */
  window.dataLunga = function (s) {
    var p = String(s).split("-");
    return new Date(+p[0], +p[1] - 1, +p[2]).toLocaleDateString(EN ? "en-GB" : "it-IT", { day: "numeric", month: "long", year: "numeric" });
  };
})();
