/* Bozze allegate alla chat: un file .docx o .pdf, oppure un testo incollato di più di 1.000 caratteri, che diventa un
   riquadro sopra la casella invece di riempirla (come in Claude). Il testo va con la domanda all'agente, che lo divide
   in emendamenti e cerca quelli simili già presentati. Il file non si conserva: il server ne legge solo il testo. */
(function () {
  const e = B.esc;
  const SOGLIA = 1000, MAX = 50000;
  const DOMANDA = TT("Questi emendamenti sono già stati presentati? Com'è finita?", "Have these amendments already been tabled? How did they end?");
  const CLIP = '<path d="M20.5 11.5 12 20a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.7 17.7a1.7 1.7 0 0 1-2.4-2.4L15 7.6"/>';
  const MATITA = '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>';
  const svg = (p) => `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;

  CH.allegato = null;      // { nome, testo, n, piu, stato: "pronto" | "leggo" | "errore", errore }

  function disegna() {
    // con una bozza pronta la casella propone la domanda che parte senza scrivere niente
    B.$$("form.chat textarea").forEach((ta) => {
      if (ta.dataset.segnaposto == null) ta.dataset.segnaposto = ta.placeholder;
      ta.placeholder = CH.allegato && CH.allegato.stato === "pronto" ? DOMANDA : ta.dataset.segnaposto;
    });
    B.$$(".allegato-box").forEach((box) => {
      const a = CH.allegato;
      box.hidden = !a;
      if (!a) { box.innerHTML = ""; return; }
      const titolo = a.nome || TT("Incollato", "Pasted");
      const sotto = a.stato === "leggo" ? TT("Leggo il file…", "Reading the file…")
        : a.stato === "errore" ? a.errore
        : [`${B.num(a.testo.length)} ${TT("caratteri", "characters")}`, a.n ? `${a.n} ${a.n === 1 ? TT("emendamento", "amendment") : TT("emendamenti", "amendments")}${a.piu ? TT(` (controllo i primi 20 di ${a.n + a.piu})`, ` (checking the first 20 of ${a.n + a.piu})`) : ""}` : "", TT("vale 3 domande", "counts as 3 questions")].filter(Boolean).join(" · ");
      box.innerHTML = `<div class="allegato${a.stato === "errore" ? " allegato--err" : ""}">
        <p class="allegato__testo">${a.stato === "pronto" ? e(a.testo.slice(0, 160)) : ""}</p>
        <div class="allegato__piede"><span class="allegato__et">${e(titolo)}</span><span class="allegato__sotto">${e(sotto)}</span>
          ${a.stato === "pronto" ? `<button type="button" class="allegato__bt" data-allegato="modifica" aria-label="${TT("Modifica il testo", "Edit the text")}" data-tip="${TT("Modifica il testo", "Edit the text")}">${svg(MATITA)}</button>` : ""}
          <button type="button" class="allegato__bt" data-allegato="togli" aria-label="${TT("Togli l'allegato", "Remove the attachment")}" data-tip="${TT("Togli", "Remove")}">${B.ico("chiudi")}</button></div></div>`;
    });
  }
  const imposta = (a) => { CH.allegato = a; disegna(); };
  CH.togliAllegato = () => imposta(null);

  async function leggiFile(f) {
    if (!/\.(docx|pdf)$/i.test(f.name)) { imposta({ nome: f.name, stato: "errore", errore: TT("Si leggono solo file .docx e .pdf.", "Only .docx and .pdf files can be read.") }); return; }
    if (f.size > 5e6) { imposta({ nome: f.name, stato: "errore", errore: TT("Il file supera 5 MB.", "The file is larger than 5 MB.") }); return; }
    imposta({ nome: f.name, stato: "leggo" });
    try {
      const buf = new Uint8Array(await f.arrayBuffer());
      let bin = ""; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
      const r = await fetch("/api/allegato", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: f.name, data: btoa(bin) }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || TT("il file non si legge", "the file cannot be read"));
      if (CH.allegato && CH.allegato.nome === f.name) imposta({ nome: f.name, testo: j.text, n: j.amendments, piu: j.more, stato: "pronto" });
    } catch (err) {
      imposta({ nome: f.name, stato: "errore", errore: `${TT("Non riesco a leggerlo", "I can't read it")}: ${err.message}` });
    }
  }

  function modifica() {
    const a = CH.allegato; if (!a || a.stato !== "pronto") return;
    let d = document.getElementById("dlg-allegato");
    if (!d) {
      d = document.createElement("dialog"); d.id = "dlg-allegato"; d.className = "dlg dlg--largo";
      d.innerHTML = `<form method="dialog" class="dlg__f"><header><h2>${TT("Testo allegato", "Attached text")}</h2><button class="dlg__x" value="annulla" aria-label="${TT("Chiudi", "Close")}">×</button></header>
        <label class="vh" for="allegato-ta">${TT("Testo allegato", "Attached text")}</label><textarea id="allegato-ta" rows="14" maxlength="${MAX}"></textarea>
        <div class="dlg__az"><button class="bt bt--linea" value="annulla">${TT("Annulla", "Cancel")}</button><button class="bt" value="salva">${TT("Salva", "Save")}</button></div></form>`;
      document.body.appendChild(d);
      d.addEventListener("close", () => { if (d.returnValue === "salva" && CH.allegato) { const t = d.querySelector("textarea").value.trim(); if (t) imposta({ ...CH.allegato, testo: t.slice(0, MAX), n: 0, piu: 0 }); else CH.togliAllegato(); } });
    }
    d.querySelector("textarea").value = a.testo;
    d.showModal();
  }

  B.$$("form.chat").forEach((f) => {
    const ta = f.querySelector("textarea");
    const box = document.createElement("div"); box.className = "allegato-box"; box.hidden = true;
    f.insertBefore(box, f.firstElementChild && f.firstElementChild.classList.contains("ctx") ? f.firstElementChild.nextSibling : f.querySelector("textarea, .riga"));
    const input = document.createElement("input"); input.type = "file"; input.accept = ".docx,.pdf"; input.hidden = true;
    const bt = document.createElement("button"); bt.type = "button"; bt.className = "ic-a allega";
    bt.setAttribute("aria-label", TT("Allega una bozza (.docx o .pdf)", "Attach a draft (.docx or .pdf)")); bt.dataset.tip = bt.getAttribute("aria-label");
    bt.innerHTML = svg(CLIP);
    const invia = f.querySelector(".invia"); invia.parentNode.insertBefore(bt, invia); invia.parentNode.insertBefore(input, invia);
    bt.addEventListener("click", () => input.click());
    input.addEventListener("change", () => { if (input.files[0]) leggiFile(input.files[0]); input.value = ""; });
    ta.addEventListener("paste", (ev) => {
      const t = (ev.clipboardData && ev.clipboardData.getData("text")) || "";
      if (t.length <= SOGLIA) return;
      ev.preventDefault();
      imposta({ nome: null, testo: t.slice(0, MAX), n: 0, piu: 0, stato: "pronto" });
    });
    f.addEventListener("dragover", (ev) => { if ([...(ev.dataTransfer?.types || [])].includes("Files")) { ev.preventDefault(); f.classList.add("trascina"); } });
    f.addEventListener("dragleave", () => f.classList.remove("trascina"));
    f.addEventListener("drop", (ev) => { const x = ev.dataTransfer?.files?.[0]; f.classList.remove("trascina"); if (x) { ev.preventDefault(); leggiFile(x); } });
  });
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-allegato]"); if (!b) return;
    if (b.dataset.allegato === "togli") CH.togliAllegato(); else modifica();
  });
  CH.domandaAllegato = DOMANDA;
})();
