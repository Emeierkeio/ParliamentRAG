"""Il comunicato del Bollettino diventa sedute, argomenti, paragrafi del sommario e allegati (I Commissione, 28/10/2026)."""

import unittest
from pathlib import Path

from pipeline.carica.postgres import script_commissione
from pipeline.controlli.uscite import _regole_commissione
from pipeline.trasforma.camera_bollettino import atti, trasforma

F = Path(__file__).parent / "fixtures"
COM, ALL = (F / "bollettino_20261028_c01.htm").read_bytes(), (F / "bollettino_20261028_c01_allegati.htm").read_bytes()


class TestBollettino(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(COM, ALL, {"chiave": "leg19-bol-20261028-c01"})
        self.per = {}
        for n in self.r["nodi"]:
            self.per.setdefault(n["label"], []).append(n)

    def test_sedute(self):
        sedi = [s["seat"] for s in self.per["Sitting"]]
        self.assertEqual(sedi[1:], ["SEDE REFERENTE", "ATTI DEL GOVERNO"])
        ref = self.per["Sitting"][1]
        self.assertEqual((ref["presided_by"], ref["start_time"], ref["end_time"]), ("it:person:camera:307857", "14:55", "15:00"))
        self.assertIn("Prisco", ref["government_present"])

    def test_argomenti(self):
        veri = [i for i in self.per["AgendaItem"] if not i.get("service")]
        self.assertEqual([i["acts"] for i in veri], [["ac:3001"], ["ag:439"]])
        self.assertTrue(veri[1]["stage"].endswith("Parere favorevole con condizioni e osservazioni"))

    def test_interventi_sono_sommari(self):
        interventi = [s for s in self.per["Speech"] if s["speaker_label"]]
        self.assertTrue(all(s["kind"] == "summary" for s in self.per["Speech"]))
        gentile = next(s for s in interventi if "GENTILE" in s["speaker_label"])
        self.assertEqual((gentile["declared_group"], gentile["as_office"]), ("FI-PPE", "relatore"))

    def test_allegati_e_controlli(self):
        self.assertEqual(len(self.per["Document"]), 4)
        testi = {t["ref"] for t in self.r["testi"]}
        self.assertEqual(_regole_commissione(self.r["nodi"], self.r["archi"], testi, "camera_bollettino"), [])
        self.assertTrue(_regole_commissione(self.r["nodi"], self.r["archi"], testi, "camera_stenografici_commissioni"))
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] \
            + [{"tipo": "arco", **a} for a in self.r["archi"]] + [{"tipo": "testo", **t} for t in self.r["testi"]]
        s = script_commissione(righe)
        self.assertIn("'it:camera:19:body:o19_35' || '01'", s)
        self.assertTrue(s.rstrip().endswith("COMMIT;"))

    def test_menzioni(self):
        sp = next(s["uri"] for s in self.per["Speech"] if s["speaker_label"])
        archi = self.r["archi"] + [{"type": "MENTIONS", "from": sp, "to": "it:person:camera:300000", "order": 1, "surface": "ROSSI", "method": "fonte"}]
        righe = [{"tipo": "ambito", **self.r["ambito"]}] + [{"tipo": "nodo", **n} for n in self.r["nodi"]] \
            + [{"tipo": "arco", **a} for a in archi] + [{"tipo": "testo", **t} for t in self.r["testi"]]
        s = script_commissione(righe)
        self.assertIn("COPY speech_mention (speech, ord, person, surface, method)", s)
        self.assertIn(f"{sp},1,it:person:camera:300000,ROSSI,fonte", s)
        self.assertLess(s.index("COPY speech "), s.index("COPY speech_mention"))
        self.assertTrue(all("mentions" not in s for s in self.per["Speech"]))

    def test_riferimenti_agli_atti(self):
        self.assertEqual(atti("C. 3001 Governo, approvato dal Senato. Atto n. 439. 5-04321"), ["ac:3001", "ag:439", "aic:5-04321"])


# il gruppo di chi parla è solo quello accanto al suo nome, anche con la parentesi dentro (bol. 2/4/2025 e 8/4/2025)
SCHEDA = '<acronym title="x"><a class="linkSchedaDeputato link_html" href="//documenti.camera.it/apps/commonServices/getDocumento.ashx?idLegislatura=19&amp;sezione=deputati&amp;tipoDoc=schedaDeputato&amp;idPersona={}">{}</a></acronym>'
GRUPPI = f"""<html><head><meta name="date" content="20250408" /><meta name="commissione" content="commissione.04" /></head><body><div id="corpo">
<div class="sede" id="data.20250408.com04.bollettino.sede00030">
<p class="titolo" id="data.20250408.com04.bollettino.sede00030.tit00010"><strong>Audizione del Comandante generale della Guardia di Finanza.</strong></p>
<p class="intervento" id="data.20250408.com04.bollettino.sede00030.tit00010.int00030">  Intervengono, quindi, per porre quesiti e formulare osservazioni, i deputati {SCHEDA.format(308790, "Pino BICCHIELLI")} <a class="gruppo">(NM(N-C-U-I)M-CP)</a>, {SCHEDA.format(308915, "Paola Maria CHIESA")} <a class="gruppo">(FDI)</a> e {SCHEDA.format(307134, "Roberto BAGNASCO")} <a class="gruppo">(FI-PPE)</a>, cui risponde Andrea DE GENNARO.</p>
<p class="intervento" id="data.20250408.com04.bollettino.sede00030.tit00010.int00040">  {SCHEDA.format(305624, "Lorenzo GUERINI")}, <em>presidente,</em> rende alcune comunicazioni sulle quali intervengono il senatore {SCHEDA.format(305999, "Enrico BORGHI")} <a class="gruppo">(IV-C-RE)</a> e i deputati {SCHEDA.format(307246, "Giovanni DONZELLI")} <a class="gruppo">(FDI)</a>.</p>
<p class="intervento" id="data.20250408.com04.bollettino.sede00030.tit00010.int00050">  {SCHEDA.format(308790, "Pino BICCHIELLI")} <a class="gruppo">(NM(N-C-U-I)M-CP)</a>, <em>relatore,</em> ricorda come lo schema di decreto concerna la cessione di radio.</p>
</div></div></body></html>""".encode()


class TestGruppoDiChiParla(unittest.TestCase):
    def test_un_solo_gruppo(self):
        r = trasforma(GRUPPI, None, {"chiave": "leg19-bol-20250408-c04"})
        sp = [n for n in r["nodi"] if n["label"] == "Speech"]
        self.assertEqual([(n["declared_group"], n["as_office"]) for n in sp], [("NM(N-C-U-I)M-CP", None), (None, "presidente"), ("NM(N-C-U-I)M-CP", "relatore")])
        by = [a["as_group"] for a in r["archi"] if a["type"] == "BY"]
        self.assertEqual(by, ["NM(N-C-U-I)M-CP", None, "NM(N-C-U-I)M-CP"])


if __name__ == "__main__":
    unittest.main()
