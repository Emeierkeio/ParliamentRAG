/* Dossier del tema (card 284): sotto le posizioni dei gruppi del fascicolo, le sezioni tecniche da /api/dossier
   (emendamenti presentati e com'è finita, atti, chi ci lavora, in arrivo), e l'esportazione in PDF di un turno della
   chat: copertina con logo, indice, una sezione per pagina, contatti in ogni pagina, nota sul metodo. Il PDF lo fa il
   browser («Salva come PDF») da una pagina di stampa: niente librerie. */
(function () {
  const e = B.esc;
  const D = (window.DOSSIER = {});
  const MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  const data = (d) => { if (!d) return ""; const x = String(d).slice(0, 10).split("-"); return `${+x[2]} ${MESI[+x[1] - 1]} ${x[0]}`; };
  const classe = (x) => (/^approvato/.test(x) ? "ok" : x === "respinto" ? "no" : "neutro");

  /* ---------- sezioni tecniche sotto il fascicolo ---------- */
  D.sezioni = async (t, tema, blocco) => {
    let d;
    try { d = await fetch("/api/dossier", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tema: tema.slice(0, 300) }) }).then((r) => (r.ok ? r.json() : null)); }
    catch { d = null; }
    if (!d) return;
    // il quadro in breve: gli atti toccati dal tema, a che punto sono, emendamenti e prossima scadenza
    const q = d.quadro || [];
    if (q.length) {
      const stato = (x) => x.legge ? TT(`Legge n. ${x.legge}`, `Law no. ${x.legge}`) + (x.data_legge ? ` · ${data(x.data_legge)}` : "") : `${B.frase(x.stato || TT("in corso", "ongoing"))}${x.data_stato ? ` · ${data(x.data_stato)}` : ""}`;
      blocco(t, "quadro", TT("In breve", "At a glance"), B.info(TT("Gli atti che toccano il tema: a che punto sono, quanti emendamenti sul tema e la prossima scadenza. Il dettaglio è nelle sezioni sotto.", "The bills touching the topic: where they stand, how many amendments on the topic and the next deadline. Details in the sections below.")),
        `<table class="dos-quadro"><thead><tr><th>${TT("Atto", "Bill")}</th><th>${TT("Di cosa parla", "Subject")}</th><th>${TT("A che punto è", "Status")}</th><th>${TT("Emendamenti sul tema", "Amendments on topic")}</th><th>${TT("Prossima scadenza", "Next deadline")}</th></tr></thead><tbody>${q.map((x) => `<tr>
          <td>${x.url ? `<a href="${e(x.url)}" target="_blank" rel="noopener"><b>${e(x.sigla)}</b></a>` : `<b>${e(x.sigla)}</b>`}</td>
          <td>${e(B.taglia(x.titolo || "", 110))}</td><td>${e(stato(x))}</td>
          <td>${x.emendamenti ? `${x.emendamenti}${x.approvati ? ` · <span class="dos-es--ok">${x.approvati} ${TT(x.approvati === 1 ? "approvato" : "approvati", "adopted")}</span>` : ""}` : "–"}</td>
          <td>${x.scadenza ? `<b>${data(x.scadenza.scadenza)}${x.scadenza.ora ? `, ${String(x.scadenza.ora).slice(0, 5)}` : ""}</b><br><span class="meta">${e(x.scadenza.organo || "")}</span>` : x.audizione ? `<span class="meta">${TT("ultima audizione", "last hearing")} ${data(x.audizione.data)}</span>` : "–"}</td></tr>`).join("")}</tbody></table>`);
    }
    const em = d.emendamenti;
    if (em.elenco.length) blocco(t, "emendamenti", TT("Emendamenti sul tema", "Amendments on the topic"), B.info(TT("I più vicini al tema per significato, in tutta la legislatura. L'esito viene dalla fonte indicata; «non pubblicato» non vuol dire respinto.", "The closest to the topic by meaning, across the legislature. The outcome comes from the stated source; «not published» does not mean rejected.")),
      `<p class="dos-sotto">${Object.entries(em.per_esito).map(([k, n]) => `<span class="dos-chip">${e(TR(k))} <b>${n}</b></span>`).join("")}</p>
       <ul class="lista dos-em">${em.elenco.map((x) => `<li><span class="meta">${e(x.numero)} · ${e(x.sigla_atto)} · ${e(x.sede)}${x.data ? ` · ${data(x.data)}` : ""} · <span class="dos-es dos-es--${classe(x.esito)}">${e(TR(x.etichetta))}</span></span>
         <span>${e(B.taglia(x.testo.replace(/\s+/g, " "), 220))}</span>
         <span class="dos-firme">${e(x.firmatari.filter((f) => f.primo).map((f) => `${f.nome}${f.gruppo ? ` (${f.gruppo})` : ""}`).join(", ") || x.gruppi.join(", "))}${x.link_atto ? ` · <a href="${e(x.link_atto)}" target="_blank" rel="noopener">${TT("scheda dell'atto", "bill page")}</a>` : ""}</span></li>`).join("")}</ul>`);
    const chi = d.chi_ci_lavora;
    if (chi.gruppi.length) blocco(t, "chi", TT("Chi ci lavora", "Who works on it"), B.info(TT("Primi firmatari degli emendamenti qui sopra: un dato pubblico sul lavoro parlamentare.", "First signatories of the amendments above: public data on parliamentary work.")),
      `<table class="dos-tab"><thead><tr><th>${TT("Gruppo", "Group")}</th><th>${TT("Emendamenti", "Amendments")}</th><th>${TT("Approvati", "Adopted")}</th></tr></thead><tbody>${chi.gruppi.map((g) => `<tr><td>${e(g.gruppo)}</td><td>${g.presentati}</td><td>${g.approvati}</td></tr>`).join("")}</tbody></table>
       ${chi.persone.length ? `<ul class="lista">${chi.persone.map((p) => `<li><span><b>${e(p.nome)}</b> · ${e(p.gruppo)}</span><span class="meta">${p.presentati} ${TT("presentati", "tabled")} · ${p.approvati} ${TT("approvati", "adopted")}</span></li>`).join("")}</ul>` : ""}`);
    const arr = d.in_arrivo;
    blocco(t, "arrivo", TT("In arrivo", "Coming up"), "",
      arr.termini.length || arr.audizioni.length
        ? `${arr.termini.length ? `<h4>${TT("Termini per gli emendamenti", "Amendment deadlines")}</h4><ul class="lista">${arr.termini.map((x) => `<li><span class="meta">${data(x.scadenza)}${x.ora ? `, ${String(x.ora).slice(0, 5)}` : ""} · ${e(x.organo || "")}</span><span>${e(x.frase)}</span></li>`).join("")}</ul>` : ""}
           ${arr.audizioni.length ? `<h4>${TT("Audizioni sugli atti del tema", "Hearings on the topic's bills")}</h4><ul class="lista">${arr.audizioni.map((x) => `<li><span class="meta">${data(x.data)} · ${e(x.organo || "")}</span><span>${e(x.chi)}</span></li>`).join("")}</ul>` : ""}`
        : `<p class="dos-sotto">${TT("Nessun termine aperto né audizione recente sugli atti trovati.", "No open deadline or recent hearing on the bills found.")}</p>`);
    if (d.atti.length) blocco(t, "atti", TT("Atti sul tema", "Bills and acts on the topic"), "",
      `<ul class="lista">${d.atti.map((a) => `<li><span class="meta">${e(a.ramo === "senato" ? "Senato" : "Camera")}${a.data ? ` · ${data(a.data)}` : ""}</span><span>${a.url ? `<a href="${e(a.url)}" target="_blank" rel="noopener">${e(B.taglia(a.titolo, 200))}</a>` : e(B.taglia(a.titolo, 200))}</span></li>`).join("")}</ul>`);
    // in fondo al dossier, l'invito alla newsletter: chi ha appena ottenuto un dossier è chi la vuole
    blocco(t, "iscriviti", TT("Ricevi le novità per email", "Get the news by email"), "",
      `<form class="dos-news" novalidate><p>${TT("Nuovi strumenti e nuovi dati sul Parlamento, appena escono. Ti scriviamo solo quando c'è qualcosa di nuovo.", "New tools and data on Parliament, as soon as they ship. We only write when there is something new.")}</p>
        <div class="news__riga"><label class="vh">Email</label><input type="email" placeholder="${TT("La tua email", "Your email")}" autocomplete="email" required><button class="bt bt--primario" type="submit">${TT("Iscriviti", "Subscribe")}</button></div>
        <label class="spunta"><input type="checkbox"> <span>${TT("Ho letto l'<a href=\"#/legale/privacy\">informativa privacy</a> e accetto di ricevere aggiornamenti.", "I have read the <a href=\"#/legale/privacy\">privacy notice</a> and agree to receive updates.")}</span></label><p class="news__msg" role="status"></p></form>`);
  };
  // i moduli di iscrizione sotto i dossier: stessa chiamata del modulo della home
  document.addEventListener("submit", async (ev) => {
    const f = ev.target.closest(".dos-news"); if (!f) return; ev.preventDefault();
    const m = f.querySelector(".news__msg"), em = f.querySelector("input[type=email]").value.trim(), bt = f.querySelector("button");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) { m.textContent = TT("Scrivi un indirizzo email valido.", "Enter a valid email address."); return; }
    if (!f.querySelector("input[type=checkbox]").checked) { m.textContent = TT("Per iscriverti serve il consenso.", "Consent is required to subscribe."); return; }
    bt.disabled = true;
    const r = await fetch("/api/iscriviti", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: em, consenso: true, lingua: window.LANG }) }).catch(() => null);
    const d = r ? await r.json().catch(() => ({})) : {};
    m.textContent = r && r.ok && d.ok ? TT("Ti abbiamo mandato una mail: clicca il link per confermare l'iscrizione.", "We sent you an email: click the link to confirm.") : d.errore || TT("Iscrizione non riuscita, riprova.", "Subscription failed, try again.");
    if (r && r.ok) f.reset(); bt.disabled = false;
  });

  /* ---------- PDF ---------- */
  D.pdf = (el) => {
    const q = (el.querySelector(".turno__dom") || {}).textContent || "Dossier";
    // «Dossier su Acme Bevande, temi: …; associazioni: ….» → titolo il soggetto, sottotitolo i temi scelti
    const m = q.match(/^(?:Dossier su|Dossier on) (.+?)(?:, (?:temi|topics): (.+?))?(?:; (?:associazioni|associations): (.+?))?\. /);
    const titolo = m ? m[1] : q, temi = m ? [m[2], m[3]].filter(Boolean).join(", ").split(/, /).join(" · ") : "";
    const sezioni = [...el.querySelectorAll("[data-blocco]")].filter((b) => !b.hidden && b.textContent.trim() && b.dataset.blocco !== "iscriviti")
      .sort((a, b) => (b.dataset.blocco === "quadro") - (a.dataset.blocco === "quadro"))
      .map((b) => ({ titolo: b.dataset.blocco === "risposta" ? TT("Posizioni e risposta", "Positions and answer") : ((b.querySelector("h3") || {}).firstChild || {}).textContent || "", html: b.innerHTML }));
    const dati = { titolo, temi, lingua: window.LANG === "en" ? "en" : "it", data: new Date().toISOString(), sezioni };
    // la finestra si apre subito (dopo un await il browser la bloccherebbe), poi va alla pagina condivisibile del dossier
    const w = window.open("", "_blank");
    fetch("/api/dossier/condividi", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dati) })
      .then((r) => (r.ok ? r.json() : Promise.reject(r))).then((x) => {
        const url = `/dossier/${x.id}?stampa=1`;
        if (w) w.location.href = url; else location.href = url;
      }).catch(() => {
        // senza salvataggio: il documento nella finestra, come prima, senza link da condividere
        const html = DOSSIER_DOC(dati, true);
        if (w) { w.document.open(); w.document.write(html); w.document.close(); return; }
        const f = document.createElement("iframe"); f.style.cssText = "position:fixed;width:0;height:0;border:0;right:0;bottom:0";
        document.body.appendChild(f); f.contentDocument.open(); f.contentDocument.write(html); f.contentDocument.close();
        setTimeout(() => f.remove(), 60000);
      });
  };
  document.addEventListener("click", (ev) => { const b = ev.target.closest("[data-pdf]"); if (!b) return; const el = b.closest(".turno"); if (el) D.pdf(el); });
})();
