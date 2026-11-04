"""Caricamento in Postgres con un psql finto: comando e credenziali, prova del database, registro file per file,
quarantena, tempo del caricamento, schema solo se cambiato, gruppi nei voti dopo l'anagrafica."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from pipeline.carica import postgres
from pipeline.controlli import uscite
from pipeline.orchestra import Contesto


def dossier(uri: str, titolo: str | None = "Titolo") -> str:
    righe = [{"tipo": "ambito", "kind": "dossier", "source_key": uri}, {"tipo": "nodo", "label": "Document", "uri": uri, "title": titolo, "date": "2024-01-01"}]
    return "\n".join(json.dumps(r) for r in righe) + "\n"


class PsqlFinto:
    def __init__(self, guasti=()):
        self.script, self.guasti = [], set(guasti)

    def __call__(self, script, timeout=900):
        self.script.append(script)
        if any(g in script for g in self.guasti):
            raise RuntimeError("ERROR: guasto finto")
        return ""

    def caricati(self) -> list[str]:
        return [u for s in self.script for u in ("d1", "d2", "d3", "d4") if f"'{u}'" in s and s.startswith("BEGIN")]


class TestComandoPsql(unittest.TestCase):
    def test_locale_senza_pghost(self):
        with mock.patch.object(postgres, "env", lambda n, p=None: p if p is not None else ""):
            cmd, amb = postgres.comando_psql()
        self.assertEqual(cmd[:5], ["docker", "compose", "exec", "-T", "testi"])
        self.assertIsNone(amb)

    def test_remoto_password_solo_nell_ambiente(self):
        valori = {"PGHOST": "db.esempio", "PGPORT": "6543", "PGPASSWORD": "segreta", "PGSSLMODE": "require"}
        finto_env = lambda n, p=None: valori.get(n, p if p is not None else "")
        with mock.patch.object(postgres, "env", finto_env), mock.patch.object(postgres.shutil, "which", lambda x: "/usr/bin/psql"):
            cmd, amb = postgres.comando_psql()
            self.assertEqual(postgres.destinazione(), "db.esempio:6543")
        self.assertEqual(cmd[0], "psql")
        self.assertNotIn("segreta", " ".join(cmd))
        self.assertEqual((amb["PGPASSWORD"], amb["PGHOST"], amb["PGUSER"]), ("segreta", "db.esempio", "parliamentrag"))
        with mock.patch.object(postgres, "env", finto_env), mock.patch.object(postgres.shutil, "which", lambda x: None):
            cmd, amb = postgres.comando_psql()
        self.assertEqual(cmd[:4], ["docker", "run", "--rm", "-i"])
        self.assertIn(postgres.IMMAGINE_PSQL, cmd)
        self.assertIn("PGPASSWORD", cmd)                     # il nome sì, il valore no
        self.assertNotIn("segreta", " ".join(cmd))

    def test_prova_ferma_se_il_database_non_risponde(self):
        with mock.patch.object(postgres, "psql", PsqlFinto(guasti=["SELECT 1"])):
            with self.assertRaises(RuntimeError):
                postgres.prova()
        with mock.patch.object(postgres, "psql", PsqlFinto()):
            postgres.prova()


class TestCarica(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cartella = Path(self.tmp.name)
        self.uscite = self.cartella / "uscite" / "v3" / "camera_dossier"
        self.uscite.mkdir(parents=True)
        self.ctx = Contesto("g1", self.cartella, {"carica": {"tempo_minuti": 60}}, {})
        self.schema = mock.patch.object(postgres, "applica_schema", lambda r: "invariato")
        self.schema.start()
        self.dest = mock.patch.object(postgres, "destinazione", lambda: "locale")
        self.dest.start()

    def tearDown(self):
        self.schema.stop()
        self.dest.stop()
        self.tmp.cleanup()

    def scrivi(self, nome: str, testo: str) -> Path:
        f = self.uscite / nome
        f.write_text(testo)
        return f

    def carica(self, finto: PsqlFinto) -> dict:
        with mock.patch.object(postgres, "psql", finto):
            return postgres.carica(self.ctx)

    def test_quarantena_e_gli_altri_vanno_avanti(self):
        self.scrivi("d1.jsonl", dossier("d1"))
        self.scrivi("d2.jsonl", dossier("d2", titolo=None))      # non passa i controlli
        self.scrivi("d3.jsonl", dossier("d3"))                   # non si carica
        finto = PsqlFinto(guasti=["'d3'"])
        r = self.carica(finto)
        self.assertEqual(r["sedute_caricati"], 1)
        self.assertEqual(r["in_quarantena"], 2)
        self.assertIn("avviso", r)
        self.assertEqual(finto.caricati(), ["d1", "d3"])
        reg = postgres.Registro(self.cartella, "locale")
        self.assertEqual({q["percorso"]: q["fase"] for q in reg.quarantena()},
                         {"camera_dossier/d2.jsonl": "controllo", "camera_dossier/d3.jsonl": "caricamento"})
        # al giro dopo: d1 non si ricarica, d3 si riprova, d2 resta fuori finché non cambia
        finto = PsqlFinto()
        r = self.carica(finto)
        self.assertEqual(finto.caricati(), ["d3"])
        self.assertEqual(r["in_quarantena"], 1)
        self.scrivi("d2.jsonl", dossier("d2"))
        uscite.controlla(self.ctx)                               # i controlli lo tolgono dalla quarantena
        finto = PsqlFinto()
        self.carica(finto)
        self.assertEqual(finto.caricati(), ["d2"])
        self.assertEqual(reg.quarantena(), [])

    def test_file_cambiato_si_ricarica_invariato_no(self):
        f = self.scrivi("d1.jsonl", dossier("d1"))
        self.carica(PsqlFinto())
        os.utime(f, None)                                       # riscritto uguale: data nuova, stessa impronta
        finto = PsqlFinto()
        self.carica(finto)
        self.assertEqual(finto.caricati(), [])
        self.scrivi("d1.jsonl", dossier("d1", titolo="Altro titolo"))
        finto = PsqlFinto()
        self.carica(finto)
        self.assertEqual(finto.caricati(), ["d1"])

    def test_tempo_finito_riprende_al_giro_dopo(self):
        for u in ("d1", "d2"):
            self.scrivi(f"{u}.jsonl", dossier(u))
        self.ctx.config["carica"]["tempo_minuti"] = -1
        finto = PsqlFinto()
        r = self.carica(finto)
        self.assertEqual((finto.caricati(), r["rimandati"]), ([], 2))
        self.assertIn("avviso", r)
        self.ctx.config["carica"]["tempo_minuti"] = 60
        finto = PsqlFinto()
        self.carica(finto)
        self.assertEqual(finto.caricati(), ["d1", "d2"])

    def test_segno_vecchio_vale_come_caricato(self):
        self.scrivi("d1.jsonl", dossier("d1"))
        (self.cartella / "uscite" / ".postgres.ultimo").write_text(str(time.time() + 10))
        finto = PsqlFinto()
        self.carica(finto)
        self.assertEqual(finto.caricati(), [])

    def test_cinque_errori_di_fila_provano_il_database(self):
        for i in range(5):
            self.scrivi(f"e{i}.jsonl", dossier(f"e{i}"))
        finto = PsqlFinto(guasti=["BEGIN", "SELECT 1"])
        with self.assertRaises(RuntimeError):
            self.carica(finto)

    def test_ordine_anagrafica_poi_governo_poi_atti(self):
        nomi = ["leg19-sed0001.jsonl", "leg19-atti.jsonl", "leg19-governo.jsonl", "leg19-anagrafica.jsonl", "leg19-aic-202301.jsonl"]
        self.assertEqual([f.name for f in sorted((Path(n) for n in nomi), key=postgres.ordine)],
                         ["leg19-anagrafica.jsonl", "leg19-governo.jsonl", "leg19-aic-202301.jsonl", "leg19-atti.jsonl", "leg19-sed0001.jsonl"])


class TestSchemaEGruppi(unittest.TestCase):
    def test_schema_solo_se_cambiato_e_con_lock_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            reg = postgres.Registro(Path(d), "locale")
            finto = PsqlFinto()
            with mock.patch.object(postgres, "psql", finto):
                self.assertEqual(postgres.applica_schema(reg), "applicato")
                self.assertEqual(postgres.applica_schema(reg), "invariato")
            self.assertEqual(len(finto.script), 1)
            self.assertTrue(finto.script[0].startswith("SET lock_timeout = '5s';"))
            with mock.patch.object(postgres, "psql", PsqlFinto(guasti=["lock_timeout"])):
                reg.scrivi("schema", "")
                with self.assertRaises(RuntimeError):
                    postgres.applica_schema(reg)
                self.assertEqual(reg.leggi("schema"), "")      # non applicato: si riprova al giro dopo

    def test_gruppi_nei_voti_dopo_l_anagrafica(self):
        senato = postgres.script_gruppi_voti("senato", 19)
        self.assertIn("group_at(b2.person, v.date)", senato)
        self.assertIn("v.chamber = 'senato'", senato)
        self.assertNotIn("b2.grp IS NULL", senato)
        camera = postgres.script_gruppi_voti("camera", 19)
        self.assertIn("b2.grp IS NULL", camera)                # alla Camera il gruppo lo dà la fonte: si completa e basta
        righe = [{"tipo": "ambito", "kind": "anagrafica", "chamber": "senato", "legislature": 19}]
        finto = PsqlFinto()
        with mock.patch.dict(postgres.SCRIPT, {"anagrafica": (lambda r: "BEGIN; ANAGRAFICA; COMMIT;", "anagrafiche_e_atti")}), \
                mock.patch.object(postgres, "psql", finto):
            self.assertEqual(postgres.carica_righe(righe), "anagrafiche_e_atti")
        self.assertEqual(len(finto.script), 2)
        self.assertIn("UPDATE ballot", finto.script[1])


if __name__ == "__main__":
    unittest.main()
