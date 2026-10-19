import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Verifica · ParliamentRAG",
  descrizione: "Il verificatore pubblico delle tre garanzie: incolla la risposta di un sistema di intelligenza artificiale e controlla gruppi, voci autorevoli e citazioni.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Verifica</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">Una risposta, <em>tre</em> controlli.</h1>
        <p class="attacco compare" style="--ritardo:160ms">Incolla la risposta che hai ricevuto da un sistema di intelligenza artificiale: il verificatore controlla se rispetta le tre garanzie che chiediamo ai nostri sistemi.</p>
      </div>
      <div class="cantiere compare" style="--ritardo:240ms">
        <span class="etichetta cantiere__stato cantiere__stato--attivo"><i aria-hidden="true"></i>Cosa copre</span>
        <p>Tutti gli interventi in Aula di Camera e Senato, XIX legislatura, aggiornati ogni notte. Le citazioni vanno tra «…» o tra "…".</p>
        <p><a class="collegamento" href="#come">Leggi come funziona la verifica</a></p>
      </div>
    </div>
  </section>

  <!-- § 1 Prova -->
  <section class="sezione-stretta" style="padding-top:0" id="prova">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Verifica · Parlamento, XIX legislatura</p></div>

      <div class="banco">
        <form class="banco__input compare" id="modulo" novalidate>
          <label class="titolo-4" for="domanda">La domanda <span class="nota">facoltativa</span></label>
          <div class="campo">
            <input id="domanda" type="text" maxlength="300" autocomplete="off" placeholder="Per esempio: cosa pensano i gruppi del salario minimo?">
          </div>
          <label class="titolo-4" for="risposta">La risposta da controllare</label>
          <div class="campo campo--area">
            <textarea id="risposta" rows="14" spellcheck="false" placeholder="Incolla qui la risposta che un sistema di intelligenza artificiale ti ha dato su un tema discusso in Parlamento. Le citazioni vanno tra «…» o tra &quot;…&quot;."></textarea>
            <div class="banco__conta"><span id="conta">0 parole</span><span class="scorciatoia">⌘/Ctrl + Invio per verificare</span></div>
          </div>
          <div class="banco__azioni">
            <button class="btn btn--accento" type="submit" id="verifica">Verifica</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="esempio">Incolla un esempio</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="svuota">Svuota</button>
          </div>
          <p class="messaggio" id="msg" role="status"></p>
          <p class="nota">Hai la risposta nel <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/schema/verifiable-answer.v1.json" rel="noopener">formato JSON verificabile</a>? Incollala qui: controllo le citazioni, una per una, con le regole del <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/tree/main/verifica" rel="noopener">verificatore aperto</a>. <button class="link-bottone" type="button" id="esempio-json">Incolla un esempio JSON</button></p>
          <p class="nota">Il testo arriva al nostro server solo per il controllo: non lo salviamo e non lo registriamo. La domanda passa a OpenAI per calcolare l'autorevolezza sul tema. <a class="collegamento" href="/privacy">Privacy</a></p>
        </form>

        <div class="foglio esito-box compare" style="--ritardo:120ms">
          <div class="esito-box__testa">
            <span class="etichetta">Esito</span>
            <span class="etichetta" id="stato">In attesa</span>
          </div>
          <div class="esito-box__corpo" id="esito" aria-live="polite" aria-busy="false">
            <div class="vuoto">
              <div class="sigillo" aria-hidden="true">
                <span class="sigillo__da">Verifica</span>
                <span class="sigillo__voce" data-esito="nd">Tutti i gruppi</span>
                <span class="sigillo__voce" data-esito="nd">Voci autorevoli</span>
                <span class="sigillo__voce" data-esito="nd">Citazioni esatte</span>
              </div>
              <p>Incolla una risposta, o usa l'esempio, e premi Verifica. L'esito compare qui, garanzia per garanzia.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- § 2 Cosa controlla -->
  <section class="sezione-stretta" id="come">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Cosa controlla, e come</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Tre controlli su tutta la XIX legislatura.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4);max-width:52ch">Gli stessi che applichiamo alle risposte dei nostri sistemi. Il verificatore non usa modelli linguistici: a parità di dati, la stessa risposta dà lo stesso esito.</p>
      <div class="tabella-scorri compare confronto-v">
        <table class="tabella">
          <thead><tr><th scope="col">Garanzia</th><th scope="col">Cosa controlla</th><th scope="col">Quando passa</th></tr></thead>
          <tbody>
            <tr>
              <td>Tutti i gruppi</td>
              <td data-l="Cosa controlla">Cerca nel testo la sigla o il nome di ogni gruppo in carica, delle componenti del Misto con deputati o senatori e del Governo. Un senatore del Misto conta per la sua componente, per esempio Cucchi per AVS. L'elenco viene dal grafo, non da una lista scritta a mano. Contano i gruppi della camera nominata nella domanda; se la domanda non ne nomina una, della camera di tutte le citazioni e i link della risposta; altrimenti di Camera e Senato.</td>
              <td data-l="Quando passa">Ogni voce è nominata o citata. Una parola uguale a un nome conta anche se è usata in altro senso. Un gruppo senza interventi sul tema dà un avviso, non un errore: non si può citare chi non ha parlato.</td>
            </tr>
            <tr>
              <td>Citazioni esatte</td>
              <td data-l="Cosa controlla">Cerca ogni testo tra virgolette, da quattro parole in su, in tutti gli interventi in Aula. Indica chi l'ha detto, quando, e il link al resoconto.</td>
              <td data-l="Quando passa">Ogni citazione è un tratto continuo di un intervento e il cognome di chi parla compare vicino. Contano solo spazi, apostrofi tipografici e la maiuscola iniziale; puntini e parole saltate no.</td>
            </tr>
            <tr>
              <td>Voci autorevoli</td>
              <td data-l="Cosa controlla">Per ogni parlamentare o membro del Governo citato o nominato (per nome e cognome, o per cognome se non ci sono omonimi) calcola l'autorevolezza sul tema della domanda, con i sei criteri e i pesi pubblici, e la sua posizione tra chi del suo gruppo ha parlato del tema. Se accanto al nome c'è un gruppo sbagliato, lo segnala.</td>
              <td data-l="Quando passa">Chi parla è un membro del Governo, il relatore del provvedimento o uno dei primi cinque del suo gruppo tra chi ha parlato del tema (se ne hanno parlato in meno di cinque, tutti). Senza domanda, il tema si ricava dalle prime righe della risposta.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <details class="domanda alias compare">
        <summary>Nomi con cui il verificatore riconosce i gruppi</summary>
        <div class="tabella-scorri">
          <table class="tabella">
            <thead><tr><th scope="col">Voce</th><th scope="col">Sigle, solo come scritte</th><th scope="col">Nomi, maiuscole libere</th></tr></thead>
            <tbody id="alias"></tbody>
          </table>
        </div>
      </details>
    </div>
  </section>

  <!-- § 3 Perché -->
  <section class="sezione-stretta" style="background:var(--carta-2);border-top:1px solid var(--filetto)">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Perché un verificatore</p></div>
      <div class="perche">
        <h2 class="titolo-2 compare">I dati sono pubblici. Le garanzie, finora, no.</h2>
        <div class="perche__testo compare" style="--ritardo:120ms">
          <p>Camera e Senato pubblicano resoconti, atti e voti. Chi riceve una risposta da un assistente AI non ha però un modo semplice per sapere se manca un gruppo o se una citazione è stata ritoccata.</p>
          <p><strong>Un controllo che dipende da chi ha scritto la risposta non basta.</strong> Per questo il verificatore applica le stesse regole a ogni risposta, anche alle nostre.</p>
          <p>Il metodo è descritto qui sopra. Lo stesso controllo è lo strumento <code>verify_answer</code> del nostro <a class="collegamento" href="/sviluppatori#mcp">server MCP</a>. Le citazioni si controllano anche sul tuo computer, con i dati aperti: <code>pip install ./verifica</code> dal <a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG" rel="noopener">repository</a>, poi <code>parliamentrag-verifica risposta.json</code>. Se hai casi difficili, risposte che ingannano un controllo o idee su cosa misurare, scrivici.</p>
          <div class="fila" style="margin-top:var(--s-2)">
            <a class="btn btn--accento" href="#come">Come funziona la verifica</a>
            <a class="btn btn--linea" href="/metodo">Come applichiamo le garanzie</a>
          </div>
          <p class="nota">Scrivi a <a class="collegamento" href="mailto:contatti@parliamentrag.it">contatti@parliamentrag.it</a>.</p>
        </div>
      </div>
    </div>
  </section>
`,
};

export default contenuto;
