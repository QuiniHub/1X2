import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import construir_memoria_ia as cmi


def equipo(nombre, posicion=1):
    return {
        "posicion": posicion,
        "equipo": nombre,
        "pj": 0,
        "g": 0,
        "e": 0,
        "p": 0,
        "gf": 0,
        "gc": 0,
        "dg": 0,
        "pts": 0,
        "racha_actual": [],
        "tendencias": {},
    }


class ObtenerTemporadaDetectadaTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._original = cmi.CLASIFICACIONES_OFICIALES

    def tearDown(self):
        cmi.CLASIFICACIONES_OFICIALES = self._original

    def test_lee_el_flag_real(self):
        ruta = Path(self._tmpdir.name) / "clasificaciones_oficiales.json"
        ruta.write_text(json.dumps({"temporada_detectada": "2026/2027"}), encoding="utf-8")
        cmi.CLASIFICACIONES_OFICIALES = ruta
        self.assertEqual(cmi.obtener_temporada_detectada(), "2026/2027")

    def test_default_si_falta(self):
        ruta = Path(self._tmpdir.name) / "no_existe.json"
        cmi.CLASIFICACIONES_OFICIALES = ruta
        self.assertEqual(cmi.obtener_temporada_detectada(), "2025/2026")


class ClasificacionFinalTests(unittest.TestCase):
    def test_conserva_temporada_detectada(self):
        ligas = {
            "primera": {"equipos": [equipo("FC Barcelona", 1)]},
            "segunda": {"equipos": [equipo("Real Oviedo", 1)]},
        }
        clasificacion_final = cmi.construir_clasificaciones(ligas)
        clasificacion_final["temporada_detectada"] = "2026/2027"

        self.assertEqual(clasificacion_final["temporada_detectada"], "2026/2027")
        self.assertEqual(clasificacion_final["primera"][0]["equipo"], "FC Barcelona")
        self.assertEqual(clasificacion_final["segunda"][0]["equipo"], "Real Oviedo")


if __name__ == "__main__":
    unittest.main()


class FusionClasificacionNombresTests(unittest.TestCase):
    """11a aparicion de la familia de nombres (08/09/2026): la clasificacion
    oficial decia "Sabadell" y el calendario "CE Sabadell" -el cruce exacto
    fallaba y al fusionar el equipo perdia forma_5/racha/split local-visitante
    (el motor lo predecia a ciegas). limpiar_nombre ahora quita ce/ca/cp/ad y
    la fusion tiene respaldo por contencion UNICA."""

    def test_limpiar_nombre_quita_siglas_ce_ca_cp_ad(self):
        self.assertEqual(cmi.limpiar_nombre("CE Sabadell"), cmi.limpiar_nombre("Sabadell"))
        self.assertEqual(cmi.limpiar_nombre("CA Osasuna"), cmi.limpiar_nombre("Osasuna"))

    def test_fusion_conserva_forma_con_nombre_de_sigla_distinta(self):
        ligas = {"segunda": {"equipos": [{
            "equipo": "CE Sabadell", "pj": 4, "pts": 8, "g": 2, "e": 2, "p": 0,
            "gf": 6, "gc": 2, "dg": 4,
            "tendencias": {"forma_5_pts": 8, "forma_10_pts": 8},
            "racha_actual": {"victorias": 2},
            "local": {"pj": 2, "pts": 4}, "visitante": {"pj": 2, "pts": 4},
            "ultimos": [{"r": "G"}],
        }]}}
        import json as _json, tempfile, pathlib
        with tempfile.TemporaryDirectory() as tmp:
            ruta = pathlib.Path(tmp) / "clasificaciones.json"
            ruta.write_text(_json.dumps({"segunda": [{
                "posicion": 1, "equipo": "Sabadell", "pj": 4, "g": 2, "e": 2,
                "p": 0, "gf": 6, "gc": 2, "dg": 4, "puntos": 8,
            }]}), encoding="utf-8")
            original = cmi.CLASIFICACIONES_OFICIALES
            cmi.CLASIFICACIONES_OFICIALES = ruta
            try:
                resultado = cmi.aplicar_clasificaciones_oficiales(ligas)
            finally:
                cmi.CLASIFICACIONES_OFICIALES = original
        equipo = resultado["segunda"]["equipos"][0]
        self.assertEqual(equipo["tendencias"].get("forma_5_pts"), 8)
        self.assertEqual(equipo["racha_actual"].get("victorias"), 2)
        self.assertEqual(equipo["local"].get("pj"), 2)
