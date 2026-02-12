# Bibliografia - Miglioramenti ParliamentRAG

Paper accademici utilizzati come fondamento per le modifiche al sistema di generazione report parlamentari. Ogni paper e' collegato alle criticita' specifiche (C1-C7) che ha motivato.

---

## 1. FActScore

**Citazione**: Min, S., Krishna, K., Lyu, X., Lewis, M., Yih, W., Koh, P. W., Iyyer, M., Zettlemoyer, L., & Hajishirzi, H. (2023). FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation. *EMNLP 2023*.

**Link**: https://arxiv.org/abs/2305.14251

**Criticita' collegata**: C1 (Citazioni generiche/prive di sostanza)

**Come e' stato utilizzato**: FActScore propone di decomporre il testo generato in "atomic facts" e verificare ciascuno contro una knowledge source. Questo principio ha motivato l'introduzione dei `_META_COMMENT_PATTERNS` nel `sentence_extractor.py`: invece di accettare qualsiasi frase che non sia procedurale (score 0.5 di default), il sistema ora verifica se la frase contiene un fatto politico sostantivo o e' solo un meta-commento sul dibattito (es. "e' un tema delicato"). Le frasi meta-commento senza contenuto fattuale politico ricevono score 0.35 e vengono filtrate prima di raggiungere il LLM.

---

## 2. ALCE (Automatic LLMs' Citation Evaluation)

**Citazione**: Gao, T., Yen, H., Yu, J., & Chen, D. (2023). Enabling Large Language Models to Generate Text with Citations. *EMNLP 2023*.

**Link**: https://arxiv.org/abs/2305.14627

**Criticita' collegata**: C1 (Citazioni generiche), C2 (Riferimenti fonte mancanti)

**Come e' stato utilizzato**:
- **Per C1**: ALCE introduce metriche di *citation precision* (la citazione supporta effettivamente il claim?) e *citation recall* (tutti i claims sono supportati?). Una citazione tecnicamente accurata ma priva di contenuto politico ("e' un tema complesso") fallisce la citation precision dal punto di vista dell'utente, perche' non supporta nessun claim sostantivo. Questo ha motivato il filtraggio dei meta-commenti.
- **Per C2**: ALCE enfatizza il concetto di *traceability* -- il lettore deve poter risalire alla fonte originale e verificarla. Nel contesto parlamentare, questo richiede che ogni citazione includa il riferimento alla seduta specifica (numero e data). Questo ha motivato l'aggiunta di "Seduta N. X, DD/MM/YYYY" nel formato delle citazioni inline nel `surgeon.py`.

---

## 3. MMR (Maximal Marginal Relevance)

**Citazione**: Carbonell, J., & Goldstein, J. (1998). The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries. *SIGIR 1998*.

**Link**: https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf

**Criticita' collegata**: C4 (Deduplicazione solo su match esatto)

**Come e' stato utilizzato**: MMR e' l'approccio canonico per selezionare contenuti che siano sia rilevanti alla query che diversi tra loro. La formula MMR bilancia `Sim(di, Q)` (rilevanza) con `max Sim(di, dj)` (ridondanza rispetto ai gia' selezionati). Questo principio ha guidato la sostituzione della deduplicazione exact-match in `sectional.py` con una deduplicazione basata su cosine similarity tra embeddings: quando due citazioni di speaker diversi hanno similarity > 0.85, vengono considerate semanticamente equivalenti e solo quella con authority_score piu' alto viene mantenuta.

---

## 4. Sentence-BERT (SBERT)

**Citazione**: Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *EMNLP 2019*.

**Link**: https://arxiv.org/abs/1908.10084

**Criticita' collegata**: C4 (Deduplicazione semantica), C7 (Validazione coerenza)

