import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_porcentajes_lae as apl


def _fuente_losilla(jornada=12, partidos=14, con_lae=True):
    lista = []
    for n in range(1, partidos + 1):
        partido = {
            "numero": n,
            "local": f"LOCAL{n}",
            "visitante": f"VISITANTE{n}",
            "probabilidades_signo": {"1": 45.0, "X": 30.0, "2": 25.0},
        }
        if con_lae:
            partido["fuentes_detalle"] = {"lae": {"1": 60, "X": 25, "2": 15}}
        lista.append(partido)
    return {"probabilidades": {"jornada": jornada, "partidos": lista}}


HTML_ESCRUTINIO = """
<html><body>
<p>Recaudación 3.500.149,50 € Bote 725.525,54 € Escrutinio de la Quiniela JORNADA 12</p>
<table>
<tr><td>15 Aciertos</td><td>0</td><td>0,00 €</td></tr>
<tr><td>14 Aciertos</td><td>32</td><td>17.500,75 €</td></tr>
<tr><td>13 Aciertos</td><td>1.033</td><td>254,13 €</td></tr>
<tr><td>12 Aciertos</td><td>11.292</td><td>23,25 €</td></tr>
<tr><td>11 Aciertos</td><td>67.200</td><td>3,91 €</td></tr>
<tr><td>10 Aciertos</td><td>240.653</td><td>0,00 €</td></tr>
<tr><td>Elige 8</td><td>1.623</td><td>36,52 €</td></tr>
</table>
</body></html>
"""


class PorcentajesDesdeLosillaTests(unittest.TestCase):
    def test_extrae_los_14_porcentajes_lae(self):
        captura = apl.porcentajes_desde_losilla(_fuente_losilla())
        self.assertEqual(captura["jornada"], 12)
        self.assertEqual(len(captura["partidos"]), 14)
        self.assertEqual(captura["partidos"][0]["porcentajes"], {"1": 60.0, "X": 25.0, "2": 15.0})

    def test_sin_columna_lae_devuelve_none(self):
        self.assertIsNone(apl.porcentajes_desde_losilla(_fuente_losilla(con_lae=False)))

    def test_con_menos_de_14_partidos_devuelve_none(self):
        self.assertIsNone(apl.porcentajes_desde_losilla(_fuente_losilla(partidos=10)))

    def test_ignora_el_pleno_al_15(self):
        fuente = _fuente_losilla()
        fuente["probabilidades"]["partidos"].append({
            "numero": 15, "local": "A", "visitante": "B",
            "fuentes_detalle": {"lae": {"1": 1, "X": 1, "2": 1}},
        })
        captura = apl.porcentajes_desde_losilla(fuente)
        self.assertEqual(len(captura["partidos"]), 14)


class ParsearEscrutinioTests(unittest.TestCase):
    def test_extrae_categorias_recaudacion_y_bote(self):
        datos = apl.parsear_escrutinio_html(HTML_ESCRUTINIO)
        self.assertEqual(datos["categorias"]["14"], {"acertantes": 32, "premio_eur": 17500.75})
        self.assertEqual(datos["categorias"]["11"], {"acertantes": 67200, "premio_eur": 3.91})
        self.assertAlmostEqual(datos["recaudacion_eur"], 3_500_149.50)
        self.assertAlmostEqual(datos["bote_eur"], 725_525.54)

    def test_html_sin_tabla_devuelve_none(self):
        self.assertIsNone(apl.parsear_escrutinio_html("<html><body>nada</body></html>"))

    def test_numero_es(self):
        self.assertEqual(apl._numero_es("3.500.149,50"), 3500149.5)
        self.assertEqual(apl._numero_es("1.033"), 1033.0)
        self.assertIsNone(apl._numero_es("sin numero"))


class GuardarPorcentajesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._base_original = apl.SALIDA_BASE
        apl.SALIDA_BASE = Path(self._tmp.name)

    def tearDown(self):
        apl.SALIDA_BASE = self._base_original
        self._tmp.cleanup()

    def test_guarda_y_conserva_escrutinio_previo(self):
        captura = apl.porcentajes_desde_losilla(_fuente_losilla())
        self.assertTrue(apl.guardar_porcentajes_jornada(captura, "2026_2027", "test"))
        destino = apl.ruta_porcentajes(12, "2026_2027")
        registro = json.loads(destino.read_text(encoding="utf-8"))
        registro["escrutinio"] = {"recaudacion_eur": 1.0}
        destino.write_text(json.dumps(registro), encoding="utf-8")
        self.assertTrue(apl.guardar_porcentajes_jornada(captura, "2026_2027", "test"))
        actualizado = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(actualizado["escrutinio"], {"recaudacion_eur": 1.0})

    def test_no_pisa_una_entrada_manual(self):
        destino = apl.ruta_porcentajes(12, "2026_2027")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"fuente": "manual", "partidos": []}), encoding="utf-8")
        captura = apl.porcentajes_desde_losilla(_fuente_losilla())
        self.assertFalse(apl.guardar_porcentajes_jornada(captura, "2026_2027", "test"))
        conservado = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(conservado["fuente"], "manual")


class TemporadaEtiquetaTests(unittest.TestCase):
    def test_agosto_pertenece_a_la_temporada_que_empieza(self):
        self.assertEqual(apl.temporada_etiqueta(datetime(2026, 8, 15)), "2026_2027")

    def test_mayo_pertenece_a_la_temporada_que_acaba(self):
        self.assertEqual(apl.temporada_etiqueta(datetime(2027, 5, 15)), "2026_2027")


if __name__ == "__main__":
    unittest.main()
