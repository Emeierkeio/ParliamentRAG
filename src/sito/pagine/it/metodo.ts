import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Metodo · ParliamentRAG",
  descrizione: "Come verifichiamo una risposta sul Parlamento: il percorso della domanda, le tre garanzie, i pesi dell'autorevolezza, la bussola e i limiti.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina">
      <p class="etichetta compare">Metodo</p>
      <h1 class="titolo-1 compare" style="--ritardo:80ms">Come verifichiamo una <em>risposta</em>.</h1>
      <p class="attacco compare" style="--ritardo:160ms">Un modello di AI scrive la risposta. Prima che arrivi a chi legge, controlliamo tre cose: che ci siano tutti i gruppi, che parli chi del tema si occupa, che le parole tra virgolette siano quelle del resoconto.</p>
      <p class="nota compare" style="--ritardo:200ms;margin-top:var(--s-4)">Il metodo ha dei limiti. Li trovi nel <a class="collegamento" href="#limiti">§ 6</a>, prima di usare una risposta.</p>

      <nav class="sommario compare" style="--ritardo:240ms" aria-label="Le tre garanzie">
        <a href="#gruppi"><span class="sommario__n">01</span><span class="sommario__t">Tutti i gruppi</span><span class="sommario__d">Nessun gruppo resta fuori senza che la risposta lo dica.</span></a>
        <a href="#autorevoli"><span class="sommario__n">02</span><span class="sommario__t">Voci autorevoli</span><span class="sommario__d">Per ogni gruppo parla chi del tema si occupa, secondo criteri pubblici.</span></a>
        <a href="#esatte"><span class="sommario__n">03</span><span class="sommario__t">Citazioni esatte</span><span class="sommario__d">Tra virgolette solo parole che coincidono con il resoconto.</span></a>
      </nav>
    </div>
  </section>

  <div class="pagina impaginato">

    <!-- Indice: fisso sul desktop, elenco in testa sul telefono -->
    <aside class="indice" aria-label="In questa pagina">
      <p class="etichetta">In questa pagina</p>
      <ol id="indice">
        <li><a href="#percorso">Il percorso</a></li>
        <li><a href="#gruppi">Tutti i gruppi</a></li>
        <li><a href="#autorevoli">Voci autorevoli</a></li>
        <li><a href="#esatte">Citazioni esatte</a></li>
        <li><a href="#bussola">La bussola</a></li>
        <li><a href="#limiti">Limiti</a></li>
        <li><a href="#fonti">Fonti</a></li>
      </ol>
    </aside>

    <div class="corpo">

      <!-- § 1 Il percorso di una domanda -->
      <section class="capitolo" id="percorso" aria-labelledby="t-percorso" style="padding-top:0">
        <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Il percorso di una domanda</p></div>
        <h2 class="titolo-2 compare" id="t-percorso">Dalla domanda alla risposta, in sei passaggi.</h2>
        <p class="attacco compare">Ogni passaggio prende il risultato del precedente. L'ultimo è un controllo: se una citazione non passa, non arriva a chi legge.</p>

        <ol class="condotto" id="condotto">
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">1</span>
            <div class="passo__corpo">
              <h3>Domanda riscritta</h3>
              <p>La domanda viene riformulata ed estesa con i termini che il dibattito usa davvero.</p>
              <span class="passo__esce">esce: la domanda e i suoi sinonimi</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">2</span>
            <div class="passo__corpo">
              <h3>Ricerca negli interventi</h3>
              <p>Una ricerca ibrida, per significato e per parole, trova gli interventi in Aula pertinenti.</p>
              <span class="passo__esce">esce: gli interventi candidati</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">3</span>
            <div class="passo__corpo">
              <h3>Autorevolezza</h3>
              <p>Per ogni parlamentare che compare calcoliamo quanto si occupa del tema di questa domanda.</p>
              <span class="passo__esce">esce: chi parla per ogni gruppo</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">4</span>
            <div class="passo__corpo">
              <h3>Una sezione per gruppo</h3>
              <p>Il modello scrive una sezione per ciascun gruppo, solo con gli interventi di quel gruppo.</p>
              <div class="ventaglio" id="ventaglio" aria-hidden="true"></div>
              <span class="passo__esce">esce: una sezione per gruppo</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">5</span>
            <div class="passo__corpo">
              <h3>Integrazione</h3>
              <p>Le sezioni diventano una risposta sola, con i punti di accordo e di disaccordo.</p>
              <span class="passo__esce">esce: la bozza della risposta</span>
            </div>
          </li>
          <li class="passo">
            <span class="passo__nodo" aria-hidden="true">6</span>
            <div class="passo__corpo">
              <h3>Controllo parola per parola</h3>
              <p>Ogni citazione è estratta per posizione dal testo originale e confrontata. Se non coincide, la togliamo.</p>
              <p class="parole-mini" aria-hidden="true"><span style="--i:0">vogliamo</span> <span style="--i:1">rafforzarla</span></p>
              <span class="passo__esce">esce: solo citazioni che coincidono</span>
            </div>
          </li>
        </ol>

        <div class="quinte compare">
          <span class="etichetta">Dietro le quinte</span>
          <p>Nella demo di ricerca un pannello mostra le fasi di ogni risposta, quanto è durata ciascuna e quali chiamate al modello ha fatto. Serve a chi studia il sistema e a chi vuole capire da dove viene una frase.</p>
        </div>
      </section>

      <!-- § 2 Tutti i gruppi -->
      <section class="capitolo" id="gruppi" aria-labelledby="t-gruppi">
        <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Prima garanzia</p></div>
        <div class="garanzia__testa compare">
          <span class="garanzia__cifra" aria-hidden="true">01</span>
          <h2 class="titolo-2" id="t-gruppi">Tutti i gruppi</h2>
        </div>
        <p class="garanzia__dice compare">Una risposta su un dibattito riporta la posizione di ogni gruppo. Se un gruppo del tema non ha parlato, la risposta lo dice.</p>

        <div class="tre-colonne compare">
          <div>
            <span class="etichetta">Cosa vuol dire</span>
            <p>Un assistente che riassume un dibattito tende a seguire chi ha parlato di più. I gruppi piccoli spariscono senza che nessuno lo noti.</p>
            <p>Questa garanzia chiede che l'assenza sia dichiarata, non decisa in silenzio dal modello.</p>
          </div>
          <div>
            <span class="etichetta">Come la applichiamo</span>
            <ul>
              <li><strong>Fascicoli</strong> dà a ogni gruppo la sua sezione, anche quando ha parlato poco.</li>
              <li><strong>Stenografo</strong> risponde a domande puntuali: cita insieme la maggioranza, o il Governo, e l'opposizione. Mai una parte sola.</li>
              <li>Il Gruppo Misto si attribuisce alla componente: +Europa, non «il Misto».</li>
            </ul>
          </div>
          <div>
            <span class="etichetta">Come si controlla</span>
            <p>Si contano i gruppi nominati nella risposta e si confrontano con quelli che siedono in Aula. Per ogni gruppo mancante si cerca la frase che spiega perché manca.</p>
            <p><a class="collegamento" href="/verifica">Prova il controllo sulla pagina Verifica</a></p>
          </div>
        </div>

        <p class="etichetta compare" style="margin-top:var(--s-6)">Nel tema d'esempio, salario minimo: dieci voci di gruppo e il Governo</p>
        <div class="fila-voci compare" id="fila-voci"></div>
      </section>

      <!-- § 3 Voci autorevoli -->
      <section class="capitolo" id="autorevoli" aria-labelledby="t-autorevoli">
        <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Seconda garanzia</p></div>
        <div class="garanzia__testa compare">
          <span class="garanzia__cifra" aria-hidden="true">02</span>
          <h2 class="titolo-2" id="t-autorevoli">Voci autorevoli</h2>
        </div>
        <p class="garanzia__dice compare">Per ogni gruppo parla chi del tema si occupa, secondo i nostri criteri. Non chi ha parlato più spesso in generale.</p>

        <div class="tre-colonne compare">
          <div>
            <span class="etichetta">Cosa vuol dire</span>
            <p>L'autorevolezza si calcola per ogni domanda. Non esiste un punteggio globale: chi è autorevole sulla sanità può non esserlo sul fisco.</p>
          </div>
          <div>
            <span class="etichetta">Come la applichiamo</span>
            <ul>
              <li><strong>Stenografo</strong> cita solo relatori, membri del Governo e i primi cinque di ogni gruppo per autorevolezza.</li>
              <li>Se queste condizioni non si possono rispettare, preferisce non citare nessun intervento.</li>
            </ul>
          </div>
          <div>
            <span class="etichetta">Come si controlla</span>
            <p>Criteri e pesi sono pubblici. Chi vuole può ricalcolare la classifica sui dati aperti e confrontarla con le voci citate.</p>
          </div>
        </div>

        <h3 class="titolo-3 compare" style="margin-top:var(--s-7)">Sei criteri, una somma pesata</h3>
        <p class="compare tenue" style="margin-top:var(--s-3);max-width:60ch">Ogni criterio vale tra 0 e 1 ed è misurato rispetto alla domanda. Il punteggio di un parlamentare è la somma dei sei, ciascuno moltiplicato per il suo peso.</p>
        <div class="tabella-scorri compare tabella-pesi">
          <table class="tabella">
            <thead><tr><th scope="col">Criterio</th><th scope="col" class="num">Peso</th><th scope="col">Cosa misura</th></tr></thead>
            <tbody id="tabella-pesi"></tbody>
          </table>
        </div>

        <div class="riquadro">
          <div class="compare">
            <h3 class="titolo-4">Il tempo conta</h3>
            <p class="tenue piccolo" style="margin-top:var(--s-2);max-width:48ch">Interventi e atti perdono peso con l'età, con un tempo di dimezzamento di 18 mesi (548 giorni). Un intervento di un anno e mezzo fa vale la metà di uno di oggi.</p>
          </div>
          <figure class="decadimento compare" style="--ritardo:120ms" aria-label="Curva di decadimento: peso 1 oggi, 0,5 a 18 mesi, 0,25 a 36 mesi">
            <p class="etichetta">Peso di un intervento secondo la sua età</p>
            <svg id="decadimento" viewBox="0 0 520 210" role="img" aria-hidden="true"></svg>
          </figure>
        </div>

        <!-- Giocattolo: cambia la distribuzione dei pesi, non la classifica -->
        <div class="foglio giocattolo compare" id="giocattolo">
          <div class="giocattolo__testa">
            <span class="etichetta">Prova · sposta i pesi</span>
            <button class="btn btn--linea btn--piccolo" type="button" id="pesi-ripristina">Ripristina i pesi pubblicati</button>
          </div>
          <div class="giocattolo__corpo">
            <div>
              <div id="cursori"></div>
              <p class="somma" id="somma" aria-live="polite"></p>
            </div>
            <div class="barre">
              <div>
                <p class="etichetta">Pesi pubblicati</p>
                <div class="barra-pila" id="barra-pubblicati" aria-hidden="true"></div>
              </div>
              <div>
                <p class="etichetta">I tuoi pesi, riportati a somma 1</p>
                <div class="barra-pila" id="barra-tuoi" aria-hidden="true"></div>
              </div>
              <div class="chiave" id="chiave"></div>
              <p class="scarti" id="scarti" aria-live="polite"></p>
              <p class="nota">Qui cambia solo come si distribuisce il peso. Non ricalcoliamo la classifica dei parlamentari: servirebbero i dati di una domanda vera.</p>
            </div>
          </div>
        </div>

        <p class="compare" style="margin-top:var(--s-5);max-width:62ch;color:var(--inchiostro-2)">I pesi sono una scelta editoriale. Li pubblichiamo perché si possano leggere, discutere e contestare. Una scelta diversa produce voci diverse: è giusto che chi legge lo sappia.</p>
      </section>

      <!-- § 4 Citazioni esatte -->
      <section class="capitolo" id="esatte" aria-labelledby="t-esatte">
        <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">Terza garanzia</p></div>
        <div class="garanzia__testa compare">
          <span class="garanzia__cifra" aria-hidden="true">03</span>
          <h2 class="titolo-2" id="t-esatte">Citazioni esatte</h2>
        </div>
        <p class="garanzia__dice compare">Quello che sta tra virgolette è stato detto in Aula, dalla persona a cui lo attribuiamo, con quelle parole.</p>

        <div class="tre-colonne compare">
          <div>
            <span class="etichetta">Cosa vuol dire</span>
            <p>Un modello di linguaggio tende a parafrasare anche quando mette le virgolette. Una parola cambiata può cambiare il senso di una frase.</p>
          </div>
          <div>
            <span class="etichetta">Come la applichiamo</span>
            <ul>
              <li>Il modello indica dove inizia e dove finisce il passaggio. Il testo lo prendiamo noi, per posizione, dal resoconto.</li>
              <li>Poi lo confrontiamo parola per parola. Se non coincide, la citazione viene tolta.</li>
            </ul>
          </div>
          <div>
            <span class="etichetta">Come si controlla</span>
            <p>Ogni citazione porta il link al resoconto ufficiale della Camera o del Senato. Basta un clic.</p>
          </div>
        </div>

        <div class="provenienza">
          <blockquote class="cit compare" id="cit-esempio"></blockquote>
          <dl class="compare" style="--ritardo:120ms" id="cit-scheda"></dl>
        </div>

        <aside class="avvertenza compare" aria-labelledby="t-scelta">
          <h3 id="t-scelta">Esatta non vuol dire neutrale.</h3>
          <p>Le parole coincidono, ma la scelta del passaggio resta del sistema: quale frase, in quale cornice, accanto a quale altra. Una citazione può essere parziale rispetto all'intervento intero. Per questo il contesto completo è sempre a un clic, sul resoconto.</p>
        </aside>
      </section>

      <!-- § 5 Bussola -->
      <section class="capitolo" id="bussola" aria-labelledby="t-bussola">
        <div class="testata compare"><span class="testata__n">§ 5</span><p class="etichetta" style="padding-top:.55em">La bussola, nella demo di ricerca</p></div>
        <h2 class="titolo-2 compare" id="t-bussola">Dove si collocano i gruppi, su quella domanda.</h2>
        <p class="attacco compare">La bussola descrive cosa hanno sostenuto i gruppi in Aula su una domanda precisa. Non certifica il loro posizionamento politico.</p>

        <div class="bussola">
          <ol class="compare">
            <li><span>Per ogni domanda il sistema propone due assi tematici. Per il salario minimo, ad esempio, uno potrebbe andare da «per legge» a «per contratto».</span></li>
            <li><span>Un modello di linguaggio legge ogni intervento recuperato e gli assegna una posizione tra −1 e +1 su ciascun asse. Se l'intervento non prende posizione, resta senza.</span></li>
            <li><span>La posizione di un gruppo è la media dei suoi interventi con una posizione.</span></li>
            <li><span>Quando gli interventi sono pochi, la media viene avvicinata al centro: due frasi non bastano per collocare un gruppo.</span></li>
          </ol>
          <figure class="piano compare" style="--ritardo:120ms">
            <svg viewBox="0 0 360 300" role="img" aria-labelledby="piano-t">
              <title id="piano-t">Schema: interventi su due assi, media del gruppo e media avvicinata al centro</title>
              <g id="piano"></g>
            </svg>
            <figcaption class="nota" style="margin-top:var(--s-2)">Schema, senza dati reali. I punti grigi sono interventi di un gruppo; il cerchio tratteggiato è la loro media; il punto pieno è la media avvicinata al centro perché gli interventi sono pochi.</figcaption>
          </figure>
        </div>
      </section>

      <!-- § 6 Limiti -->
      <section class="capitolo" id="limiti" aria-labelledby="t-limiti">
        <div class="testata compare"><span class="testata__n">§ 6</span><p class="etichetta" style="padding-top:.55em">Limiti</p></div>
        <div class="limiti compare">
          <h2 class="titolo-2" id="t-limiti">Prima di usare una risposta, sappi questo.</h2>
          <ol>
            <li><div><p>Il testo generato può contenere errori o omissioni.</p><p>Le garanzie controllano gruppi, voci e citazioni. Il resto della risposta lo scrive un modello.</p></div></li>
            <li><div><p>Un intervento pertinente può non essere recuperato.</p><p>La ricerca trova molto, non tutto. Un'assenza nella risposta non prova un'assenza in Aula.</p></div></li>
            <li><div><p>Una citazione esatta resta una scelta.</p><p>Il passaggio e la cornice li sceglie il sistema. Il contesto è sul resoconto.</p></div></li>
            <li><div><p>L'autorevolezza dipende dai nostri pesi.</p><p>Con pesi diversi parlerebbero altre persone. Per questo li pubblichiamo.</p></div></li>
            <li><div><p>È un progetto indipendente.</p><p>Non è affiliato alla Camera dei Deputati né al Senato della Repubblica, che non lo approvano e non ne rispondono.</p></div></li>
            <li><div><p>Per un uso che conta, controlla il resoconto ufficiale.</p><p>Ogni citazione ha il link. Usalo.</p></div></li>
          </ol>
          <p class="limiti__piede">Hai trovato un errore? Scrivi a <a href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a> con il link alla risposta.</p>
        </div>
      </section>

      <!-- § 7 Fonti -->
      <section class="capitolo" id="fonti" aria-labelledby="t-fonti">
        <div class="testata compare"><span class="testata__n">§ 7</span><p class="etichetta" style="padding-top:.55em">Fonti</p></div>
        <h2 class="titolo-2 compare" id="t-fonti">Il metodo per esteso.</h2>
        <div class="fonti compare">
          <a class="fonte" href="https://emeierkeio.github.io/papers/who-speaks-matters-iswc2026.pdf" rel="noopener">
            <span class="etichetta">Articolo · ISWC 2026</span>
            <span><span class="fonte__t">Who Speaks Matters: Authority-Aware Multi-View RAG over Italian Parliamentary Proceedings</span><span class="fonte__d">M. Tritella, R. Pozzi, M. Palmonari. Pipeline, pesi e valutazione.</span></span>
            <span class="etichetta">PDF ↗</span>
          </a>
          <a class="fonte" href="https://arxiv.org/abs/2608.13410" rel="noopener">
            <span class="etichetta">Preprint</span>
            <span><span class="fonte__t">arXiv 2608.13410</span><span class="fonte__d">La stessa ricerca, in accesso aperto.</span></span>
            <span class="etichetta">arXiv ↗</span>
          </a>
          <a class="fonte" href="https://orkg.org/papers/R1909763" rel="noopener">
            <span class="etichetta">Scheda strutturata</span>
            <span><span class="fonte__t">Open Research Knowledge Graph</span><span class="fonte__d">Problema, metodo e risultati in forma confrontabile con altri lavori.</span></span>
            <span class="etichetta">ORKG ↗</span>
          </a>
          <a class="fonte" href="/verifica">
            <span class="etichetta">Su questo sito</span>
            <span><span class="fonte__t">Verifica</span><span class="fonte__d">Incolli una risposta sul Parlamento e controlli se rispetta le tre garanzie.</span></span>
            <span class="etichetta">→</span>
          </a>
          <a class="fonte" href="/dati">
            <span class="etichetta">Su questo sito</span>
            <span><span class="fonte__t">Dati</span><span class="fonte__d">Il grafo su cui il metodo lavora, da scaricare.</span></span>
            <span class="etichetta">→</span>
          </a>
        </div>
      </section>
    </div>
  </div>
`,
};

export default contenuto;
