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
        entry = {"fuente_premio": "multicolumna_loteriaanta", "premio_eur": 5000000.0}
        self.assertTrue(cp.premio_multicolumna_implausible(entry))

    def test_false_si_esta_dentro_del_limite(self):
        entry = {"fuente_premio": "multicolumna_loteriaanta", "premio_eur": 123.45}
        self.assertFalse(cp.premio_multicolumna_implausible(entry))

    def test_false_si_no_viene_de_multicolumna(self):
        entry = {"fuente_premio": "labrujadeoro", "premio_eur": 999999.0}
        self.assertFalse(cp.premio_multicolumna_implausible(entry))

    def test_revertir_resetea_el_premio_implausible_a_pendiente(self):
        historial = {"jornadas": [
            {"jornada": 70, "fuente_premio": "multicolumna_loteriaanta", "premio_eur": 5000000.0, "aciertos": 12}
        ]}
        cambios = cp.revertir_estimados_y_labruja_invalidos(historial)
        self.assertEqual(cambios, 1)
        entry = historial["jornadas"][0]
        self.assertEqual(entry["premio_eur"], 0.0)
        self.assertEqual(entry["fuente_premio"], "pendiente")


class BuscarTablaPremiosLosillaTests(unittest.TestCase):
    """Usa el HTML real (simplificado) del escrutinio de la jornada 70 de
    eduardolosilla.es, con los importes oficiales reales de esa jornada."""

    HTML_JORNADA_70 = """
    <table>
      <tr><th>Aciertos</th><th>Acertantes</th><th>Euros</th></tr>
      <tr><td>15</td><td>4</td><td>17.119,56 €</td></tr>
      <tr><td>14</td><td>48</td><td>3.043,48 €</td></tr>
      <tr><td>13</td><td>1.084</td><td>63,17 €</td></tr>
      <tr><td>12</td><td>7.805</td><td>8,77 €</td></tr>
      <tr><td>11</td><td>33.788</td><td>2,03 €</td></tr>
      <tr><td>10</td><td>99.928</td><td>0,00 €</td></tr>
      <tr><td>Elige 8</td><td>775</td><td>25,73 €</td></tr>
    </table>
    """

    def setUp(self):
        self._original_descargar = cp.descargar_html
        cp.descargar_html = lambda url, params=None: self.HTML_JORNADA_70

    def tearDown(self):
        cp.descargar_html = self._original_descargar

    def test_extrae_los_importes_reales_de_todas_las_categorias(self):
        tabla = cp.buscar_tabla_premios_losilla(70)
        self.assertEqual(tabla.get("15"), 17119.56)
        self.assertEqual(tabla.get("14"), 3043.48)
        self.assertEqual(tabla.get("13"), 63.17)
        self.assertEqual(tabla.get("12"), 8.77)
        self.assertEqual(tabla.get("11"), 2.03)
        self.assertEqual(tabla.get("10"), 0.0)
        self.assertEqual(tabla.get("elige8"), 25.73)

    def test_el_calculo_multicolumna_con_esta_tabla_da_el_premio_real(self):
        """Con la distribucion real del boleto de J70 (30 columnas a 10
        aciertos, 12 a 11 y 2 a 12) y estos precios oficiales, el total debe
        ser 41.90e -el importe que realmente se cobro-."""
        tabla = cp.buscar_tabla_premios_losilla(70)
        dist_total = {10: 30, 11: 12, 12: 2}
        total = sum(tabla.get(str(k), 0) * n for k, n in dist_total.items())
        self.assertAlmostEqual(round(total, 2), 41.90, places=2)


class FilaContieneCategoriaTests(unittest.TestCase):
    def test_no_confunde_categoria_con_un_numero_mayor_que_la_contiene(self):
        """'11' no debe coincidir dentro de '17.119,56' (el premio de la
        categoria 15), o se cogeria la fila equivocada de la tabla."""
        self.assertFalse(cp.fila_contiene_categoria("15 4 17.119,56 €", 11))

    def test_si_reconoce_la_fila_real_de_la_categoria(self):
        self.assertTrue(cp.fila_contiene_categoria("11 33.788 2,03 €", 11))
        self.assertTrue(cp.fila_contiene_categoria("15 4 17.119,56 €", 15))


class LimiteCategoriaTests(unittest.TestCase):
    def test_categoria_15_tiene_limite_mucho_mas_alto(self):
        self.assertGreater(cp.limite_categoria(15), cp.limite_categoria(12))
        self.assertGreaterEqual(cp.limite_categoria(15), 17119.56)

    def test_otras_categorias_usan_el_limite_normal(self):
        for cat in (10, 11, 12, 13, 14):
            self.assertEqual(cp.limite_categoria(cat), cp.PREMIO_CATEGORIA_MAXIMO_PLAUSIBLE)


if __name__ == "__main__":
    unittest.main()
