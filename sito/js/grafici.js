/* Grafici nelle risposte della chat (27/11/2026). I numeri vengono dal risultato dello strumento (evento «dati» dell'agente),
   mai dal testo del modello. La forma si sceglie dal compito dei dati: parte di un totale piccolo → un quadratino per voto;
   andamento nel tempo → colonne; confronto fra gruppi o persone → barre orizzontali ordinate; due scelte incrociate → matrice.
   Contrario e astenuto non stanno mai accostati: i loro colori, vicini, si confondono anche con la vista normale. */
(function () {
  const e = B.esc, num = B.num;
  const G = (window.GR = {});
  const pct = (x, d = 0) => `${(x * 100).toLocaleString(window.LANG === "en" ? "en-GB" : "it-IT", { maximumFractionDigits: d, minimumFractionDigits: d })}%`;
  const nomeGruppo = (s) => String(s || "").replace(/\s*\([^()]*(\([^()]*\)[^()]*)*\)\s*$/, "").trim() || String(s || "");
  const senzaGruppo = (s) => /^\(/.test(String(s || ""));
  const CORTI = { FdI: "FdI", PD: "PD", Lega: "Lega", FI: "FI", M5S: "M5S", AVS: "AVS", Azione: "Az", IV: "IV", NM: "NM", "+Europa": "+Eu", FNV: "FNV", MinLing: "Min", SCN: "SCN", PSI: "PSI", Aut: "Aut", Misto: "Misto", Governo: "Gov" };
  const VOTO = () => ({ favor: B.colVoto("favor"), against: B.colVoto("against"), abstain: B.colVoto("abstain") });

  // una figura: titolo che dice il fatto, il grafico, una nota su cosa si conta
  const figura = (titolo, corpo, nota, cls = "") => `<figure class="gr ${cls}"><figcaption class="gr__t">${titolo}</figcaption>${corpo}${nota ? `<p class="gr__nota">${nota}</p>` : ""}</figure>`;

  /* ---------- forme ---------- */

  // un quadratino per unità, un blocco di colonne per parte, una colonna vuota fra le parti
  function quadratini(parti, etichetta) {
    const tot = parti.reduce((s, p) => s + p.n, 0); if (!tot) return "";
    const righe = Math.max(8, Math.min(28, Math.round(Math.sqrt(tot / 2.6)))), L = 10, P = 12.5;
    let col = 0, rect = ""; const blocchi = [];
    for (const p of parti) {
      if (!p.n) continue;
      const da = col;
      for (let i = 0; i < p.n; i++) rect += `<rect x="${(col + Math.floor(i / righe)) * P}" y="${(i % righe) * P}" width="${L}" height="${L}" rx="2" fill="${p.c}"><title>${e(p.nome)}: ${num(p.n)}</title></rect>`;
      col += Math.ceil(p.n / righe); blocchi.push({ ...p, da, a: col }); col += 1;
    }
    const W = (col - 1) * P - (P - L), H = righe * P - (P - L);
    // legenda che va a capo da sola: con blocchi stretti le etichette sotto ogni blocco si sovrapporrebbero
    const lab = blocchi.map((b) => `<span class="gr-q__l"><i style="background:${b.c}"></i><b>${num(b.n)}</b>${e(b.nome)}</span>`).join("");
    return `<div class="gr-q"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${e(etichetta)}">${rect}</svg><div class="gr-q__ls">${lab}</div></div>`;
  }

  // colonne per un andamento: base a zero, etichetta del valore solo su primo, ultimo e massimo
  function colonne(punti, fmt = num, opz = {}) {
    if (punti.length < 2) return "";
    // fino a 16 colonne in HTML: le scritte restano della loro misura anche su un telefono
    if (punti.length <= 16) {
      const max = opz.max ?? (Math.max(...punti.map((p) => p.v), 0) || 1), n = punti.length;
      const imax = punti.reduce((m, p, i) => (p.v > punti[m].v ? i : m), 0);
      return `<div class="gr-c" role="img" aria-label="${e(punti.map((p) => `${p.l} ${fmt(p.v)}`).join(", "))}">${punti.map((p, i) => `<div class="gr-c__k" title="${e(p.l)}: ${e(fmt(p.v))}${p.tip ? ` · ${e(p.tip)}` : ""}"><span class="gr-c__z"><span class="gr-c__v">${i === 0 || i === n - 1 || i === imax || opz.tutte ? e(fmt(p.v)) : ""}</span><span class="gr-c__b" style="height:${Math.max(p.v > 0 ? 1.5 : 0, (p.v / max) * 82)}%"></span></span><span class="gr-c__l">${e(p.l)}${p.sub ? `<small>${e(p.sub)}</small>` : ""}</span></div>`).join("")}</div>`;
    }
    const max = opz.max ?? (Math.max(...punti.map((p) => p.v), 0) || 1), n = punti.length;
    const W = 600, H = punti.some((p) => p.sub) ? 186 : 170, base = 140, alt = 112, passo = W / n, larg = Math.max(2, Math.min(56, passo * 0.62));
    const imax = punti.reduce((m, p, i) => (p.v > punti[m].v ? i : m), 0);
    const ogni = Math.ceil(n / 12);
    let svg = `<line x1="0" x2="${W}" y1="${base}" y2="${base}" class="gr-asse"/>`;
    punti.forEach((p, i) => {
      const h = Math.max(p.v > 0 ? 2 : 0, (p.v / max) * alt), x = i * passo + (passo - larg) / 2;
      svg += `<rect x="${x}" y="${base - h}" width="${larg}" height="${h}" rx="${Math.min(4, larg / 2)}" class="gr-col"><title>${e(p.l)}: ${e(fmt(p.v))}${p.tip ? ` · ${e(p.tip)}` : ""}</title></rect>`;
      if (i === 0 || i === n - 1 || i === imax || (opz.tutte && n <= 8)) svg += `<text x="${x + larg / 2}" y="${base - h - 7}" text-anchor="middle" class="gr-v">${e(fmt(p.v))}</text>`;
      if (i % ogni === 0 || i === n - 1) svg += `<text x="${x + larg / 2}" y="${base + 20}" text-anchor="middle" class="gr-x">${e(p.l)}</text>${p.sub ? `<text x="${x + larg / 2}" y="${base + 36}" text-anchor="middle" class="gr-x gr-x--sub">${e(p.sub)}</text>` : ""}`;
    });
    return `<svg class="gr-colonne" viewBox="0 0 ${W} ${H}" role="img" aria-label="${e(punti.map((p) => `${p.l} ${fmt(p.v)}`).join(", "))}">${svg}</svg>`;
  }

  // barre orizzontali ordinate, il nome a sinistra, il numero a destra
  function barre(voci, fmt = num, opz = {}) {
    if (!voci.length) return "";
    const max = opz.max ?? (Math.max(...voci.map((v) => v.v), 0) || 1), quante = opz.quante || 12;
    const mostra = voci.slice(0, quante), altre = voci.slice(quante);
    return `<div class="gr-b" role="table">${mostra.map((v) => `<div class="gr-b__r" role="row"><span class="gr-b__n" role="cell">${v.c ? `<i style="background:${v.c}"></i>` : ""}<span>${e(v.l)}${v.sub ? `<small>${e(v.sub)}</small>` : ""}</span></span><span class="gr-b__s" role="cell"><span style="width:${Math.max(v.v > 0 ? 0.6 : 0, (v.v / max) * 100)}%"></span></span><span class="gr-b__v" role="cell">${e(fmt(v.v))}</span></div>`).join("")}</div>${altre.length ? `<p class="gr__nota">${TT(`Altre ${altre.length} voci, in tutto`, `${altre.length} more, totalling`)} ${e(fmt(altre.reduce((s, v) => s + v.v, 0)))}.</p>` : ""}`;
  }

  // matrice delle scelte incrociate di due persone: righe = scelta di A, colonne = scelta di B
  function matrice(pairs, na, nb) {
    const k = ["favor", "against", "abstain"], nomi = { favor: TT("sì", "yes"), against: "no", abstain: TT("astenuto", "abstained") };
    const max = Math.max(...Object.values(pairs), 1);
    const cella = (a, b) => { const n = pairs[`${a}/${b}`] || 0, o = n ? 0.1 + 0.9 * Math.sqrt(n / max) : 0;
      return `<td class="${a === b ? "gr-m__d" : ""}${o > 0.55 ? " gr-m__forte" : ""}" style="--o:${o.toFixed(3)}" title="${e(na)} ${nomi[a]}, ${e(nb)} ${nomi[b]}: ${num(n)}"><span>${num(n)}</span></td>`; };
    return `<div class="gr-m-box"><table class="gr-m"><thead><tr><th></th><th colspan="3" class="gr-m__chi">${e(nb)}</th></tr><tr><th class="gr-m__chi">${e(na)}</th>${k.map((b) => `<th>${nomi[b]}</th>`).join("")}</tr></thead><tbody>${k.map((a) => `<tr><th>${nomi[a]}</th>${k.map((b) => cella(a, b)).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  // gruppo × gruppo: quanto spesso hanno preso la stessa posizione
  function intreccio(acc, gruppi) {
    const g = gruppi.filter((x) => acc[x.code]);
    if (g.length < 3) return "";
    return `<div class="gr-m-box"><table class="gr-m gr-m--gruppi"><thead><tr><th></th>${g.map((x) => `<th title="${e(x.nome)}">${e(CORTI[x.sigla] || x.sigla)}</th>`).join("")}</tr></thead><tbody>${g.map((a) => `<tr><th>${B.sig(a.sigla)}</th>${g.map((b) => { if (a === b) return `<td class="gr-m__vuota"></td>`; const v = (acc[a.code] || {})[b.code]; const o = Math.max(0, v - 0.3) / 0.7; return v == null ? `<td></td>` : `<td class="${o > 0.55 ? "gr-m__forte" : ""}" style="--o:${o.toFixed(3)}" title="${e(a.nome)} ${TT("e", "and")} ${e(b.nome)}: ${pct(v)}"><span>${Math.round(v * 100)}</span></td>`; }).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  /* ---------- un grafico per ogni strumento ---------- */

  function persone(r, a) {
    const pairs = r.pairs || {};
    if (!r.votes_both) return null;
    const v = VOTO(), diversi = r.votes_both - (r.same || 0);
    const ids = (a.persons || []).map((u) => (/^it:person:camera:(\d+)$/.exec(u) || [])[1]);
    // il nome con cui il sito conosce la persona (Elly Schlein, non Elena Ethel Schlein)
    const [na, nb] = (r.persons || []).map((x, i) => { const p = ids[i] && B.persona(ids[i]); return p ? p.n : x; });
    const volto = (id, nome) => { const p = id && B.persona(id); return `<span class="gr-volto">${p ? B.fotoHtml(p) : ""}<span><b>${e(nome)}</b>${p ? `<small>${e(B.NOMI[p.sigla] || "")}</small>` : ""}</span></span>`; };
    const testa = `<div class="gr-testa">${volto(ids[0], na)}${volto(ids[1], nb)}<span class="gr-grande"><b>${pct(r.share || 0, 1)}</b><small>${TT("stesso voto", "same vote")}</small></span></div>`;
    let h = figura(TT(`${e(na)} e ${e(nb)} hanno votato allo stesso modo in ${num(r.same)} votazioni su ${num(r.votes_both)}`, `${e(na)} and ${e(nb)} voted the same way in ${num(r.same)} of ${num(r.votes_both)} votes`),
      testa + quadratini([{ n: pairs["favor/favor"] || 0, c: v.favor, nome: TT("entrambi sì", "both yes") }, { n: pairs["against/against"] || 0, c: v.against, nome: TT("entrambi no", "both no") },
        { n: pairs["abstain/abstain"] || 0, c: v.abstain, nome: TT("entrambi astenuti", "both abstained") }, { n: diversi, c: "var(--gr-neutro)", nome: TT("voto diverso", "different vote") }],
        TT(`${num(r.votes_both)} votazioni, un quadratino ciascuna`, `${num(r.votes_both)} votes, one square each`)),
      TT("Un quadratino per votazione palese in cui hanno votato tutti e due. Assenze, missioni e voti segreti esclusi.", "One square per open vote in which both voted. Absences, missions and secret ballots excluded."));
    if (diversi) h += figura(TT("Dove le scelte si dividono", "Where their choices split"), matrice(pairs, na, nb),
      TT(`Sulla diagonale le votazioni in cui hanno scelto lo stesso; fuori, le ${num(diversi)} in cui no.`, `The diagonal holds the votes where they chose alike; the other cells the ${num(diversi)} where they did not.`));
    if ((r.by_year || []).length > 1) h += figura(TT("Anno per anno, quota di voti uguali", "Year by year, share of identical votes"),
      colonne(r.by_year.map((y) => ({ l: String(y.anno), v: y.share, sub: TT(`su ${num(y.votes)}`, `of ${num(y.votes)}`), tip: TT(`${num(y.same)} su ${num(y.votes)}`, `${num(y.same)} of ${num(y.votes)}`) })), (x) => pct(x), { max: 1, tutte: true }),
      TT("Ogni colonna conta le votazioni di quell'anno in cui hanno votato entrambi.", "Each column counts that year's votes in which both voted."));
    return h;
  }

  function maggioranza(r) {
    if (!r.votes) return null;
    const diversi = r.votes - (r.same || 0);
    let h = figura(TT(`${e(nomeGruppo(r.subject))} ha votato come la maggioranza di governo nel ${pct(r.share || 0, 1)} delle votazioni`, `${e(nomeGruppo(r.subject))} voted with the governing majority in ${pct(r.share || 0, 1)} of votes`),
      `<div class="gr-testa"><span class="gr-grande gr-grande--sx"><b>${num(diversi)}</b><small>${TT(`voti diversi su ${num(r.votes)}`, `different votes out of ${num(r.votes)}`)}</small></span></div>`, "");
    if ((r.by_year || []).length > 1) h += figura(TT("Voti diversi dalla maggioranza, anno per anno", "Votes against the majority line, year by year"),
      colonne(r.by_year.map((y) => ({ l: String(y.anno), v: y.votes - y.same, tip: TT(`${pct(y.share, 1)} uguali su ${num(y.votes)}`, `${pct(y.share, 1)} alike of ${num(y.votes)}`) })), num, { tutte: true }),
      TT("Posizione della maggioranza: la scelta più frequente fra i suoi membri che hanno votato.", "Majority position: the most frequent choice among its members who voted."));
    return h;
  }

  function dissensi(r) {
    const ps = (r.people || {}).rows || [];
    if (!ps.length) return null;
    return figura(TT("Chi ha votato più spesso contro il proprio gruppo", "Who voted most often against their group"),
      barre(ps.map((p) => ({ l: p.persona, sub: `${nomeGruppo(p.gruppo)} · ${TT(`su ${num(p.votes)} voti`, `of ${num(p.votes)} votes`)}`, v: p.against_group, c: B.col(B.sigla(nomeGruppo(p.gruppo))) })), num),
      TT("Voti palesi in cui la scelta è diversa da quella più frequente nel gruppo.", "Open votes where the choice differs from the group's most frequent one."));
  }

  function segreti(r) {
    const rs = (r.rows || []).filter((x) => x.majority_voters && x.majority_short_if_for > 0).slice(0, 8);
    if (!rs.length) return null;
    const max = Math.max(...rs.map((x) => Math.max(x.majority_voters, x.favor)));
    const titolo = (x) => { const t = String(x.title || "").replace(/^Votazione\s*/i, "").trim(); return t ? t.charAt(0).toUpperCase() + t.slice(1) : TT(`Votazione n. ${x.number}`, `Vote no. ${x.number}`); };
    const righe = rs.map((x) => `<div class="gr-s__r"><span class="gr-s__t"><b>${e(B.taglia(titolo(x), 60))}</b><small>${B.data(x.date)} · ${num(x.favor)} ${TT("sì", "yes")}, ${num(x.against)} no${x.decisive ? ` · <em>${TT("potevano cambiare l'esito", "could have changed the outcome")}</em>` : ""}</small></span><span class="gr-s__barra" title="${TT(`${num(x.majority_voters)} votanti di maggioranza, ${num(x.favor)} sì`, `${num(x.majority_voters)} majority voters, ${num(x.favor)} yes`)}"><span class="gr-s__magg" style="width:${(x.majority_voters / max) * 100}%"></span><span class="gr-s__si" style="width:${(Math.min(x.favor, x.majority_voters) / max) * 100}%"></span></span><span class="gr-s__n"><b>−${num(x.majority_short_if_for)}</b><small>${TT("sì", "yes")}</small></span></div>`).join("");
    return figura(TT("Voti segreti: quanti sì sono mancati, al minimo, alla maggioranza", "Secret ballots: the minimum number of yes votes the majority lost"),
      `<div class="gr-s"><div class="gr-leg"><span><i class="gr-s__si"></i>${TT("sì arrivati", "yes votes cast")}</span><span><i class="gr-s__magg"></i>${TT("votanti di maggioranza", "majority members voting")}</span></div>${righe}</div>`,
      TT("Nel voto segreto non si sa chi ha votato come: la differenza è un minimo certo, se la maggioranza era per il sì. Nessun nome.", "In a secret ballot nobody knows who voted how: the gap is a certain minimum, if the majority backed yes. No names."));
  }

  function votoGruppi(r) {
    const gs = (r.groups || []).filter((g) => g.votes_with_voters);
    if (gs.length < 2) return null;
    // la compattezza media sta quasi sempre sopra il 99% e le barre sembrerebbero uguali: la quota di voti unanimi distingue i gruppi
    const ord = [...gs].sort((a, b) => b.unanimous_share - a.unanimous_share || b.cohesion - a.cohesion);
    let h = figura(TT("In quante votazioni ogni gruppo ha votato unito", "In how many votes each group voted as one"),
      barre(ord.map((g) => ({ l: nomeGruppo(g.group), v: g.unanimous_share, c: B.col(B.sigla(nomeGruppo(g.group))), sub: TT(`${num(Math.round(g.unanimous_share * g.votes_with_voters))} su ${num(g.votes_with_voters)} voti`, `${num(Math.round(g.unanimous_share * g.votes_with_voters))} of ${num(g.votes_with_voters)} votes`) })), (x) => pct(x), { max: 1, quante: 16 }),
      TT("Unito: tutti i membri del gruppo che hanno votato hanno fatto la stessa scelta.", "As one: every member of the group who voted made the same choice."));
    if (r.agreement) {
      const gruppi = gs.map((g) => { const nome = nomeGruppo(g.group), code = (/\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$/.exec(g.group) || [])[1]; return { code, nome, sigla: B.sigla(nome) }; })
        .filter((x) => x.code).sort((a, b) => B.ORDINE.indexOf(a.sigla) - B.ORDINE.indexOf(b.sigla));
      const m = intreccio(r.agreement, gruppi);
      if (m) h += figura(TT("Quanto spesso due gruppi hanno preso la stessa posizione", "How often two groups took the same position"), m, TT("Percentuale delle votazioni in cui la posizione dei due gruppi coincide.", "Share of votes in which the two groups' positions match."));
    }
    return h;
  }

  function presenzeGruppi(r) {
    const rs = (r.rows || []).filter((x) => x.gruppo && !senzaGruppo(x.gruppo) && x.expected);
    if (rs.length < 2 || rs[0].voted_share == null) return null;
    return figura(TT("Presenza al voto per gruppo", "Voting attendance by group"),
      barre([...rs].sort((a, b) => b.voted_share - a.voted_share).map((x) => ({ l: nomeGruppo(x.gruppo), v: x.voted_share / 100, c: B.col(B.sigla(nomeGruppo(x.gruppo))), sub: TT(`${num(x.persons)} membri · in missione ${pct(x.mission_share / 100)}`, `${num(x.persons)} members · on mission ${pct(x.mission_share / 100)}`) })), (x) => pct(x, 1), { max: 1, quante: 18 }),
      TT("Voti espressi sul totale dei voti attesi dai membri del gruppo in quel periodo.", "Votes cast over the votes expected from the group's members in the period."));
  }

  function presenzePersone(r) {
    const rs = (r.rows || []).filter((x) => x.persona && x.ballots);
    if (!rs.length) return null;
    if (rs.length === 1) {
      const x = rs[0], v = VOTO();
      return figura(TT(`${e(x.persona)} ha votato in ${num(x.voted)} votazioni su ${num(x.ballots)}`, `${e(x.persona)} voted in ${num(x.voted)} of ${num(x.ballots)} votes`),
        barre([{ l: TT("a favore", "in favour"), v: x.favor, c: v.favor }, { l: TT("assente", "absent"), v: x.absent, c: "var(--gr-neutro)" }, { l: TT("contro", "against"), v: x.against, c: v.against },
          { l: TT("in missione", "on mission"), v: x.mission, c: "var(--gr-neutro)" }, { l: TT("astenuto", "abstained"), v: x.abstain, c: v.abstain }, { l: TT("presidente di turno", "chairing"), v: x.chair || 0, c: "var(--gr-neutro)" }].filter((y) => y.v), num, { max: x.ballots }), "");
    }
    return figura(TT("Presenza al voto", "Voting attendance"),
      barre([...rs].sort((a, b) => b.voted / b.ballots - a.voted / a.ballots).map((x) => ({ l: x.persona, v: x.voted / x.ballots, sub: TT(`${num(x.voted)} su ${num(x.ballots)}`, `${num(x.voted)} of ${num(x.ballots)}`) })), (x) => pct(x, 1), { max: 1 }), "");
  }

  function composizione(r) {
    const gs = (r.groups || []).filter((g) => g.members);
    if (gs.length < 2) return null;
    const voci = [];
    gs.forEach((g) => { const comp = (g.components || []).filter((c) => c.members);
      if (comp.length) comp.forEach((c) => { const n = c.name || (c.group || {}).name || ""; voci.push({ l: `Misto · ${nomeGruppo(n)}`, v: c.members, c: B.col(B.sigla(n)) }); });
      else voci.push({ l: nomeGruppo(g.group.name), v: g.members, c: B.col(B.sigla(g.group.name)) }); });
    return figura(TT(`${num(r.members)} seggi, gruppo per gruppo`, `${num(r.members)} seats, group by group`), barre(voci.sort((a, b) => b.v - a.v), num, { quante: 20 }),
      TT("Il Misto è diviso per componente.", "The Mixed Group is split by component."));
  }

  function decreti(r) {
    const anni = Object.entries(r.by_year || {});
    if (anni.length < 2) return null;
    return figura(TT(`${num(r.total)} decreti-legge, ${num(r.converted)} convertiti in legge`, `${num(r.total)} decree-laws, ${num(r.converted)} converted into law`),
      colonne(anni.map(([a, n]) => ({ l: a, v: n })), num, { tutte: true }), TT("Decreti-legge per anno di emanazione.", "Decree-laws by year issued."));
  }

  function sedute(r) {
    const rs = (r.rows || []).filter((x) => x.mese || x.anno);
    if (rs.length < 3 || new Set(rs.map((x) => x.ramo)).size > 1) return null;
    return figura(TT("Sedute, mese per mese", "Sittings, month by month"), colonne(rs.map((x) => ({ l: etichettaTempo(x.mese || x.anno), v: x.sedute, tip: x.ore_da_video ? TT(`${x.ore_da_video} ore di video`, `${x.ore_da_video} hours of video`) : "" })), num), "");
  }

  function profilo(r) {
    let h = "";
    const liv = Object.entries(r.education_level || {}).filter(([, n]) => n);
    if (liv.length > 1) h += figura(TT("Titolo di studio", "Education"), barre(liv.map(([l, n]) => ({ l, v: n })).sort((a, b) => b.v - a.v), num, { max: r.members }), "");
    if ((r.profession || []).length > 2) h += figura(TT("Professioni più frequenti", "Most common professions"), barre(r.profession.map((x) => ({ l: x.value, v: x.members })), num, { quante: 10 }), TT("Come la dichiara ognuno nella scheda ufficiale.", "As each member states it in the official profile."));
    return h || null;
  }

  function atto(r) {
    const by = ((r.amendments || {}).by_outcome) || {};
    const voci = Object.entries(by).filter(([, n]) => n).map(([l, n]) => ({ l, v: n })).sort((a, b) => b.v - a.v);
    if (voci.length < 2) return null;
    return figura(TT(`${num(r.amendments.total)} emendamenti, per esito`, `${num(r.amendments.total)} amendments, by outcome`), barre(voci, num), "");
  }

  // i conteggi generici: la forma dipende dalla dimensione che resta dopo il ramo
  const MISURE = ["votazioni", "interventi", "atti", "leggi", "proposte", "reazioni", "parole", "occorrenze"];
  const NOMI_DIM = () => ({ gruppo: TT("gruppo", "group"), gruppo_primo_firmatario: TT("gruppo del primo firmatario", "first signatory's group"), gruppo_che_reagisce: TT("gruppo che reagisce", "reacting group"), gruppo_oratore: TT("gruppo di chi parla", "speaker's group"), persona: TT("persona", "person"), esito: TT("esito", "outcome"), tipo: TT("tipo", "type"), sede: TT("sede", "venue"), organo: TT("organo", "body"), tema: TT("tema", "topic"), ruolo: TT("ruolo", "role"), iniziativa: TT("iniziativa", "initiative") });
  const NOMI_MIS = () => ({ votazioni: TT("Votazioni", "Votes"), interventi: TT("Interventi", "Speeches"), atti: TT("Atti", "Bills"), leggi: TT("Leggi", "Laws"), proposte: TT("Emendamenti", "Amendments"), reazioni: TT("Reazioni in Aula", "Reactions in the chamber"), parole: TT("Parole", "Words"), occorrenze: TT("Occorrenze", "Occurrences") });
  function etichettaTempo(x) { const s = String(x), m = /^(\d{4})-(\d{2})$/.exec(s); if (!m) return s; const mesi = window.LANG === "en" ? ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] : ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]; return `${mesi[+m[2] - 1]} ${m[1].slice(2)}`; }
  function conteggio(r) {
    const rs = r.rows || [];
    if (rs.length < 2) return null;
    const chiavi = Object.keys(rs[0]).filter((k) => !["dal", "al"].includes(k));
    const mis = MISURE.find((m) => chiavi.includes(m) && typeof rs[0][m] === "number");
    if (!mis) return null;
    let dims = chiavi.filter((k) => k !== mis && !MISURE.includes(k) && !/_uri$/.test(k));
    if (dims.includes("ramo") && new Set(rs.map((x) => x.ramo)).size === 1) dims = dims.filter((k) => k !== "ramo");
    if (dims.length !== 1) return null;   // due dimensioni insieme: un grafico affollato dice meno del testo
    const d = dims[0], tit = NOMI_MIS()[mis], nota = r.more ? TT("Solo la prima pagina dei risultati.", "First page of results only.") : "";
    if (d === "anno" || d === "mese") {
      const pts = [...rs].sort((a, b) => String(a[d]).localeCompare(String(b[d]))).map((x) => ({ l: etichettaTempo(x[d]), v: x[mis] }));
      return figura(`${tit}, ${d === "anno" ? TT("anno per anno", "year by year") : TT("mese per mese", "month by month")}`, colonne(pts, num, { tutte: pts.length <= 8 }), nota);
    }
    if (rs.length > 40) return null;
    const gruppi = /^gruppo/.test(d);
    const voci = rs.filter((x) => x[d] != null).map((x) => ({ l: gruppi ? nomeGruppo(x[d]) : String(x[d]), v: x[mis], c: gruppi ? (senzaGruppo(x[d]) ? "var(--gr-neutro)" : B.col(B.sigla(nomeGruppo(x[d])))) : null })).sort((a, b) => b.v - a.v);
    return figura(`${tit} ${TT("per", "by")} ${NOMI_DIM()[d] || d}`, barre(voci, num, { quante: 15 }), nota);
  }

  /* ---------- scelta ---------- */
  G.da = (nome, args, r) => {
    if (!r || typeof r !== "object" || r.errore) return null;
    args = args || {};
    try {
      if (nome === "confronta_voti") return ({ persone, maggioranza, dissensi, segreti }[args.mode] || (() => null))(r, args);
      if (nome === "voto_gruppi") return votoGruppi(r);
      if (nome === "presenze") return args.by_group ? presenzeGruppi(r) : presenzePersone(r);
      if (nome === "composizione") return composizione(r);
      if (nome === "conta_decreti") return decreti(r);
      if (nome === "conta_sedute") return sedute(r);
      if (nome === "profilo_parlamentari") return profilo(r);
      if (nome === "atto") return atto(r);
      if (/^conta_/.test(nome)) return conteggio(r);
    } catch (err) { /* un grafico che non si disegna non ferma la risposta */ }
    return null;
  };
  G._prova = { quadratini, colonne, barre, matrice };
})();
