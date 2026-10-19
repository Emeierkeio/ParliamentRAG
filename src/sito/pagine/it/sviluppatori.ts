import type { Contenuto } from "../../guscio";

const contenuto: Contenuto = {
  titolo: "Sviluppatori · ParliamentRAG",
  descrizione: "Server MCP per collegare un assistente AI ai dati ufficiali di Camera e Senato, API HTTP su richiesta e dump del grafo con DOI.",
  html: String.raw`
  <!-- Apertura -->
  <section class="apertura">
    <div class="pagina apertura__griglia">
      <div>
        <p class="etichetta compare">Sviluppatori</p>
        <h1 class="titolo-1 compare" style="--ritardo:80ms">Collega il tuo assistente AI ai <em>resoconti</em>.</h1>
        <p class="attacco compare" style="--ritardo:160ms">Il server MCP di ParliamentRAG dà al tuo assistente gli atti ufficiali di Camera e Senato: interventi, atti, sedute, voti. Ogni risultato porta il link alla fonte.</p>
        <div class="fila clienti compare" style="--ritardo:220ms" aria-label="Client compatibili">
          <span class="sigla">Claude</span><span class="sigla">ChatGPT</span><span class="sigla">Cursor</span><span class="sigla">VS Code</span><span class="sigla">e altri client MCP</span>
        </div>
      </div>
      <div class="foglio galleggia indirizzo compare" style="--ritardo:200ms">
        <p class="etichetta">Server remoto · niente da installare</p>
        <div class="indirizzo__url">
          <code id="url-mcp">https://mcp.parliamentrag.it/mcp</code>
          <button class="btn btn--linea btn--piccolo" type="button" data-copia="url-mcp">Copia</button>
        </div>
        <p class="nota">Aggiungilo come server MCP remoto nelle impostazioni del tuo client. <a class="collegamento" href="#mcp">Come collegarlo</a>.</p>
      </div>
    </div>
  </section>

  <!-- MCP -->
  <section class="sezione-stretta" id="mcp" style="padding-top:0">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 1</span><p class="etichetta" style="padding-top:.55em">Server MCP</p></div>

      <div class="mcp">
        <div class="istruzioni compare">
          <h2 class="titolo-3">Come collegarlo</h2>
          <div class="schede" role="tablist" aria-label="Modo di collegamento">
            <button type="button" role="tab" id="tab-remoto" aria-controls="pan-remoto" aria-selected="true">Endpoint remoto</button>
            <button type="button" role="tab" id="tab-claude" aria-controls="pan-claude" aria-selected="false" tabindex="-1">Claude Code</button>
          </div>

          <div role="tabpanel" id="pan-remoto" aria-labelledby="tab-remoto">
            <p>Il server gira da noi. Nel client aggiungi un server MCP remoto con questo indirizzo.</p>
            <div class="blocco-codice">
              <pre class="codice codice--a-capo" id="cod-remoto">https://mcp.parliamentrag.it/mcp</pre>
              <button class="copia" type="button" data-copia="cod-remoto">Copia</button>
            </div>
            <p class="nota">Ogni client ha un suo menu. Su claude.ai: Settings → Connectors → Add custom connector, poi incolla l'indirizzo. Su ChatGPT: Impostazioni → Connettori, in modalità sviluppatore, poi aggiungi l'indirizzo. In Cursor e VS Code: aggiungi un server remoto con questo indirizzo in <span class="mono">mcp.json</span>.</p>
          </div>

          <div role="tabpanel" id="pan-claude" aria-labelledby="tab-claude" hidden>
            <p>Per farlo girare sul tuo computer con Claude Code, lancia questo comando nel terminale.</p>
            <div class="blocco-codice">
              <pre class="codice codice--a-capo" id="cod-claude"><span class="k">claude</span> mcp add parliamentrag -- uvx --from <span class="s">"git+https://github.com/Emeierkeio/parliamentrag-iswc.git#subdirectory=mcp"</span> parliamentrag-mcp</pre>
              <button class="copia" type="button" data-copia="cod-claude">Copia</button>
            </div>
            <p class="nota">Il comando usa <span class="mono">uvx</span>: serve uv installato. Il codice del server è nella cartella <span class="mono">mcp</span> del <a class="collegamento" href="https://github.com/Emeierkeio/parliamentrag-iswc/tree/main/mcp" rel="noopener">repository</a>.</p>
          </div>
        </div>

        <div class="compare" style="--ritardo:120ms">
          <h2 class="titolo-3">Otto strumenti</h2>
          <p class="tenue piccolo" style="margin-top:var(--s-2);margin-bottom:var(--s-4)">L'assistente li sceglie da solo in base alla domanda.</p>
          <ol class="strumenti" id="strumenti">
            <li class="strumento" data-s="search_parliament"><code>search_parliament</code><span>Ricerca ibrida su interventi e atti di Camera e Senato.</span></li>
            <li class="strumento" data-s="list_sessions"><code>list_sessions</code><span>Sedute di Camera e Senato, con riassunto e dibattiti.</span></li>
            <li class="strumento" data-s="get_debate"><code>get_debate</code><span>Un dibattito: riassunto, atti, oratori, e la legge che ne è uscita.</span></li>
            <li class="strumento" data-s="get_session_votes"><code>get_session_votes</code><span>Le votazioni di una seduta.</span></li>
            <li class="strumento" data-s="get_vote_details"><code>get_vote_details</code><span>Una votazione: esiti per gruppo, voti dei singoli, l'atto votato e la sua legge.</span></li>
            <li class="strumento" data-s="get_vote_hemicycle"><code>get_vote_hemicycle</code><span>L'emiciclo di un voto, come immagine.</span></li>
            <li class="strumento" data-s="get_voted_text"><code>get_voted_text</code><span>Il testo votato: emendamenti, articoli, ordini del giorno.</span></li>
            <li class="strumento" data-s="verify_answer"><code>verify_answer</code><span>Controlla una risposta: tutti i gruppi, voci autorevoli, citazioni esatte.</span></li>
          </ol>
        </div>
      </div>

      <!-- Domande d'esempio -->
      <div class="esempi">
        <div class="compare">
          <p class="etichetta">Esempi di domanda</p>
          <h2 class="titolo-3" style="margin-top:var(--s-3)">Cosa puoi chiedere</h2>
          <p class="tenue piccolo" style="margin-top:var(--s-3);max-width:40ch">Scegli una domanda: si accendono gli strumenti che l'assistente userebbe per rispondere. Qui non mostriamo risposte: le dà il tuo assistente, con le fonti.</p>
        </div>
        <div class="compare" style="--ritardo:120ms">
          <div class="esempi__lista" id="esempi" role="group" aria-label="Domande d'esempio">
            <button class="esempio" type="button" aria-pressed="false" data-strumenti="list_sessions get_session_votes get_vote_details get_vote_hemicycle">Chi ha votato contro la fiducia del 7 ottobre? <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
            <button class="esempio" type="button" aria-pressed="false" data-strumenti="search_parliament get_debate verify_answer">Cosa hanno detto i gruppi in Aula sul salario minimo? <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
            <button class="esempio" type="button" aria-pressed="false" data-strumenti="list_sessions get_session_votes get_voted_text">Quali emendamenti ha votato l'Aula nell'ultima seduta? <svg class="freccia" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>
          </div>
          <p class="percorso" id="percorso" aria-live="polite">Nessuna domanda scelta.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- API -->
  <section class="sezione-stretta" id="api">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 2</span><p class="etichetta" style="padding-top:.55em">API HTTP · su richiesta</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Le stesse interrogazioni che usano i nostri sistemi, in JSON.</h2>
      <div class="api">
        <ul class="offre compare">
          <li><strong>Ricerca</strong>Ricerca ibrida sugli interventi in Aula e sugli atti.</li>
          <li><strong>Sedute e dibattiti</strong>Riassunti, atti discussi e oratori.</li>
          <li><strong>Votazioni</strong>Esiti per gruppo e voto di ogni parlamentare.</li>
          <li><strong>Statistiche</strong>Numeri del grafo e indice dei dati aperti.</li>
        </ul>
        <div class="token compare" style="--ritardo:120ms">
          <p class="etichetta">Perché serve un token</p>
          <p>Ogni richiesta ha un costo di calcolo. Per questo l'accesso è personale: ti diamo un token e sappiamo a chi appartiene ogni richiesta.</p>
          <p>Scrivici chi sei e cosa vuoi costruire.</p>
          <div class="fila">
            <a class="btn btn--accento" href="mailto:contatti@parliamentrag.it?subject=Richiesta%20token%20API%20ParliamentRAG">Richiedi un token</a>
          </div>
          <p class="nota">Oppure scrivi a <span class="mono">contatti@parliamentrag.it</span>. Cosa conserviamo delle richieste è scritto nell'<a class="collegamento" href="/privacy">informativa</a>.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Dump -->
  <section class="sezione-stretta" id="dump">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 3</span><p class="etichetta" style="padding-top:.55em">Dump e dataset</p></div>
      <h2 class="titolo-2 compare" style="margin-top:var(--s-6);max-width:22ch">Il grafo intero, da scaricare.</h2>
      <p class="tenue compare" style="margin-top:var(--s-3);max-width:52ch">Se ti serve tutto, e non una domanda alla volta, scarica i dati. Non serve un token.</p>
      <div class="dump compare">
        <a class="dump__voce" href="/dati">
          <span class="dump__nome">RDF Turtle</span>
          <span class="dump__cosa">L'export del grafo, dalla pagina Dati.</span>
          <span class="dump__dove">parliamentrag.it/dati</span>
        </a>
        <a class="dump__voce" href="https://doi.org/10.5281/zenodo.21560331" rel="noopener">
          <span class="dump__nome">Zenodo</span>
          <span class="dump__cosa">Il dataset archiviato, con DOI da citare.</span>
          <span class="dump__dove">doi.org/10.5281/zenodo.21560331</span>
        </a>
        <a class="dump__voce" href="https://huggingface.co/datasets/emeierkeio/parliamentrag-leg19" rel="noopener">
          <span class="dump__nome">Hugging Face</span>
          <span class="dump__cosa">Il dataset della Camera, XIX legislatura.</span>
          <span class="dump__dove">emeierkeio/parliamentrag-leg19</span>
        </a>
        <a class="dump__voce" href="https://github.com/Emeierkeio/parliamentrag-iswc/tree/main/build" rel="noopener">
          <span class="dump__nome">Pipeline</span>
          <span class="dump__cosa">Il codice che costruisce il grafo dagli open data.</span>
          <span class="dump__dove">parliamentrag-iswc/build</span>
        </a>
      </div>
    </div>
  </section>

  <!-- Licenza -->
  <section class="sezione-stretta" id="licenza">
    <div class="pagina">
      <div class="testata compare"><span class="testata__n">§ 4</span><p class="etichetta" style="padding-top:.55em">Licenza</p></div>
      <div class="licenza">
        <h2 class="titolo-3 compare">I dati restano di Camera e Senato, con le loro licenze.</h2>
        <div class="prosa compare" style="--ritardo:120ms">
          <p>I dati vengono dagli open data della Camera dei Deputati, con licenza <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.it" rel="noopener">CC BY-SA 4.0</a>, e del Senato della Repubblica, con licenza <a href="https://creativecommons.org/licenses/by/3.0/it/" rel="noopener">CC BY 3.0</a>. Se li riusi, cita come fonte la Camera o il Senato. Per i dati della Camera condividi i lavori derivati con la stessa licenza.</p>
          <p>Le regole d'uso del servizio sono nei <a href="/termini">termini</a>. Per un accesso automatico, chiedi un token invece di scaricare le pagine.</p>
        </div>
      </div>
    </div>
  </section>
`,
};

export default contenuto;
