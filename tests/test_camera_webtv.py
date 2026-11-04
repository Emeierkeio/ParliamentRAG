"""L'indice del video di una seduta d'Aula si lega agli interventi del resoconto (seduta 735, evento 32715)."""

import unittest
from pathlib import Path

from pipeline.controlli.uscite import _regole_video
from pipeline.trasforma.camera_webtv import trasforma

CORPO = (Path(__file__).parent / "fixtures" / "webtv_evento_32715.htm.gz").read_bytes()


class TestWebtv(unittest.TestCase):
    def setUp(self):
        self.r = trasforma(CORPO, {"chiave": "leg19-webtv-evento-32715"})
        self.tratti = [a for a in self.r["archi"] if a["type"] == "HAS_VIDEO"]

    def test_video_della_seduta(self):
        v = self.r["nodi"][0]
        self.assertEqual((v["sitting"], v["event_id"], v["url"]), ("it:camera:19:sed0735", 32715, "https://webtv.camera.it/evento/32715"))

    def test_tratti_legati_alle_ancore(self):
        con_ancora = [a for a in self.tratti if a["anchor"]]
        self.assertGreater(len(con_ancora), 100)
        self.assertTrue(all(a["from"] == "it:camera:19:sed0735:" + a["anchor"] for a in con_ancora))
        self.assertTrue(all("_" not in a["anchor"] for a in con_ancora))  # tit00020_int00010 -> tit00020.int00010
        self.assertTrue(all(a["start"] <= a["end"] for a in con_ancora if a["start"] is not None and a["end"] is not None))

    def test_id_webtv_degli_interventi(self):
        # /evento/32715/601280 apre il video dove comincia il primo intervento
        self.assertEqual(self.tratti[0]["webtv_id"], 601280)
        self.assertTrue(all(isinstance(a["webtv_id"], int) for a in self.tratti))
        self.assertEqual(len({a["webtv_id"] for a in self.tratti}), len(self.tratti))

    def test_controlli(self):
        self.assertEqual(_regole_video(self.r["nodi"], self.tratti), [])


if __name__ == "__main__":
    unittest.main()
