"""Il resoconto AKN del Senato diventa interventi singoli, anche dentro i blocchi di scambio (seduta 300, 7/5/2025)."""

import unittest
from pathlib import Path

from pipeline.controlli.uscite import _regole
from pipeline.trasforma.senato_resoconto import sigla, trasforma

CORPO = (Path(__file__).parent / "fixtures" / "senato_resoconto_0300.akn").read_bytes()


class TestSenatoResoconto(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-senato-sed0300"})
        self.testi = {t["ref"]: t["text"] for t in self.r["testi"]}
        self.by = {a["from"]: a for a in self.r["archi"] if a["type"] == "BY"}

    def test_seduta(self):
        s = self.r["nodi"][0]
        self.assertEqual((s["uri"], s["date"], s["chamber"]), ("it:senato:19:sed0300", "2025-05-07", "senato"))

    def test_scambio_diviso(self):
        sp = [n for n in self.r["nodi"] if n["label"] == "Speech"]
        meloni = next(n for n in sp if (n["speaker_label"] or "").startswith("MELONI"))
        self.assertTrue(self.testi[meloni["text_ref"]].startswith("Signor Presidente"))
        self.assertTrue(self.by[meloni["uri"]]["to"].startswith("it:person:senato:"))
        senza = sum(1 for n in sp if n["uri"] not in self.by)
        self.assertLess(senza / len(sp), 0.05)

    def test_sigla_annidata(self):
        sp = [n for n in self.r["nodi"] if n["label"] == "Speech"]
        self.assertIn("Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP", {n["declared_group"] for n in sp})
        self.assertNotIn("Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP", {n["raw"] for n in self.r["nodi"] if n["label"] == "Reaction"})

    def test_controlli(self):
        righe = [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]] + [{"tipo": "testo", **t} for t in self.r["testi"]]
        self.assertEqual(_regole(righe), [])


# omonimi (seduta 26, 11/1/2023): dentro il blocco la senatrice riprende la parola come «FLORIDIA Barbara (M5S).»
NS = 'xmlns:an="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03"'
OMONIMI = f"""<an:akomaNtoso {NS}><an:debate><an:meta><an:identification><an:FRBRWork><an:FRBRdate date="2023-01-11" name="presentazione"/>
<an:FRBRnumber value="26"/></an:FRBRWork></an:identification><an:references>
<an:TLCPerson id="p1" href="http://dati.senato.it/senato/Persona/1" showAs="x"/><an:TLCPerson id="p32634" href="http://dati.senato.it/senato/Persona/32634" showAs="x"/>
<an:TLCRole id="senatore" href="/x" showAs="senatore"/></an:references></an:meta><an:debateBody>
<an:debateSection id="d1" name="x"><an:heading>Disegni di legge</an:heading>
<an:speech by="#p1" as="#senatore"><an:from>PRESIDENTE</an:from><an:p>Ha chiesto di parlare la senatrice Floridia Barbara.</an:p></an:speech>
<an:speech by="#p32634" as="#senatore"><an:from>FLORIDIA Barbara</an:from>
<an:p><an:i>(M5S)</an:i>. Domando di parlare per dichiarazione di voto.</an:p>
<an:p>PRESIDENTE. Ne ha facoltà.</an:p>
<an:p>FLORIDIA Barbara <an:i>(M5S)</an:i>. Signora Presidente, colleghi, voteremo a favore. <an:i>(Applausi)</an:i>.</an:p></an:speech>
</an:debateSection></an:debateBody></an:debate></an:akomaNtoso>""".encode()


class TestSenatoOmonimi(unittest.TestCase):
    def test_cambio_oratore(self):
        r = trasforma(OMONIMI, {"chiave": "leg19-senato-sed0026"})
        testi = {t["ref"]: t["text"] for t in r["testi"]}
        by = {a["from"]: a["to"] for a in r["archi"] if a["type"] == "BY"}
        sp = [(n["speaker_label"], n["declared_group"], by.get(n["uri"]), testi[n["text_ref"]][:20]) for n in r["nodi"] if n["label"] == "Speech"]
        self.assertEqual(sp[-1], ("FLORIDIA Barbara", "M5S", "it:person:senato:32634", "Signora Presidente, "))
        self.assertTrue(all("Signora Presidente" not in t for (e, _, _, t) in sp if e == "PRESIDENTE"))


# le sedute solo web (212, 30/7/2024): stessa struttura della pagina show-doc, accorciata
L = '<a title="x" href="https://www.senato.it/loc/link.asp?leg=19&amp;tipodoc=sanasen&amp;id={}">{}</a>'
PAGINA = f"""<!DOCTYPE html><html><head><title>Legislatura 19ª - Aula - Resoconto stenografico della seduta n. 212 del 30/07/2024</title></head><body>
<p style="text-align:center"><b>RESOCONTO STENOGRAFICO</b></p>
<p style="text-align:center"><b>Presidenza del vice presidente CENTINAIO</b></p>
<p style="text-align:justify">{L.format(29067, "PRESIDENTE")}. La seduta &egrave; aperta <i>(ore 10,02)</i>.</p>
<p style="text-align:center"><b>Discussione del disegno di legge: (1162) Conversione in legge</b></p>
<p style="text-align:justify">{L.format(36391, "DAMANTE")} <i>(M5S)</i>. Domando di parlare.</p>
<p style="text-align:justify">PRESIDENTE. Ne ha facolt&agrave;.</p>
<p style="text-align:justify">DAMANTE <i>(M5S)</i>. Signora Presidente, intervengo sul PNRR. <i>(Applausi)</i>.</p>
<p style="text-align:justify">Colleghi, dobbiamo riprendere la discussione.</p>
<p style="text-align:center">Allegato A</p>
<p style="text-align:justify">{L.format(1, "ROSSI")}. Fuori dal resoconto.</p>
</body></html>""".encode()


