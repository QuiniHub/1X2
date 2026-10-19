import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tercero_valor as tv


def _partido(num=1, local="Cadiz CF", visitante="Levante UD", probs=None, **extra):
    return {
        "num": num,
        "local": local,
        "visitante": visitante,
        "probabilidades": probs or {"1": 50.0, "X": 30.0, "2": 20.0},
        **extra,
    }


def _metricas(n=250, por_signo=None):
    return {"rps_calibracion": {
        "partidos_con_probabilidades": n,
        "calibracion_por_signo": por_signo if por_signo is not None else {
            "1": {"prob_media_pronosticada": 40.0, "frecuencia_real_pct": 44.0},
            "X": {"prob_media_pronosticada": 30.0, "frecuencia_real_pct": 22.5},
            "2": {"prob_media_pronosticada": 30.0, "frecuencia_real_pct": 33.0},
        },
    }}


def _calibracion(n=250):
    return tv.factores_calibracion(_metricas(n=n))


class SignoTerceroTests(unittest.TestCase):
    def test_signo_de_menor_probabilidad(self):
        self.assertEqual(tv.signo_tercero({"1": 50.0, "X": 30.0, "2": 20.0}), "2")
        self.assertEqual(tv.signo_tercero({"1": 20.0, "X": 30.0, "2": 50.0}), "1")
        self.assertEqual(tv.signo_tercero({"1": 45.0, "X": 15.0, "2": 40.0}), "X")

    def test_empate_exacto_gana_el_primero_en_orden_1_x_2(self):
        # prerregistrado: desempate por el orden 1, X, 2
        self.assertEqual(tv.signo_tercero({"1": 25.0, "X": 25.0, "2": 50.0}), "1")
        self.assertEqual(tv.signo_tercero({"1": 50.0, "X": 25.0, "2": 25.0}), "X")

    def test_sin_probabilidades_no_hay_tercero(self):
        self.assertIsNone(tv.signo_tercero({}))
        self.assertIsNone(tv.signo_tercero(None))
        self.assertIsNone(tv.signo_tercero({"1": 0, "X": 0, "2": 0}))
        self.assertIsNone(tv.signo_tercero({"1": "no", "X": 30, "2": 20}))


