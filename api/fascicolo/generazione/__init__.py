"""La generazione del fascicolo in quattro passi, con l'integrità delle citazioni, portata dal backend precedente con
la stessa logica, gli stessi prompt e gli stessi modelli: l'analista scompone la domanda in claim (analyst.py), una
sezione per gruppo attorno a una citazione già scelta e verificata (sectional.py), l'integratore compone i blocchi e
scrive l'introduzione (integrator.py), il chirurgo mette le citazioni parola per parola (surgeon.py). Registro delle
citazioni, controllo di coerenza e verifica letterale le seguono lungo tutto il percorso (pipeline.py).

Le chiamate al modello passano da ..modello (contesto.chat), sincrone; i passi in parallelo usano thread."""

from .pipeline import GenerationPipeline

__all__ = ["GenerationPipeline"]
