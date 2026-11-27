"""Tests de la auditoria del 26/11/2026, paquete P5 (premios, reparto y optimizadores).

Cada clase reproduce un hallazgo confirmado: fallaba antes del arreglo.
Sin red: lo que consulta webs se sustituye por funciones locales.
"""
import json
import math
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_porcentajes_lae as apl
import aplicar_elige8_seguro as e8
import backtest_optimizador_boleto as bt
import calcular_premios as cp
import modelo_reparto_quiniela as mr
import optimizador_boleto as ob
import optimizador_ev_premio as oev
import publicar_optimizador_boleto as pub
import seleccionar_pleno15 as p15

DATA = ROOT / "data"


def _html_escrutinio(recaudacion, filas):
    cuerpo = "".join(
        f"<tr><td>{cat} Aciertos</td><td>{acert}</td><td>{premio} &euro;</td></tr>"
        for cat, acert, premio in filas
    )
    return (f"<html><body><p>Recaudaci&oacute;n {recaudacion} &euro; Bote 220.379,09 &euro;</p>"
            f"<table>{cuerpo}</table></body></html>")


FILAS_J23 = [
    (15, "30", "14.696,74"), (14, "152", "3.095,06"), (13, "3.105", "71,02"),
    (12, "28.917", "7,63"), (11, "148.971", "1,48"), (10, "455.229", "0,00"),
]
FILAS_PLACEBO = [(c, "0", "0,00") for c in (15, 14, 13, 12, 11, 10)]


