import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Dati · ParliamentRAG",
  descrizione: "Il grafo della XIX legislatura di Camera e Senato in RDF: parlamentari, gruppi, atti, sedute, interventi e voti, con licenza CC BY-SA 4.0.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Dati aperti · CC BY-SA 4.0</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">Il grafo, da <em>scaricare</em>.</h1>
        <p class="attacco compare" style="--ritardo:160ms">La XIX legislatura di Camera e Senato come grafo RDF. Parlamentari, gruppi, atti, emendamenti, documenti, leggi, sedute, interventi e voti, collegati tra loro e ai temi EuroVoc e TESEO. È lo stesso grafo che usano Stenografo, Fascicoli e Scranno.</p>
        <div class="fila apertura__azioni compare" style="--ritardo:240ms">
          <a class="btn btn--accento" href="#scarica">Scarica <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
          <a class="btn btn--linea" href="#deputato">Com'è fatto</a>
        </div>
      </div>
      <dl class="frontespizio compare" style="--ritardo:200ms" id="frontespizio">{{frontespizio}}</dl>
    </div>
  </section>

  <!-- § 1 Numeri -->
  <section class="sezione-stretta" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Nel grafo, al <span id="data-agg">{{dataAgg}}</span></p></div>
      <div id="registro">{{registro}}</div>
      <p class="nota compare" style="margin-top:var(--s-4)">Fonti: open data della Camera (dati.camera.it) e del Senato (dati.senato.it), thesaurus EuroVoc. I numeri si aggiornano con il grafo, a ogni nuova seduta.</p>
    </div>
  </section>

  <!-- § 2 Tre idee -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Come è pensato</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:20ch">Un grafo aperto, che chiunque può riusare.</h2>
      <div class="idee">
        <article class="idea compare">
          <span class="idea__n">01</span>
          <h3 class="titolo-3">Ogni cosa ha un indirizzo</h3>
          <p>Persone, atti, sedute, interventi e voti hanno un URI stabile. Per le persone usiamo quello ufficiale: dati.camera.it per i deputati, dati.senato.it per i senatori. Chi ha già quei dati li collega ai nostri senza tabelle di conversione.</p>
          <div class="idea__vista" aria-label="Esempio di indirizzo">
            <span class="mono">http://dati.camera.it/ocd/persona.rdf/p308912</span>
            <span class="freccia-giu" aria-hidden="true">↓</span>
            <span>Gian Antonio Girelli, deputato</span>
          </div>
        </article>
        <article class="idea compare" style="--ritardo:100ms">
          <span class="idea__n">02</span>
          <h3 class="titolo-3">Vocabolari condivisi</h3>
          <p>Usiamo vocabolari che esistono già. Un programma che conosce W3C ORG capisce i nostri gruppi; uno che conosce EuroVoc legge i temi degli atti in 24 lingue.</p>
          <div class="idea__vista">
            <div class="vocabolari-mini"><span class="sigla">foaf</span><span class="sigla">org</span><span class="sigla">ocd</span><span class="sigla">skos</span><span class="sigla">prov</span><span class="sigla">eli</span><span class="sigla">eurovoc</span><span class="sigla">teseo</span></div>
            <span class="nota">Il nostro spazio di nomi copre solo quello che manca: <span class="mono">w3id.org/parliamentrag/ontology#</span></span>
          </div>
        </article>
        <article class="idea compare" style="--ritardo:200ms">
          <span class="idea__n">03</span>
          <h3 class="titolo-3">Fatti elementari</h3>
          <p>Ogni informazione è una tripla: soggetto, relazione, oggetto. Le triple si contano, si filtrano e si uniscono ad altri dati. Nell'export sono <span id="triple-n">{{triple}}</span>.</p>
          <div class="idea__vista" aria-label="Esempio di tripla">
            <div class="tripla"><span>appartenenza</span><i aria-hidden="true">→</i><span>org:organization</span><i aria-hidden="true">→</i><span>gruppo AZ</span>
              <em>soggetto</em><em></em><em>relazione</em><em></em><em>oggetto</em></div>
          </div>
        </article>
      </div>
    </div>
  </section>

  <!-- § 3 Un deputato nel grafo -->
  <section class="sezione-stretta" id="deputato" style="scroll-margin-top:72px">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Un deputato nel grafo</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Gian Antonio Girelli, nel gruppo PD dal 18 ottobre 2022.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4);max-width:52ch">Così appare nel file Turtle. Passa sopra a una nota, o sceglila con la tastiera, per vedere le righe a cui si riferisce.</p>

      <div class="estratto">
        <div class="estratto__codice compare">
          <span class="estratto__titolo">Estratto abbreviato, URI accorciati</span>
          <pre class="codice" id="ttl"><span class="blocco" data-n="1"><span class="k">@prefix</span> foaf: <span class="s">&lt;http://xmlns.com/foaf/0.1/&gt;</span> .
