import json
import tempfile
import unittest
from pathlib import Path

import actualizar_aprendizaje_ia as aa
from actualizar_aprendizaje_ia import (
    aciertos_verificados_con_jugada_real,
    actualizar_historial_premios,
    debe_reemplazar_registro_premios,
    generar_ajuste_motor,
    registrar_revision,
    resumen_vacio,
)


class ActualizarAprendizajeIATest(unittest.TestCase):
    def test_generar_ajuste_motor_convierte_fallos_en_reglas(self):
        resumen = {
            "partidos_revisados": 111,
            "fallos": 42,
            "fallos_por_tipo": {
                "Fijo fallado": 23,
                "No cubrio empate": 11,
                "Doble insuficiente": 8,
            },
        }

        ajuste = generar_ajuste_motor(resumen)

        self.assertEqual(ajuste["muestra"], "suficiente")
        self.assertGreater(ajuste["boost_empate_zona_riesgo"], 0)
        self.assertGreater(ajuste["riesgo_extra_fijo_fragil"], 0)
        self.assertGreater(ajuste["riesgo_extra_triple_insuficiente"], 0)
        self.assertEqual(ajuste["min_dobles_auto"], 3)
        self.assertEqual(ajuste["min_triples_auto"], 1)

    def test_registrar_revision_guarda_signo_omitido_en_fallo(self):
        resumen = resumen_vacio()
        partido = {"local": "A", "visitante": "B", "resultado": "1-1"}

        registrar_revision(resumen, 1, partido, "1", "X", "test")

        self.assertEqual(resumen["fallos"], 1)
        self.assertEqual(resumen["fallos_por_tipo"]["No cubrio empate"], 1)
        self.assertEqual(resumen["signos_omitidos_en_fallo"]["X"], 1)
        self.assertEqual(resumen["detalle"][0]["signo_omitido"], "X")

    def test_registrar_revision_enriquece_detalle_aprendizaje(self):
        resumen = resumen_vacio()
        partido = {"local": "A", "visitante": "B", "resultado": "2-0"}
        prediccion = {
            "probabilidades": {"1": 55.0, "X": 25.0, "2": 20.0},
            "origen_probabilidades": "modelo_test",
            "razonamiento": "Decision final: 1.",
            "cuotas": {"1": 1.8},
        }
        pesos = {"pesos": {"empate": 0.1, "sorpresa": 0.09}}

        registrar_revision(resumen, 1, partido, "X", "1", "test", prediccion, pesos)

        detalle = resumen["detalle"][0]
        self.assertEqual(detalle["probabilidades_usadas"]["1"], 55.0)
        self.assertEqual(detalle["pesos_modelo"]["empate"], 0.1)
        self.assertEqual(detalle["fuentes_utilizadas"], ["modelo_test"])
        self.assertEqual(detalle["resultado_final"], "2-0")
        self.assertEqual(detalle["motivo_error"], "Fijo fallado")
        self.assertEqual(detalle["cuotas"]["1"], 1.8)


