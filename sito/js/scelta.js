/* La scelta sopra la casella (come le domande di Claude): per un soggetto che non è un tema parlamentare, i temi e le
   associazioni che il modello propone e il database ha verificato, ognuno con i suoi numeri. L'utente spunta, aggiunge
   qualcos'altro o salta; poi parte il dossier sulle voci scelte. Le voci senza riscontro non arrivano qui. */
(function () {
  const e = B.esc;
  const S = (window.SCELTA = {});
  const numeri = (o) => {
    const c = o.conteggi || {};
    // [numero, singolare, plurale]
    const pezzi = o.tipo === "tema"
      ? [[c.interventi, TT("intervento", "speech"), TT("interventi", "speeches")], [c.emendamenti, TT("emendamento", "amendment"), TT("emendamenti", "amendments")], [c.atti, TT("atto", "act"), TT("atti", "acts")]]
      : [[c.audizioni, TT("audizione", "hearing"), TT("audizioni", "hearings")], [c.memorie, TT("memoria", "written submission"), TT("memorie", "written submissions")], [c.interventi, TT("intervento che la nomina", "speech naming it"), TT("interventi che la nominano", "speeches naming it")]];
    return pezzi.filter(([n]) => n).map(([n, uno, piu]) => `${n >= 1000 ? "1.000+" : B.num(n)} ${n === 1 ? uno : piu}`).join(" · ");
  };
  const togli = () => { const x = document.getElementById("scelta"); if (x) x.remove(); };
  S.togli = togli;

  // prima della scelta dei temi, quando dal nome non si capisce di cosa si occupa l'azienda: si sceglie il settore
  const SETTORI = [["Alimentare e bevande", "Food and drink"], ["Commercio, turismo e ristorazione", "Retail, tourism and hospitality"],
    ["Edilizia e immobiliare", "Construction and real estate"], ["Energia e ambiente", "Energy and environment"],
    ["Industria e manifattura", "Industry and manufacturing"], ["Salute e farmaceutica", "Health and pharma"],
    ["Trasporti e logistica", "Transport and logistics"], ["Tecnologia e telecomunicazioni", "Technology and telecoms"],
    ["Banche, finanza e assicurazioni", "Banking, finance and insurance"], ["Agricoltura e pesca", "Farming and fishing"]];
  const temi = (soggetto, settore) => fetch("/api/temi", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ soggetto, settore }) })
    .then((x) => x.json()).catch(() => ({}));
  S.settore = (r) => {
    togli();
    const box = document.createElement("div");
    box.id = "scelta"; box.className = "scelta"; box.setAttribute("role", "group"); box.setAttribute("aria-labelledby", "scelta-t");
    box.innerHTML = `<header><div><h3 id="scelta-t">${e(TT(`Di cosa si occupa ${r.soggetto}?`, `What does ${r.soggetto} do?`))}</h3><p>${e(TT("Dal nome non lo capiamo. Scegli uno o più settori e ti proponiamo i temi del Parlamento che lo riguardano.", "We can't tell from the name. Pick one or more sectors and we'll suggest the topics before Parliament."))}</p></div>
        <button type="button" class="scelta__x" data-scelta="chiudi" aria-label="${TT("Chiudi", "Close")}">${B.ico("chiudi")}</button></header>
      <ol>${SETTORI.map(([it, en], i) => `<li><label><input type="checkbox" value="${e(TT(it, en))}"><span class="scelta__n">${i + 1}</span><span class="scelta__c"><b>${e(TT(it, en))}</b></span></label></li>`).join("")}
        <li class="scelta__altro"><span class="scelta__n">${B.ico("piu")}</span><label class="vh" for="scelta-altro">${TT("Altro: scrivilo tu", "Other: type it")}</label><input id="scelta-altro" placeholder="${TT("Altro: scrivilo tu (es. «produciamo imballaggi»)", "Other: type it (e.g. «we make packaging»)")}" maxlength="120"></li></ol>
      <footer><p class="scelta__nota">${TT("Serve solo a proporti i temi giusti.", "Only used to suggest the right topics.")}</p>
        <button type="button" class="bt bt--linea" data-scelta="chiudi">${TT("Salta", "Skip")}</button><button type="button" class="bt" data-scelta="vai">${TT("Continua", "Continue")}</button></footer>`;
    const comp = document.querySelector(".compositore");
    comp.insertBefore(box, comp.querySelector("form"));
    box.addEventListener("keydown", (ev) => {
      if (ev.target.id === "scelta-altro") { if (ev.key === "Enter") { ev.preventDefault(); box.querySelector('[data-scelta="vai"]').click(); } return; }
      const n = parseInt(ev.key, 10); if (n >= 1 && n <= SETTORI.length) { const c = box.querySelectorAll("input[type=checkbox]")[n - 1]; c.checked = !c.checked; }
      if (ev.key === "Escape") togli();
    });
    box.addEventListener("click", async (ev) => {
      // solo i pulsanti del riquadro: <html> ha data-scelta (il tema), e un clic su una voce ci arriverebbe risalendo
      const b = ev.target.closest("button[data-scelta]"); if (!b || !box.contains(b)) return;
      if (b.dataset.scelta === "chiudi") return togli();
      const altro = box.querySelector("#scelta-altro").value.trim();
      const settore = [...box.querySelectorAll("input[type=checkbox]:checked")].map((x) => x.value).concat(altro ? [altro] : []).join(", ");
      if (!settore) return;
      b.disabled = true; b.textContent = TT("Cerco i temi…", "Finding topics…");
      const x = await temi(r.soggetto, settore);
      if (x && x.opzioni && x.opzioni.length) S.mostra(x);
      else { b.disabled = false; b.textContent = TT("Riprova", "Try again"); }
    });
    const primo = box.querySelector("input[type=checkbox]"); if (primo) primo.focus({ preventScroll: true });
  };

  S.mostra = (r) => {
    togli();
    const ops = (r.opzioni || []).slice().sort((a, b) => (b.consigliato ? 1 : 0) - (a.consigliato ? 1 : 0) || b.peso - a.peso);
    if (!ops.length) return;
    const d = r.diretto || {};
    const diretto = d.audizioni || d.memorie || d.interventi
      ? TT(`${r.soggetto} in Parlamento: ${[d.audizioni && `${d.audizioni} ${d.audizioni === 1 ? "audizione" : "audizioni"}`, d.memorie && `${d.memorie} ${d.memorie === 1 ? "memoria" : "memorie"}`, d.interventi && `${d.interventi} ${d.interventi === 1 ? "intervento che lo nomina" : "interventi che lo nominano"}`].filter(Boolean).join(", ")}.`,
        `${r.soggetto} in Parliament: ${[d.audizioni && `${d.audizioni} hearings`, d.memorie && `${d.memorie} submissions`, d.interventi && `${d.interventi} speeches naming it`].filter(Boolean).join(", ")}.`)
      : TT(`${r.soggetto} non è mai nominato in modo pertinente. Ti propongo:`, `${r.soggetto} is never mentioned in a relevant way. I suggest:`);
    const box = document.createElement("div");
    box.id = "scelta"; box.className = "scelta"; box.setAttribute("role", "group"); box.setAttribute("aria-labelledby", "scelta-t");
    box.innerHTML = `<header><div><h3 id="scelta-t">${e(TT(`Quali temi all'esame del Parlamento interessano ${r.soggetto}?`, `Which topics before Parliament matter to ${r.soggetto}?`))}</h3><p>${e(diretto)}</p></div>
        <button type="button" class="scelta__x" data-scelta="chiudi" aria-label="${TT("Chiudi", "Close")}">${B.ico("chiudi")}</button></header>
      <ol>${ops.map((o, i) => `<li><label><input type="checkbox" value="${i}"${o.consigliato || (o.tipo === "associazione" && i < 3) ? " checked" : ""}>
        <span class="scelta__n">${i + 1}</span><span class="scelta__c"><b>${e(o.nome)}${o.tipo === "associazione" ? ` <small>${TT("associazione di categoria", "trade association")}</small>` : ""}${o.consigliato ? ` <em>${TT("Consigliato", "Recommended")}</em>` : ""}${o.generico ? ` <small>${TT("tema molto ampio", "very broad topic")}</small>` : ""}</b>
        <span>${e(numeri(o))}</span></span></label></li>`).join("")}
        <li class="scelta__altro"><span class="scelta__n">${B.ico("piu")}</span><label class="vh" for="scelta-altro">${TT("Qualcos'altro", "Something else")}</label><input id="scelta-altro" placeholder="${TT("Qualcos'altro", "Something else")}" maxlength="80"></li></ol>
      <footer><p class="scelta__nota">${TT("Proposte del modello, verificate sui dati del Parlamento.", "Model suggestions, checked against Parliament's data.")}</p>
        <button type="button" class="bt bt--linea" data-scelta="salta">${TT("Salta", "Skip")}</button><button type="button" class="bt" data-scelta="vai">${TT("Fai il dossier", "Build the dossier")}</button></footer>`;
    const comp = document.querySelector(".compositore");
    comp.insertBefore(box, comp.querySelector("form"));
    box.addEventListener("keydown", (ev) => {
      if (ev.target.id === "scelta-altro") { if (ev.key === "Enter") { ev.preventDefault(); box.querySelector('[data-scelta="vai"]').click(); } return; }
      const n = parseInt(ev.key, 10); if (n >= 1 && n <= ops.length) { const c = box.querySelectorAll("input[type=checkbox]")[n - 1]; c.checked = !c.checked; }
      if (ev.key === "Escape") togli();
    });
    box.addEventListener("click", (ev) => {
      // solo i pulsanti del riquadro: <html> ha data-scelta (il tema), e un clic su una voce ci arriverebbe risalendo
      const b = ev.target.closest("button[data-scelta]"); if (!b || !box.contains(b)) return;
      if (b.dataset.scelta === "chiudi") return togli();
      const scelti = [...box.querySelectorAll("input[type=checkbox]:checked")].map((x) => ops[+x.value]);
      const altro = box.querySelector("#scelta-altro").value.trim();
      const temi = scelti.filter((o) => o.tipo === "tema").map((o) => o.nome).concat(altro ? [altro] : []);
      const ass = scelti.filter((o) => o.tipo === "associazione").map((o) => o.nome);
      togli();
      const q = b.dataset.scelta === "salta" || (!temi.length && !ass.length)
        ? TT(`Cosa c'è in Parlamento su ${r.soggetto} in sé: interventi che lo nominano, audizioni, memorie, atti?`, `What does Parliament have on ${r.soggetto} itself: speeches naming it, hearings, submissions, acts?`)
        : TT(`Dossier su ${r.soggetto}${temi.length ? `, temi: ${temi.join(", ")}` : ""}${ass.length ? `; associazioni: ${ass.join(", ")}` : ""}. Per ogni tema le posizioni dei gruppi, gli emendamenti presentati e com'è finita, i voti e le scadenze; per le associazioni le audizioni e le memorie.`,
          `Dossier on ${r.soggetto}${temi.length ? `, topics: ${temi.join(", ")}` : ""}${ass.length ? `; associations: ${ass.join(", ")}` : ""}. For each topic the groups' positions, the amendments tabled and how they ended, votes and deadlines; for associations their hearings and submissions.`);
      CH.chiedi(q);
    });
    const primo = box.querySelector("input[type=checkbox]"); if (primo) primo.focus({ preventScroll: true });
  };
})();
