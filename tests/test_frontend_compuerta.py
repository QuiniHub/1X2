import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


class FrontendCompuertaTests(unittest.TestCase):
    def test_frontend_carga_fuentes_reales_del_nuevo_diseno(self):
        html = INDEX.read_text(encoding="utf-8")

        self.assertIn("data/predicciones/ultima_prediccion.json", html)
        self.assertIn("data/predicciones/pleno15_jornada_actual.json", html)
        self.assertIn("data/memoria_ia/diario_aprendizaje.json", html)
        self.assertIn("data/premios/historial_premios.json", html)
        self.assertIn("data/memoria_ia/metricas_probabilisticas.json", html)
        self.assertIn("data/jornadas/jornada_", html)

    def test_frontend_genera_boleto_con_animacion_desde_prediccion(self):
        html = INDEX.read_text(encoding="utf-8")

        self.assertIn("generated: false", html)
        self.assertIn("function predictionMatches()", html)
        self.assertIn("function renderTicket()", html)
        self.assertIn("function animateTicket()", html)
        self.assertIn("data-selected", html)
        self.assertIn("data-sign", html)
        self.assertIn("No hay partidos cargados todavía.", html)
        self.assertIn("generateBtn", html)
        self.assertRegex(
            html,
            re.compile(
                r"qs\('#generateBtn'\)\.addEventListener\('click',\s*animateTicket\)",
                re.S,
            ),
        )
        self.assertRegex(
            html,
            re.compile(
                r"chosen\.includes\(sign\.dataset\.sign\)",
                re.S,
            ),
        )

    def test_frontend_pleno15_historial_aprendizaje_y_metricas_actuales(self):
        html = INDEX.read_text(encoding="utf-8")

        self.assertIn("function extractPleno15(data)", html)
        self.assertIn("Number(p.num ?? p.numero ?? 0) === 15", html)
        self.assertIn("function latestLearningEntries()", html)
        self.assertIn("a.entradas", html)
        self.assertIn("function rowPrize(row)", html)
        self.assertIn("row.premio_eur", html)
        self.assertIn("Premio cobrado", html)
        self.assertIn("Acumulado total", html)
        self.assertIn("m.precision", html)
        self.assertIn("m.jornadas_evaluadas", html)


if __name__ == "__main__":
    unittest.main()