class ProteccionPremiosConfirmadosTests(unittest.TestCase):
    """calcular_premios.py bloquea premios verificados a mano con
    fuente_premio="confirmado_usuario" (p.ej. jornada 71). Este script tiene
    su propio bloqueo ("manual") pero debe respetar tambien ese otro, o
    sobrescribe un premio ya comprobado contra el escrutinio oficial con su
    propia estimacion generica (mucho mas simple)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = aa.HISTORIAL_PREMIOS
        aa.HISTORIAL_PREMIOS = Path(self._tmp.name) / "historial_premios.json"

    def tearDown(self):
        aa.HISTORIAL_PREMIOS = self._original
        self._tmp.cleanup()

    def test_debe_reemplazar_es_true_para_confirmado_usuario(self):
        """Se permite refrescar aciertos/detalle, pero el premio se conserva
        (ver actualizar_historial_premios)."""
        actual = {"fuente_premio": "confirmado_usuario", "aciertos": 10}
        nuevo = {"aciertos": 10}
        self.assertTrue(debe_reemplazar_registro_premios(actual, nuevo))

    def test_actualizar_historial_premios_no_pisa_el_premio_confirmado(self):
        aa.guardar_json(aa.HISTORIAL_PREMIOS, {"jornadas": [
            {
                "jornada": 71,
                "aciertos": 10,
                "premio_eur": 0.0,
                "fuente_premio": "confirmado_usuario",
                "notas": "Verificado a mano contra eduardolosilla.es",
            }
        ]})

        registros = {71: {
            "jornada": 71,
            "aciertos": 10,
            "premio_eur": 8132.1,
            "fuente_premio": "eduardolosilla",
            "notas": "Comparado automaticamente contra data/predicciones/jornada_71.json al cerrarse la jornada.",
        }}

        actualizar_historial_premios(registros)

        historial = aa.cargar_json(aa.HISTORIAL_PREMIOS, {"jornadas": []})
        entry = next(j for j in historial["jornadas"] if j["jornada"] == 71)
        self.assertEqual(entry["premio_eur"], 0.0)
        self.assertEqual(entry["fuente_premio"], "confirmado_usuario")


class AciertosVerificadosConJugadaRealTests(unittest.TestCase):
    """Reproduce el bug real de la jornada 71: este script compara la
    prediccion CRUDA del motor contra la realidad (13 aciertos), pero
    calcular_premios.py ya habia guardado los aciertos de la quiniela
    REALMENTE jugada (10, via data/quinielas_jugadas.json). Sin esta
    proteccion, actualizar_historial_premios() pisaba los 10 aciertos reales
    con los 13 de la comparacion generica."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = aa.HISTORIAL_PREMIOS
        aa.HISTORIAL_PREMIOS = Path(self._tmp.name) / "historial_premios.json"

    def tearDown(self):
        aa.HISTORIAL_PREMIOS = self._original
        self._tmp.cleanup()

    def _entrada_real_j71(self):
        return {
            "jornada": 71,
            "aciertos": 10,
            "fallos": 4,
            "premio_eur": 0.0,
            "fuente_premio": "confirmado_usuario",
            "fuente_aciertos": "quinielas_jugadas",
            "origen_prediccion": "data/quinielas_jugadas.json",
            "aciertos_confirmados": True,
            "boleto": "1X21X22111X2X2112221",
        }

    def test_true_si_fuente_aciertos_es_quinielas_jugadas(self):
        self.assertTrue(aciertos_verificados_con_jugada_real(self._entrada_real_j71()))

    def test_false_si_no_hay_marca_de_jugada_real(self):
        actual = {"fuente_premio": "confirmado_usuario", "aciertos": 11}
        self.assertFalse(aciertos_verificados_con_jugada_real(actual))

    def test_debe_reemplazar_es_false_aunque_el_premio_sea_confirmado(self):
        nuevo = {"aciertos": 13, "boleto": "1X1XX11X1111X1X21X1X21"}
        self.assertFalse(debe_reemplazar_registro_premios(self._entrada_real_j71(), nuevo))

    def test_actualizar_historial_premios_no_pisa_los_aciertos_reales(self):
        real = self._entrada_real_j71()
        aa.guardar_json(aa.HISTORIAL_PREMIOS, {"jornadas": [real]})

        registros = {71: {
            "jornada": 71,
            "aciertos": 13,
            "fallos": 1,
            "premio_eur": 0.0,
            "fuente_premio": "eduardolosilla",
            "boleto": "1X1XX11X1111X1X21X1X21",
            "notas": "Comparado automaticamente contra data/predicciones/jornada_71.json al cerrarse la jornada.",
        }}

        actualizar_historial_premios(registros)

        historial = aa.cargar_json(aa.HISTORIAL_PREMIOS, {"jornadas": []})
        entry = next(j for j in historial["jornadas"] if j["jornada"] == 71)
        self.assertEqual(entry["aciertos"], 10)
        self.assertEqual(entry["boleto"], "1X21X22111X2X2112221")
        self.assertEqual(entry["fuente_aciertos"], "quinielas_jugadas")