class CalibracionTests(unittest.TestCase):
    def test_factores_desde_metricas(self):
        cal = _calibracion()
        self.assertEqual(cal["metodo"], "factor_global_por_signo")
        self.assertEqual(cal["n"], 250)
        self.assertEqual(cal["factores"]["1"], 1.1)    # 44/40
        self.assertEqual(cal["factores"]["X"], 0.75)   # 22.5/30
        self.assertEqual(cal["factores"]["2"], 1.1)    # 33/30
        self.assertIn("no por bandas", cal["declaracion"])

    def test_freno_de_muestra_prerregistrado_usa_cruda_y_lo_declara(self):
        cal = _calibracion(n=99)
        self.assertEqual(cal["metodo"], "cruda_sin_calibrar")
        self.assertIsNone(cal["factores"])
        self.assertIn("SIN CALIBRAR", cal["declaracion"])
        self.assertIn("prerregistrado", cal["declaracion"])
        # el umbral exacto del freno
        self.assertEqual(_calibracion(n=100)["metodo"], "factor_global_por_signo")

    def test_tabla_rota_cae_a_cruda_declarada(self):
        rotas = [
            {},  # sin tabla
            {"1": {"prob_media_pronosticada": 0.0, "frecuencia_real_pct": 44.0},
             "X": {"prob_media_pronosticada": 30.0, "frecuencia_real_pct": 22.0},
             "2": {"prob_media_pronosticada": 30.0, "frecuencia_real_pct": 33.0}},
            {"1": {"prob_media_pronosticada": "x", "frecuencia_real_pct": 44.0},
             "X": {"prob_media_pronosticada": 30.0, "frecuencia_real_pct": 22.0},
             "2": {"prob_media_pronosticada": 30.0, "frecuencia_real_pct": 33.0}},
        ]
        for por_signo in rotas:
            cal = tv.factores_calibracion(_metricas(por_signo=por_signo))
            self.assertEqual(cal["metodo"], "cruda_sin_calibrar")

    def test_sin_metricas_cae_a_cruda(self):
        cal = tv.factores_calibracion({})
        self.assertEqual(cal["metodo"], "cruda_sin_calibrar")
        self.assertEqual(cal["n"], 0)

    def test_desde_registros_replica_la_formula_del_artefacto(self):
        # 2 partidos: media del 1 = 45, sale una vez de dos = 50% real
        items = [
            {"probabilidades_usadas": {"1": 50.0, "X": 30.0, "2": 20.0}, "signo_real": "1"},
            {"probabilidades_usadas": {"1": 40.0, "X": 35.0, "2": 25.0}, "signo_real": "X"},
            {"probabilidades_usadas": {"1": 40.0, "X": 35.0}, "signo_real": "1"},   # probs rotas: fuera
            {"probabilidades_usadas": {"1": 40.0, "X": 35.0, "2": 25.0}, "signo_real": "M"},  # signo invalido
        ]
        cal = tv.calibracion_desde_registros(items)
        self.assertEqual(cal["n"], 2)  # solo los 2 validos
        self.assertEqual(cal["metodo"], "cruda_sin_calibrar")  # freno de muestra
        # con muestra suficiente, los factores salen de la misma formula
        muchos = [
            {"probabilidades_usadas": {"1": 50.0, "X": 30.0, "2": 20.0},
             "signo_real": "1" if i % 2 == 0 else "X"}
            for i in range(120)
        ]
        cal = tv.calibracion_desde_registros(muchos)
        self.assertEqual(cal["metodo"], "factor_global_por_signo")
        self.assertEqual(cal["n"], 120)
        self.assertEqual(cal["factores"]["1"], 1.0)   # 50 real / 50 media
        self.assertAlmostEqual(cal["factores"]["X"], round(50.0 / 30.0, 4))
        self.assertEqual(cal["factores"]["2"], 0.0)   # nunca salio

    def test_prob_calibrada_aplica_el_factor_y_acota(self):
        cal = _calibracion()
        self.assertEqual(tv.prob_calibrada_tercero(20.0, "X", cal), 15.0)   # x0,75
        self.assertEqual(tv.prob_calibrada_tercero(20.0, "2", cal), 22.0)   # x1,1
        # sin factores (freno): la cruda tal cual, declarada aparte
        self.assertEqual(tv.prob_calibrada_tercero(20.0, "X", _calibracion(n=50)), 20.0)
        # acotada a [0, 100]
        self.assertEqual(tv.prob_calibrada_tercero(95.0, "1", cal), 100.0)
        self.assertEqual(tv.prob_calibrada_tercero("no", "1", cal), 0.0)


