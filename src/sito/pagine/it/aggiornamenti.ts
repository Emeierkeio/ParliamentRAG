import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Aggiornamenti · ParliamentRAG",
  descrizione: "Cosa cambia in ParliamentRAG: articoli, sistemi, interventi pubblici. Con l'iscrizione agli aggiornamenti via email.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Aggiornamenti</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">Cosa cambia nel progetto.</h1>
        <p class="attacco compare" style="--ritardo:160ms">Articoli, sistemi nuovi, interventi pubblici. In ordine, dal più recente.</p>
      </div>
      <div class="compare" style="--ritardo:220ms">
        <div class="schede" role="group" aria-label="Filtra per tipo" id="filtro">
          <button type="button" aria-pressed="true" aria-selected="true" data-tipo="">Tutti</button>
          <button type="button" aria-pressed="false" aria-selected="false" data-tipo="pubblicazioni">Pubblicazioni</button>
          <button type="button" aria-pressed="false" aria-selected="false" data-tipo="sistemi">Sistemi</button>
          <button type="button" aria-pressed="false" aria-selected="false" data-tipo="interventi">Interventi</button>
        </div>
      </div>
    </div>
  </section>

  <!-- Cronaca -->
  <section class="sezione-stretta" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em" id="conteggio" aria-live="polite">Ottobre 2026</p></div>

      <ol class="cronaca" id="cronaca">
        <li class="notizia compare" data-tipo="pubblicazioni">
          <div class="notizia__quando">
            <time datetime="2026-10-25">25–29 ott. 2026</time>
            <span class="sigla">Pubblicazioni</span>
          </div>
          <div class="notizia__corpo">
            <h2>Due articoli accettati a ISWC 2026</h2>
            <p>L'articolo dell'In-Use Track e la demo di ParliamentRAG sono stati accettati alla International Semantic Web Conference. Li presentiamo a Bari, dal 25 al 29 ottobre.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="/ricerca">Leggi gli articoli e come citarli</a>
              <a class="collegamento" href="https://iswc2026.semanticweb.org/#/program/acceptedpapers" rel="noopener">Programma della conferenza <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            </div>
          </div>
        </li>

        <li class="notizia compare" data-tipo="sistemi">
          <div class="notizia__quando">
            <time datetime="2026-10-03">3 ott. 2026</time>
            <span class="sigla">Sistemi</span>
          </div>
          <div class="notizia__corpo">
            <h2>Fascicoli è online</h2>
            <p>I fascicoli su un tema ora sono un sistema a sé, su fascicoli.it. Per ogni tema trovi la posizione di ogni gruppo, le voci autorevoli e le citazioni esatte.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="https://www.fascicoli.it">Apri Fascicoli</a>
            </div>
          </div>
        </li>

        <li class="notizia compare" data-tipo="interventi">
          <div class="notizia__quando">
            <time datetime="2026-10-01">1 ott. 2026</time>
            <span class="sigla">Interventi</span>
          </div>
          <div class="notizia__corpo">
            <h2>ParliamentRAG alla Milano Digital Week</h2>
            <p>Abbiamo presentato il progetto alla Milano Digital Week 2026, all'Università di Milano-Bicocca.</p>
            <div class="fila notizia__link">
              <a class="collegamento" href="https://www.milanodigitalweek.com/event/parliamentrag-navigare-gli-atti-parlamentari-con-lia-affidabile" rel="noopener">Pagina dell'evento <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            </div>
          </div>
        </li>
      </ol>
      <p class="cronaca__vuota" id="vuota" hidden>Nessun aggiornamento di questo tipo, per ora.</p>
    </div>
  </section>

  <!-- Iscrizione -->
  <section class="sezione-stretta" id="iscriviti" style="background:var(--carta-2);border-top:1px solid var(--filetto)">
    <div class="pagina iscriviti">
      <div class="compare">
        <h2 class="titolo-2">Ricevi gli aggiornamenti per email.</h2>
        <p class="tenue" style="margin-top:var(--s-3);max-width:44ch">Poche email, quando c'è qualcosa da dire. Ti disiscrivi con un clic.</p>
        <ul class="iscriviti__regole">
          <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Confermi l'iscrizione da un'email che ti mandiamo.</li>
          <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>L'indirizzo resta su Brevo. Non lo colleghiamo alle domande che fai.</li>
        </ul>
      </div>
      <form class="compare" id="iscrizione" novalidate style="--ritardo:120ms">
        <label class="sr" for="email">La tua email</label>
        <div class="campo">
          <input id="email" name="email" type="email" autocomplete="email" placeholder="nome@esempio.it" required>
          <button class="btn btn--accento" type="submit">Iscriviti</button>
        </div>
        <label class="spunta"><input type="checkbox" id="consenso"> <span>Ho letto l'<a class="collegamento" href="/privacy#newsletter">informativa privacy</a> e accetto di ricevere aggiornamenti su ParliamentRAG.</span></label>
        <p class="messaggio" id="iscrizione-msg" role="status"></p>
      </form>
    </div>
  </section>
`,
};

export default contenuto;
