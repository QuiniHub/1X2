import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import radar_tormenta as rt
import test_aud_P4_sombra_snapshot_util as util


def _partido(num=1, local="Cadiz CF", visitante="Levante UD", probs=None):
    return {
        "num": num,
        "local": local,
        "visitante": visitante,
        "probabilidades": probs or {"1": 55.0, "X": 25.0, "2": 20.0},
    }


def _prediccion(partidos=None, jornada=16):
    if partidos is None:
        partidos = [_partido(num=n) for n in range(1, 15)]
    return {"jornada": jornada, "partidos": partidos}


class EquiposCaosTests(unittest.TestCase):
    def test_eibar_femenino_si_y_masculino_no(self):
        self.assertTrue(rt.equipos_caos_en_partido("Eibar (F)", "Madrid CFF (F)"))
        # El SD Eibar masculino (1 solo tercero en J1-14) NO esta en la lista.
        self.assertEqual(rt.equipos_caos_en_partido("SD Eibar", "Tenerife"), [])

    def test_levante_solo_en_casa(self):
        self.assertTrue(rt.equipos_caos_en_partido("Levante UD", "Real Betis"))
        self.assertEqual(rt.equipos_caos_en_partido("Girona FC", "Levante UD"), [])

    def test_levante_las_planas_no_dispara_levante(self):
        # "Levante Las Planas (F)" es otro club: el filtro femenino lo excluye.
        self.assertEqual(rt.equipos_caos_en_partido("Las Planas (F)", "Sevilla (F)"), [])

    def test_oviedo_y_granada_solo_fuera(self):
        self.assertTrue(rt.equipos_caos_en_partido("Albacete", "Real Oviedo"))
        self.assertEqual(rt.equipos_caos_en_partido("Real Oviedo", "CD Leganes"), [])
        self.assertTrue(rt.equipos_caos_en_partido("Burgos CF", "Granada CF"))
        self.assertEqual(rt.equipos_caos_en_partido("Granada CF", "FC Andorra"), [])

    def test_athletic_masculino_si_femenino_no(self):
        self.assertTrue(rt.equipos_caos_en_partido("Athletic Club", "Sevilla FC"))
        self.assertEqual(rt.equipos_caos_en_partido("Eibar (M)", "Athletic Club (F)"), [])


class SignoDelRayoTests(unittest.TestCase):
    def test_nunca_es_x_aunque_la_x_sea_la_menos_jugada(self):
        # Masa: X es el signo menos jugado, pero el rayo salta a 1/2 (los 25
        # terceros de J1-14 fueron 19 doses y 6 unos; ninguno X).
        masa = {"1": 50.0, "X": 10.0, "2": 40.0}
        self.assertEqual(rt.signo_del_rayo({"1": 50, "X": 25, "2": 25}, masa), "2")

    def test_menor_masa_entre_1_y_2(self):
        self.assertEqual(rt.signo_del_rayo({}, {"1": 70.0, "X": 20.0, "2": 10.0}), "2")
        self.assertEqual(rt.signo_del_rayo({}, {"1": 12.0, "X": 20.0, "2": 68.0}), "1")

    def test_sin_masa_cae_al_motor(self):
        self.assertEqual(rt.signo_del_rayo({"1": 60.0, "X": 25.0, "2": 15.0}, {}), "2")


class PuntuarPartidoTests(unittest.TestCase):
    def test_sin_dueno_puntua_dos(self):
        fila = rt.puntuar_partido(_partido(probs={"1": 40.0, "X": 32.0, "2": 28.0}), {})
        self.assertEqual(fila["score"], 2)
        self.assertIn("sin dueño", fila["motivos"][0])

    def test_favorito_claro_sin_caos_puntua_cero(self):
        fila = rt.puntuar_partido(
            _partido(local="Real Madrid CF", visitante="CD Leganes",
                     probs={"1": 70.0, "X": 18.0, "2": 12.0}), {})
        self.assertEqual(fila["score"], 0)

    def test_caos_mas_sin_dueno_acumula(self):
        fila = rt.puntuar_partido(
            _partido(local="Levante UD", visitante="Athletic Club",
                     probs={"1": 35.0, "X": 32.0, "2": 33.0}), {})
        # sin dueño (+2) + Levante en casa (+2) + Athletic (+2)
        self.assertEqual(fila["score"], 6)

    def test_probabilidades_rotas_devuelve_none(self):
        self.assertIsNone(rt.puntuar_partido({"num": 1, "probabilidades": {"1": 50}}, {}))