# ---------------------------------------------------------------- 7 / 12 / 40
class RecaudacionParseoTests(unittest.TestCase):
    def test_punto_decimal_no_multiplica_por_cien(self):
        self.assertEqual(apl._numero_es("2.940.306.75"), 2940306.75)
        self.assertEqual(apl._numero_es("2940306.75"), 2940306.75)
        self.assertEqual(apl._numero_es("12.50"), 12.5)

    def test_formato_espanol_sigue_igual(self):
        self.assertEqual(apl._numero_es("3.500.149,50"), 3500149.5)
        self.assertEqual(apl._numero_es("1.033"), 1033.0)
        self.assertEqual(apl._numero_es("28.917"), 28917.0)
        self.assertEqual(apl._numero_es("0,00"), 0.0)
        self.assertIsNone(apl._numero_es("sin dato"))

    def test_escrutinio_con_punto_decimal_guarda_la_recaudacion_real(self):
        datos = apl.parsear_escrutinio_html(_html_escrutinio("2.940.306.75", FILAS_J23))
        self.assertAlmostEqual(datos["recaudacion_eur"], 2940306.75, places=2)

    def test_recaudacion_absurda_se_reconstruye_desde_el_escrutinio(self):
        datos = apl.parsear_escrutinio_html(_html_escrutinio("294.030.675,00", FILAS_J23))
        self.assertTrue(mr.recaudacion_en_rango(datos["recaudacion_eur"]))
        self.assertAlmostEqual(datos["recaudacion_eur"], 3105 * 71.02 / 0.075, delta=1.0)
        self.assertTrue(datos["recaudacion_reconstruida"])
        self.assertEqual(datos["recaudacion_leida_descartada"], 294030675.0)

    def test_recaudacion_estimada_no_se_infla_con_un_escrutinio_corrupto(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            buena = {"categorias": {}, "recaudacion_eur": 2_000_000.0}
            corrupta = {
                "recaudacion_eur": 294030675.0,
                "categorias": {str(c): {"acertantes": int(a.replace(".", "")),
                                        "premio_eur": float(p.replace(".", "").replace(",", "."))}
                               for c, a, p in FILAS_J23},
            }
            (carpeta / "jornada_1.json").write_text(json.dumps({"escrutinio": buena}), encoding="utf-8")
            (carpeta / "jornada_2.json").write_text(json.dumps({"escrutinio": corrupta}), encoding="utf-8")
            valor, n = oev.recaudacion_estimada(carpeta=carpeta)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(valor, (2_000_000.0 + 3105 * 71.02 / 0.075) / 2, delta=1.0)

    def test_la_recaudacion_de_un_escrutinio_placebo_no_cuenta_en_la_media(self):
        # J14 26/27: todas las categorias a 0 pero con recaudacion declarada.
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            buena = {"categorias": {}, "recaudacion_eur": 2_000_000.0}
            placebo = {"recaudacion_eur": 3488166.0,
                       "categorias": {str(c): {"acertantes": 0, "premio_eur": 0.0}
                                      for c in (15, 14, 13, 12, 11, 10)}}
            (carpeta / "jornada_1.json").write_text(json.dumps({"escrutinio": buena}), encoding="utf-8")
            (carpeta / "jornada_14.json").write_text(json.dumps({"escrutinio": placebo}), encoding="utf-8")
            self.assertEqual(oev.recaudacion_estimada(carpeta=carpeta), (2_000_000.0, 1))

    def test_los_dos_optimizadores_usan_la_misma_recaudacion(self):
        self.assertEqual(oev.recaudacion_estimada(), ob.recaudacion_media_plausible())

    def test_dato_real_j23_reparado_y_temporada_en_rango(self):
        j23 = json.loads((DATA / "memoria_ia" / "porcentajes_lae" / "2026_2027" / "jornada_23.json")
                         .read_text(encoding="utf-8"))
        self.assertAlmostEqual(j23["escrutinio"]["recaudacion_eur"], 2940306.75, places=2)
        valor, n = oev.recaudacion_estimada(etiqueta="2026_2027")
        self.assertGreater(n, 10)
        self.assertTrue(600_000 < valor < 4_000_000, valor)


# ---------------------------------------------------------------- 53 / 102
class EscrutinioPlaceboTests(unittest.TestCase):
    def test_plantilla_a_cero_no_se_guarda(self):
        self.assertIsNone(apl.parsear_escrutinio_html(_html_escrutinio("3.488.166,00", FILAS_PLACEBO)))

    def test_acertantes_que_no_crecen_al_bajar_no_son_plausibles(self):
        escrutinio = {"categorias": {
            "14": {"acertantes": 5}, "13": {"acertantes": 40}, "12": {"acertantes": 334},
            "11": {"acertantes": 2}, "10": {"acertantes": 15}}}
        self.assertFalse(mr.escrutinio_plausible(escrutinio))

    def test_el_placebo_guardado_se_vuelve_a_pedir(self):
        originales = (apl.SALIDA_BASE, apl.jornada_cerrada, apl.descargar_escrutinio)
        pedidas = []
        with tempfile.TemporaryDirectory() as tmp:
            try:
                apl.SALIDA_BASE = Path(tmp)
                carpeta = Path(tmp) / "2026_2027"
                carpeta.mkdir()
                placebo = {"categorias": {str(c): {"acertantes": 0, "premio_eur": 0.0}
                                          for c in (15, 14, 13, 12, 11, 10)}, "recaudacion_eur": 3488166.0}
                (carpeta / "jornada_14.json").write_text(
                    json.dumps({"jornada": 14, "partidos": [], "escrutinio": placebo}), encoding="utf-8")
                apl.jornada_cerrada = lambda jornada: True
                apl.descargar_escrutinio = lambda jornada: pedidas.append(jornada)
                apl.completar_escrutinios("2026_2027")
            finally:
                apl.SALIDA_BASE, apl.jornada_cerrada, apl.descargar_escrutinio = originales
        self.assertEqual(pedidas, [14])


# ---------------------------------------------------------------- 136 / 243
class TemporadaYCierreTests(unittest.TestCase):
    def test_julio_de_una_jornada_alta_es_la_temporada_que_acaba(self):
        self.assertEqual(apl.temporada_etiqueta(datetime(2026, 7, 20), 74), "2025_2026")
        self.assertEqual(apl.temporada_etiqueta(datetime(2026, 8, 7), 76), "2025_2026")
        self.assertEqual(apl.temporada_etiqueta(datetime(2026, 8, 15), 1), "2026_2027")

    def test_no_hereda_el_escrutinio_de_otra_jornada_con_el_mismo_numero(self):
        original = apl.SALIDA_BASE
        with tempfile.TemporaryDirectory() as tmp:
            try:
                apl.SALIDA_BASE = Path(tmp)
                viejos = [{"numero": n, "local": f"Viejo{n}", "visitante": f"Rival{n}",
                           "porcentajes": {"1": 40, "X": 30, "2": 30}} for n in range(1, 15)]
                nuevos = [{"numero": n, "local": f"Nuevo{n}", "visitante": f"Otro{n}",
                           "porcentajes": {"1": 40, "X": 30, "2": 30}} for n in range(1, 15)]
                destino = apl.ruta_porcentajes(72, "2026_2027")
                destino.parent.mkdir(parents=True)
                destino.write_text(json.dumps({"jornada": 72, "partidos": viejos, "fuente": "x",
                                               "escrutinio": {"recaudacion_eur": 1.0}}), encoding="utf-8")
                apl.guardar_porcentajes_jornada({"jornada": 72, "partidos": nuevos}, "2026_2027", "fuente nueva")
                guardado = json.loads(destino.read_text(encoding="utf-8"))
            finally:
                apl.SALIDA_BASE = original
        self.assertNotIn("escrutinio", guardado)

    def test_cierre_en_horario_de_verano_mantiene_el_margen(self):
        cierre = apl.cierre_aproximado_utc(datetime(2026, 8, 15, 17, 0))  # 17:00 Madrid = 15:00 UTC
        self.assertEqual((cierre.hour, cierre.minute), (13, 0))
        cierre = apl.cierre_aproximado_utc(datetime(2026, 12, 5, 14, 0))  # 14:00 Madrid = 13:00 UTC
        self.assertEqual((cierre.hour, cierre.minute), (11, 0))


# ---------------------------------------------------------------- 150
class SinSegundaMezclaTests(unittest.TestCase):
    MOTOR = {"1": 70.3, "X": 20.6, "2": 9.1}
    LOSILLA = {"1": 50.0, "X": 30.0, "2": 20.0}

    def _partido(self, peso):
        return {"ajuste_mercado_losilla": {"activo": True, "lecturas": [
            f"Mercado Losilla: consenso publico integrado con peso {peso} (calidad_datos=alta)."]}}

    def setUp(self):
        self._interruptor = oev.EVITAR_SEGUNDA_MEZCLA

    def tearDown(self):
        oev.EVITAR_SEGUNDA_MEZCLA = self._interruptor

    def test_por_defecto_no_se_toma_la_decision_de_modelado(self):
        # Quitar la segunda mezcla cambia pesos y el boleto en sombra: lo
        # decide Marc. Apagado, la formula publicada es la de siempre.
        self.assertFalse(oev.EVITAR_SEGUNDA_MEZCLA)
        mezcla = oev.mezclar_probabilidades(self.MOTOR, self.LOSILLA, partido=self._partido(0.85))
        self.assertAlmostEqual(mezcla["1"], 0.6015, places=6)

    def test_apagado_el_bloque_avisa_de_la_doble_mezcla_sin_cambiar_numeros(self):
        partidos = [self._partido(0.85) for _ in range(14)]
        texto, ya, sin_mezcla, sin_peso = oev.descripcion_fuente_probabilidad(partidos)
        self.assertEqual((ya, sin_mezcla, sin_peso), (14, 0, 0))
        self.assertIn("50/50", texto)
        self.assertIn("pendiente de Marc", texto)
        oev.EVITAR_SEGUNDA_MEZCLA = True
        texto, ya, sin_mezcla, _ = oev.descripcion_fuente_probabilidad(partidos)
        self.assertEqual((ya, sin_mezcla), (14, 14))
        self.assertIn("sin segunda mezcla", texto)

    def test_traza_activa_sin_peso_reconocible_se_cuenta(self):
        # Si el motor cambia el texto de la lectura, no debe pasar en silencio.
        raro = {"ajuste_mercado_losilla": {"activo": True, "lecturas": ["Mercado aplicado (0.85)."]}}
        self.assertTrue(oev.traza_mercado_sin_peso(raro))
        self.assertFalse(oev.traza_mercado_sin_peso(self._partido(0.85)))
        self.assertEqual(oev.descripcion_fuente_probabilidad([raro, self._partido(0.85)])[3], 1)

    def test_con_el_interruptor_encendido_se_usa_la_probabilidad_publicada(self):
        oev.EVITAR_SEGUNDA_MEZCLA = True
        mezcla = oev.mezclar_probabilidades(self.MOTOR, self.LOSILLA, partido=self._partido(0.85))
        self.assertAlmostEqual(mezcla["1"], 0.703, places=6)
        self.assertAlmostEqual(mezcla["2"], 0.091, places=6)

    def test_con_peso_bajo_sigue_la_mezcla_al_50(self):
        oev.EVITAR_SEGUNDA_MEZCLA = True
        mezcla = oev.mezclar_probabilidades(self.MOTOR, self.LOSILLA, partido=self._partido(0.45))
        self.assertAlmostEqual(mezcla["1"], (0.703 + 0.5) / 2, places=6)

    def test_sin_traza_o_inactiva_sigue_la_mezcla_al_50(self):
        oev.EVITAR_SEGUNDA_MEZCLA = True
        self.assertAlmostEqual(oev.mezclar_probabilidades(self.MOTOR, self.LOSILLA)["1"], 0.6015, places=6)
        inactiva = {"ajuste_mercado_losilla": {"activo": False, "lecturas": ["integrado con peso 0.85"]}}
        self.assertAlmostEqual(
            oev.mezclar_probabilidades(self.MOTOR, self.LOSILLA, partido=inactiva)["1"], 0.6015, places=6)

    def test_peso_numerico_tambien_vale(self):
        partido = {"ajuste_mercado_losilla": {"activo": True, "peso": 0.85}}
        self.assertTrue(oev.mercado_ya_integrado(partido))
        self.assertEqual(oev.peso_mercado_integrado(self._partido("0,85")), 0.85)


# ---------------------------------------------------------------- 71 / 103
class Pleno15Tests(unittest.TestCase):
    def test_m_es_tres_o_mas_goles_y_las_casillas_suman_cien(self):
        goles = p15.calcular_probs_goles({"probabilidades": {"1": 50, "X": 25, "2": 25}})
        lam = goles["lambda_local"]
        p_tres_o_mas = 1 - sum(math.exp(-lam) * lam ** k / math.factorial(k) for k in range(3))
        self.assertAlmostEqual(goles["local"]["M"], round(p_tres_o_mas * 100, 1), places=1)
        for lado in ("local", "visitante"):
            self.assertAlmostEqual(sum(goles[lado].values()), 100.0, delta=0.25)

    def test_el_motivo_no_dice_que_la_prediccion_este_bloqueada(self):
        motivo = p15.MOTIVO_SIN_PROBABILIDADES_PLENO15
        self.assertIn("partido 15", motivo)
        self.assertNotIn("ningun partido", motivo)


# ---------------------------------------------------------------- 129 / 72
class JugadaPorTemporadaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._orig = {k: getattr(cp, k) for k in
                      ("QUINIELAS_JUGADAS", "HISTORIAL_QUINIELAS", "PREDICCIONES", "JORNADAS",
                       "PORCENTAJES_LAE", "SALIDA")}
        cp.QUINIELAS_JUGADAS = tmp / "quinielas_jugadas.json"
        cp.HISTORIAL_QUINIELAS = tmp / "historial_quinielas.json"
        cp.PREDICCIONES = tmp / "predicciones"
        cp.JORNADAS = tmp / "jornadas"
        cp.PORCENTAJES_LAE = tmp / "porcentajes_lae"
        cp.SALIDA = tmp / "historial_premios.json"
        cp.PREDICCIONES.mkdir()
        cp.JORNADAS.mkdir()
        cp.HISTORIAL_QUINIELAS.write_text(json.dumps({"jornadas": []}), encoding="utf-8")
        self._red = (cp.descargar_html, cp.requests.get, cp.requests.post)

        def sin_red(*args, **kwargs):
            raise AssertionError("este test no debe consultar la red")

        cp.descargar_html = lambda url, params=None: None
        cp.requests.get = sin_red
        cp.requests.post = sin_red
        cp._TEMPORADA_ACTUAL_CACHE.clear()

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(cp, k, v)
        cp.descargar_html, cp.requests.get, cp.requests.post = self._red
        cp._TEMPORADA_ACTUAL_CACHE.clear()
        self._tmp.cleanup()

    def _fixture(self, jornada, fecha, oficiales=None):
        oficiales = oficiales or ["1"] * 14
        (cp.JORNADAS / f"jornada_{jornada}.json").write_text(json.dumps({
            "jornada": jornada,
            "partidos": [{"num": i + 1, "local": f"L{i}", "visitante": f"V{i}", "fecha": fecha,
                          "signo_oficial": s} for i, s in enumerate(oficiales)],
        }), encoding="utf-8")

    def _jugadas(self, *jugadas):
        cp.QUINIELAS_JUGADAS.write_text(json.dumps({"jugadas": list(jugadas)}), encoding="utf-8")

    def test_la_j59_nueva_no_casa_con_la_jugada_de_la_temporada_pasada(self):
        self._fixture(59, "2027-04-25")
        self._jugadas({"jornada": 59, "signos": ["2"] * 14, "validado_en": "13/5/2026, 13:18:27"})
        self.assertEqual(cp.jugada_por_jornada(59), {})
        self.assertEqual(cp.prediccion_desde_quinielas_jugadas(59), {})

    def test_con_dos_jugadas_del_mismo_numero_gana_la_de_la_temporada_del_fixture(self):
        self._fixture(59, "2027-04-25")
        self._jugadas(
            {"jornada": 59, "signos": ["2"] * 14, "validado_en": "13/5/2026, 13:18:27"},
            {"jornada": 59, "signos": ["1"] * 14, "validado_en": "2027-04-24T09:00:00+00:00"},
        )
        self.assertEqual(cp.jugada_por_jornada(59)["signos"][0], "1")
        self._fixture(59, "2026-05-16")
        self.assertEqual(cp.jugada_por_jornada(59)["signos"][0], "2")

    def test_el_campo_temporada_manda_sobre_validado_en(self):
        self._fixture(59, "2027-04-25")
        self._jugadas({"jornada": 59, "temporada": "2026_2027", "signos": ["X"] * 14,
                       "validado_en": "13/5/2026, 13:18:27"})
        self.assertEqual(cp.jugada_por_jornada(59)["signos"][0], "X")

    def test_sin_fechas_en_el_fixture_se_conserva_el_comportamiento_anterior(self):
        self._jugadas({"jornada": 70, "signos": ["1X"] + ["1"] * 13})
        self.assertEqual(cp.jugada_por_jornada(70)["signos"][0], "1X")

    def test_sin_boleto_no_se_siembra_un_registro_de_cero_aciertos(self):
        self._fixture(30, "2025-12-21")
        self._jugadas()
        self.assertIsNone(cp.registro_jornada(30))

    def test_sin_jugada_real_no_se_atribuye_premio_ni_se_confirma(self):
        self._fixture(22, "2026-11-18")
        self._jugadas()
        cp.HISTORIAL_QUINIELAS.write_text(json.dumps({"jornadas": [
            {"jornada": 22, "nuestra_quiniela": " ".join(["1"] * 14)}]}), encoding="utf-8")
        carpeta = cp.PORCENTAJES_LAE / "2026_2027"
        carpeta.mkdir(parents=True)
        (carpeta / "jornada_22.json").write_text(json.dumps({"jornada": 22, "partidos": [], "escrutinio": {
            "categorias": {"14": {"acertantes": 267, "premio_eur": 372.67},
                           "13": {"acertantes": 4832, "premio_eur": 9.65},
                           "12": {"acertantes": 30425, "premio_eur": 3.07},
                           "11": {"acertantes": 90814, "premio_eur": 0.0},
                           "10": {"acertantes": 155685, "premio_eur": 0.0}}}}), encoding="utf-8")
        reg = cp.registro_jornada(22)
        self.assertEqual(reg["aciertos"], 14)
        self.assertEqual(reg["premio_eur"], 0.0)
        self.assertEqual(reg["fuente_premio"], "sin_jugada")
        self.assertFalse(reg["aciertos_confirmados"])
        self.assertEqual(reg["temporada"], "2026_2027")
        self.assertFalse(cp.pendiente_premio(reg))

    def test_main_no_mezcla_el_registro_de_otra_temporada_y_purga_los_sembrados(self):
        self._fixture(59, "2027-04-25", ["1"] * 14)
        self._fixture(30, "2025-12-21")
        self._jugadas(
            {"jornada": 59, "signos": ["2"] * 14, "validado_en": "13/5/2026, 13:18:27"},
            {"jornada": 59, "signos": ["1"] * 13 + ["2"], "validado_en": "2027-04-24T09:00:00+00:00",
             "premio_eur": 0.0},
        )
        viejo = {"jornada": 59, "temporada": "2025_2026", "aciertos": 9, "fallos": 5, "premio_eur": 0.0,
                 "fuente_premio": "pendiente", "fuente_aciertos": "quinielas_jugadas",
                 "origen_prediccion": "data/quinielas_jugadas.json", "aciertos_confirmados": True,
                 "detalle_partidos": [{"num": i + 1, "tipo": "FIJO", "signo_oficial": "2"} for i in range(14)]}
        sembrado = {"jornada": 30, "aciertos": 0, "fallos": 0, "premio_eur": 0.0, "fuente_premio": "pendiente",
                    "fuente_aciertos": "historial_quinielas", "aciertos_confirmados": True,
                    "detalle_partidos": []}
        cp.SALIDA.write_text(json.dumps({"jornadas": [sembrado, viejo]}), encoding="utf-8")
        cp.main()
        guardadas = json.loads(cp.SALIDA.read_text(encoding="utf-8"))["jornadas"]
        self.assertEqual([(e["jornada"], e.get("temporada")) for e in guardadas],
                         [(59, "2025_2026"), (59, "2026_2027")])
        self.assertEqual(guardadas[0]["aciertos"], 9)           # el viejo no se toca
        self.assertEqual(guardadas[1]["aciertos"], 13)          # el nuevo usa la jugada de su temporada
        self.assertEqual(guardadas[1]["fuente_premio"], "confirmado_usuario")

    def test_main_dos_veces_conserva_los_dos_registros_del_mismo_numero(self):
        # Con dos registros J59 en el fichero (uno por temporada), indexar
        # solo por numero perdia el archivado en el segundo guardado.
        self._fixture(59, "2027-04-25", ["1"] * 14)
        self._fixture(30, "2025-12-21")
        self._jugadas(
            {"jornada": 59, "signos": ["2"] * 14, "validado_en": "13/5/2026, 13:18:27"},
            {"jornada": 59, "signos": ["1"] * 13 + ["2"], "validado_en": "2027-04-24T09:00:00+00:00",
             "premio_eur": 0.0},
        )
        viejo = {"jornada": 59, "temporada": "2025_2026", "aciertos": 9, "fallos": 5, "premio_eur": 0.0,
                 "fuente_premio": "pendiente", "fuente_aciertos": "quinielas_jugadas",
                 "origen_prediccion": "data/quinielas_jugadas.json", "aciertos_confirmados": True,
                 "detalle_partidos": [{"num": i + 1, "tipo": "FIJO", "signo_oficial": "2"} for i in range(14)]}
        cp.SALIDA.write_text(json.dumps({"jornadas": [viejo]}), encoding="utf-8")
        cp.main()
        # segunda pasada con otro cambio que obliga a guardar (un sembrado a purgar)
        historial = json.loads(cp.SALIDA.read_text(encoding="utf-8"))
        historial["jornadas"].append(
            {"jornada": 30, "aciertos": 0, "fallos": 0, "premio_eur": 0.0, "fuente_premio": "pendiente",
             "fuente_aciertos": "historial_quinielas", "aciertos_confirmados": True, "detalle_partidos": []})
        for orden in (historial["jornadas"], list(reversed(historial["jornadas"]))):
            cp.SALIDA.write_text(json.dumps({"jornadas": orden}), encoding="utf-8")
            cp.main()
            guardadas = json.loads(cp.SALIDA.read_text(encoding="utf-8"))["jornadas"]
            self.assertEqual([(e["jornada"], e.get("temporada")) for e in guardadas],
                             [(59, "2025_2026"), (59, "2026_2027")])
            self.assertEqual(guardadas[0]["aciertos"], 9)
            self.assertEqual(guardadas[1]["aciertos"], 13)
            guardadas.append(historial["jornadas"][-1])

    def _escrutinio_j20(self):
        carpeta = cp.PORCENTAJES_LAE / "2026_2027"
        carpeta.mkdir(parents=True)
        (carpeta / "jornada_20.json").write_text(json.dumps({"jornada": 20, "partidos": [], "escrutinio": {
            "categorias": {"14": {"acertantes": 6, "premio_eur": 80079.2},
                           "13": {"acertantes": 185, "premio_eur": 1369.75},
                           "12": {"acertantes": 2301, "premio_eur": 110.13},
                           "11": {"acertantes": 17496, "premio_eur": 14.48},
                           "10": {"acertantes": 89116, "premio_eur": 0.0}}}}), encoding="utf-8")

    def _entrada_10_aciertos(self, elige8):
        # doble en el P1 (multicolumna); 10 aciertos, categoria de 10 a 0,00
        oficiales = ["1"] * 10 + ["2"] * 4
        self._fixture(20, "2026-11-08", oficiales)
        self._jugadas({"jornada": 20, "temporada": "2026_2027", "signos": ["1X"] + ["1"] * 13})
        detalle = [{"num": i + 1, "tipo": "DOBLE" if i == 0 else "FIJO", "signo_oficial": s,
                    "signo_final": "1X" if i == 0 else "1"} for i, s in enumerate(oficiales)]
        return {"jornada": 20, "temporada": "2026_2027", "aciertos": 10, "fallos": 4, "premio_eur": 0.0,
                "fuente_premio": "pendiente", "boleto": "1X" + "1" * 13, "detalle_partidos": detalle,
                "elige8_jugado": elige8, "elige8_seleccion": list(range(1, 9)) if elige8 else [],
                "elige8_acertado": elige8}

    def test_cero_del_escrutinio_versionado_no_cierra_un_elige8_acertado(self):
        self._escrutinio_j20()
        sin_elige8 = self._entrada_10_aciertos(False)
        if not cp.boleto_tiene_multiples_columnas(sin_elige8):
            self.skipTest("el registro sintetico no se reconoce como multicolumna")
        cp.refrescar_premio_real(sin_elige8)
        self.assertEqual(sin_elige8["fuente_premio"], "escrutinio_versionado")
        self.assertFalse(cp.pendiente_premio(sin_elige8))
        con_elige8 = self._entrada_10_aciertos(True)
        cp.refrescar_premio_real(con_elige8)
        self.assertNotEqual(con_elige8["fuente_premio"], "escrutinio_versionado")
        self.assertTrue(cp.pendiente_premio(con_elige8))

    def test_elige8_sin_premio_en_la_tabla_deja_el_registro_pendiente(self):
        self.assertTrue(cp.elige8_sin_premio_en_tabla(True, {"13": 10.0}))
        self.assertFalse(cp.elige8_sin_premio_en_tabla(True, {"13": 10.0, "elige8": 94.33}))
        self.assertFalse(cp.elige8_sin_premio_en_tabla(False, {"13": 10.0}))
        reg = {"premio_eur": 14.48, "fuente_premio": "multicolumna_loteriaanta", "notas": "x"}
        cp.marcar_elige8_pendiente(reg, True)
        self.assertTrue(cp.pendiente_premio(reg))
        self.assertIn("Elige 8", reg["notas"])
        cp.marcar_elige8_pendiente(reg, False)
        self.assertNotIn("elige8_premio_pendiente", reg)


# ---------------------------------------------------------------- 11 / 25 / 97
class TablaPremiosTests(unittest.TestCase):
    HTML_J20 = """
    <html><body><h1>Resultados Quiniela - Jornada 20</h1><table>
      <tr><td>1a (14 aciertos)</td><td>6</td><td>80.079,20 &euro;</td></tr>
      <tr><td>2a (13 aciertos)</td><td>185</td><td>1.369,75 &euro;</td></tr>
      <tr><td>3a (12 aciertos)</td><td>2.301</td><td>110,13 &euro;</td></tr>
      <tr><td>4a (11 aciertos)</td><td>17.496</td><td>14,48 &euro;</td></tr>
      <tr><td>5a (10 aciertos)</td><td>89.116</td><td>3,41 &euro;</td></tr>
    </table></body></html>
    """

    def test_no_acepta_la_pagina_de_otra_jornada(self):
        self.assertEqual(cp.tabla_premios_desde_html_loteriaanta(self.HTML_J20, 15), {})
        self.assertEqual(cp.tabla_premios_desde_html_loteriaanta(self.HTML_J20, 2), {})

    def test_un_desplegable_con_todas_las_jornadas_no_hace_pasar_la_pagina(self):
        desplegable = "<select>" + "".join(
            f"<option>Jornada {n}</option>" for n in range(1, 61)) + "</select>"
        html = self.HTML_J20.replace("<table>", desplegable + "<table>")
        self.assertEqual(cp.tabla_premios_desde_html_loteriaanta(html, 15), {})
        self.assertTrue(cp.tabla_premios_desde_html_loteriaanta(html, 20))
        # listado de enlaces sin titular que diga de que jornada es la tabla
        listado = "<ul>" + "".join(f"<li><a>Jornada {n}</a></li>" for n in range(1, 61)) + "</ul>"
        sin_titular = self.HTML_J20.replace("<h1>Resultados Quiniela - Jornada 20</h1>", listado)
        self.assertEqual(cp.tabla_premios_desde_html_loteriaanta(sin_titular, 15), {})
        self.assertEqual(cp.tabla_premios_desde_html_loteriaanta(sin_titular, 20), {})

    def test_la_categoria_no_se_confunde_con_los_importes(self):
        tabla = cp.tabla_premios_desde_html_loteriaanta(self.HTML_J20, 20)
        self.assertEqual(tabla, {"13": 1369.75, "12": 110.13, "11": 14.48, "10": 3.41})

    def test_ya_no_se_consulta_la_url_sin_jornada(self):
        original = cp.requests.get
        urls = []

        class Respuesta:
            status_code = 200
            text = TablaPremiosTests.HTML_J20

        def falso_get(url, **kwargs):
            urls.append(url)
            return Respuesta()

        try:
            cp.requests.get = falso_get
            tabla = cp.buscar_tabla_premios_loteriaanta(15)
        finally:
            cp.requests.get = original
        self.assertEqual(tabla, {})
        self.assertTrue(urls and all("jornada=15" in u for u in urls), urls)

    def test_tablas_placebo_reales_del_historial_no_son_validas(self):
        self.assertFalse(cp.tabla_premios_valida(
            {"14": 14.48, "13": 110.13, "12": 12.55, "11": 14.48, "10": 3.41}))
        self.assertFalse(cp.tabla_premios_valida(
            {"14": 1.14, "15": 17119.56, "13": 13.93, "11": 2.03, "10": 10.0, "12": 8.77}))
        self.assertFalse(cp.tabla_premios_valida(
            {"14": 8132.1, "15": 15.22, "10": 8132.1, "11": 3.08, "12": 17.09, "13": 158.32}))
        self.assertFalse(cp.tabla_premios_valida({str(c): 0.0 for c in (15, 14, 13, 12, 11, 10)}))

    def test_tablas_reales_son_validas(self):
        self.assertTrue(cp.tabla_premios_valida(
            {"15": 0.0, "14": 0.0, "13": 6795.61, "12": 322.21, "11": 23.43, "10": 3.93}))
        self.assertTrue(cp.tabla_premios_valida(
            {"15": 1008.51, "14": 589.67, "13": 13.96, "12": 4.26, "11": 0.0, "10": 0.0}))
        self.assertTrue(cp.tabla_premios_valida({"15": 0.0, "12": 446.23, "11": 54.78, "10": 11.26}))

    def test_el_escrutinio_versionado_manda_sobre_una_web_que_no_coincide(self):
        originales = (cp.buscar_tabla_premios_losilla, cp.buscar_tabla_premios_loteriaanta,
                      cp.fuentes_web_aplicables)
        try:
            cp.fuentes_web_aplicables = lambda jornada: True
            cp.buscar_tabla_premios_losilla = lambda jornada: {
                "13": 1369.75, "12": 110.13, "11": 14.48, "10": 3.41, "elige8": 214.66}
            cp.buscar_tabla_premios_loteriaanta = lambda jornada: {}
            tabla_j19 = cp.tabla_premios_jornada(19)
            tabla_j20 = cp.tabla_premios_jornada(20)
        finally:
            (cp.buscar_tabla_premios_losilla, cp.buscar_tabla_premios_loteriaanta,
             cp.fuentes_web_aplicables) = originales
        self.assertEqual(tabla_j19["10"], 0.0)          # el real de la J19, no el 3,41 de la J20
        self.assertEqual(tabla_j19["12"], 11.6)
        self.assertEqual(tabla_j20["elige8"], 214.66)   # coincide: se acepta la web con su Elige 8

    def test_no_se_pregunta_a_las_webs_por_un_fixture_de_la_temporada_pasada(self):
        self.assertFalse(cp.fuentes_web_aplicables(59))
        self.assertTrue(cp.fuentes_web_aplicables(20))

    def test_historial_real_sin_premios_de_otra_jornada(self):
        historial = json.loads((DATA / "premios" / "historial_premios.json").read_text(encoding="utf-8"))
        # Dato vivo (lo reescribe el pipeline y esta suite corre ANTES que el):
        # solo se fija lo reparado en J8/J15/J19 y solo mientras el registro
        # siga siendo el calculado (si Marc declara un premio real, manda el).
        por_clave = {(e.get("temporada"), e.get("jornada")): e for e in historial["jornadas"]}
        for jornada in (8, 15, 19):
            entrada = por_clave.get(("2026_2027", jornada))
            if not entrada or entrada.get("fuente_premio") == "confirmado_usuario":
                continue
            # los premios falsos eran la categoria de 10 de OTRA jornada
            self.assertNotIn(entrada.get("premio_eur"), (3.93, 6.82, 3.41), f"J{jornada}")
            tabla = entrada.get("tabla_premios")
            if tabla:
                self.assertEqual(tabla.get("10"), 0.0, f"J{jornada}")
                self.assertTrue(cp.tabla_premios_valida(tabla), f"J{jornada}")


# ---------------------------------------------------------------- 145
class PremioTavilyTests(unittest.TestCase):
    def _buscar(self, contenido):
        import os
        original_post, original_key = cp.requests.post, os.environ.get("TAVILY_API_KEY")

        class Respuesta:
            status_code = 200

            @staticmethod
            def json():
                return {"answer": "", "results": [{"content": contenido}]}

        try:
            os.environ["TAVILY_API_KEY"] = "clave-de-test"
            cp.requests.post = lambda *a, **k: Respuesta()
            return cp.buscar_premio_tavily(20, 10, False)
        finally:
            cp.requests.post = original_post
            if original_key is None:
                os.environ.pop("TAVILY_API_KEY", None)
            else:
                os.environ["TAVILY_API_KEY"] = original_key

    def test_punto_decimal_no_se_multiplica_por_cien(self):
        self.assertEqual(self._buscar("Premio 10 aciertos: 12.50 € por apuesta"), (12.5, "tavily"))

    def test_formato_espanol_con_miles(self):
        self.assertEqual(self._buscar("10 aciertos: 1.234,56 € por apuesta"), (1234.56, "tavily"))


# ---------------------------------------------------------------- 218
class Elige8JornadaActivaTests(unittest.TestCase):
    def test_sin_espejo_elige_la_prediccion_mas_reciente_por_fecha_no_la_de_numero_mas_alto(self):
        original = e8.PREDICCIONES
        with tempfile.TemporaryDirectory() as tmp:
            try:
                e8.PREDICCIONES = Path(tmp)
                (Path(tmp) / "ultima_prediccion.json").write_text(json.dumps({"jornada": 26}), encoding="utf-8")
                (Path(tmp) / "jornada_76.json").write_text(
                    json.dumps({"jornada": 76, "generado_en": "2026-08-06T10:00:00+00:00"}), encoding="utf-8")
                (Path(tmp) / "jornada_25.json").write_text(
                    json.dumps({"jornada": 25, "generado_en": "2026-11-27T11:20:00+00:00"}), encoding="utf-8")
                self.assertEqual(e8.detectar_jornada_activa(), 25)
            finally:
                e8.PREDICCIONES = original


# ---------------------------------------------------------------- 124 / 175
class VariantePrerregistradaTests(unittest.TestCase):
    def test_el_bloque_dice_que_la_prerregistrada_no_supero(self):
        resumen = pub.resumen_backtest()
        self.assertEqual(resumen["variante_prerregistrada"], "premio_esperado")
        self.assertEqual(resumen["veredicto_variante_prerregistrada"], "no supera")
        self.assertTrue(resumen["variante_publicada_elegida_a_posteriori"])
        # es el texto que la web pinta tras "Veredicto:"
        self.assertIn("a posteriori", resumen["veredicto_variante_publicada"])
        self.assertIn("no supero", resumen["veredicto_variante_publicada"])
        self.assertIn("NO supero", resumen["aviso_seleccion"])

    def test_con_backtest_rapido_no_se_afirma_que_no_supero(self):
        original = pub.BACKTEST
        with tempfile.TemporaryDirectory() as tmp:
            try:
                pub.BACKTEST = Path(tmp) / "backtest.json"
                pub.BACKTEST.write_text(json.dumps({
                    "jornadas_evaluadas": 20, "variante_principal": "P13plus",
                    "variantes": {"P13plus": {"veredicto": "supera"}}}), encoding="utf-8")
                resumen = pub.resumen_backtest()
            finally:
                pub.BACKTEST = original
        self.assertIsNone(resumen["veredicto_variante_prerregistrada"])
        self.assertNotIn("NO supero", resumen["aviso_seleccion"])
        self.assertNotIn("no supero", resumen["veredicto_variante_publicada"])
        self.assertIn("no se calculo", resumen["aviso_seleccion"])
        self.assertIn("no se calculo", resumen["veredicto_variante_publicada"])

    def test_el_backtest_no_cambia_la_variante_prerregistrada(self):
        self.assertEqual(bt.VARIANTE_PRERREGISTRADA, ("premio_esperado", False))
        if bt.VARIANTE_PRINCIPAL == bt.VARIANTE_PRERREGISTRADA:
            self.assertIn("variante principal = premio_esperado", bt.CRITERIOS["veredicto"])
        else:
            self.assertIn("a posteriori", bt.CRITERIOS["veredicto"])


# ---------------------------------------------------------------- 26 / 230 / datos
class DatosReparadosTests(unittest.TestCase):
    def test_memoria_socio_no_afirma_premios_que_no_existieron(self):
        memoria = json.loads((DATA / "memoria_ia" / "memoria_socio.json").read_text(encoding="utf-8"))
        bloque = memoria["bloque_para_chat"]
        self.assertNotIn("285,70", bloque)
        self.assertNotIn("672,54", bloque)
        # Solo aserciones negativas y el limite del chat: el texto se
        # reescribe al cierre de cada jornada y no debe parar el pipeline.
        self.assertLessEqual(len(bloque), 2600)

    def test_la_temporada_de_las_jugadas_es_coherente_con_su_fecha(self):
        # Dato vivo: una jugada nueva sin 'temporada' ni fecha se salta (no
        # debe parar el pipeline); solo falla una temporada CONTRADICTORIA.
        jugadas = json.loads((DATA / "quinielas_jugadas.json").read_text(encoding="utf-8"))["jugadas"]
        for jugada in jugadas:
            por_fecha = cp.temporada_de_jugada({**jugada, "temporada": None})
            if jugada.get("temporada") and por_fecha:
                self.assertEqual(jugada["temporada"], por_fecha, jugada.get("jornada"))


if __name__ == "__main__":
    unittest.main()