class RankingYUmbralesTests(unittest.TestCase):
    def _masa(self, **por_num):
        base = {n: {"1": 60.0, "X": 25.0, "2": 15.0} for n in range(1, 15)}
        for n, v in por_num.items():
            base[int(n)] = v
        return base

    def test_ranking_por_ventaja_con_desempates(self):
        partidos = [
            _partido(num=1, probs={"1": 50.0, "X": 30.0, "2": 20.0}),   # tercero 2: cal 22, masa 15 -> +7
            _partido(num=2, probs={"1": 50.0, "X": 30.0, "2": 20.0}),   # igual pero masa 10 -> +12
            _partido(num=3, probs={"1": 30.0, "X": 30.0, "2": 40.0}),   # tercero 1 (empate): cal 33, masa 21 -> +12
        ]
        masa = self._masa(**{
            "1": {"1": 60.0, "X": 25.0, "2": 15.0},
            "2": {"1": 65.0, "X": 25.0, "2": 10.0},
            "3": {"1": 21.0, "X": 30.0, "2": 49.0},
        })
        filas = tv.clasificar_terceros(partidos, masa, _calibracion())
        self.assertEqual([f["num"] for f in filas], [3, 2, 1])
        # empate a ventaja (+12): gana la prob calibrada mayor (33 > 22)
        self.assertEqual(filas[0]["prob_calibrada"], 33.0)
        self.assertEqual(filas[0]["signo"], "1")

    def test_chip_es_el_mejor_que_cumple_ambos_umbrales(self):
        partidos = [
            # ventaja enorme pero prob calibrada < 18: NO puede ser el chip
            _partido(num=1, probs={"1": 60.0, "X": 25.0, "2": 15.0}),   # tercero 2: cal 16,5, masa 2 -> +14,5
            # cumple ambos umbrales
            _partido(num=2, probs={"1": 50.0, "X": 30.0, "2": 20.0}),   # tercero 2: cal 22, masa 12 -> +10
        ]
        masa = self._masa(**{
            "1": {"1": 70.0, "X": 28.0, "2": 2.0},
            "2": {"1": 63.0, "X": 25.0, "2": 12.0},
        })
        chip, filas = tv.elegir_tercero_valor(partidos, masa, _calibracion())
        self.assertEqual(filas[0]["num"], 1)
        self.assertFalse(filas[0]["cumple_umbrales"])
        self.assertIsNotNone(chip)
        self.assertEqual(chip["num"], 2)
        self.assertTrue(chip["cumple_umbrales"])

    def test_sin_candidatos_no_hay_chip(self):
        partidos = [_partido(num=1, probs={"1": 50.0, "X": 30.0, "2": 20.0})]
        masa = {1: {"1": 55.0, "X": 25.0, "2": 20.0}}  # ventaja 2 < 6
        chip, filas = tv.elegir_tercero_valor(partidos, masa, _calibracion())
        self.assertIsNone(chip)
        self.assertEqual(len(filas), 1)

    def test_umbral_de_ventaja_exacto(self):
        # cal 22 - masa 16 = +6: justo en el umbral, cumple (>=)
        partidos = [_partido(num=1, probs={"1": 50.0, "X": 30.0, "2": 20.0})]
        chip, _ = tv.elegir_tercero_valor(partidos, {1: {"1": 60.0, "X": 24.0, "2": 16.0}}, _calibracion())
        self.assertIsNotNone(chip)
        chip, _ = tv.elegir_tercero_valor(partidos, {1: {"1": 60.0, "X": 23.9, "2": 16.1}}, _calibracion())
        self.assertIsNone(chip)

    def test_partido_sin_masa_de_su_tercero_queda_fuera(self):
        partidos = [_partido(num=1)]
        filas = tv.clasificar_terceros(partidos, {1: {"1": 60.0, "X": 25.0}}, _calibracion())
        self.assertEqual(filas, [])


