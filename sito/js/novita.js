/* Novità: una card animata che da desktop si apre sulla home, una volta per versione. Per le novità successive si
   cambiano VERSIONE e PASSI; i dati negli esempi vengono dal database (niente esempi inventati). */
(function () {
  const VERSIONE = "2026-11-10b";
  const CHIAVE = "parliamentrag-novita";
  const e = B.esc;

  const PASSI = [
    {
      titolo: TT("L'agenda del Parlamento, settimana per settimana", "Parliament's agenda, week by week"),
      testo: TT("Sedute d'Aula e delle commissioni, termini per gli emendamenti, voti finali e leggi approvate in un solo calendario. La trovi negli Strumenti, e la chat risponde a «cosa succede questa settimana?».",
        "Floor and committee sittings, amendment deadlines, final votes and laws in one calendar. It is among the Tools, and the chat answers «what is happening this week?»."),
      cta: [TT("Apri l'agenda", "Open the agenda"), "#/strumenti/agenda"],
      scena: () => {
        const g = TT("Lun Mar Mer Gio Ven", "Mon Tue Wed Thu Fri").split(" ");
        const blocchi = [[1, 0, 1], [1, 0, 0, 0], [0, 1, 0], [1, 0, 0], [0, 0]];
        return `<div class="nov-sett">${g.map((x, i) => `<div class="nov-g" style="animation-delay:${.08 * i}s"><b>${x} <span>${9 + i}</span></b>${blocchi[i].map((a, j) => `<i class="nov-bl${a ? " aula" : ""}" style="animation-delay:${.35 + .08 * i + .1 * j}s;width:${70 + ((i * 7 + j * 13) % 30)}%"></i>`).join("")}${i === 0 ? `<div class="nov-term" style="animation-delay:1.1s">${TT("Termine emendamenti", "Amendment deadline")}<span>C. 3120 · ${TT("ore 12", "12:00")}</span></div>` : ""}</div>`).join("")}</div>`;
      },
    },
    {
      titolo: TT("I termini per gli emendamenti diventano un dato", "Amendment deadlines become data"),
      testo: TT("Li leggiamo nei sommari delle commissioni: atto, commissione, data e ora, proroghe. Ogni termine è letto due volte, con le regole e con un modello, ed entra solo se le due letture coincidono. Accanto c'è sempre la frase da cui viene.",
        "We read them in the committee summaries: bill, committee, date and time, extensions. Each deadline is read twice, by rules and by a model, and goes in only when both readings agree. The sentence it comes from is always next to it."),
      cta: [TT("Vedi i termini", "See the deadlines"), "#/strumenti/agenda"],
      scena: () => `<div class="nov-estr"><div class="nov-frase"><small>${TT("Bollettino, X Commissione Camera, 4 novembre 2026", "Bulletin, Chamber Committee X, 4 November 2026")}</small>«… ricorda che il <mark data-k="0">termine per la presentazione delle proposte emendative</mark> è fissato <mark data-k="2">alle ore 12 di lunedì 9 novembre</mark>.» <mark data-k="1">C. 3120</mark></div><div class="nov-fr">↓ amendment_deadline</div><div class="nov-campi"><div class="nov-c" data-k="0"><i>kind</i><b>${TT("emendamenti", "amendments")}</b></div><div class="nov-c" data-k="1"><i>act</i><b>C. 3120, ${TT("concorrenza", "competition")}</b></div><div class="nov-c scad" data-k="2"><i>due</i><b>${TT("lun 9/11/2026, 12:00", "Mon 9/11/2026, 12:00")}</b></div></div></div>`,
      dopo: (el, t) => [0, 1, 2].forEach((k) => t.push(setTimeout(() => el.querySelectorAll(`[data-k="${k}"]`).forEach((n) => n.classList.add("on")), 600 + k * 650))),
    },
    {
      titolo: TT("Audizioni, pareri e interrogazioni in chat", "Hearings, opinions and questions in the chat"),
      testo: TT("La chat ora sa chi è stato audito su una legge, che parere hanno dato le commissioni e come ha risposto il governo alle interrogazioni in commissione. Ogni fatto porta la frase del sommario e il link alla seduta.",
        "The chat now knows who was heard on a bill, which opinions the committees gave and how the government answered questions in committee. Every fact carries the summary sentence and the link to the sitting."),
      cta: [TT("Prova nella chat", "Try it in the chat"), null, TT("Chi è stato audito sul ddl concorrenza?", "Who was heard on the competition bill?")],
      scena: () => `<div class="nov-chat"><div class="nov-dom">${TT("Chi è stato audito sul ddl concorrenza?", "Who was heard on the competition bill?")}</div><div class="nov-str"><i class="nov-giro"></i>${TT("Leggo i fatti delle commissioni", "Reading committee facts")} <code>fatti_commissioni</code></div><div class="nov-risp"><p>${TT("Nella X Commissione della Camera, sul C. 3120, fra gli auditi:", "In Chamber Committee X, on C. 3120, among those heard:")}</p><div class="nov-chips">${["Confimprese", "Assopetroli-Assoenergia", "Federchimica-Assogasliquidi", "FIAIP", "FIMAA"].map((s, i) => `<span style="animation-delay:${2.1 + i * .12}s">${s}</span>`).join("")}</div></div></div>`,
      dopo: (el, t) => t.push(setTimeout(() => el.querySelector(".nov-str")?.classList.add("fatto"), 1800)),
    },
    {
      titolo: TT("Il dossier di un tema, anche da un'azienda", "A topic dossier, even from a company"),
      testo: TT("Scrivi un tema o il nome di un'azienda: la chat propone i temi parlamentari e le associazioni di categoria, li conta sui dati e tu scegli. Il dossier mette insieme posizioni dei gruppi, emendamenti e com'è finita, chi ci lavora e cosa è in arrivo, e si scarica in PDF.",
        "Type a topic or a company name: the chat suggests the parliamentary topics and trade associations, counts them on the data, and you choose. The dossier brings together group positions, amendments and their outcome, who works on it and what is coming, and downloads as a PDF."),
      cta: [TT("Prova con Coca-Cola", "Try Coca-Cola"), null, TT("Fai un dossier su Coca-Cola", "Make a dossier on Coca-Cola")],
      scena: () => {
        const temi = [[TT("Sugar tax", "Sugar tax"), TT("87 interventi · 5 emendamenti", "87 speeches · 5 amendments"), 1],
          ["Assobibe", TT("3 audizioni · 1 memoria", "3 hearings · 1 memo"), 1],
          [TT("Imballaggi e plastica monouso", "Packaging and single-use plastic"), TT("22 interventi · 21 emendamenti", "22 speeches · 21 amendments"), 0]];
        const sez = [TT("Posizioni dei gruppi", "Group positions"), TT("Emendamenti", "Amendments"), TT("Chi ci lavora", "Who works on it"), TT("In arrivo", "Coming up")];
        return `<div class="nov-tema"><div class="nov-scelta"><small>${TT("Su cosa faccio il dossier di Coca-Cola?", "What should the Coca-Cola dossier cover?")}</small>${temi.map(([n, c, s], i) => `<div class="nov-op" style="animation-delay:${.2 + i * .12}s"><i class="nov-ck" data-s="${s ? i : ""}"></i><span><b>${n}</b>${c}</span></div>`).join("")}</div><div class="nov-dos"><small>${TT("Dossier · sugar tax", "Dossier · sugar tax")}<span class="nov-pdf">PDF</span></small>${sez.map((x, i) => `<div class="nov-sez" data-z="${i}">${x}</div>`).join("")}</div></div>`;
      },
      dopo: (el, t) => {
        [0, 1].forEach((k) => t.push(setTimeout(() => el.querySelector(`[data-s="${k}"]`)?.classList.add("on"), 800 + k * 400)));
        [0, 1, 2, 3].forEach((k) => t.push(setTimeout(() => el.querySelector(`[data-z="${k}"]`)?.classList.add("on"), 1800 + k * 220)));
        t.push(setTimeout(() => el.querySelector(".nov-pdf")?.classList.add("on"), 2800));
      },
    },
  ];

  const vista = () => { try { return localStorage.getItem(CHIAVE) === VERSIONE; } catch { return true; } };
  const segna = () => { try { localStorage.setItem(CHIAVE, VERSIONE); } catch { /* navigazione privata: la card torna alla prossima visita */ } };

  function apri() {
    const box = document.createElement("div");
    box.className = "nov"; box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true"); box.setAttribute("aria-labelledby", "nov-titolo");
    box.innerHTML = `<div class="nov__card"><div class="nov__scena"><span class="nov__et"></span><button class="nov__x" type="button" aria-label="${TT("Chiudi", "Close")}">${B.ico("chiudi")}</button><div class="nov__anim"></div></div><div class="nov__corpo"></div><div class="nov__piede"><div class="nov__punti" role="tablist" aria-label="${TT("Novità", "What's new")}">${PASSI.map((p, k) => `<button type="button" role="tab" data-k="${k}" aria-label="${e(p.titolo)}"></button>`).join("")}</div><div class="nov__az"><button class="nov__bt nov__bt--2" type="button" data-nov="indietro">${TT("Indietro", "Back")}</button><button class="nov__bt nov__bt--1" type="button" data-nov="avanti"></button></div></div></div>`;
    document.body.appendChild(box);
    const $ = (s) => box.querySelector(s);
    let i = 0, tempi = [];
    const vai = (k) => {
      tempi.forEach(clearTimeout); tempi = [];
      i = Math.max(0, Math.min(PASSI.length - 1, k));
      const p = PASSI[i];
      $(".nov__et").textContent = `${TT("Novità", "What's new")} · ${i + 1} ${TT("di", "of")} ${PASSI.length}`;
      $(".nov__anim").innerHTML = p.scena();
      $(".nov__corpo").innerHTML = `<div class="nov__passo"><h2 id="nov-titolo">${e(p.titolo)}</h2></div><div class="nov__passo" style="animation-delay:.06s"><p>${e(p.testo)}</p></div>`;
      p.dopo?.($(".nov__anim"), tempi);
      box.querySelectorAll(".nov__punti button").forEach((b, n) => b.setAttribute("aria-current", n === i ? "true" : "false"));
      $('[data-nov="indietro"]').hidden = i === 0;
      $('[data-nov="avanti"]').textContent = i === PASSI.length - 1 ? p.cta[0] : TT("Avanti", "Next");
    };
    const chiudi = () => {
      tempi.forEach(clearTimeout); segna();
      document.removeEventListener("keydown", tasti);
      box.classList.add("via"); setTimeout(() => box.remove(), 240);
    };
    const tasti = (ev) => {
      if (ev.key === "Escape") chiudi();
      else if (ev.key === "ArrowRight") vai(i + 1);
      else if (ev.key === "ArrowLeft") vai(i - 1);
    };
    box.addEventListener("click", (ev) => {
      if (ev.target === box || ev.target.closest(".nov__x")) return chiudi();
      const p = ev.target.closest(".nov__punti button"); if (p) return vai(+p.dataset.k);
      const b = ev.target.closest("[data-nov]"); if (!b) return;
      if (b.dataset.nov === "indietro") return vai(i - 1);
      if (i < PASSI.length - 1) return vai(i + 1);
      const [, dove, domanda] = PASSI[i].cta;
      chiudi();
      if (dove) location.hash = dove; else if (domanda && window.CH) CH.chiedi(domanda);
    });
    document.addEventListener("keydown", tasti);
    vai(0);
    $('[data-nov="avanti"]').focus();
  }

  window.NOVITA = { apri };
  // solo da desktop, solo sulla home, e mai nei controlli automatici
  const home = !location.hash || location.hash === "#/" || location.hash === "#";
  if (matchMedia("(min-width: 761px)").matches && home && !navigator.webdriver && !vista() && !/[?&]novita=0/.test(location.search))
    setTimeout(apri, 900);
})();
