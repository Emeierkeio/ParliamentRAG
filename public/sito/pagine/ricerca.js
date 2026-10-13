(function () {
  "use strict";

  /* ---------- «Cita»: apre e chiude il BibTeX sotto l'articolo ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-cita]");
    if (!b) return;
    var box = document.getElementById(b.getAttribute("aria-controls"));
    var aperto = b.getAttribute("aria-expanded") === "true";
    b.setAttribute("aria-expanded", aperto ? "false" : "true");
    box.hidden = aperto;
  });
})();
