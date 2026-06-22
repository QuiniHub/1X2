import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


class FrontendCompuertaTests(unittest.TestCase):
    def test_frontend_no_genera_boleto_sin_prediccion_backend_autorizada(self):
        html = INDEX.read_text(encoding="utf-8")

        self.assertIn("function prediccionBackendBloqueada", html)
        self.assertIn("prediccionBackend.prediccion_disponible === false", html)
        self.assertIn("prediccionBackend.publicar_prediccion === false", html)
        self.assertIn("prediccionBackend.prediccion_permitida === false", html)
        self.assertIn("mostrarPrediccionNoAutorizada(prediccionBackend);", html)
        self.assertRegex(
            html,
            re.compile(
                r"if \(!hayPrediccionBackend\)\s*\{\s*"
                r"mostrarPrediccionNoAutorizada\(prediccionBackend\);\s*"
                r"return;\s*\}",
                re.S,
            ),
        )


if __name__ == "__main__":
    unittest.main()
