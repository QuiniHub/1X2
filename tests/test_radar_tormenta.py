import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import radar_tormenta as rt


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
    def test_registra_una_vez_y_es_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "predicciones").mkdir()
            (tmp / "jornadas").mkdir()
            porcentajes = rt.PORCENTAJES_DIR / "test_temp"
            snapshot = {
                "jornada": 99,
                "partidos": [_partido(num=n, local=f"L{n}", visitante=f"V{n}")
                             for n in range(1, 15)],
                "radar_tormenta": {
                    "estado": "ok", "jornada": 99,
                    "zona": [{"num": 2, "local": "L2", "visitante": "V2",
                              "signo_rayo": "2", "motivos": ["test"]}],
                },
            }
            jornada = {"partidos": [{"num": n, "local": f"L{n}", "visitante": f"V{n}",
                                     "signo_oficial": "2" if n == 2 else "1"}
                                    for n in range(1, 15)]}
            (tmp / "predicciones" / "jornada_99.json").write_text(
                json.dumps(snapshot), encoding="utf-8")
            (tmp / "jornadas" / "jornada_99.json").write_text(
                json.dumps(jornada), encoding="utf-8")
            porcentajes.mkdir(parents=True, exist_ok=True)
            try:
                (porcentajes / "jornada_99.json").write_text(json.dumps({
                    "partidos": [{"numero": n, "porcentajes": {"1": 60.0, "X": 25.0, "2": 15.0}}
                                 for n in range(1, 15)]}), encoding="utf-8")
                ruta = tmp / "marcador.json"
                r1 = rt.actualizar_marcador_radar(
                    dir_predicciones=tmp / "predicciones", dir_jornadas=tmp / "jornadas",
                    ruta_marcador=ruta, etiqueta="test_temp")
                self.assertEqual(r1["nuevas"], 1)
                datos = json.loads(ruta.read_text(encoding="utf-8"))
                self.assertEqual(datos["resumen"]["terceros_en_zona"], 1)
                self.assertEqual(datos["resumen"]["rayos_acertados"], 1)
                self.assertEqual(datos["resumen"]["veredicto"], "en_prueba")
                r2 = rt.actualizar_marcador_radar(
                    dir_predicciones=tmp / "predicciones", dir_jornadas=tmp / "jornadas",
                    ruta_marcador=ruta, etiqueta="test_temp")
                self.assertEqual(r2["nuevas"], 0)
            finally:
                for f in porcentajes.glob("*.json"):
                    f.unlink()
                porcentajes.rmdir()


if __name__ == "__main__":
    unittest.main()