class BloqueTerceroValorTests(unittest.TestCase):
    def _prediccion(self, jornada=99, n=14, probs=None):
        return {
            "jornada": jornada,
            "partidos": [
                _partido(num=i, local=f"LOCAL{i}", visitante=f"VISITANTE{i}",
                         probs=dict(probs or {"1": 50.0, "X": 30.0, "2": 20.0}))
                for i in range(1, n + 1)
            ],
        }

    def _losilla(self, jornada=99, lae=None):
        lae = lae or {"1": 60, "X": 28, "2": 12}
        return {"probabilidades": {"jornada": jornada, "partidos": [
            {"numero": i, "fuentes_detalle": {"lae": dict(lae)}}
            for i in range(1, 15)
        ]}}

    def test_sin_14_partidos_no_disponible(self):
        bloque = tv.construir_bloque_tercero_valor(
            self._prediccion(n=10), self._losilla(), _calibracion())
        self.assertEqual(bloque["estado"], "no_disponible")

    def test_sin_masa_no_disponible(self):
        bloque = tv.construir_bloque_tercero_valor(
            self._prediccion(jornada=98), self._losilla(jornada=97), _calibracion())
        self.assertEqual(bloque["estado"], "no_disponible")
        self.assertIn("masa", bloque["motivo"])

    def test_chip_publicado_con_calibracion_declarada_y_top3(self):
        bloque = tv.construir_bloque_tercero_valor(
            self._prediccion(), self._losilla(), _calibracion())
        self.assertEqual(bloque["estado"], "ok")
        self.assertEqual(bloque["modo"], "sombra")
        self.assertEqual(bloque["signo"], "2")
        self.assertEqual(bloque["prob_motor"], 20.0)
        self.assertEqual(bloque["prob_calibrada"], 22.0)
        self.assertEqual(bloque["masa_pct"], 12.0)
        self.assertEqual(bloque["ventaja_sobre_masa"], 10.0)
        self.assertEqual(bloque["pago_estimado_eur"], 8.33)  # 100/12
        self.assertEqual(bloque["calibracion"]["metodo"], "factor_global_por_signo")
        self.assertIn("declaracion", bloque["calibracion"])
        self.assertEqual(len(bloque["top3"]), 3)
        self.assertTrue(bloque["top3"][0]["es_el_chip"])
        self.assertIn("sombra", bloque["aviso"].lower())

    def test_chip_con_freno_de_muestra_declara_cruda(self):
        bloque = tv.construir_bloque_tercero_valor(
            self._prediccion(), self._losilla(), _calibracion(n=50))
        self.assertEqual(bloque["estado"], "ok")
        self.assertEqual(bloque["prob_calibrada"], 20.0)  # la cruda
        self.assertEqual(bloque["calibracion"]["metodo"], "cruda_sin_calibrar")
        self.assertIn("SIN CALIBRAR", bloque["calibracion"]["declaracion"])

    def test_sin_candidatos_declara_sin_tercero_con_top3(self):
        bloque = tv.construir_bloque_tercero_valor(
            self._prediccion(), self._losilla(lae={"1": 55, "X": 26, "2": 19}),
            _calibracion())
        self.assertEqual(bloque["estado"], "sin_tercero_valor")
        self.assertIn("parte del diseño", bloque["motivo"])
        self.assertEqual(len(bloque["top3"]), 3)
        self.assertFalse(any(t["es_el_chip"] for t in bloque["top3"]))


class MarcadorTerceroValorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.dir_pred = base / "predicciones"
        self.dir_jorn = base / "jornadas"
        self.ruta = base / "marcador_tercero_valor.json"
        self.dir_pred.mkdir()
        self.dir_jorn.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _escribir(self, jornada=20, signo_oficial="2", local="Cadiz CF",
                  visitante="Levante UD", local_fixture=None, visitante_fixture=None):
        bloque = {
            "estado": "ok", "modo": "sombra", "jornada": jornada, "num": 5,
            "local": local, "visitante": visitante, "signo": "2",
            "prob_motor": 20.0, "prob_calibrada": 22.0, "masa_pct": 10.0,
            "calibracion": {"metodo": "factor_global_por_signo"},
        }
        (self.dir_pred / f"jornada_{jornada}.json").write_text(
            json.dumps({"jornada": jornada, "tercero_valor": bloque}), encoding="utf-8")
        (self.dir_jorn / f"jornada_{jornada}.json").write_text(json.dumps({
            "jornada": jornada,
            "partidos": [{"num": 5, "local": local_fixture or local,
                          "visitante": visitante_fixture or visitante,
                          "signo_oficial": signo_oficial}],
        }), encoding="utf-8")

    def _actualizar(self):
        return tv.actualizar_marcador_tercero_valor(
            dir_predicciones=self.dir_pred, dir_jornadas=self.dir_jorn,
            ruta_marcador=self.ruta, etiqueta="2026_2027")

    def test_registra_acierto_con_prob_calibrada_declarada(self):
        self._escribir(signo_oficial="2")
        resultado = self._actualizar()
        self.assertEqual(resultado["nuevos"], 1)
        marcador = json.loads(self.ruta.read_text(encoding="utf-8"))
        t = marcador["terceros"][0]
        self.assertTrue(t["acierto"])
        self.assertEqual(t["prob_declarada"], 22.0)  # la CALIBRADA, no la cruda
        self.assertEqual(t["prob_motor"], 20.0)
        self.assertEqual(t["pago_hipotetico_eur"], 10.0)  # 100/10
        self.assertEqual(marcador["resumen"]["aciertos"], 1)
        self.assertIn("Prerregistrado", marcador["criterio_graduacion"])

    def test_es_idempotente_por_temporada_y_jornada(self):
        self._escribir()
        self._actualizar()
        resultado = self._actualizar()
        self.assertEqual(resultado["nuevos"], 0)
        marcador = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(len(marcador["terceros"]), 1)

    def test_jornada_abierta_no_se_registra(self):
        self._escribir(signo_oficial="Pendiente")
        self.assertEqual(self._actualizar()["nuevos"], 0)

    def test_nombres_de_otra_temporada_no_puntuan(self):
        self._escribir(local_fixture="Real Zaragoza", visitante_fixture="SD Huesca")
        self.assertEqual(self._actualizar()["nuevos"], 0)

    def test_un_solo_nombre_casa_si_puntua(self):
        # alias legitimos del motor ("Celta B" vs "Celta Fortuna"): basta uno
        self._escribir(local_fixture="Cadiz CF", visitante_fixture="Levante Union Deportiva")
        self.assertEqual(self._actualizar()["nuevos"], 1)

    def test_fallo_registra_pago_cero(self):
        self._escribir(signo_oficial="1")
        self._actualizar()
        marcador = json.loads(self.ruta.read_text(encoding="utf-8"))
        t = marcador["terceros"][0]
        self.assertFalse(t["acierto"])
        self.assertEqual(t["pago_hipotetico_eur"], 0.0)