<span class="k">@prefix</span> org:  <span class="s">&lt;http://www.w3.org/ns/org#&gt;</span> .
<span class="k">@prefix</span> ocd:  <span class="s">&lt;http://dati.camera.it/ocd/&gt;</span> .
<span class="k">@prefix</span> skos: <span class="s">&lt;http://www.w3.org/2004/02/skos/core#&gt;</span> .
<span class="k">@prefix</span> pr:   <span class="s">&lt;https://w3id.org/parliamentrag/ontology#&gt;</span> .
<span class="k">@prefix</span> xsd:  <span class="s">&lt;http://www.w3.org/2001/XMLSchema#&gt;</span> .
<span class="k">@base</span>   <span class="s">&lt;https://w3id.org/parliamentrag/resource/&gt;</span> .
</span>
<span class="blocco" data-n="2"><span class="c"># Il deputato: l'indirizzo è quello della Camera</span>
<span class="m">&lt;http://dati.camera.it/ocd/persona.rdf/p308912&gt;</span>
</span><span class="blocco" data-n="3">    <span class="k">a</span> foaf:Person, ocd:deputato ;
</span><span class="blocco" data-n="2">    foaf:givenName  <span class="s">"GIAN ANTONIO"</span> ;
    foaf:familyName <span class="s">"GIRELLI"</span> .
</span>
<span class="blocco" data-n="4"><span class="c"># Il gruppo</span>
<span class="m">&lt;group/pd&gt;</span>
    <span class="k">a</span> org:Organization, ocd:gruppoParlamentare ;
    skos:altLabel <span class="s">"PD"</span> .
