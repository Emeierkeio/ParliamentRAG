import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Verifica · ParliamentRAG",
  descrizione: "Il verificatore pubblico delle tre garanzie, in costruzione: incolla una risposta sul Parlamento e controlla gruppi, voci e citazioni.",
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
        <span class="etichetta cantiere__stato"><i aria-hidden="true"></i>In costruzione</span>
        <p>Qui sotto c'è un'anteprima che gira nel tuo browser. Lavora su un solo tema, il salario minimo, e conosce solo le 11 citazioni verificate dell'esempio.</p>
        <p><a class="collegamento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/piano-verifica.md" rel="noopener">Leggi il piano della verifica</a></p>
      </div>
    </div>
  </section>

  <!-- § 1 Prova -->
  <section class="sezione-stretta" style="padding-top:0" id="prova">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Anteprima · tema salario minimo</p></div>

      <div class="banco">
        <form class="banco__input compare" id="modulo" novalidate>
          <label class="titolo-4" for="risposta">La risposta da controllare</label>
          <div class="campo campo--area">
            <textarea id="risposta" rows="14" spellcheck="false" placeholder="Incolla qui la risposta che un sistema di intelligenza artificiale ti ha dato sul salario minimo. Le citazioni vanno tra «…» o tra &quot;…&quot;."></textarea>
            <div class="banco__conta"><span id="conta">0 parole</span><span class="scorciatoia">⌘/Ctrl + Invio per verificare</span></div>
          </div>
          <div class="banco__azioni">
            <button class="btn btn--accento" type="submit" id="verifica">Verifica</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="esempio">Incolla un esempio</button>
            <button class="btn btn--linea btn--piccolo" type="button" id="svuota">Svuota</button>
          </div>
          <p class="messaggio" id="msg" role="status"></p>
          <p class="nota">Il testo resta nel tuo browser: l'anteprima non lo invia a nessun server.</p>
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

  <!-- § 2 Anteprima e versione pubblica -->
  <section class="sezione-stretta">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">Cosa controlla, e come</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">L'anteprima fa due controlli su tre, su un corpus piccolo.</h2>
      <p class="attacco compare" style="margin-top:var(--s-4);max-width:52ch">La versione pubblica userà tutto il grafo della XIX legislatura. Qui sotto, per ogni garanzia, cosa fa oggi la pagina e cosa farà il verificatore.</p>
      <div class="tabella-scorri compare confronto-v">
        <table class="tabella">
          <thead><tr><th scope="col">Garanzia</th><th scope="col">Anteprima, in questa pagina</th><th scope="col">Verificatore pubblico</th></tr></thead>
          <tbody>
            <tr>
              <td>Tutti i gruppi</td>
              <td data-l="Anteprima">Cerca nel testo la sigla o il nome di ciascuno dei dieci gruppi del tema e del Governo. Una parola uguale a un nome conta come menzione anche se è usata in altro senso.</td>
              <td data-l="Verificatore pubblico">Confronta i gruppi citati con quelli in carica alla data della domanda, componenti del Misto comprese, e cerca la frase che dichiara un gruppo assente.</td>
            </tr>
            <tr>
              <td>Citazioni esatte</td>
              <td data-l="Anteprima">Estrae il testo tra «…» o tra "…", normalizza spazi e apostrofi e lo confronta parola per parola con le 11 citazioni dell'esempio. Vale anche una parte di citazione.</td>
              <td data-l="Verificatore pubblico">Cerca ogni citazione in tutti gli interventi in Aula, controlla che l'oratore sia quello indicato e restituisce il link al resoconto.</td>
            </tr>
            <tr>
              <td>Voci autorevoli</td>
              <td data-l="Anteprima">Non la controlla. Servono i punteggi di autorevolezza per la domanda, che qui non abbiamo.</td>
              <td data-l="Verificatore pubblico">Calcola l'autorevolezza sul tema con i sei criteri pubblici e controlla che per ogni gruppo parli un relatore, un membro del Governo o uno dei primi cinque.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <details class="domanda alias compare">
        <summary>Nomi con cui l'anteprima riconosce i gruppi</summary>
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
          <p>La Camera pubblica resoconti, atti e voti. Chi riceve una risposta da un assistente AI non ha però un modo semplice per sapere se manca un gruppo o se una citazione è stata ritoccata.</p>
          <p><strong>Un controllo che dipende da chi ha scritto la risposta non basta.</strong> Per questo il verificatore sarà separato dai nostri sistemi e funzionerà con le risposte di chiunque.</p>
          <p>Il metodo è descritto nel piano della verifica. Se hai casi difficili, risposte che ingannano un controllo o idee su cosa misurare, scrivici.</p>
          <div class="fila" style="margin-top:var(--s-2)">
            <a class="btn btn--accento" href="https://github.com/Emeierkeio/ParliamentRAG/blob/main/docs/piano-verifica.md" rel="noopener">Il piano della verifica <svg class="freccia-nord-est" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4"/></svg></a>
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
