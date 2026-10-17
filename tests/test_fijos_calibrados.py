"""Tests del proyecto "fijos calibrados" (17/10/2026): la DECISION de
cobertura (prioridad_cobertura/doble/triple) ve al favorito corregido a su
tasa real de banda, el backtest prerregistrado que decidio el flag, el aviso
web FIJO FORZADO y el cuaderno "fijos por banda" del Laboratorio."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aprendizaje_modulos as am  # noqa: E402
import backtest_fijos_calibrados as bfc  # noqa: E402
import motor_prediccion_quiniela as motor  # noqa: E402
from actualizar_porcentajes_lae import temporada_etiqueta  # noqa: E402

BANDAS = {
    "30-40": {"n": 74, "prob_media": 36.9, "acierto_real_pct": 40.5},
    "40-50": {"n": 101, "prob_media": 44.8, "acierto_real_pct": 56.4},
    "50-60": {"n": 48, "prob_media": 54.3, "acierto_real_pct": 64.6},
    "60-70": {"n": 27, "prob_media": 64.3, "acierto_real_pct": 74.1},
}


class PuntosCalibracionTests(unittest.TestCase):
    def test_filtra_bandas_sin_muestra_y_ordena(self):
        puntos = motor.puntos_calibracion_favorito(BANDAS)
        self.assertEqual([p[0] for p in puntos], [36.9, 44.8, 54.3])  # 60-70 fuera (n=27)
        self.assertAlmostEqual(puntos[0][1], 3.6, places=2)
        self.assertAlmostEqual(puntos[1][1], 11.6, places=2)

    def test_bandas_corruptas_o_vacias(self):
        self.assertEqual(motor.puntos_calibracion_favorito({}), [])
        self.assertEqual(motor.puntos_calibracion_favorito(None), [])
        self.assertEqual(
            motor.puntos_calibracion_favorito({"40-50": {"n": "no", "prob_media": 44.8}}), []
        )


class ProbCalibradaFavoritoTests(unittest.TestCase):
    def setUp(self):
        self.puntos = motor.puntos_calibracion_favorito(BANDAS)

    def test_identidad_sin_datos(self):
        self.assertEqual(motor.prob_calibrada_favorito(45.0, []), 45.0)

    def test_identidad_fuera_de_rango(self):
        # mas alla del decaimiento (centros 36,9-54,3 +-10): identidad
        self.assertEqual(motor.prob_calibrada_favorito(20.0, self.puntos), 20.0)
        self.assertEqual(motor.prob_calibrada_favorito(80.0, self.puntos), 80.0)

    def test_en_el_centro_de_banda_devuelve_la_tasa_real(self):
        self.assertAlmostEqual(motor.prob_calibrada_favorito(44.8, self.puntos), 56.4, places=1)
        self.assertAlmostEqual(motor.prob_calibrada_favorito(54.3, self.puntos), 64.6, places=1)

    def test_interpola_entre_centros_sin_escalones(self):
        # punto medio entre 36,9 (corr 3,6) y 44,8 (corr 11,6): corr ~7,6
        medio = (36.9 + 44.8) / 2
        esperado = medio + (3.6 + 11.6) / 2
        self.assertAlmostEqual(motor.prob_calibrada_favorito(medio, self.puntos), esperado, places=1)
        # continuidad: dos puntos pegados no saltan una banda entera
        a = motor.prob_calibrada_favorito(49.9, self.puntos)
        b = motor.prob_calibrada_favorito(50.1, self.puntos)
        self.assertLess(abs(a - b), 1.0)

    def test_decaimiento_a_identidad_en_una_banda(self):
        # a mitad del decaimiento superior (54,3 -> 64,3) queda media correccion
        self.assertAlmostEqual(motor.prob_calibrada_favorito(59.3, self.puntos), 59.3 + 10.3 / 2, places=1)
        # y en el borde ya es identidad
        self.assertEqual(motor.prob_calibrada_favorito(64.3, self.puntos), 64.3)

    def test_entrada_no_numerica(self):
        self.assertIsNone(motor.prob_calibrada_favorito(None, self.puntos))


class ProbsCalibradasCoberturaTests(unittest.TestCase):
    def setUp(self):
        self.puntos = motor.puntos_calibracion_favorito(BANDAS)

    def test_favorito_corregido_y_resto_reescalado(self):
        probs = {"1": 42.0, "X": 33.0, "2": 25.0}
        nuevos = motor.probs_calibradas_cobertura(probs, self.puntos)
        self.assertGreater(nuevos["1"], 42.0)  # infraconfiado: sube
        self.assertAlmostEqual(sum(nuevos.values()), 100.0, delta=0.1)
        # el orden 2o/3o no cambia (el doble cubriria los mismos signos)
        self.assertGreater(nuevos["X"], nuevos["2"])
        self.assertEqual(motor.signo_top(nuevos), "1")

    def test_identidad_sin_puntos(self):
        probs = {"1": 42.0, "X": 33.0, "2": 25.0}
        self.assertEqual(motor.probs_calibradas_cobertura(probs, []), probs)


class PrioridadConProbsCoberturaTests(unittest.TestCase):
    def _partido(self, probs):
        return {"probabilidades": dict(probs), "incertidumbre": 50}

    def test_prioridad_cobertura_lee_probs_calibradas(self):
        # crudo: margen 42-33=9 (<16: +18); calibrado: margen 50,8-28=22,7 (sin bono)
        partido = self._partido({"1": 42.0, "X": 33.0, "2": 25.0})
        crudo = motor.prioridad_cobertura(partido)
        partido["_probs_cobertura"] = motor.probs_calibradas_cobertura(
            partido["probabilidades"], motor.puntos_calibracion_favorito(BANDAS)
        )
        calibrado = motor.prioridad_cobertura(partido)
        self.assertLess(calibrado, crudo)

    def test_prioridad_doble_y_triple_leen_probs_calibradas(self):
        partido = self._partido({"1": 42.0, "X": 33.0, "2": 25.0})
        d0, t0 = motor.prioridad_doble(partido), motor.prioridad_triple(partido)
        partido["_probs_cobertura"] = motor.probs_calibradas_cobertura(
            partido["probabilidades"], motor.puntos_calibracion_favorito(BANDAS)
        )
        d1, t1 = motor.prioridad_doble(partido), motor.prioridad_triple(partido)
        self.assertNotEqual((d0, t0), (d1, t1))

    def test_sin_clave_interna_usa_las_publicadas(self):
        partido = self._partido({"1": 42.0, "X": 33.0, "2": 25.0})
        self.assertEqual(motor.probs_para_cobertura(partido), partido["probabilidades"])


class AplicarCalibracionCoberturaTests(unittest.TestCase):
    METRICAS = {"rps_calibracion": {"calibracion_favorito": BANDAS}}

    def test_flag_desactivado_no_marca_nada(self):
        evaluados = [{"probabilidades": {"1": 42.0, "X": 33.0, "2": 25.0}}]
        with mock.patch.object(motor, "USAR_CALIBRACION_EN_COBERTURA", False):
            bloque = motor.aplicar_calibracion_cobertura(evaluados, self.METRICAS)
        self.assertFalse(bloque["activa"])
        self.assertNotIn("_probs_cobertura", evaluados[0])

    def test_flag_activo_marca_probs_cobertura(self):
        evaluados = [{"probabilidades": {"1": 42.0, "X": 33.0, "2": 25.0}}]
        with mock.patch.object(motor, "USAR_CALIBRACION_EN_COBERTURA", True):
            bloque = motor.aplicar_calibracion_cobertura(evaluados, self.METRICAS)
        self.assertTrue(bloque["activa"])
        self.assertEqual(bloque["bandas_usadas"], 3)
        self.assertGreater(evaluados[0]["_probs_cobertura"]["1"], 42.0)

    def test_sin_bandas_validas_no_marca(self):
        evaluados = [{"probabilidades": {"1": 42.0, "X": 33.0, "2": 25.0}}]
        with mock.patch.object(motor, "USAR_CALIBRACION_EN_COBERTURA", True):
            bloque = motor.aplicar_calibracion_cobertura(evaluados, {"rps_calibracion": {}})
        self.assertFalse(bloque["activa"])
        self.assertNotIn("_probs_cobertura", evaluados[0])

    def test_no_toca_las_probabilidades_publicadas(self):
        probs = {"1": 42.0, "X": 33.0, "2": 25.0}
        evaluados = [{"probabilidades": probs}]
        with mock.patch.object(motor, "USAR_CALIBRACION_EN_COBERTURA", True):
            motor.aplicar_calibracion_cobertura(evaluados, self.METRICAS)
        self.assertEqual(evaluados[0]["probabilidades"], {"1": 42.0, "X": 33.0, "2": 25.0})


class BacktestHelpersTests(unittest.TestCase):
    def test_estructura_jugada(self):
        signos = ["1", "X2", "2", "1X2", "12", "2", "1", "1", "1X2", "1X", "1", "1", "1X2", "1"]
        self.assertEqual(bfc.estructura_jugada(signos), (3, 3))

    def test_bandas_walk_forward_corta_por_jornada_sin_tocar_temporadas_viejas(self):
        revisiones = [
            # temporada anterior (numeracion alta): siempre pasado
            {"jornada": 74, "probabilidades_usadas": {"1": 55.0, "X": 25.0, "2": 20.0}, "signo_real": "1"},
            # 26/27 anteriores a la J5: entran
            {"jornada": 4, "probabilidades_usadas": {"1": 52.0, "X": 28.0, "2": 20.0}, "signo_real": "X"},
            # 26/27 en o despues de la J5: fuera (serian futuro)
            {"jornada": 5, "probabilidades_usadas": {"1": 58.0, "X": 22.0, "2": 20.0}, "signo_real": "1"},
            {"jornada": 9, "probabilidades_usadas": {"1": 51.0, "X": 29.0, "2": 20.0}, "signo_real": "1"},
            # sin signo real valido: fuera
            {"jornada": 3, "probabilidades_usadas": {"1": 50.0, "X": 30.0, "2": 20.0}, "signo_real": ""},
        ]
        bandas = bfc.bandas_walk_forward(revisiones, 5, jornadas_actuales={3, 4, 5, 9})
        self.assertEqual(bandas["50-60"]["n"], 2)  # J74 + J4
        self.assertEqual(bandas["50-60"]["acierto_real_pct"], 50.0)

    def test_asignar_cobertura_respeta_presupuesto_y_prioridades(self):
        numeros = [1, 2, 3, 4]
        st = {1: 10, 2: 40, 3: 30, 4: 5}
        sd = {1: 50, 2: 1, 3: 1, 4: 20}
        triples, dobles = bfc.asignar_cobertura(numeros, st, sd, 1, 2)
        self.assertEqual(triples, {2})
        self.assertEqual(dobles, {1, 4})

    def test_signos_cubiertos(self):
        p = {"probabilidades": {"1": 50.0, "X": 30.0, "2": 20.0}, "signo_base": "1"}
        self.assertEqual(bfc.signos_cubiertos(p, 3, {3}, set()), "1X2")
        self.assertEqual(bfc.signos_cubiertos(p, 3, set(), {3}), "1X")
        self.assertEqual(bfc.signos_cubiertos(p, 3, set(), set()), "1")

    def test_umbral_prerregistrado_documentado(self):
        self.assertIn(">= acumulado crudo", bfc.UMBRAL_PRERREGISTRADO)
        self.assertIn("+1", bfc.UMBRAL_PRERREGISTRADO)


class FijosBandaCuadernoTests(unittest.TestCase):
    def setUp(self):
        self.etiqueta = temporada_etiqueta(datetime.now())
        self.ahora = datetime.now(timezone.utc).isoformat()
        signos = ["1", "X2", "2"] + ["1"] * 10 + ["1X2"]
        self.datos_jugadas = {"jugadas": [{"jornada": 5, "signos": signos, "validado_en": self.ahora}]}
        self.fixture = {
            n: {"local": f"L{n}", "visitante": f"V{n}", "fecha": "2026-10-01", "signo_oficial": "1"}
            for n in range(1, 15)
        }
        self.fixture[3]["signo_oficial"] = "X"  # el fijo "2" del P3... P3 es doble X2 en realidad
        self.prediccion = {"partidos": [
            {"num": n, "local": f"L{n}", "visitante": f"V{n}",
             "probabilidades": {"1": 45.0, "X": 30.0, "2": 25.0}}
            for n in range(1, 15)
        ]}

    def test_fila_solo_cuenta_fijos_con_banda_y_acierto(self):
        fila = am.fila_fijos_banda(5, self.etiqueta, self.fixture, self.prediccion, self.datos_jugadas)
        self.assertEqual(fila["estado"], "ok")
        fijos = fila["fijos"]
        self.assertEqual(len(fijos), 12)  # 14 - 1 doble - 1 triple
        self.assertEqual(fijos[0], {
            "num": 1, "partido": "L1 - V1", "signo": "1", "probabilidad": 45.0,
            "banda": "40-50", "acierto": True,
        })
        # el fijo "2" del P3 (prob 25) cae en la banda 20-30 y falla (salio X)
        p3 = next(f for f in fijos if f["num"] == 3)
        self.assertEqual((p3["banda"], p3["acierto"]), ("20-30", False))

    def test_fila_sin_jugada_o_sin_snapshot(self):
        self.assertEqual(
            am.fila_fijos_banda(9, self.etiqueta, self.fixture, self.prediccion, self.datos_jugadas)["estado"],
            "sin_jugada_real",
        )
        self.assertEqual(
            am.fila_fijos_banda(5, self.etiqueta, self.fixture, {}, self.datos_jugadas)["estado"],
            "sin_snapshot",
        )

    def test_fila_cuenta_fijos_sin_probabilidad(self):
        prediccion = {"partidos": [
            {"num": n, "local": f"L{n}", "visitante": f"V{n}",
             "probabilidades": ({} if n == 1 else {"1": 45.0, "X": 30.0, "2": 25.0})}
            for n in range(1, 15)
        ]}
        fila = am.fila_fijos_banda(5, self.etiqueta, self.fixture, prediccion, self.datos_jugadas)
        self.assertEqual(fila["fijos_sin_probabilidad"], 1)
        self.assertEqual(len(fila["fijos"]), 11)

    def _filas(self, n_fijos, aciertos, prob=45.0):
        fijos = [{"num": i + 1, "partido": "a - b", "signo": "1", "probabilidad": prob,
                  "banda": f"{int(prob // 10) * 10}-{int(prob // 10) * 10 + 10}",
                  "acierto": i < aciertos} for i in range(n_fijos)]
        return [{"estado": "ok", "fijos": fijos}]

    def test_resumen_usa_la_promesa_de_banda_solo_con_muestra(self):
        resumen = am.resumen_fijos_banda(self._filas(12, 7), bandas_promesa=BANDAS)
        banda = resumen["por_banda"]["40-50"]
        self.assertEqual(banda["jugados"], 12)
        self.assertEqual(banda["promesa_pct"], 56.4)
        self.assertAlmostEqual(resumen["comparacion"], 12 * 0.564, places=2)
        self.assertEqual(resumen["semaforo"], "verde")  # 7 >= 6,77
        # banda sin muestra (60-70, n=27): el esperado honesto es la prob dicha
        resumen2 = am.resumen_fijos_banda(self._filas(12, 9, prob=65.0), bandas_promesa=BANDAS)
        self.assertIsNone(resumen2["por_banda"]["60-70"]["promesa_pct"])
        self.assertAlmostEqual(resumen2["comparacion"], 12 * 0.65, places=2)

    def test_resumen_semaforos(self):
        self.assertEqual(
            am.resumen_fijos_banda(self._filas(5, 5), bandas_promesa=BANDAS)["semaforo"], "ambar"
        )  # muestra minima
        self.assertEqual(
            am.resumen_fijos_banda(self._filas(12, 2), bandas_promesa=BANDAS)["semaforo"], "rojo"
        )  # 2 vs 6,77 esperados
        self.assertEqual(
            am.resumen_fijos_banda(self._filas(12, 6), bandas_promesa=BANDAS)["semaforo"], "ambar"
        )  # 6 vs 6,77: dentro del margen de 2
        self.assertEqual(
            am.resumen_fijos_banda([], bandas_promesa=BANDAS)["texto_semaforo"],
            "en vigilancia: aun sin fijos evaluables",
        )

    def test_cuaderno_exporta_el_bloque(self):
        html_keys = am.resumen_fijos_banda([], bandas_promesa=BANDAS)
        for clave in ("semaforo", "titular", "por_banda", "promesa"):
            self.assertIn(clave, html_keys)


class FrontendFijosCalibradosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_replica_js_de_la_calibracion(self):
        self.assertIn("function probCalibradaFavorito(p)", self.html)
        self.assertIn("Number(b?.n) >= 30", self.html)
        self.assertIn("calibracion_favorito", self.html)

    def test_aviso_fijo_forzado_en_panel_de_avisos(self):
        self.assertIn("FIJO FORZADO", self.html)
        self.assertIn("banda real", self.html)
        self.assertIn("si sueltas un doble", self.html)
        # reacciona a la jugada actual y se oculta si el partido esta cubierto
        bloque = self.html[self.html.index("FIJO FORZADO (17/10/2026"):]
        bloque = bloque[:bloque.index("Rediseno compacto")]
        self.assertIn("selectedSigns(m)", bloque)
        self.assertIn("jugado.length !== 1", bloque)
        self.assertIn("pCal === null || pCal >= 60", bloque)

    def test_tarjeta_laboratorio_fijos_por_banda(self):
        self.assertIn("Fijos por banda", self.html)
        self.assertIn("res.fijos_banda", self.html)
        self.assertIn("Promesa (banda real)", self.html)
        self.assertIn("cardDc + cardEv + cardVal + cardRev + cardFb", self.html)

    def test_motor_exporta_bloque_calibracion_cobertura(self):
        fuente = (ROOT / "motor_prediccion_quiniela.py").read_text(encoding="utf-8")
        self.assertIn('"calibracion_cobertura": calibracion_cobertura', fuente)
        self.assertIn("USAR_CALIBRACION_EN_COBERTURA = True", fuente)


if __name__ == "__main__":
    unittest.main()
