import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


class FrontendCompuertaTests(unittest.TestCase):
    def test_frontend_no_genera_boleto_sin_prediccion_backend_cargada(self):
        html = INDEX.read_text(encoding="utf-8")

        self.assertIn("data/predicciones/ultima_prediccion.json", html)
        self.assertIn("generated: false", html)
        self.assertIn("const matches = (state.prediccion?.partidos || [])", html)
        self.assertIn("No hay partidos cargados todavía.", html)
        self.assertIn("generateBtn", html)
        self.assertIn("animateTicket", html)
        self.assertRegex(
            html,
            re.compile(
                r"qs\('#generateBtn'\)\.addEventListener\('click',\s*animateTicket\)",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
