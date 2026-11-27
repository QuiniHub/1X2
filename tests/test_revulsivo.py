import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import motor_prediccion_quiniela as motor
from motor_prediccion_quiniela import ajustar_por_revulsivo

_EFECTOS_ORIGINAL = None


def setUpModule():
    # Efectos del estudio base fijados para todo el modulo: sin esto el primer
    # test leia data/memoria_ia/efecto_revulsivo.json (lo regenera el
    # meta-aprendizaje) y una re-estimacion de signo contrario habria dado la
    # vuelta a los assertGreater/assertLess sin que el codigo estuviera roto.
    global _EFECTOS_ORIGINAL
    _EFECTOS_ORIGINAL = motor._EFECTOS_REVULSIVO_CACHE
    motor._EFECTOS_REVULSIVO_CACHE = (
        motor.EFECTO_REVULSIVO_DEBUT_FUERA, motor.EFECTO_REVULSIVO_DEBUT_CASA)


def tearDownModule():
    motor._EFECTOS_REVULSIVO_CACHE = _EFECTOS_ORIGINAL


CESES = [{
    "equipo": "Valencia CF",
    "fecha_cese": "2026-09-13",
    "interino": "Oscar Sanchez",
    "fecha_nuevo": "2026-09-23",
    "nuevo": "Javier Aguirre",
}]
PROBS = {"1": 44.0, "X": 29.0, "2": 27.0}


class RevulsivoTests(unittest.TestCase):
    def test_debut_fuera_sube_el_signo_del_tecnico_nuevo(self):
        partido = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(
            PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0
        )
        self.assertTrue(traza["activo"])
        self.assertEqual(traza["lado"], "visitante")
        self.assertEqual(traza["etapa"], "debut")
        self.assertGreater(p["2"], PROBS["2"])
        self.assertLess(p["1"], PROBS["1"])
        self.assertIn("FUERA", lecturas[0])
        self.assertAlmostEqual(sum(p.values()), 100.0, delta=0.5)

    def test_debut_en_casa_recorta_al_equipo_del_tecnico_nuevo(self):
        partido = {"local": "Valencia CF", "visitante": "Sevilla FC", "fecha": "2026-10-11"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(
            PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0
        )
        self.assertTrue(traza["activo"])
        self.assertEqual(traza["lado"], "local")
        self.assertLess(p["1"], PROBS["1"])
        self.assertIn("CASA", lecturas[0])

    def test_segundo_partido_aplica_mitad_de_efecto(self):
        partido = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}
        completo, _, _, _ = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0)
        medio, _, _, traza = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 1)
        self.assertEqual(traza["etapa"], "2o partido")
        self.assertGreater(completo["2"], medio["2"])
        self.assertGreater(medio["2"], PROBS["2"])

    def test_efecto_agotado_con_dos_partidos_jugados(self):
        partido = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 2)
        self.assertFalse(traza["activo"])
        self.assertEqual(p, PROBS)

    def test_equipo_sin_cese_no_se_toca(self):
        partido = {"local": "FC Barcelona", "visitante": "Getafe CF", "fecha": "2026-10-10"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0)
        self.assertFalse(traza["activo"])
        self.assertEqual(p, PROBS)



class RevulsivoRutasPorDefectoTests(unittest.TestCase):
    """Caso real J12 (Racing-Valencia, debut de Aguirre fuera) por el camino
    SIN inyectar: fichero de ceses + calendarios leidos de disco. Antes este
    test leia data/memoria_ia/ceses_actuales.json y los calendarios vivos del
    repo, y habria tumbado el CI en cuanto el pipeline regenerase los ceses
    (auditoria 26/11, hallazgo 106). Ahora los datos son una copia fija en un
    directorio temporal y se redirigen las rutas del motor."""

    PARTIDO = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        (self.base / "memoria_ia").mkdir()
        (self.base / "memoria_ia" / "ceses_actuales.json").write_text(
            json.dumps({"ceses": CESES}), encoding="utf-8")
        self._guardado = (motor.DATA, motor.CESES_ACTUALES_PATH, motor._CAL_REVULSIVO_CACHE)
        motor.DATA = self.base
        motor.CESES_ACTUALES_PATH = self.base / "memoria_ia" / "ceses_actuales.json"
        motor._CAL_REVULSIVO_CACHE = None

    def tearDown(self):
        motor.DATA, motor.CESES_ACTUALES_PATH, motor._CAL_REVULSIVO_CACHE = self._guardado
        self._tmp.cleanup()

    def _calendario(self, partidos_valencia):
        (self.base / "calendario_primera.json").write_text(
            json.dumps({"jornadas": [{"partidos": partidos_valencia}]}), encoding="utf-8")
        (self.base / "calendario_segunda.json").write_text(
            json.dumps({"jornadas": [{"partidos": [
                {"local": "Real Racing Club de Santander", "visitante": "Cadiz CF",
                 "fecha": "2026-10-04", "resultado": "1-1"},
            ]}]}), encoding="utf-8")
        motor._CAL_REVULSIVO_CACHE = None

    def test_debut_detectado_leyendo_ceses_y_calendario_de_disco(self):
        # ultimo partido con resultado ANTES de la llegada del tecnico nuevo
        # (23/09) y el siguiente aun sin jugar: el 11/10 es su debut.
        self._calendario([
            {"local": "Valencia CF", "visitante": "Getafe CF", "fecha": "2026-09-20", "resultado": "0-2"},
            {"local": "Real Racing Club de Santander", "visitante": "Valencia CF",
             "fecha": "2026-10-11", "resultado": ""},
        ])
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(PROBS, self.PARTIDO)
        self.assertTrue(traza["activo"], "el debut de Aguirre fuera debe activar el revulsivo")
        self.assertEqual(traza["lado"], "visitante")
        self.assertEqual(traza["etapa"], "debut")
        self.assertGreater(p["2"], PROBS["2"])

    def test_un_partido_ya_jugado_con_el_nuevo_lo_deja_en_segundo_partido(self):
        self._calendario([
            {"local": "Valencia CF", "visitante": "Getafe CF", "fecha": "2026-09-20", "resultado": "0-2"},
            {"local": "Valencia CF", "visitante": "Sevilla FC", "fecha": "2026-09-27", "resultado": "2-1"},
        ])
        _, _, _, traza = ajustar_por_revulsivo(PROBS, self.PARTIDO)
        self.assertTrue(traza["activo"])
        self.assertEqual(traza["etapa"], "2o partido")

    def test_dos_partidos_ya_jugados_agotan_el_efecto(self):
        self._calendario([
            {"local": "Valencia CF", "visitante": "Sevilla FC", "fecha": "2026-09-27", "resultado": "2-1"},
            {"local": "Girona FC", "visitante": "Valencia CF", "fecha": "2026-10-04", "resultado": "0-0"},
        ])
        p, _, _, traza = ajustar_por_revulsivo(PROBS, self.PARTIDO)
        self.assertFalse(traza["activo"])
        self.assertEqual(p, PROBS)

    def test_sin_fichero_de_ceses_no_toca_nada(self):
        motor.CESES_ACTUALES_PATH = self.base / "memoria_ia" / "no_existe.json"
        p, _, _, traza = ajustar_por_revulsivo(PROBS, self.PARTIDO)
        self.assertFalse(traza["activo"])
        self.assertEqual(p, PROBS)


if __name__ == "__main__":
    unittest.main()