class GraduacionTests(unittest.TestCase):
    def _terceros(self, n, aciertos, prob=25.0):
        return [{"acierto": i < aciertos, "prob_declarada": prob,
                 "pago_hipotetico_eur": 8.0 if i < aciertos else 0.0}
                for i in range(n)]

    def test_menos_de_12_sigue_en_sombra(self):
        resumen = tv._resumen_marcador(self._terceros(11, aciertos=9))
        self.assertEqual(resumen["estado"], "en_sombra")

    def test_candidata_a_dinero(self):
        # 12 chips al 25% = 3 esperados; 3 aciertos (>=3 y >= esperados) gradua
        resumen = tv._resumen_marcador(self._terceros(12, aciertos=3))
        self.assertEqual(resumen["estado"], "candidata_a_dinero")
        self.assertTrue(resumen["avisar_a_marc"])

    def test_suspendida_por_debajo_del_60_pct(self):
        # 12 chips al 25% = 3 esperados; 1 acierto < 1,8 suspende
        resumen = tv._resumen_marcador(self._terceros(12, aciertos=1))
        self.assertEqual(resumen["estado"], "suspendida")

    def test_zona_intermedia_sigue_en_sombra(self):
        # 2 aciertos con 3 esperados: ni gradua ni suspende
        resumen = tv._resumen_marcador(self._terceros(12, aciertos=2))
        self.assertEqual(resumen["estado"], "en_sombra")


class BacktestTests(unittest.TestCase):
    def test_registros_previos_sin_fuga_de_futuro(self):
        from backtest_tercero_valor import registros_previos
        detalle = [
            {"jornada": 75, "x": "temporada vieja"},     # fuera del set 26/27: entra siempre
            {"jornada": 3, "x": "anterior"},             # 26/27 < limite: entra
            {"jornada": 7, "x": "la evaluada"},          # 26/27 >= limite: fuera
            {"jornada": 9, "x": "futura"},               # 26/27 >= limite: fuera
        ]
        previos = registros_previos(detalle, {1, 2, 3, 7, 9}, jornada_limite=7)
        self.assertEqual([it["jornada"] for it in previos], [75, 3])

    def test_backtest_prerregistrado_documentado(self):
        datos = json.loads(
            (ROOT / "data" / "memoria_ia" / "backtest_tercero_valor.json").read_text(encoding="utf-8"))
        criterios = datos["criterios_prerregistrados"]
        for campo in ("verde", "rojo", "neutro", "umbrales_chip", "calibracion"):
            self.assertIn(campo, criterios)
        resumen = datos["resumen"]
        for campo in ("terceros", "aciertos", "esperados", "esperados_con_prob_cruda", "veredicto"):
            self.assertIn(campo, resumen)
        # cada chip del backtest lleva su calibracion por jornada (sin fuga)
        chips = [f for f in datos["jornadas"] if f.get("estado") == "chip"]
        self.assertTrue(chips)
        for f in chips:
            self.assertIn(f["calibracion_metodo"], ("factor_global_por_signo", "cruda_sin_calibrar"))
            self.assertIn("calibracion_n", f)

    def test_advertencia_del_backtest_incrustada_en_el_bloque(self):
        texto = tv.advertencia_backtest()
        self.assertIsNotNone(texto)
        self.assertIn("sin fuga de futuro", texto)
        self.assertIn("modo sombra", texto)