**Come e' stato utilizzato**:
- **Per C4**: SBERT dimostra che gli embeddings frasali catturano efficacemente la similarita' semantica tra frasi, anche quando espresse con parole diverse. Questo ha motivato l'uso di embedding cosine similarity (tramite `text-embedding-3-small` di OpenAI, gia' disponibile nel sistema) per la deduplicazione cross-speaker in sostituzione del confronto esatto di stringhe.
- **Per C7**: Lo stesso principio si applica alla validazione coerenza: la cosine similarity tra embedding dell'intro e della citazione cattura l'allineamento semantico molto meglio dell'overlap lessicale Jaccard. Questo ha motivato la sostituzione del `CoherenceValidator` da Jaccard-based a embedding-based.

---

## 5. SummaC

**Citazione**: Laban, P., Schnabel, T., Bennett, P. N., & Hearst, M. A. (2022). SummaC: Re-Visiting NLI-based Models for Inconsistency Detection in Summarization. *TACL 2022*.

**Link**: https://arxiv.org/abs/2111.09525

**Criticita' collegata**: C7 (Validazione coerenza debole)

**Come e' stato utilizzato**: SummaC dimostra che i modelli basati su NLI (Natural Language Inference) superano l'overlap lessicale di circa il 5% nell'individuare inconsistenze tra testo sorgente e summary. Il metodo SummaCZS esegue NLI zero-shot a livello di frase e aggrega i punteggi. Questo risultato ha motivato il passaggio dalla validazione Jaccard (soglia 0.2) alla validazione embedding-based (soglia 0.6) nel `coherence_validator.py`, con la possibilita' futura di aggiungere un check NLI esplicito (Tier 2) se l'approccio embedding non dovesse essere sufficiente.

---

## 6. BERTScore

**Citazione**: Zhang, T., Kishore, V., Wu, F., Weinberger, K. Q., & Artzi, Y. (2020). BERTScore: Evaluating Text Generation with BERT. *ICLR 2020*.

**Link**: https://arxiv.org/abs/1904.09675

**Criticita' collegata**: C6 (Citazioni troncate), C7 (Validazione coerenza)

**Come e' stato utilizzato**:
- **Per C6**: BERTScore utilizza matching contestuale a livello di token tramite embeddings BERT. Questo framework dimostra che frammenti sintatticamente incompleti (come citazioni che iniziano con "internazionale, serve...") ottengono punteggi significativamente piu' bassi perche' i token di contesto mancanti degradano il matching. Questo ha motivato il miglioramento del `_clean_result()` nel `sentence_extractor.py` per rilevare e rimuovere frammenti iniziali (parola minuscola + virgola) che indicano continuazione da frase precedente.
- **Per C7**: BERTScore fornisce un framework intermedio tra l'overlap lessicale puro e il NLI completo, dimostrando che il matching contestuale cattura parafrasi e relazioni semantiche che il Jaccard ignora.

---

## 7. Coverage-based Fairness in Multi-document Summarization

**Citazione**: NAACL 2025. Coverage-based Fairness in Multi-document Summarization.

**Link**: https://arxiv.org/abs/2412.08795

**Criticita' collegata**: C3 (Sbilanciamento maggioranza/opposizione)

**Come e' stato utilizzato**: Il paper introduce "Equal Coverage" come misura di fairness a livello di singolo summary e "Coverage Parity" come metrica a livello di corpus. La distinzione chiave e' che la fairness non richiede solo *menzionare* ogni gruppo, ma fornire una *profondita' di copertura proporzionalmente rappresentativa*. Nel contesto di ParliamentRAG, questo ha motivato l'aggiunta di: (1) istruzioni esplicite nel prompt dell'integrator per bilanciare la lunghezza delle sezioni maggioranza/opposizione, (2) un check post-generazione che misura il ratio tra parole per coalizione e segnala sbilanciamenti con ratio > 2:1.

---

## 8. Fair Abstractive Summarization of Diverse Perspectives

**Citazione**: Shen, T., et al. (2023). Fair Abstractive Summarization of Diverse Perspectives. *arXiv preprint*.

**Link**: https://arxiv.org/abs/2311.07884

**Criticita' collegata**: C3 (Sbilanciamento maggioranza/opposizione)

**Come e' stato utilizzato**: Il paper dimostra empiricamente che sia i summary generati da LLM che quelli scritti da umani soffrono di bassa fairness nella rappresentazione di prospettive diverse, con bias sistematici verso prospettive dominanti o piu' frequenti nel training data. Propone strategie di prompting specifiche per mitigare questi bias. Questo ha direttamente motivato l'aggiunta dell'istruzione "BILANCIAMENTO: Le sezioni Maggioranza e Opposizione devono avere lunghezza comparabile" nel prompt dell'integrator, e il requisito "ALMENO 2 frasi di analisi sostantiva" per ogni partito nel prompt del sectional writer.

---

## 9. Positioning Political Texts with Large Language Models

**Citazione**: Becker, M., et al. (2023). Positioning Political Texts with Large Language Models. *arXiv preprint*.

**Link**: https://arxiv.org/html/2311.16639v3

**Criticita' collegata**: C5 (Assenza sintesi convergenze/divergenze)

**Come e' stato utilizzato**: Il paper dimostra che gli LLM possono efficacemente identificare la similarita' tra posizioni politiche tramite un approccio "asking and averaging" -- formulando domande mirate sulle posizioni e aggregando le risposte per rilevare allineamenti. Questo approccio ha ispirato il design dello Stage 3.5 (Convergence-Divergence Analyzer) nel `synthesis.py`: un prompt LLM dedicato analizza il report generato per identificare convergenze cross-coalizione, linee di frattura fondamentali, e posizioni trasversali, basandosi esclusivamente sulle citazioni gia' presenti nel testo.

---

## 10. Sentiment and Position-Taking Analysis of Parliamentary Debates

**Citazione**: Abercrombie, G., & Batista-Navarro, R. (2019). Sentiment and position-taking analysis of parliamentary debates: a systematic literature review. *Journal of Computational Social Science*, 3, 245-270.

**Link**: https://link.springer.com/article/10.1007/s42001-019-00060-w

**Criticita' collegata**: C2 (Riferimenti fonte mancanti)

**Come e' stato utilizzato**: Questa survey sistematica analizza tutti i principali sistemi di analisi computazionale dei dibattiti parlamentari e nota che i sistemi credibili e accademicamente validi forniscono *sempre* metadati a livello di seduta (session ID, data, numero seduta, titolo del dibattito). Questo standard de facto nel campo ha motivato l'inclusione obbligatoria dei riferimenti alla seduta nel formato delle citazioni inline: ogni citazione ora include "Seduta N. X, DD/MM/YYYY" per garantire la tracciabilita' richiesta dagli standard accademici del settore.

---

## 11. Convergence Coefficient (Mean Voter Theorem)

**Citazione**: Schofield, N. (2013). The Mean Voter Theorem: Experiments and Models. *Annals of the New York Academy of Sciences*, PMC 2013.

**Link**: https://pmc.ncbi.nlm.nih.gov/articles/PMC3872446/

**Criticita' collegata**: C5 (Assenza sintesi convergenze/divergenze)

**Come e' stato utilizzato**: Il convergence coefficient fornisce un framework formale per misurare le forze centripete (convergenza verso il centro) e centrifughe (divergenza verso le estremita') tra attori politici in uno spazio politico. Questo framework concettuale ha ispirato la struttura dell'analisi trasversale nel `synthesis.py`: le "CONVERGENZE" corrispondono alle forze centripete (posizioni condivise tra coalizioni), le "LINEE DI FRATTURA" alle forze centrifughe (disaccordi fondamentali), e le "POSIZIONI TRASVERSALI" agli outlier che rompono la disciplina di coalizione.
