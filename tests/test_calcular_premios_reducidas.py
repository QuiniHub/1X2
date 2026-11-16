import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import calcular_premios as cp


class PremiosReducidasYDeclaradosTests(unittest.TestCase):
    """Auditoria 16/11/2026: el historial valoraba las reducidas como si fueran
    el desarrollo directo (J16 285,70 vs 24,26 reales; J18 672,54 vs 0; J20
    103,98 vs 6,82). El premio declarado por Marc en quinielas_jugadas manda, y
    una reducida sin premio declarado queda pendiente, nunca estimada."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = cp.QUINIELAS_JUGADAS
        cp.QUINIELAS_JUGADAS = Path(self._tmp.name) / "quinielas_jugadas.json"
        cp.QUINIELAS_JUGADAS.write_text(json.dumps({"jugadas": [
            {"jornada": 16, "signos": ["1"] * 14, "modalidad": "multiple_reducida_64_reduccion_cuarta_2T_6D", "premio_eur": 24.26},
            {"jornada": 18, "signos": ["1"] * 14, "modalidad": "losilla_reducida_super13_7T_1D_333_columnas"},
            {"jornada": 19, "signos": ["1"] * 14, "modalidad": "losilla_multiple_directa_2T_2D_36_apuestas"},
            {"jornada": 17, "signos": ["1"] * 14, "modalidad": "multiple_reducida_64_reduccion_cuarta_2T_6D", "premio_eur": 0.0},
        ]}), encoding="utf-8")

    def tearDown(self):
        cp.QUINIELAS_JUGADAS = self._original
        self._tmp.cleanup()

    def test_premio_declarado_se_lee_incluido_el_cero(self):
        self.assertEqual(cp.premio_declarado_en_jugada(16), 24.26)
        self.assertEqual(cp.premio_declarado_en_jugada(17), 0.0)
        self.assertIsNone(cp.premio_declarado_en_jugada(18))
        self.assertIsNone(cp.premio_declarado_en_jugada(99))

    def test_modalidad_reducida_se_detecta(self):
        self.assertTrue(cp.jugada_es_reducida(16))
        self.assertTrue(cp.jugada_es_reducida(18))
        self.assertFalse(cp.jugada_es_reducida(19))
        self.assertFalse(cp.jugada_es_reducida(99))

    def test_registro_multicolumna_de_una_reducida_esta_desalineado(self):
        entry = {"fuente_premio": "multicolumna_loteriaanta", "premio_eur": 672.54}
        self.assertTrue(cp.premio_desalineado_con_jugada(entry, 18))
        self.assertTrue(cp.premio_desalineado_con_jugada(entry, 16))   # ademas hay declarado
        directa = {"fuente_premio": "multicolumna_loteriaanta", "premio_eur": 3.41}
        self.assertFalse(cp.premio_desalineado_con_jugada(directa, 19))
        ok = {"fuente_premio": "confirmado_usuario", "premio_eur": 24.26}
        self.assertFalse(cp.premio_desalineado_con_jugada(ok, 16))

    def test_refrescar_usa_el_declarado_y_borra_el_desglose_directo(self):
        entry = {"jornada": 16, "aciertos": 12, "fuente_premio": "multicolumna_loteriaanta",
                 "premio_eur": 285.7, "desglose_columnas": {"columnas_totales": 576}}
        self.assertTrue(cp.refrescar_premio_real(entry))
        self.assertEqual(entry["premio_eur"], 24.26)
        self.assertEqual(entry["fuente_premio"], "confirmado_usuario")
        self.assertNotIn("desglose_columnas", entry)

    def test_refrescar_no_valora_una_reducida_sin_declarar(self):
        llamadas = []
        original = cp.buscar_tabla_premios_losilla
        cp.buscar_tabla_premios_losilla = lambda jornada: llamadas.append(jornada) or None
        try:
            entry = {"jornada": 18, "aciertos": 13, "fuente_premio": "multicolumna_loteriaanta", "premio_eur": 672.54}
            self.assertTrue(cp.refrescar_premio_real(entry))
            self.assertEqual(entry["premio_eur"], 0.0)
            self.assertEqual(entry["fuente_premio"], "pendiente_reducida")
            self.assertFalse(cp.refrescar_premio_real(entry))  # ya esta marcada: no insiste
            self.assertEqual(llamadas, [])  # nunca fue a buscar tablas para estimar
        finally:
            cp.buscar_tabla_premios_losilla = original


if __name__ == "__main__":
    unittest.main()
