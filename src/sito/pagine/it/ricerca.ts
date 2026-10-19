import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Ricerca · ParliamentRAG",
  descrizione: "Gli articoli di ParliamentRAG a ISWC 2026, il codice con DOI, gli interventi pubblici e il finanziamento del progetto.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina">
      <p class="etichetta compare">Ricerca · Università di Milano-Bicocca</p>
      <h1 class="titolo-1 compare" style="--ritardo:80ms">Il metodo è scritto, revisionato e <em>citabile</em>.</h1>
      <p class="attacco compare" style="--ritardo:160ms">ParliamentRAG è descritto in due articoli accettati a ISWC 2026, a Bari dal 25 al 29 ottobre.</p>

    </div>
  </section>

  <!-- Articoli -->
  <section class="sezione-stretta" id="articoli" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Articoli</p></div>

      <article class="lavoro compare" aria-labelledby="a1-t">
        <div class="lavoro__dove">
          <span class="sigla sigla--accento">ISWC 2026</span>
          <span class="etichetta">In-Use Track</span>
          <span class="mono">LNCS 17128, cap. 24</span>
          <span class="mono">Springer</span>
        </div>
        <div>
          <h2 class="lavoro__t" id="a1-t">Who Speaks Matters: Authority-Aware Multi-View RAG over Italian Parliamentary Proceedings</h2>
          <p class="lavoro__chi">Mirko Tritella, Riccardo Pozzi, Matteo Palmonari</p>
          <p class="lavoro__cosa">L'articolo che descrive il metodo: come scegliere le voci autorevoli di ogni gruppo e come costruire una risposta che li comprenda tutti.</p>
          <div class="fila lavoro__azioni">
            <a class="btn btn--accento btn--piccolo" href="https://emeierkeio.github.io/papers/who-speaks-matters-iswc2026.pdf" rel="noopener">PDF</a>
            <a class="btn btn--linea btn--piccolo" href="https://arxiv.org/abs/2608.13410" rel="noopener">arXiv</a>
            <a class="btn btn--linea btn--piccolo" href="https://doi.org/10.5281/zenodo.23173703" rel="noopener">Codice</a>
            <a class="btn btn--linea btn--piccolo" href="https://orkg.org/papers/R1909763" rel="noopener">ORKG</a>
            <button class="btn btn--linea btn--piccolo" type="button" aria-expanded="false" aria-controls="cita-1" data-cita>Cita</button>
          </div>
          <p class="nota">DOI 10.1007/978-3-032-42029-9_24, attivo all'uscita del volume.</p>
          <div class="citazione-bib" id="cita-1" hidden>
            <div class="blocco-codice">
              <pre class="codice" id="bib-1">@inproceedings{tritella2026whospeaksmatters,
  author    = {Tritella, Mirko and Pozzi, Riccardo and Palmonari, Matteo},
  title     = {Who Speaks Matters: Authority-Aware Multi-View RAG over Italian Parliamentary Proceedings},
  booktitle = {Proceedings of the 25th International Semantic Web Conference (ISWC 2026), In-Use Track},
  series    = {Lecture Notes in Computer Science},
  volume    = {17128},
  publisher = {Springer},
  year      = {2026},
  doi       = {10.1007/978-3-032-42029-9_24}
}</pre>
              <button class="copia" type="button" data-copia="bib-1">Copia</button>
            </div>
            <p class="nota">BibTeX. Se scrivi del progetto, cita questo articolo.</p>
          </div>
        </div>
      </article>

      <article class="lavoro compare" aria-labelledby="a2-t">
        <div class="lavoro__dove">
          <span class="sigla sigla--accento">ISWC 2026</span>
          <span class="etichetta">Posters &amp; Demos</span>
        </div>
        <div>
          <h2 class="lavoro__t" id="a2-t">ParliamentRAG: An Authority-Aware Multi-View RAG System for Italian Parliamentary Proceedings</h2>
          <p class="lavoro__chi">Mirko Tritella, Riccardo Pozzi, Matteo Palmonari</p>
          <p class="lavoro__cosa">Il sistema in funzione: la demo presentata alla conferenza. A Bari la mostriamo dal vivo su Fascicoli, con i dati di Camera e Senato.</p>
          <div class="fila lavoro__azioni">
            <a class="btn btn--accento btn--piccolo" href="https://emeierkeio.github.io/papers/parliamentrag-demo-iswc2026.pdf" rel="noopener">PDF</a>
            <a class="btn btn--linea btn--piccolo" href="https://truthful-amazement-production.up.railway.app" rel="noopener">Demo <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            <a class="btn btn--linea btn--piccolo" href="https://www.fascicoli.it" rel="noopener">Fascicoli <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
          </div>
        </div>
      </article>
    </div>
  </section>


  <!-- Conferenza e interventi -->
  <section class="sezione-stretta" id="interventi">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Conferenza e interventi</p></div>
      <div class="eventi">
        <article class="foglio foglio--pad evento compare">
          <span class="etichetta">Conferenza</span>
          <p class="evento__quando">25–29 ottobre 2026</p>
          <p class="evento__dove"><strong>ISWC 2026, Bari</strong>25th International Semantic Web Conference. Presentiamo l'articolo In-Use e la demo.</p>
          <p class="evento__vai"><a class="collegamento" href="https://iswc2026.semanticweb.org/#/program/acceptedpapers" rel="noopener">Articoli accettati nel programma</a></p>
        </article>
        <article class="foglio foglio--pad evento compare" style="--ritardo:100ms">
          <span class="etichetta">Intervento</span>
          <p class="evento__quando">1 ottobre 2026</p>
          <p class="evento__dove"><strong>Milano Digital Week 2026</strong>«ParliamentRAG», all'Università di Milano-Bicocca.</p>
          <p class="evento__vai"><a class="collegamento" href="https://www.milanodigitalweek.com/event/parliamentrag-navigare-gli-atti-parlamentari-con-lia-affidabile" rel="noopener">Pagina dell'evento</a></p>
        </article>
      </div>
      <p class="nota compare" style="margin-top:var(--s-5)">Per invitarci a parlare del progetto scrivi a <a class="collegamento" href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a>.</p>
    </div>
  </section>

  <!-- Persone e sostegno -->
  <section class="sezione-stretta" id="persone">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Persone e sostegno</p></div>
      <div class="chi">
        <div class="compare">
          <h3>Autori</h3>
          <ul class="persone">
            <li>
              <span>Mirko Tritella</span>
              <span class="fila">
                <a class="collegamento" href="https://emeierkeio.github.io" rel="noopener">Sito</a>
                <a class="collegamento" href="https://orcid.org/0009-0000-8611-8189" rel="noopener">ORCID</a>
                <a class="collegamento" href="https://github.com/Emeierkeio" rel="noopener">GitHub</a>
              </span>
            </li>
            <li>
              <span>Riccardo Pozzi</span>
              <span class="fila">
                <a class="collegamento" href="https://www.riccardopozzi.com/" rel="noopener">Sito</a>
                <a class="collegamento" href="https://orcid.org/0000-0002-4954-3837" rel="noopener">ORCID</a>
                <a class="collegamento" href="https://github.com/rpo19" rel="noopener">GitHub</a>
              </span>
            </li>
            <li>
              <span>Matteo Palmonari</span>
              <span class="fila">
                <a class="collegamento" href="https://www.unimib.it/matteo-luigi-palmonari" rel="noopener">Sito</a>
                <a class="collegamento" href="https://orcid.org/0000-0002-1801-5118" rel="noopener">ORCID</a>
              </span>
            </li>
          </ul>
          <p class="nota" style="margin-top:var(--s-3)">Università di Milano-Bicocca.</p>
        </div>
        <div class="compare" style="--ritardo:100ms">
          <h3>Finanziamento</h3>
          <p class="tenue" style="max-width:44ch">Il progetto ha il sostegno del programma EU Horizon Europe, grant 101189771 (DataPACT).</p>
          <p style="margin-top:var(--s-4)"><a class="riproduci__doi" style="margin-top:0" href="https://doi.org/10.3030/101189771" rel="noopener">doi.org/10.3030/101189771</a></p>
        </div>
      </div>
    </div>
  </section>
`,
};

export default contenuto;