class ProbabilidadesJornadaLosillaTests(unittest.TestCase):
    """Bug real (18/08/2026): registrar_sorpresas_mercado() leia siempre
    fuente_losilla["probabilidades"] (la jornada ACTIVA en Losilla en ese
    momento) para puntuar la jornada que se estaba cerrando -en cuanto
    Losilla avanzaba a la jornada siguiente, se comparaba la jornada cerrada
    contra las cuotas de la jornada equivocada (o contra nada). Ahora debe
    usar el historico por jornada que escribe actualizar_fuente_losilla.py."""

    def test_usa_el_historico_de_la_jornada_pedida(self):
        fuente_losilla = {
            "probabilidades": {"jornada": 2, "partidos": [{"numero": 1, "probabilidad_1": 58.5}]},
            "historico_probabilidades": {
                "jornada_01": {"jornada": 1, "partidos": [{"numero": 1, "probabilidad_1": 44.6}]}
            },
        }
        bloque = aa.probabilidades_jornada_losilla(fuente_losilla, 1)
        self.assertEqual(bloque["partidos"][0]["probabilidad_1"], 44.6)

    def test_no_usa_el_bloque_actual_si_es_de_otra_jornada(self):
        """Sin historico para la jornada 1 y con "probabilidades" ya en la
        jornada 2, no debe devolver por error las cuotas de la jornada 2
        como si fueran de la 1."""
        fuente_losilla = {
            "probabilidades": {"jornada": 2, "partidos": [{"numero": 1, "probabilidad_1": 58.5}]},
        }
        bloque = aa.probabilidades_jornada_losilla(fuente_losilla, 1)
        self.assertEqual(bloque, {})

    def test_cae_al_bloque_actual_si_coincide_la_jornada(self):
        fuente_losilla = {
            "probabilidades": {"jornada": 1, "partidos": [{"numero": 1, "probabilidad_1": 44.6}]},
        }
        bloque = aa.probabilidades_jornada_losilla(fuente_losilla, 1)
        self.assertEqual(bloque["partidos"][0]["probabilidad_1"], 44.6)

    def test_mercado_partido_losilla_respeta_la_jornada(self):
        fuente_losilla = {
            "historico_probabilidades": {
                "jornada_01": {
                    "jornada": 1,
                    "partidos": [{"numero": 5, "probabilidades_signo": {"1": 10.0, "X": 10.0, "2": 80.0}}],
                },
                "jornada_02": {
                    "jornada": 2,
                    "partidos": [{"numero": 5, "probabilidades_signo": {"1": 90.0, "X": 5.0, "2": 5.0}}],
                },
            }
        }
        favorito, prob, _ = aa.mercado_partido_losilla(fuente_losilla, 1, 5)
        self.assertEqual(favorito, "2")
        self.assertEqual(prob, 80.0)


if __name__ == "__main__":
    unittest.main()


class OrdenCronologicoJornadaTests(unittest.TestCase):
    """Bug real (18/08/2026): el detalle de revisiones se recorta a las
    ultimas 250 entradas dando por hecho que "ultimas" == "numero mas alto".
    Con el reinicio de numeracion de La Quiniela, la J1 de 26/27 -la mas
    reciente- quedaba la PRIMERA de la lista y era justo la que el recorte
    tiraba. Sin sus 14 revisiones, la compuerta de aprendizaje dejaba la
    prediccion de la J2 bloqueada indefinidamente."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def _escribir(self, numero, fecha):
        (self.base / f"jornada_{numero}.json").write_text(
            json.dumps({
                "jornada": numero,
                "partidos": [{"num": 1, "fecha": fecha}],
            }),
            encoding="utf-8",
        )
        return self.base / f"jornada_{numero}.json"

    def test_la_jornada_1_nueva_va_despues_de_la_76_vieja(self):
        vieja = self._escribir(76, "2026-08-09")
        nueva = self._escribir(1, "2026-08-15")
        orden = sorted([nueva, vieja], key=aa.orden_cronologico_jornada)
        self.assertEqual([p.stem for p in orden], ["jornada_76", "jornada_1"])

    def test_dentro_de_la_misma_temporada_manda_la_fecha(self):
        j2 = self._escribir(2, "2026-08-22")
        j3 = self._escribir(3, "2026-08-29")
        orden = sorted([j3, j2], key=aa.orden_cronologico_jornada)
        self.assertEqual([p.stem for p in orden], ["jornada_2", "jornada_3"])

    def test_sin_fecha_se_trata_como_lo_mas_antiguo(self):
        sin_fecha = self.base / "jornada_9.json"
        sin_fecha.write_text(json.dumps({"jornada": 9, "partidos": [{"num": 1}]}), encoding="utf-8")
        con_fecha = self._escribir(1, "2026-08-15")
        orden = sorted([con_fecha, sin_fecha], key=aa.orden_cronologico_jornada)
        self.assertEqual([p.stem for p in orden], ["jornada_9", "jornada_1"])


if __name__ == "__main__":
    unittest.main()