class TestSenatoResocontoWeb(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(PAGINA, {"chiave": "leg19-senato-sed0212"})
        self.sp = [n for n in self.r["nodi"] if n["label"] == "Speech"]
        self.testi = {t["ref"]: t["text"] for t in self.r["testi"]}
        self.by = {a["from"]: a["to"] for a in self.r["archi"] if a["type"] == "BY"}

    def test_seduta(self):
        s = self.r["nodi"][0]
        self.assertEqual((s["uri"], s["date"], s["source"]), ("it:senato:19:sed0212", "2024-07-30", "senato_html"))

    def test_interventi(self):
        self.assertEqual([n["speaker_label"] for n in self.sp], ["PRESIDENTE", "DAMANTE", "PRESIDENTE", "DAMANTE"])
        self.assertEqual(self.testi[self.sp[0]["text_ref"]], "La seduta è aperta.")
        damante = self.sp[3]
        self.assertEqual(self.testi[damante["text_ref"]], "Signora Presidente, intervengo sul PNRR.\n\nColleghi, dobbiamo riprendere la discussione.")
        self.assertEqual((damante["declared_group"], self.by[damante["uri"]]), ("M5S", "it:person:senato:36391"))
        self.assertEqual(self.by[self.sp[2]["uri"]], "it:person:senato:29067")    # il Presidente senza link: l'ultimo con link

    def test_punto_e_ddl(self):
        self.assertIn({"type": "ABOUT", "from": "it:senato:19:sed0212:tit00002", "to_ref": "ddl:1162"}, self.r["archi"])
        self.assertTrue(any(n["label"] == "Reaction" and n["raw"] == "Applausi" for n in self.r["nodi"]))

    def test_controlli(self):
        righe = [{"tipo": "nodo", **n} for n in self.r["nodi"]] + [{"tipo": "arco", **a} for a in self.r["archi"]] + [{"tipo": "testo", **t} for t in self.r["testi"]]
        self.assertEqual(_regole(righe), [])


# una didascalia in testa al primo paragrafo non è il gruppo (sedute 277, 152 e 444): diventa una reazione
DIDASCALIE = f"""<an:akomaNtoso {NS}><an:debate><an:meta><an:identification><an:FRBRWork><an:FRBRdate date="2025-03-18" name="presentazione"/>
<an:FRBRnumber value="277"/></an:FRBRWork></an:identification><an:references>
<an:TLCPerson id="p1275" href="http://dati.senato.it/senato/Persona/1275" showAs="x"/><an:TLCRole id="pres" href="/x" showAs="Presidente"/></an:references></an:meta><an:debateBody>
<an:debateSection id="d1" name="x"><an:heading>Sul lutto del senatore Occhiuto</an:heading>
<an:speech by="#p1275" as="#pres"><an:from refersTo="#p1275">PRESIDENTE</an:from>
<an:p>. <an:i>(Il Presidente e l'Assemblea si levano in piedi)</an:i>. Onorevoli senatori, vorrei a nome di tutti voi rivolgere un commosso pensiero.</an:p></an:speech>
<an:speech by="#p1275" as="#pres"><an:from refersTo="#p1275">PRESIDENTE</an:from>
<an:p>. La seduta è aperta <an:i>(ore 10,05)</an:i>.</an:p></an:speech>
<an:speech by="#p1275" as="#pres"><an:from refersTo="#p1275">PRESIDENTE</an:from>
<an:p>. Per favore, lasciamo parlare il collega. <an:i>(Vivi commenti)</an:i>. Per favore, lasciamo parlare il collega.</an:p></an:speech>
</an:debateSection></an:debateBody></an:debate></an:akomaNtoso>""".encode()


class TestSenatoDidascalie(unittest.TestCase):
    def test_non_gruppo(self):
        r = trasforma(DIDASCALIE, {"chiave": "leg19-senato-sed0277"})
        testi = {t["ref"]: t["text"] for t in r["testi"]}
        sp = [n for n in r["nodi"] if n["label"] == "Speech"]
        self.assertEqual([n["declared_group"] for n in sp], [None, None, None])
        self.assertTrue(all(a["as_group"] is None for a in r["archi"] if a["type"] == "BY"))
        self.assertTrue(testi[sp[0]["text_ref"]].startswith("Onorevoli senatori"))
        self.assertTrue(testi[sp[1]["text_ref"]].startswith("La seduta è aperta"))
        raw = [n["raw"] for n in r["nodi"] if n["label"] == "Reaction"]
        self.assertEqual(raw, ["Il Presidente e l'Assemblea si levano in piedi", "ore 10,05", "Vivi commenti"])

    def test_sigla(self):
        for g in ("FdI", "PD-IDP", "M5S", "LSP-PSd'Az", "LSP- PSd'Az", "Misto", "Misto-AVS", "Misto-Avanti PSI", "Misto-PRC-SE-OS",
                  "Aut (SVP-Patt, Cb, SCN)", "Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP", "Cd'I-NM (UDC-CI-NcI-IaC)-MAIE", "IV-C-RE"):
            self.assertTrue(sigla(g), g)
        for d in ("ore 10,05", "Il Presidente e l'Assemblea si levano in piedi", "Reiterate proteste", "Vivi commenti", "Agevolazioni tariffarie",
                  "Si leva in piedi", "L'Assemblea osserva un minuto di silenzio", "Prolungati applausi", "Pausa", "Interruzioni", "2025"):
            self.assertFalse(sigla(d), d)


if __name__ == "__main__":
    unittest.main()