class PipelineTests(unittest.TestCase):
    def test_cableado_en_el_pipeline(self):
        import actualizar_todo
        self.assertIn("tercero_valor.py", actualizar_todo.SCRIPTS_ACTIVOS)
        self.assertIn("tercero_valor.py", actualizar_todo.SCRIPTS_NO_CRITICOS_RED)
        activos = actualizar_todo.SCRIPTS_ACTIVOS
        # corre justo despues de La Valiente: misma prediccion corregida y masa
        self.assertEqual(
            activos.index("tercero_valor.py"),
            activos.index("senal_valiente.py") + 1,
        )

    def test_limpiar_prediccion_bloqueada_retira_el_bloque(self):
        import limpiar_prediccion_bloqueada
        self.assertIn("tercero_valor", limpiar_prediccion_bloqueada.CAMPOS_RAIZ_PREDICTIVOS)

    def test_marcador_enganchado_al_ciclo_de_aprendizaje(self):
        import generar_artefactos_compuerta_aprendizaje as gen
        self.assertTrue(hasattr(gen, "actualizar_marcador_tercero_valor_seguro"))
        fuente = (ROOT / "generar_artefactos_compuerta_aprendizaje.py").read_text(encoding="utf-8")
        self.assertIn("actualizar_marcador_tercero_valor_seguro()", fuente)


class FrontendTerceroValorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_tarjeta_y_render_existen(self):
        self.assertIn('id="terceroValorCard"', self.html)
        self.assertIn("function renderTerceroValor()", self.html)
        self.assertIn("renderTerceroValor();", self.html)
        self.assertIn("data/memoria_ia/marcador_tercero_valor.json", self.html)

    def test_tarjeta_no_rompe_sin_datos(self):
        bloque = self.html[self.html.index("function renderTerceroValor()"):]
        bloque = bloque[:bloque.index("// 🧪 Laboratorio")]
        # sin bloque ni marcador, la tarjeta se oculta en vez de romperse
        self.assertIn("if (!bloque && !hayMarcador) { card.style.display = 'none'; return; }", bloque)
        self.assertIn("state.prediccion?.tercero_valor", bloque)
        self.assertIn("state.marcadorTerceroValor?.resumen", bloque)
        # la advertencia roja del backtest se pinta en rojo
        self.assertIn("/ROJO/.test(bloque.advertencia_backtest)", bloque)

    def test_medidor_regla_de_los_terceros_en_panel_de_avisos(self):
        self.assertIn("Regla de los Terceros", self.html)
        bloque = self.html[self.html.index("Regla de los Terceros (19/10/2026"):]
        bloque = bloque[:bloque.index("FIJO FORZADO")]
        # reactivo a la jugada actual, como la Regla 15
        self.assertIn("selectedSigns(m)", bloque)
        self.assertIn("jugado.includes(tercero)", bloque)
        # sin probabilidades publicadas no pinta nada (ni rompe)
        self.assertIn("tEsperados >= 0.5", bloque)
        # sin jugada marcada, invita a marcarla en vez de listar nada
        self.assertIn("marca tu quiniela", bloque)
        # mismo desempate que tercero_valor.py (orden 1, X, 2 con <)
        self.assertIn("if (v < minP)", bloque)
        self.assertIn("['1', 'X', '2']", bloque)

    def test_medidor_lista_supervivientes_y_caidas(self):
        bloque = self.html[self.html.index("Regla de los Terceros (19/10/2026"):]
        bloque = bloque[:bloque.index("FIJO FORZADO")]
        self.assertIn("sobreviven", bloque)
        self.assertIn("caen", bloque)
        self.assertIn("cae con los de", bloque)


if __name__ == "__main__":
    unittest.main()