class BloqueRadarTests(unittest.TestCase):
    def _con_masa(self, masa):
        original = rt.porcentajes_masa
        rt.porcentajes_masa = lambda jornada, losilla: (masa, "test")
        self.addCleanup(lambda: setattr(rt, "porcentajes_masa", original))

    def test_zona_con_tope_de_tres_y_orden_por_score(self):
        self._con_masa({})
        partidos = [_partido(num=n, probs={"1": 60.0, "X": 25.0, "2": 15.0}) for n in range(1, 15)]
        # 4 partidos sin dueño; uno ademas con equipo del caos (score 4).
        for n, (local, visitante) in zip(
            (3, 6, 9, 12),
            (("A", "B"), ("C", "D"), ("E", "F"), ("Burgos CF", "Granada CF")),
        ):
            partidos[n - 1] = _partido(num=n, local=local, visitante=visitante,
                                       probs={"1": 40.0, "X": 32.0, "2": 28.0})
        bloque = rt.construir_bloque_radar(_prediccion(partidos))
        self.assertEqual(bloque["estado"], "ok")
        self.assertEqual(len(bloque["zona"]), rt.MAX_ZONA)
        self.assertEqual(bloque["zona"][0]["num"], 12)  # el de mas score manda

    def test_sin_tormenta_cuando_nadie_llega_al_umbral(self):
        self._con_masa({})
        bloque = rt.construir_bloque_radar(_prediccion())
        self.assertEqual(bloque["estado"], "sin_tormenta")
        self.assertEqual(bloque["zona"], [])

    def test_no_disponible_sin_los_14_partidos(self):
        bloque = rt.construir_bloque_radar(_prediccion(partidos=[_partido(num=1)]))
        self.assertEqual(bloque["estado"], "no_disponible")

    def test_rayo_usa_la_masa_de_su_partido(self):
        self._con_masa({5: {"1": 15.0, "X": 25.0, "2": 60.0}})
        partidos = [_partido(num=n, probs={"1": 60.0, "X": 25.0, "2": 15.0}) for n in range(1, 15)]
        partidos[4] = _partido(num=5, probs={"1": 40.0, "X": 32.0, "2": 28.0})
        bloque = rt.construir_bloque_radar(_prediccion(partidos))
        zona5 = [z for z in bloque["zona"] if z["num"] == 5][0]
        self.assertEqual(zona5["signo_rayo"], "1")
        self.assertEqual(zona5["masa_rayo"], 15.0)


class EvaluarJornadaCerradaTests(unittest.TestCase):
    def _escenario(self):
        snapshot = [_partido(num=n, local=f"L{n}", visitante=f"V{n}") for n in range(1, 15)]
        jornada = [{"num": n, "local": f"L{n}", "visitante": f"V{n}", "signo_oficial": "1"}
                   for n in range(1, 15)]
        masa = {n: {"1": 60.0, "X": 25.0, "2": 15.0} for n in range(1, 15)}
        bloque = {"zona": [{"num": 3, "local": "L3", "visitante": "V3",
                            "signo_rayo": "2", "motivos": []}]}
        return bloque, snapshot, jornada, masa

    def test_tercero_dentro_y_rayo_exacto(self):
        bloque, snapshot, jornada, masa = self._escenario()
        jornada[2]["signo_oficial"] = "2"   # P3 (en zona): sale el tercero
        jornada[7]["signo_oficial"] = "2"   # P8 (fuera): otro tercero
        r = rt.evaluar_jornada_cerrada(bloque, snapshot, jornada, masa)
        self.assertEqual(r["terceros_totales"], 2)
        self.assertEqual(r["terceros_en_zona"], 1)
        self.assertEqual(r["rayos_acertados"], 1)

    def test_jornada_abierta_no_evaluable(self):
        bloque, snapshot, jornada, masa = self._escenario()
        jornada[0]["signo_oficial"] = "Pendiente"
        self.assertIsNone(rt.evaluar_jornada_cerrada(bloque, snapshot, jornada, masa))

    def test_fixtures_de_otra_temporada_no_evaluables(self):
        bloque, snapshot, jornada, masa = self._escenario()
        for p in jornada:
            p["local"] = p["local"] + " viejo"
        self.assertIsNone(rt.evaluar_jornada_cerrada(bloque, snapshot, jornada, masa))


