import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "ParliamentRAG",
  descrizione: "Progetto di ricerca per l'AI sui dibattiti delle istituzioni italiane: tre garanzie per ogni risposta sul Parlamento, dati aperti e un metodo per verificarle.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Progetto di ricerca · Università di Milano-Bicocca</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms;font-size:clamp(2.5rem,1.3rem + 3.9vw,5rem);line-height:.98;letter-spacing:-.03em">Quando si parla del Parlamento servono <em>garanzie</em>.</h1>
        <p class="attacco compare" style="--ritardo:160ms">Un dibattito in Aula si racconta in modo corretto solo se c'è la voce di tutti i partiti, se parla chi conosce il tema e se le parole tra virgolette sono state dette davvero. ParliamentRAG accerta queste tre garanzie nelle risposte dell'AI sulle istituzioni, e le applica in strumenti gratuiti per chiunque.</p>
        <div class="fila apertura__azioni compare" style="--ritardo:240ms">
          <a class="btn btn--accento" href="https://www.stenografo.it">Fai una domanda <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
          <a class="btn btn--linea" href="#garanzie">Le tre garanzie</a>
        </div>
      </div>

      <figure class="foglio galleggia campione compare" style="--ritardo:200ms" aria-label="Esempio di risposta controllata">
        <div class="campione__testa">
          <span class="etichetta">Esempio · citazioni reali</span>
          <span class="etichetta" id="campione-stato">Controllo in corso</span>
        </div>
        <div class="campione__corpo">
          <p class="campione__domanda">Cosa dicono i partiti sul salario minimo?</p>
          <p class="campione__risposta">Le opposizioni chiedono una soglia fissata per legge; la maggioranza punta sulla contrattazione collettiva. Il 5 dicembre 2023 l'Aula ha respinto l'emendamento Conte con 149 voti contrari e 111 favorevoli.</p>
          <div class="campione__gruppi" id="campione-gruppi" aria-label="Gruppi considerati">{{sigle}}</div>
          <div class="campione__voci" id="campione-voci" aria-live="polite">{{voci}}</div>
        </div>
        <div class="campione__piede">
          <div class="sigillo" id="campione-sigillo">
            <span class="sigillo__da">Verifica</span>
            <span class="sigillo__voce"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>Tutti i partiti</span>
            <span class="sigillo__voce"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>Voci autorevoli</span>
            <span class="sigillo__voce"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.6"/><path d="M5.2 8.2l1.9 1.9 3.8-4"/></svg>Citazioni esatte</span>
          </div>
        </div>
      </figure>
    </div>
  </section>

  <!-- Il problema -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Il problema</p></div>
      <div class="problema">
        <h2 class="titolo-2 compare">Sempre più persone chiedono all'AI cosa succede in Parlamento.</h2>
        <div class="problema__testo compare" style="--ritardo:120ms">
          <p>Un assistente può lasciare fuori un gruppo, far parlare chi del tema non si occupa, mettere in bocca a un parlamentare parole mai dette. <strong>Chi legge non ha modo di accorgersene.</strong></p>
          <p>I dati per controllare esistono: Camera e Senato pubblicano resoconti, atti e voti. Mancano un metodo che dica cosa controllare e uno strumento che lo faccia. ParliamentRAG lavora su entrambi.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Le tre garanzie -->
  <section class="sezione-stretta" id="garanzie">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Tre garanzie per ogni risposta</p></div>

      <article class="garanzia">
        <div class="compare">
          <p class="garanzia__n">01</p>
          <h3 class="titolo-2">Tutti i gruppi</h3>
          <p class="garanzia__testo">Nessun gruppo resta fuori in silenzio. Se un gruppo non ha parlato del tema, la risposta lo dice.</p>
          <p class="garanzia__come"><span class="etichetta">Prova</span>Scegli un gruppo: si accendono i suoi seggi nell'Aula di oggi e compare quello che ha detto sul salario minimo, con il link al resoconto.</p>
        </div>
        <div class="aula-demo compare" style="--ritardo:120ms">
          <svg class="emiciclo" id="aula" data-scelto="PD" viewBox="0 0 2560 1760" role="img" aria-label="Seggi dell'Aula di Montecitorio, XIX legislatura">{{seggi}}</svg>
          <div class="gruppi-lista" id="gruppi" role="group" aria-label="Gruppi parlamentari">{{gruppi}}</div>
          <div class="gruppo-voce" id="gruppo-voce" aria-live="polite">{{voce}}</div>
        </div>
      </article>

      <article class="garanzia">
        <div class="compare">
          <p class="garanzia__n">02</p>
          <h3 class="titolo-2">Voci autorevoli</h3>
          <p class="garanzia__testo">Per ogni gruppo parla chi del tema si occupa davvero. Lo misuriamo con sei criteri e pesi pubblici, ricalcolati per ogni domanda.</p>
          <p class="garanzia__come"><span class="etichetta">Perché i pesi sono pubblici</span>Sono una scelta editoriale, non una misura neutrale. Li pubblichiamo perché chiunque possa contestarli.</p>
        </div>
        <div class="pesi compare" style="--ritardo:120ms" aria-label="Pesi dei sei criteri di autorevolezza">
          <div class="peso"><span class="peso__nome">Interventi in Aula<small>quanto, e quanto di recente, ha parlato del tema</small></span><span class="peso__barra"><i style="--w:100%;--ritardo:0ms"></i></span><span class="peso__v">0,25</span></div>
          <div class="peso"><span class="peso__nome">Commissione<small>vicinanza della sua commissione al tema</small></span><span class="peso__barra"><i style="--w:100%;--ritardo:80ms"></i></span><span class="peso__v">0,25</span></div>
          <div class="peso"><span class="peso__nome">Atti firmati<small>proposte e atti sul tema, pesati per recenza</small></span><span class="peso__barra"><i style="--w:80%;--ritardo:160ms"></i></span><span class="peso__v">0,20</span></div>
          <div class="peso"><span class="peso__nome">Professione<small>affinità tra il suo lavoro e il tema</small></span><span class="peso__barra"><i style="--w:60%;--ritardo:240ms"></i></span><span class="peso__v">0,15</span></div>
          <div class="peso"><span class="peso__nome">Formazione<small>affinità tra i titoli di studio e il tema</small></span><span class="peso__barra"><i style="--w:40%;--ritardo:320ms"></i></span><span class="peso__v">0,10</span></div>
          <div class="peso"><span class="peso__nome">Ruolo<small>incarichi istituzionali in corso</small></span><span class="peso__barra"><i style="--w:20%;--ritardo:400ms"></i></span><span class="peso__v">0,05</span></div>
        </div>
      </article>

      <article class="garanzia">
        <div class="compare">
          <p class="garanzia__n">03</p>
          <h3 class="titolo-2">Citazioni esatte</h3>
          <p class="garanzia__testo">Quello che sta tra virgolette è stato detto in Aula, dalla persona a cui lo attribuiamo. Confrontiamo ogni citazione con il resoconto parola per parola: se non coincide, la togliamo.</p>
          <p class="garanzia__come"><span class="etichetta">Prova</span>Cambia anche una sola parola della citazione qui accanto e guarda cosa succede.</p>
        </div>
        <div class="confronto compare" style="--ritardo:120ms">
          <p class="etichetta">Citazione proposta dal modello</p>
          <div class="campo campo--area">
            <textarea id="confronto-input" rows="3" spellcheck="false" aria-label="Citazione da confrontare">Siamo contrari all'idea di un salario minimo legale, fissato per legge, che rischia di diventare un tetto e non certo un pavimento per le retribuzioni.</textarea>
          </div>
          <p class="etichetta" style="margin-top:var(--s-3)">Confronto con il resoconto · Marcello Coppo, FdI, 14 luglio 2025</p>
          <p class="confronto__parole" id="confronto-parole" aria-live="polite">{{parole}}</p>
          <div class="esito" id="confronto-esito" role="status" data-esito="ok">{{esito}}</div>
          <div class="fila">
            <button class="btn btn--linea btn--piccolo" type="button" id="confronto-ripristina">Ripristina</button>
            <a class="collegamento piccolo" href="https://www.camera.it/leg19/410?idSeduta=0510&tipo=stenografico#sed0510.stenografico.tit00040.sub00010.int00080" rel="noopener">Apri il resoconto della seduta 510</a>
          </div>
        </div>
      </article>
    </div>
  </section>

  <!-- Sistemi -->
  <section class="sezione-stretta" id="sistemi">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Dove le applichiamo</p></div>
      <h2 class="titolo-1 compare" style="margin-top:var(--s-6);max-width:16ch">Tre sistemi gratuiti, un solo grafo.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4)">Ognuno fa una cosa sola e porta il sigillo delle tre garanzie. Si usano senza account.</p>

      <div class="sistemi">
        <a class="foglio sistema compare" href="https://www.stenografo.it">
          <span class="sistema__marchio"><svg viewBox="6 8.5 50.5 48" aria-hidden="true" focusable="false"><path d="M10 42C12 23 29 16 33.5 27C37 36 24 42 27.5 49.5C31 56.5 46 52 48.5 28" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="50" cy="15" r="6.6" fill="#167A68"/></svg></span>
          <span class="sistema__nome">Stenografo</span>
          <span class="sistema__cosa">Fai una domanda su una seduta, un atto o un voto. Ricevi una risposta breve, con il resoconto ufficiale accanto a ogni frase.</span>
          <span class="sistema__per">Per chi cerca un fatto preciso: giornalisti, uffici studi, cittadini.</span>
          <span class="sistema__vai">Fai una domanda <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></span>
        </a>
        <a class="foglio sistema compare" style="--ritardo:100ms" href="https://www.fascicoli.it">
          <span class="sistema__marchio"><svg viewBox="-5.8 5.5 57.8 55" aria-hidden="true" focusable="false"><g transform="rotate(-30 28 32)"><path d="M14 14V44a14 14 0 0 0 28 0V18a7 7 0 0 0-14 0V40" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="14" cy="2" r="6.6" fill="#167A68"/></g></svg></span>
          <span class="sistema__nome">Fascicoli</span>
          <span class="sistema__cosa">Scegli un tema. Ricevi la posizione di ogni gruppo, le voci più autorevoli di ciascuno, le citazioni esatte e i voti collegati.</span>
          <span class="sistema__per">Per chi deve capire un dibattito intero: ricercatori, analisti, redazioni.</span>
          <span class="sistema__vai">Apri un fascicolo <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></span>
        </a>
        <a class="foglio sistema compare" style="--ritardo:200ms" href="https://www.scranno.it">
          <span class="sistema__marchio"><svg viewBox="14.3 8.3 36.5 45.5" aria-hidden="true" focusable="false"><path d="M18 12C18 24 18 32 20 36C22 40 30 40 42 40C46 40 47 43 47 50M24 40V50" fill="none" stroke="currentColor" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="34" cy="24" r="6.4" fill="#167A68"/></svg></span>
          <span class="sistema__nome">Scranno</span>
          <span class="sistema__cosa">Entri nell'Aula di Montecitorio. Ogni seggio porta al deputato che lo occupa e al suo lavoro: interventi, atti, voti.</span>
          <span class="sistema__per">Per chi vuole sapere chi siede dove, e come ha votato.</span>
          <span class="sistema__vai">Entra in Aula <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></span>
        </a>
      </div>
    </div>
  </section>

  <!-- Numeri -->
  <section class="sezione numeri">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">Nel grafo, al <span id="data-agg">{{dataAgg}}</span></p></div>
      <h2 class="titolo-1 compare" style="margin-top:var(--s-6);max-width:18ch">La XIX legislatura di Camera e Senato, collegata fatto per fatto.</h2>
      <div id="numeri">{{numeri}}</div>
      <div class="fila compare" style="margin-top:var(--s-7)">
        <a class="btn btn--linea" href="/dati">Scarica il grafo</a>
        <a class="btn btn--linea" href="/sviluppatori">Collega un assistente AI</a>
      </div>
      <p class="nota compare" style="margin-top:var(--s-4)">Fonti: open data della Camera dei Deputati e del Senato della Repubblica, thesaurus EuroVoc. Il grafo è rilasciato con licenza CC BY-SA 4.0.</p>
    </div>
  </section>

  <!-- Ricerca -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 5</span><p class="etichetta" style="padding-top:.55em">Ricerca</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6)">Due articoli a ISWC 2026, Bari, 25–29 ottobre.</h2>
      <div class="articoli compare">
        <a class="articolo" href="https://emeierkeio.github.io/papers/who-speaks-matters-iswc2026.pdf" rel="noopener">
          <span class="etichetta">In-Use Track · LNCS 17128</span>
          <span><span class="articolo__t">Who Speaks Matters: Authority-Aware Multi-View Retrieval-Augmented Generation over Italian Parliamentary Proceedings</span><span class="articolo__a" style="display:block">M. Tritella, R. Pozzi, M. Palmonari</span></span>
          <span class="etichetta">PDF ↗</span>
        </a>
        <a class="articolo" href="https://emeierkeio.github.io/papers/parliamentrag-demo-iswc2026.pdf" rel="noopener">
          <span class="etichetta">Posters &amp; Demos</span>
          <span><span class="articolo__t">ParliamentRAG: An Authority-Aware Multi-View RAG System for Italian Parliamentary Proceedings</span><span class="articolo__a" style="display:block">M. Tritella, R. Pozzi, M. Palmonari</span></span>
          <span class="etichetta">PDF ↗</span>
        </a>
      </div>
      <p class="compare" style="margin-top:var(--s-5)"><a class="collegamento" href="/ricerca">Come citarli, e gli interventi pubblici</a></p>
    </div>
  </section>

  <!-- Cosa copre -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 6</span><p class="etichetta" style="padding-top:.55em">Prima di usare una risposta</p></div>
      <div class="copre">
        <div class="compare">
          <h3>Copre</h3>
          <ul>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Camera dei Deputati e Senato della Repubblica nella XIX legislatura, dal 13 ottobre 2022</li>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Resoconti delle sedute in Aula, con il testo integrale</li>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Atti e votazioni elettroniche, con il voto di ogni parlamentare</li>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.4l3 3 6-6.6"/></svg>Aggiornamento a ogni nuova seduta</li>
          </ul>
        </div>
        <div class="compare presto" style="--ritardo:100ms">
          <h3>Prossimamente</h3>
          <ul>
            <li><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/></svg>Le legislature precedenti alla XIX</li>
          </ul>
        </div>
        <div class="compare" style="--ritardo:200ms">
          <h3>Hai trovato un errore?</h3>
          <p class="piccolo tenue">Scrivi a <a class="collegamento" href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a> con il link alla risposta. Lo controlliamo sul resoconto e lo correggiamo.</p>
        </div>
      </div>

      <div style="margin-top:var(--s-8)">
        <h2 class="titolo-3 compare">Domande frequenti</h2>
        <div class="compare" style="margin-top:var(--s-4);border-top:1px solid var(--filetto)">
          <details class="domanda"><summary>È un servizio ufficiale del Parlamento?</summary><p class="domanda__r">No. È un progetto di ricerca indipendente nato all'Università di Milano-Bicocca. Usa gli open data che Camera e Senato pubblicano su dati.camera.it e dati.senato.it, ma non è affiliato al Parlamento e non parla a suo nome.</p></details>
          <details class="domanda"><summary>Posso fidarmi delle citazioni?</summary><p class="domanda__r">Delle parole sì: ogni citazione è confrontata con il resoconto e ha il link alla fonte. Il resto della risposta lo scrive un modello di AI, che può omettere qualcosa o sbagliare. Per un uso che conta, controlla sul resoconto.</p></details>
          <details class="domanda"><summary>È gratis?</summary><p class="domanda__r">Sì. Stenografo, Fascicoli e Scranno si usano senza account e senza pagare. I dati si scaricano liberamente.</p></details>
          <details class="domanda"><summary>Posso usare una risposta in un articolo?</summary><p class="domanda__r">Sì. Cita la fonte ufficiale linkata accanto a ogni frase, non il testo generato. Se scrivi del progetto, nella pagina Ricerca trovi il riferimento in BibTeX.</p></details>
          <details class="domanda"><summary>Cosa fate dei miei dati?</summary><p class="domanda__r">Su questo sito non serve un account e non usiamo strumenti di analisi o pubblicità. Se ti iscrivi agli aggiornamenti, l'email resta su Brevo e non la colleghiamo alle domande che fai. <a class="collegamento" href="/privacy">Leggi l'informativa</a>.</p></details>
        </div>
      </div>
    </div>
  </section>

  <!-- Iscrizione -->
  <section class="sezione-stretta" style="background:var(--carta-2);border-top:1px solid var(--filetto)">
    <div class="pagina iscriviti">
      <div class="compare">
        <h2 class="titolo-2">Nuovi sistemi, nuovi dati, nuovi articoli.</h2>
        <p class="tenue" style="margin-top:var(--s-3);max-width:44ch">Poche email, quando c'è qualcosa da dire. Ti disiscrivi con un clic.</p>
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
