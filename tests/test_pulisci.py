import unittest

from api.pulisci import pulisci


class TestPulisci(unittest.TestCase):
    def test_via_gli_script(self):
        for cattivo in ('<img src=x onerror="alert(1)">', "<script>alert(1)</script>", '<a href="javascript:alert(1)">x</a>',
                        '<a href=" jav&#x61;script:alert(1)">x</a>', '<svg onload="alert(1)"></svg>', '<iframe src="https://x"></iframe>',
                        '<div style="background:url(javascript:alert(1))">x</div>', '<a href="data:text/html,<script>">x</a>',
                        '<details open ontoggle="alert(1)">', '<form action="/x"><input name="q"></form>'):
            pulito = pulisci(cattivo).lower()
            for parola in ("onerror", "onload", "ontoggle", "<script", "javascript:", "<iframe", "url(", "data:", "<form", "<input"):
                self.assertNotIn(parola, pulito, cattivo)

    def test_restano_le_risposte(self):
        buono = ('<section class="blocco" data-tip="Fonte"><h3>Voti</h3><p>Il <a href="https://www.camera.it/leg19/410?idSeduta=0180&amp;tipo=stenografico" '
                 'target="_blank" rel="noopener">resoconto</a> e la <a href="#/strumenti/deputato/307926">scheda</a>.</p>'
                 '<svg class="ic" viewBox="0 0 24 24"><path d="M5 12l5 5" stroke="currentColor"/></svg>'
                 '<div class="bv"><i style="width:40%;background:#1d6b4a"></i></div><img src="/dati/foto/senatori/1.jpg" alt=""></section>')
        p = pulisci(buono)
        for pezzo in ('href="https://www.camera.it/leg19/410?idSeduta=0180&amp;tipo=stenografico"', 'href="#/strumenti/deputato/307926"',
                      'data-tip="Fonte"', 'viewbox="0 0 24 24"', 'd="M5 12l5 5"', 'style="width:40%;background:#1d6b4a"',
                      'src="/dati/foto/senatori/1.jpg"', "<h3>Voti</h3>"):
            self.assertIn(pezzo, p)


if __name__ == "__main__":
    unittest.main()