class MarcadorRadarTests(unittest.TestCase):
    """Auditoria 26/11: el marcador lee la zona del snapshot PRE-CIERRE, la
    temporada sale de la fecha de la jornada y los % LAE se leen de un
    directorio temporal (antes el test escribia dentro de data/)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.dir_jor = self.base / "jornadas"
        self.dir_snap = self.base / "snapshots"
        self.ruta = self.base / "marcador.json"
        self._porcentajes_original = rt.PORCENTAJES_DIR
        rt.PORCENTAJES_DIR = self.base / "porcentajes"

    def tearDown(self):
        rt.PORCENTAJES_DIR = self._porcentajes_original
        self.tmp.cleanup()

    def _masa(self, jornada=20, etiqueta="2026_2027"):
        carpeta = rt.PORCENTAJES_DIR / etiqueta
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f"jornada_{jornada}.json").write_text(json.dumps({
            "jornada": jornada,
            "partidos": [{"numero": n, "porcentajes": {"1": 60.0, "X": 25.0, "2": 15.0}}
                         for n in range(1, 15)]}), encoding="utf-8")

    def _bloque(self, num=2):
        local, visitante = util.EQUIPOS[num - 1]
        return {"estado": "ok", "jornada": 20,
                "zona": [{"num": num, "local": local, "visitante": visitante,
                          "signo_rayo": "2", "motivos": ["test"]}]}

    def _actualizar(self, etiqueta="2026_2027"):
        return rt.actualizar_marcador_radar(
            dir_predicciones=self.base / "predicciones", dir_jornadas=self.dir_jor,
            ruta_marcador=self.ruta, etiqueta=etiqueta, dir_snapshots=self.dir_snap)

    def test_registra_una_vez_y_es_idempotente(self):
        util.montar_cierre(self.base, 20, {"radar_tormenta": self._bloque()}, signos={2: "2"})
        self._masa()
        r1 = self._actualizar()
        self.assertEqual(r1["nuevas"], 1)
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(datos["resumen"]["terceros_en_zona"], 1)
        self.assertEqual(datos["resumen"]["rayos_acertados"], 1)
        self.assertEqual(datos["resumen"]["veredicto"], "en_prueba")
        self.assertEqual(datos["jornadas"][0]["temporada"], "2026_2027")
        # ni repitiendo ni cambiando la etiqueta (now() en julio de 2027) se duplica
        self.assertEqual(self._actualizar()["nuevas"], 0)
        self.assertEqual(self._actualizar(etiqueta="2027_2028")["nuevas"], 0)

    def test_la_zona_es_la_del_snapshot_no_la_del_espejo(self):
        # J22 real: el marcador guardo la zona [8, 3, 14] del espejo reescrito
        # y el snapshot pre-cierre decia [5, 12].
        util.montar_cierre(self.base, 20, {"radar_tormenta": self._bloque(num=2)}, signos={2: "2"})
        self._masa()
        (self.base / "predicciones").mkdir()
        (self.base / "predicciones" / "jornada_20.json").write_text(json.dumps({
            "jornada": 20, "partidos": util.partidos_prediccion(util.EQUIPOS),
            "radar_tormenta": self._bloque(num=9)}), encoding="utf-8")
        self._actualizar()
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual([z["num"] for z in datos["jornadas"][0]["zona"]], [2])

    def test_nombres_de_otra_fuente_no_descartan_la_jornada(self):
        # Auditoria 26/11: J17, J19, J20 y J24 (Copa y Champions) no se
        # registraban porque 'Borussia Dortmund' != 'B. Dortmund'.
        fixture = [("B. Dortmund" if l == "Alaves" else l + " CF", "R. " + v) for l, v in util.EQUIPOS]
        util.montar_cierre(self.base, 20, {"radar_tormenta": self._bloque()}, signos={2: "2"},
                           nombres=[("Borussia Dortmund" if l == "Alaves" else l, v) for l, v in util.EQUIPOS],
                           nombres_fixture=fixture)
        self._masa()
        self.assertEqual(self._actualizar()["nuevas"], 1)

    def test_jornada_sin_masa_queda_como_no_evaluable_con_motivo(self):
        util.montar_cierre(self.base, 20, {"radar_tormenta": self._bloque()}, signos={2: "2"})
        r = self._actualizar()
        self.assertEqual(r["nuevas"], 0)
        self.assertEqual([(n["jornada"], n["temporada"]) for n in r["no_evaluables"]], [(20, "2026_2027")])
        self.assertIn("LAE", r["no_evaluables"][0]["motivo"])

    def test_jornada_abierta_no_se_registra(self):
        util.montar_cierre(self.base, 20, {"radar_tormenta": self._bloque()}, signos={7: "Pendiente"})
        self._masa()
        self.assertEqual(self._actualizar()["nuevas"], 0)


if __name__ == "__main__":
    unittest.main()
