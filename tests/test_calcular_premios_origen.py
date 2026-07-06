import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import calcular_premios as cp


class PuedeMejorarseConJugadaRealTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original_quinielas = cp.QUINIELAS_JUGADAS
        cp.QUINIELAS_JUGADAS = Path(self._tmp.name) / "quinielas_jugadas.json"

    def tearDown(self):
        cp.QUINIELAS_JUGADAS = self._original_quinielas
        self._tmp.cleanup()

    def _escribir_jugada(self, jornada):
        cp.QUINIELAS_JUGADAS.write_text(
            json.dumps({"jugadas": [{"jornada": jornada, "signos": ["1"] * 14, "elige8": []}]}),
            encoding="utf-8",
        )

    def test_true_si_hay_jugada_real_y_el_registro_no_viene_de_ahi(self):
        self._escribir_jugada(70)
        entry = {"origen_prediccion": "data/predicciones/jornada_70.json", "aciertos": 9}
        self.assertTrue(cp.puede_mejorarse_con_jugada_real(entry, 70))

    def test_false_si_el_registro_ya_viene_de_quinielas_jugadas(self):
        self._escribir_jugada(70)
        entry = {"origen_prediccion": "data/quinielas_jugadas.json", "aciertos": 12}
        self.assertFalse(cp.puede_mejorarse_con_jugada_real(entry, 70))

    def test_false_si_no_hay_jugada_real_registrada(self):
        cp.QUINIELAS_JUGADAS.write_text(json.dumps({"jugadas": []}), encoding="utf-8")
        entry = {"origen_prediccion": "data/predicciones/jornada_71.json", "aciertos": 13}
        self.assertFalse(cp.puede_mejorarse_con_jugada_real(entry, 71))

    def test_true_si_el_registro_no_tiene_origen_prediccion_en_absoluto(self):
        """Registros antiguos (de antes de que existiera este campo) tambien deben poder mejorarse."""
        self._escribir_jugada(70)
        entry = {"aciertos": 9}
        self.assertTrue(cp.puede_mejorarse_con_jugada_real(entry, 70))


class LeerPrediccionJornadaOrigenTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._originales = {
            "QUINIELAS_JUGADAS": cp.QUINIELAS_JUGADAS,
            "HISTORIAL_QUINIELAS": cp.HISTORIAL_QUINIELAS,
            "PREDICCIONES": cp.PREDICCIONES,
        }
        cp.QUINIELAS_JUGADAS = tmp / "quinielas_jugadas.json"
        cp.HISTORIAL_QUINIELAS = tmp / "historial_quinielas.json"
        cp.PREDICCIONES = tmp / "predicciones"
        cp.PREDICCIONES.mkdir()

    def tearDown(self):
        for clave, valor in self._originales.items():
            setattr(cp, clave, valor)
        self._tmp.cleanup()

    def test_prioriza_quinielas_jugadas_y_marca_su_origen(self):
        cp.QUINIELAS_JUGADAS.write_text(
            json.dumps({"jugadas": [{"jornada": 70, "signos": ["1X"] + ["1"] * 13, "elige8": []}]}),
            encoding="utf-8",
        )
        prediccion = cp.leer_prediccion_jornada(70)
        self.assertEqual(prediccion.get("origen_prediccion"), "data/quinielas_jugadas.json")
        self.assertEqual(prediccion["partidos"][0]["signo_final"], "1X")

    def test_sin_jugada_real_cae_al_archivo_de_prediccion_y_lo_marca(self):
        cp.QUINIELAS_JUGADAS.write_text(json.dumps({"jugadas": []}), encoding="utf-8")
        cp.HISTORIAL_QUINIELAS.write_text(json.dumps({"jornadas": []}), encoding="utf-8")
        (cp.PREDICCIONES / "jornada_70.json").write_text(
            json.dumps({"jornada": 70, "partidos": [{"num": 1, "signo_final": "2"}]}),
            encoding="utf-8",
        )
        prediccion = cp.leer_prediccion_jornada(70)
        self.assertEqual(prediccion.get("origen_prediccion"), "data/predicciones/jornada_70.json")


class PremioMulticolumnaImplausibleTests(unittest.TestCase):
    def test_true_si_supera_el_limite_plausible(self):
        entry = {"fuente_premio": "multicolumna_loteriaanta", "premio_eur": 244034.14}
        self.assertTrue(cp.premio_multicolumna_implausible(entry))

    def test_false_si_esta_dentro_del_limite(self):
        entry = {"fuente_premio": "multicolumna_loteriaanta", "premio_eur": 123.45}
        self.assertFalse(cp.premio_multicolumna_implausible(entry))

    def test_false_si_no_viene_de_multicolumna(self):
        entry = {"fuente_premio": "labrujadeoro", "premio_eur": 999999.0}
        self.assertFalse(cp.premio_multicolumna_implausible(entry))

    def test_revertir_resetea_el_premio_implausible_a_pendiente(self):
        historial = {"jornadas": [
            {"jornada": 70, "fuente_premio": "multicolumna_loteriaanta", "premio_eur": 244034.14, "aciertos": 12}
        ]}
        cambios = cp.revertir_estimados_y_labruja_invalidos(historial)
        self.assertEqual(cambios, 1)
        entry = historial["jornadas"][0]
        self.assertEqual(entry["premio_eur"], 0.0)
        self.assertEqual(entry["fuente_premio"], "pendiente")


if __name__ == "__main__":
    unittest.main()
