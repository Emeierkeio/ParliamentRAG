/*
 * Iscrizione agli aggiornamenti: il modulo #iscrizione manda l'indirizzo a
 * /api/newsletter/subscribe, che lo passa a Brevo con il doppio consenso.
 * Parte solo l'email, il consenso e la pagina da cui arriva: niente altro.
 */
(function () {
  "use strict";
  var form = document.getElementById("iscrizione");
  if (!form) return;
  var EN = document.documentElement.lang === "en";
  var T = EN
    ? {
        email: "Enter a complete email address, for example name@example.com.",
        consenso: "To subscribe you need to accept the privacy notice.",
        server: "I can't complete the signup right now. Try again shortly.",
        spento: "Signup is not available right now. Try again later or write to contatti@parliamentrag.it.",
        ok: "Check your inbox: we sent you a link to confirm your subscription.",
        invio: "Sending…",
      }
    : {
        email: "Scrivi un indirizzo email completo, ad esempio nome@esempio.it.",
        consenso: "Per iscriverti devi accettare l'informativa.",
        server: "Non riesco a completare l'iscrizione adesso. Riprova tra poco.",
        spento: "L'iscrizione non è disponibile in questo momento. Riprova più tardi o scrivi a contatti@parliamentrag.it.",
        ok: "Controlla la posta: ti abbiamo inviato un link per confermare l'iscrizione.",
        invio: "Invio…",
      };
  var msg = document.getElementById("iscrizione-msg");
  var campo = document.getElementById("email");
  var consenso = document.getElementById("consenso");
  var bottone = form.querySelector('button[type="submit"]');
  var etichetta = bottone.textContent;
  var pagina = document.documentElement.getAttribute("data-pagina") || "home";

  function scrivi(tipo, testo) {
    msg.dataset.tipo = tipo;
    msg.textContent = testo;
  }
  campo.addEventListener("input", function () { campo.removeAttribute("aria-invalid"); });
  consenso.addEventListener("change", function () { consenso.removeAttribute("aria-invalid"); });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = campo.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) {
      campo.setAttribute("aria-invalid", "true");
      scrivi("errore", T.email);
      campo.focus();
      return;
    }
    if (!consenso.checked) {
      consenso.setAttribute("aria-invalid", "true");
      scrivi("errore", T.consenso);
      consenso.focus();
      return;
    }
    bottone.disabled = true;
    bottone.textContent = T.invio;
    msg.removeAttribute("data-tipo");
    msg.textContent = "";
    fetch("/api/newsletter/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, consent: true, source: pagina }),
    })
      .then(function (r) {
        if (r.ok) {
          scrivi("ok", T.ok);
          form.reset();
          return;
        }
        scrivi("errore", r.status === 503 ? T.spento : T.server);
      })
      .catch(function () {
        scrivi("errore", T.server);
      })
      .then(function () {
        bottone.disabled = false;
        bottone.textContent = etichetta;
      });
  });
})();