</span>
<span class="blocco" data-n="5"><span class="c"># L'appartenenza: un fatto a sé, con la sua data</span>
<span class="m">&lt;membership/p308912_pd_2022-10-18&gt;</span>
    <span class="k">a</span> org:Membership ;
    org:member       <span class="m">&lt;http://dati.camera.it/ocd/persona.rdf/p308912&gt;</span> ;
    org:organization <span class="m">&lt;group/pd&gt;</span> ;
    pr:startDate     <span class="s">"2022-10-18"</span>^^xsd:date .</span></pre>
          <button class="copia" type="button" data-copia="ttl">Copia</button>
        </div>

        <ol class="note compare" style="--ritardo:120ms" id="note">
          <li tabindex="0" data-n="1"><div><strong>Prefissi</strong><p>Abbreviazioni dei vocabolari usati. Tutti tranne <span class="mono">pr:</span> esistono già e sono mantenuti da altri.</p></div></li>
          <li tabindex="0" data-n="2"><div><strong>La persona</strong><p>L'URI è quello della scheda ufficiale della Camera. Per i senatori è quello di dati.senato.it. Lo stesso indirizzo vale in qualsiasi altro dataset che lo usi.</p></div></li>
          <li tabindex="0" data-n="3"><div><strong>Due tipi insieme</strong><p>È una persona per chiunque usi FOAF, ed è un deputato nel vocabolario open data della Camera.</p></div></li>
          <li tabindex="0" data-n="4"><div><strong>Il gruppo</strong><p>Un'organizzazione secondo W3C ORG, lo stesso modello usato per partiti, enti e aziende.</p></div></li>
          <li tabindex="0" data-n="5"><div><strong>L'appartenenza</strong><p>Collega persona e gruppo con una data di inizio, e di fine quando c'è. Se un deputato cambia gruppo nasce un'altra appartenenza: la storia resta nel grafo.</p></div></li>
        </ol>
      </div>
    </div>
  </section>

  <!-- § 4 Schema -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">Lo schema</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Quattordici tipi di nodo, e come si tengono.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4);max-width:52ch">È lo schema del file che scarichi da Zenodo. Non ci trovi i riassunti né i passaggi che usiamo per la ricerca: li produce ParliamentRAG, non vengono dagli open data.</p>
      <div class="schema" id="schema">
        <figure class="foglio schema__figura compare">
          <p class="etichetta" style="margin-bottom:var(--s-3)">Schema, non dati · scegli un nodo</p>
          <div class="schema__scorri">
            <svg viewBox="0 62 740 482" id="schema-svg" role="group" aria-label="Schema del grafo: quattordici tipi di nodo e le relazioni tra loro"></svg>
          </div>
        </figure>
        <div class="schema-desc compare" style="--ritardo:120ms" id="schema-desc" aria-live="polite"></div>
      </div>
    </div>
  </section>

  <!-- § 5 Vocabolari -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 5</span><p class="etichetta" style="padding-top:.55em">Vocabolari</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Il grafo usa vocabolari standard già esistenti.</h2>
      <div class="tabella-scorri compare vocabolari">
        <table class="tabella">
          <thead><tr><th scope="col">Nel grafo</th><th scope="col">Vocabolario</th><th scope="col">Cosa permette</th></tr></thead>
          <tbody>
            <tr><td>Parlamentare</td><td class="mono">ocd:deputato, osr:Senatore, foaf:Person</td><td>Lo stesso record ufficiale della Camera, riusabile ovunque. Per i senatori, quello di dati.senato.it.</td></tr>
            <tr><td>Gruppo parlamentare, commissione</td><td class="mono">org:Organization</td><td>Il modello W3C per le organizzazioni.</td></tr>
            <tr><td>Appartenenza a un gruppo</td><td class="mono">org:Membership</td><td>Inizio e fine: i cambi di gruppo restano tracciati.</td></tr>
            <tr><td>Tema di un atto</td><td class="mono">EuroVoc, via SKOS</td><td>Gli stessi temi in 24 lingue.</td></tr>
            <tr><td>Tema di un disegno di legge del Senato</td><td class="mono">TESEO, via SKOS</td><td>Il thesaurus del Senato, con gli stessi indirizzi di dati.senato.it.</td></tr>
            <tr><td>Legge pubblicata</td><td class="mono">eli:LegalResource</td><td>L'identificativo europeo delle leggi (ELI), lo stesso di Normattiva.</td></tr>
            <tr><td>Emendamento</td><td class="mono">pr:Amendment, sottoclasse di osr:Emendamento</td><td>La classe che il Senato usa per i suoi emendamenti, estesa a quelli della Camera.</td></tr>
            <tr><td>Documento parlamentare</td><td class="mono">ocd:atto, pr:ParliamentaryDocument</td><td>È un atto come gli altri: una query su ocd:atto lo trova.</td></tr>
            <tr><td>Percorso di una legge, versioni del testo</td><td class="mono">dcterms, prov</td><td>Le letture di Camera e Senato in ordine, fino alla legge che ne è uscita.</td></tr>
            <tr><td>Seduta, dibattito, intervento</td><td>Lo standard internazionale degli atti parlamentari</td><td>Una struttura che altri parlamenti già usano.</td></tr>
            <tr><td>Votazione e voto individuale</td><td class="mono">ocd</td><td>Il vocabolario open data della Camera.</td></tr>
            <tr><td>Provenienza</td><td class="mono">prov</td><td>Ogni costruzione dichiara quando è stata fatta e da quali fonti.</td></tr>
          </tbody>
        </table>
      </div>
      <p class="prefissi compare">
        <span><b>foaf</b>http://xmlns.com/foaf/0.1/</span>
        <span><b>org</b>http://www.w3.org/ns/org#</span>
        <span><b>ocd</b>http://dati.camera.it/ocd/</span>
        <span><b>eli</b>http://data.europa.eu/eli/ontology#</span>
        <span><b>osr</b>http://dati.senato.it/osr/</span>
        <span><b>pr</b>https://w3id.org/parliamentrag/ontology#</span>
      </p>
    </div>
  </section>

  <!-- § 6 Scarica -->
  <section class="sezione-stretta" id="scarica" style="background:var(--carta-2);border-top:1px solid var(--filetto);scroll-margin-top:64px">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 6</span><p class="etichetta" style="padding-top:.55em">Scarica</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:20ch">Due depositi, un codice sorgente.</h2>

      <div class="scarica">
        <article class="foglio deposito compare">
          <div class="deposito__testa"><span class="etichetta">Zenodo · RDF</span><span class="sigla sigla--accento">DOI</span></div>
          <div class="deposito__corpo">
            <div class="file">
              <div><p class="file__nome">parliamentrag_kg.ttl</p><p class="file__cosa">Il grafo in Turtle: persone, gruppi, commissioni, atti con relatori ed esiti, documenti parlamentari, emendamenti con testo, firmatari ed esito, leggi e percorsi tra Camera e Senato, temi EuroVoc e TESEO, sedute, dibattiti e interventi con il testo integrale.</p></div>
              <span class="sigla">Turtle</span>
            </div>
            <div class="file">
              <div><p class="file__nome">Voti individuali</p><p class="file__cosa">In un file a parte, perché è il più grande: il voto di ogni parlamentare in ogni votazione.</p></div>
              <span class="sigla">RDF</span>
            </div>
          </div>
          <div class="deposito__piede">
            <span class="doi" id="doi">10.5281/zenodo.21560331</span>
            <button class="btn btn--linea btn--piccolo" type="button" data-copia="doi">Copia il DOI</button>
            <a class="btn btn--accento btn--piccolo" href="https://doi.org/10.5281/zenodo.21560331" rel="noopener">Apri su Zenodo <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
          </div>
        </article>

        <article class="foglio deposito compare" style="--ritardo:100ms">
          <div class="deposito__testa"><span class="etichetta">Hugging Face · tabelle</span></div>
          <div class="deposito__corpo">
            <div class="file">
              <div><p class="file__nome">emeierkeio/parliamentrag-leg19</p><p class="file__cosa">I dati della XIX legislatura in forma tabellare, per chi lavora con pandas, R o un foglio di calcolo e non con RDF.</p></div>
              <span class="sigla">Tabelle</span>
            </div>
            <div class="file">
              <div><p class="file__nome">parliamentrag-iswc / build</p><p class="file__cosa">Il codice che costruisce il grafo dagli open data di Camera e Senato. Chi vuole può rifarlo da capo e confrontare.</p></div>
              <span class="sigla">Codice</span>
            </div>
          </div>
          <div class="deposito__piede">
            <a class="btn btn--accento btn--piccolo" href="https://huggingface.co/datasets/emeierkeio/parliamentrag-leg19" rel="noopener">Apri su Hugging Face <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
            <a class="btn btn--linea btn--piccolo" href="https://github.com/Emeierkeio/parliamentrag-iswc/tree/main/build" rel="noopener">La pipeline su GitHub <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
          </div>
        </article>
      </div>

      <div class="avvisi compare">
        <div>
          <h3>Licenza</h3>
          <p>I dati sono rilasciati con licenza <a class="collegamento" href="https://creativecommons.org/licenses/by-sa/4.0/deed.it" rel="noopener">CC BY-SA 4.0</a>. Puoi copiarli, modificarli e ridistribuirli, anche per uso commerciale, citando la fonte e usando la stessa licenza. Le fonti sono gli open data della Camera (CC BY-SA 4.0) e del Senato (<a class="collegamento" href="https://creativecommons.org/licenses/by/3.0/it/" rel="noopener">CC BY 3.0</a>).</p>
        </div>
        <div>
          <h3>Istantanee</h3>
          <p>Su Zenodo pubblichiamo un'istantanea alle tappe importanti, non a ogni aggiornamento. Il grafo usato dai sistemi è più recente dell'ultima istantanea.</p>
        </div>
        <div>
          <h3>Cosa non c'è</h3>
          <p>L'export non contiene gli embedding, le conversazioni degli utenti né i riassunti scritti dall'AI. Solo dati pubblici e le loro relazioni.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- § 7 Interrogalo -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 7</span><p class="etichetta" style="padding-top:.55em">Interrogalo</p></div>
      <div class="interroga" style="margin-top:var(--s-6)">
      <div class="compare">
        <h2 class="titolo-2">Non serve scaricarlo per usarlo.</h2>
        <p class="tenue" style="margin-top:var(--s-4);max-width:46ch">Un server MCP espone il grafo agli assistenti AI che lo supportano. L'assistente cerca negli interventi, apre un dibattito, legge un voto, e ogni risultato porta il link al resoconto.</p>
        <a class="btn btn--linea" style="margin-top:var(--s-5)" href="/sviluppatori">Collega un assistente <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></a>
      </div>
      <ul class="strumenti compare" style="--ritardo:120ms" aria-label="Strumenti del server MCP">
        <li><code>search_parliament</code><span>cerca negli interventi in Aula</span></li>
        <li><code>list_sessions</code><span>elenca le sedute</span></li>
        <li><code>get_debate</code><span>apre un dibattito</span></li>
        <li><code>get_session_votes</code><span>le votazioni di una seduta</span></li>
        <li><code>get_vote_details</code><span>il voto per gruppo e per parlamentare</span></li>
        <li><code>get_vote_hemicycle</code><span>l'emiciclo di una votazione</span></li>
        <li><code>get_voted_text</code><span>il testo messo ai voti</span></li>
        <li><code>verify_answer</code><span>controlla le tre garanzie su una risposta</span></li>
      </ul>
      </div>
    </div>
  </section>
`,
};

export default contenuto;
