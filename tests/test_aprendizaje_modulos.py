"""Tests del meta-aprendizaje por modulo (15/10/2026): cuaderno, frenos de
cada auto-correccion (incluido que NO disparan bajo minimos), auditoria con
puerta y cableado de la pestaña Laboratorio."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aprendizaje_modulos as am
import senal_valiente as sv
from modelo_reparto_quiniela import EvaluadorEV
from motor_prediccion_quiniela import (
    EFECTO_REVULSIVO_DEBUT_CASA,
    EFECTO_REVULSIVO_DEBUT_FUERA,
    _efectos_revulsivo,
)
from optimizador_ev_premio import factor_acertantes_actual


class ModeloFalso:
    """Dixon-Coles de pega: devuelve probabilidades fijas, o None para
    equipos 'sin cobertura'."""

    def __init__(self, probs=None, cubre=True):
        self.probs = probs or {"1": 0.5, "X": 0.3, "2": 0.2}
        self.cubre = cubre

    def probabilidades(self, local, visitante):
        if not self.cubre or "Extranjero" in str(local):
            return None
        return dict(self.probs)


def _fixture(signos):
    return {
        i: {"local": f"L{i}", "visitante": f"V{i}", "fecha": "2026-10-10",
            "signo_oficial": s}
        for i, s in enumerate(signos, start=1)
    }


def _partidos(n=2, probs=None, mercado=None, **extra):
    return [{
        "num": i,
        "local": f"L{i}",
        "visitante": f"V{i}",
        "probabilidades": probs or {"1": 60.0, "X": 25.0, "2": 15.0},
        "mercado_losilla": mercado or {"1": 50.0, "X": 28.0, "2": 22.0},
        **extra,
    } for i in range(1, n + 1)]


class FilaDixonColesTests(unittest.TestCase):
    def test_evalua_rps_aciertos_y_sesgo(self):
        fixture = _fixture(["1", "2"])
        fila = am.fila_dixon_coles(_partidos(2), fixture, ModeloFalso())
        self.assertEqual(fila["estado"], "ok")
        self.assertEqual(fila["partidos"], 2)
        # el modelo falso da favorito "1": acierta el partido 1 y falla el 2
        self.assertEqual(fila["aciertos_dc"], 1)
        self.assertEqual(fila["aciertos_motor"], 1)
        self.assertIsNotNone(fila["rps_mercado"])
        # sesgo: prob media del 1 = 50, frecuencia real = 50 -> sesgo 0
        self.assertAlmostEqual(fila["sesgo_dc_por_signo"]["1"]["sesgo_puntos"], 0.0)

    def test_sin_cobertura_es_honesto(self):
        partidos = _partidos(1)
        partidos[0]["local"] = "Extranjero FC"
        fila = am.fila_dixon_coles(partidos, _fixture(["1"]), ModeloFalso())
        self.assertEqual(fila["estado"], "sin_cobertura")
        self.assertEqual(fila["partidos"], 0)


class BoletoEvTests(unittest.TestCase):
    TABLA = {"10": 10.0, "11": 50.0, "12": 400.0, "13": 8000.0, "14": 200000.0}

    def test_aciertos_cuentan_dobles_y_triples(self):
        fixture = _fixture(["1", "X", "2"])
        self.assertEqual(am._aciertos_boleto(["1X", "1X2", "1"], fixture), 2)

    def test_premio_con_tabla_real_multicolumna(self):
        # 14 fijos: 10 aciertos exactos -> una columna de 10 = 10 EUR
        signos = ["1"] * 14
        fixture = _fixture(["1"] * 10 + ["2"] * 4)
        premio = am._premio_tabla_real(signos, fixture, self.TABLA)
        self.assertEqual(premio, 10.0)

    def test_boleto_ev_cae_al_backtest_cuando_el_snapshot_no_lo_trae(self):
        backtest = {"test_b_ev_walk_forward": {"detalle": [
            {"jornada": 4, "boleto_ev": ["1"] * 14},
        ]}}
        signos, fuente = am.boleto_ev_de_jornada(4, {}, backtest)
        self.assertEqual(signos, ["1"] * 14)
        self.assertIn("backtest", fuente)

    def test_jugada_de_otra_temporada_no_cuela(self):
        # la numeracion se reinicia: una J1 vieja (mayo 2026 = 25/26) no debe
        # pisar la J1 de 26/27 aunque comparta numero
        datos = {"jugadas": [
            {"jornada": 1, "validado_en": "13/5/2026, 13:18:27", "signos": ["2"] * 14},
            {"jornada": 1, "validado_en": "2026-08-15T06:45:14.841Z", "signos": ["1"] * 14},
        ]}
        self.assertEqual(am.jugada_temporada(1, "2026_2027", datos), ["1"] * 14)
        self.assertEqual(am.jugada_temporada(1, "2025_2026", datos), ["2"] * 14)


class RevulsivoCuadernoTests(unittest.TestCase):
    def _partido_con_traza(self, lado="visitante", mercado=None):
        p = _partidos(1, mercado=mercado)[0]
        p["ajuste_revulsivo"] = {
            "activo": True, "lado": lado, "etapa": "debut",
            "tecnico": "Aguirre", "equipo": p["visitante" if lado == "visitante" else "local"],
        }
        return p

    def test_veredictos_fuera(self):
        self.assertEqual(am.veredicto_revulsivo("visitante", "2"), "ayudo")
        self.assertEqual(am.veredicto_revulsivo("visitante", "X"), "neutro")
        self.assertEqual(am.veredicto_revulsivo("visitante", "1"), "perjudico")

    def test_veredictos_casa(self):
        self.assertEqual(am.veredicto_revulsivo("local", "1"), "perjudico")
        self.assertEqual(am.veredicto_revulsivo("local", "X"), "ayudo")
        self.assertEqual(am.veredicto_revulsivo("local", "2"), "ayudo")

    def test_fila_calcula_sorpresa_vs_mercado(self):
        # mercado 50/28/22 para el equipo visitante (signo 2): esperado
        # 3*0.22 + 0.28 = 0.94; sale 2 -> 3 - 0.94 = +2.06
        fila = am.fila_revulsivo([self._partido_con_traza()], _fixture(["2"]))
        caso = fila["casos"][0]
        self.assertEqual(caso["veredicto"], "ayudo")
        self.assertAlmostEqual(caso["sorpresa_vs_mercado"], 2.06, places=2)

    def test_sin_traza_cuando_la_prediccion_es_anterior_al_modulo(self):
        fila = am.fila_revulsivo(_partidos(2), _fixture(["1", "1"]))
        self.assertEqual(fila["estado"], "sin_traza")


class FrenoOverdispersionTests(unittest.TestCase):
    def _escrutinio(self, acertantes_10=1000, modelo_sesgo=1.0):
        # 14 partidos 100% de masa al signo real -> la masa acierta 14 seguro;
        # mas facil: usar pcts uniformes y categorias sinteticas
        return {
            "pcts": [{"1": 50.0, "X": 30.0, "2": 20.0}] * 14,
            "signos": ["1"] * 14,
            "recaudacion_eur": 1_500_000.0,
            "categorias": {"10": {"acertantes": acertantes_10}},
        }

    def test_no_dispara_bajo_minimo_de_escrutinios(self):
        bloque = am.calcular_factor_overdispersion([self._escrutinio()] * 9)
        self.assertEqual(bloque["estado"], "sin_ajuste")
        self.assertEqual(bloque["valor"], 1.0)
        self.assertIn("Freno", bloque["motivo"])

    def test_con_minimo_ajusta_y_acota_por_arriba(self):
        # acertantes reales disparatados -> mediana enorme -> acotado a 2.0
        bloque = am.calcular_factor_overdispersion(
            [self._escrutinio(acertantes_10=10_000_000)] * 10)
        self.assertEqual(bloque["estado"], "ajustado")
        self.assertEqual(bloque["valor"], 2.0)

    def test_acota_por_abajo(self):
        bloque = am.calcular_factor_overdispersion(
            [self._escrutinio(acertantes_10=10)] * 10)
        self.assertEqual(bloque["estado"], "ajustado")
        self.assertEqual(bloque["valor"], 0.5)

    def test_celdas_pequenas_quedan_fuera(self):
        e = self._escrutinio()
        e["categorias"]["14"] = {"acertantes": 3}  # < 10: ruido, fuera
        ratios_con = am.celdas_overdispersion([e])
        e2 = self._escrutinio()
        self.assertEqual(len(ratios_con), len(am.celdas_overdispersion([e2])))

    def test_evaluador_ev_aplica_y_reacota_el_factor(self):
        p_real = [{"1": 0.5, "X": 0.3, "2": 0.2}] * 14
        masa = [{"1": 50.0, "X": 30.0, "2": 20.0}] * 14
        base = EvaluadorEV(p_real, masa, n_muestras=300, semilla=7).evaluar(["1"] * 14)
        igual = EvaluadorEV(p_real, masa, n_muestras=300, semilla=7,
                            factor_acertantes=1.0).evaluar(["1"] * 14)
        self.assertEqual(base["ev_eur"], igual["ev_eur"])
        # mas acertantes esperados -> menos premio por cabeza -> menos EV
        con_factor = EvaluadorEV(p_real, masa, n_muestras=300, semilla=7,
                                 factor_acertantes=2.0).evaluar(["1"] * 14)
        self.assertLess(con_factor["ev_eur"], base["ev_eur"])
        # el clamp se re-aplica dentro: 10x se queda en 2x
        loco = EvaluadorEV(p_real, masa, n_muestras=300, semilla=7, factor_acertantes=10.0)
        self.assertEqual(loco.factor_acertantes, 2.0)

    def test_optimizador_lee_el_factor_con_respaldo(self):
        factor, origen = factor_acertantes_actual(ruta=Path(tempfile.gettempdir()) / "no_existe_x.json")
        self.assertEqual(factor, 1.0)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "ajustes.json"
            ruta.write_text(json.dumps({"factor_acertantes": {"valor": 5.0, "celdas": 9, "escrutinios": 12}}),
                            encoding="utf-8")
            factor, origen = factor_acertantes_actual(ruta=ruta)
            self.assertEqual(factor, 2.0)  # re-acotado
            self.assertIn("meta-aprendizaje", origen)


class FrenoRevulsivoTests(unittest.TestCase):
    def _casos(self, n, lado="visitante", sorpresa=1.0):
        return [{"lado": lado, "sorpresa_vs_mercado": sorpresa} for _ in range(n)]

    def test_no_dispara_bajo_minimo_de_casos(self):
        bloque = am.reestimar_efecto_revulsivo(self._casos(9))
        self.assertEqual(bloque["estado"], "sin_ajuste")
        self.assertNotIn("debut_fuera_pts", bloque)
        self.assertIn("Freno", bloque["motivo"])

    def test_con_minimo_reestima_agregando_al_estudio_base(self):
        bloque = am.reestimar_efecto_revulsivo(self._casos(10, sorpresa=0.26))
        self.assertEqual(bloque["estado"], "ajustado")
        # misma sorpresa media que el estudio base -> mismo efecto (+5)
        self.assertAlmostEqual(bloque["debut_fuera_pts"], 5.0, places=1)
        self.assertNotIn("debut_casa_pts", bloque)  # casa sigue bajo minimo

    def test_acota_a_mas_menos_8(self):
        bloque = am.reestimar_efecto_revulsivo(self._casos(50, sorpresa=3.0))
        self.assertEqual(bloque["debut_fuera_pts"], 8.0)
        bloque = am.reestimar_efecto_revulsivo(self._casos(500, sorpresa=-3.0))
        self.assertEqual(bloque["debut_fuera_pts"], -8.0)

    def test_motor_lee_la_reestimacion_acotada(self):
        # sin bloque: los efectos del estudio base
        self.assertEqual(_efectos_revulsivo(datos={}),
                         (EFECTO_REVULSIVO_DEBUT_FUERA, EFECTO_REVULSIVO_DEBUT_CASA))
        # con bloque: usa los re-estimados, re-acotando por si el JSON viene roto
        datos = {"reestimacion_2627": {"debut_fuera_pts": 6.5, "debut_casa_pts": 99.0}}
        self.assertEqual(_efectos_revulsivo(datos=datos), (6.5, 8.0))
        # basura no numerica: se ignora
        datos = {"reestimacion_2627": {"debut_fuera_pts": "mucho"}}
        self.assertEqual(_efectos_revulsivo(datos=datos),
                         (EFECTO_REVULSIVO_DEBUT_FUERA, EFECTO_REVULSIVO_DEBUT_CASA))


class FrenoSuspensionSenalTests(unittest.TestCase):
    def _valientes(self, n, aciertos, senal="h2h_caotico", prob=30.0):
        return [{"acierto": i < aciertos, "prob_declarada": prob,
                 "pago_hipotetico_eur": 0.0, "senales": [senal]}
                for i in range(n)]

    def test_no_suspende_bajo_minimo_de_valientes(self):
        resumen = sv._resumen_marcador(self._valientes(7, aciertos=0))
        self.assertEqual(resumen["senales_suspendidas"], [])
        self.assertFalse(resumen["por_senal"]["h2h_caotico"]["suspendida"])

    def test_suspende_con_8_propias_y_menos_del_50_pct(self):
        # 8 valientes al 30% = 2,4 esperados; 1 acierto < 1,2 -> suspendida
        resumen = sv._resumen_marcador(self._valientes(8, aciertos=1))
        self.assertEqual(resumen["senales_suspendidas"], ["h2h_caotico"])

    def test_no_suspende_si_cumple_lo_esperado(self):
        resumen = sv._resumen_marcador(self._valientes(8, aciertos=2))
        self.assertEqual(resumen["senales_suspendidas"], [])

    def test_atribucion_reparte_entre_las_senales_del_pick(self):
        valientes = [{"acierto": True, "prob_declarada": 40.0,
                      "pago_hipotetico_eur": 5.0, "senales": ["empatador", "h2h_caotico"]}]
        resumen = sv._resumen_marcador(valientes)
        self.assertEqual(resumen["por_senal"]["empatador"]["aciertos"], 1)
        self.assertEqual(resumen["por_senal"]["h2h_caotico"]["valientes"], 1)

    def test_senal_suspendida_deja_de_contar_como_dura(self):
        partido = {"num": 3, "local": "Cadiz CF", "visitante": "Levante UD",
                   "fecha": "2026-10-17",
                   "probabilidades": {"1": 40.0, "X": 33.0, "2": 27.0}}
        estudio = {"equipos_empatadores": [{"equipo": "cadiz", "pj": 100, "x_pct": 36.0,
                                            "x_casa_pct": 30.0, "x_fuera_pct": 30.0}],
                   "fiabilidad_nuestra_por_equipo": []}
        masa = {"1": 50.0, "X": 20.0, "2": 30.0}
        fuentes = {"ceses": [], "estudio_x": estudio, "h2h": {}, "sorpresas_equipo": {},
                   "contador": None}
        con_senal = sv.evaluar_candidato(partido, "X", masa, fuentes)
        self.assertIsNotNone(con_senal)
        fuentes["senales_suspendidas"] = {"empatador"}
        self.assertIsNone(sv.evaluar_candidato(partido, "X", masa, fuentes))

    def test_senales_suspendidas_actuales_lee_el_marcador(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "marcador.json"
            ruta.write_text(json.dumps({"resumen": {"senales_suspendidas": ["nemesis"]}}),
                            encoding="utf-8")
            self.assertEqual(sv.senales_suspendidas_actuales(ruta), {"nemesis"})
        self.assertEqual(sv.senales_suspendidas_actuales(Path(tempfile.gettempdir()) / "nope.json"), set())


class AuditoriaTests(unittest.TestCase):
    def test_puerta_cada_5_jornadas(self):
        self.assertFalse(am.auditoria_pendiente(4, {}))
        self.assertTrue(am.auditoria_pendiente(5, {}))
        previa = {"jornadas_cerradas_al_auditar": 11}
        self.assertFalse(am.auditoria_pendiente(15, previa))
        self.assertTrue(am.auditoria_pendiente(16, previa))

    def test_barrido_dc_no_es_candidato_bajo_minimo_de_partidos(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "pre").mkdir()
            (base / "jor").mkdir()
            fixture = {"jornada": 20, "partidos": [
                {"num": i, "local": f"L{i}", "visitante": f"V{i}",
                 "fecha": "2026-10-10", "signo_oficial": "1"} for i in range(1, 15)]}
            snapshot = {"prediccion": {"partidos": [
                {"num": i, "local": f"L{i}", "visitante": f"V{i}",
                 "probabilidades": {"1": 40.0, "X": 30.0, "2": 30.0},
                 "trazabilidad_datos": {"dixon_coles": {"activo": True}}} for i in range(1, 15)]}}
            (base / "jor" / "jornada_20.json").write_text(json.dumps(fixture), encoding="utf-8")
            (base / "pre" / "jornada_20.json").write_text(json.dumps(snapshot), encoding="utf-8")
            # D-C "perfecto": clavaria el 1 siempre -> mejor_u = 1.0 con mejora
            # clara... pero con 14 partidos NO llega al minimo de 60: sin cambios
            resultado = am.barrido_peso_dc(
                [20], lambda j: ModeloFalso({"1": 0.97, "X": 0.02, "2": 0.01}),
                dir_pre_cierre=base / "pre", dir_jornadas=base / "jor")
            self.assertEqual(resultado["estado"], "ok")
            self.assertEqual(resultado["partidos"], 14)
            self.assertEqual(resultado["mejor_peso_extra"], 1.0)
            self.assertGreater(resultado["mejora_rps_vs_actual"], am.AUDITORIA_DC_UMBRAL_RPS)
            self.assertFalse(resultado["candidato"])

    def test_construir_auditoria_reporta_candidato_sin_aplicar_nada(self):
        dc = {"estado": "ok", "partidos": 80, "mejor_peso_extra": 0.9,
              "mejora_rps_vs_actual": 0.004, "candidato": True}
        vetos = {
            "criterio_vivo": {"aciertos": 4, "esperados": 3.0, "veredicto": "VERDE..."},
            "veto_grandes": {"resumen": {"jornadas_evaluadas": 26, "valientes": 9,
                                         "veredicto": "VERDE segun el prerregistro"},
                             "ratio": 1.5, "ratio_vivo": 1.33, "candidato": True,
                             "minimo_jornadas": 25},
            "veto_favorito_55": {"resumen": {"jornadas_evaluadas": 26, "valientes": 9,
                                             "veredicto": "NEUTRO"},
                                 "ratio": 1.0, "ratio_vivo": 1.33, "candidato": False,
                                 "minimo_jornadas": 25},
        }
        auditoria = am.construir_auditoria(25, dc, vetos)
        self.assertEqual(len(auditoria["candidatos"]), 2)
        mensajes = " ".join(c["mensaje"] for c in auditoria["candidatos"])
        self.assertIn("CANDIDATO A CAMBIO", mensajes)
        self.assertIn("Decides tu", mensajes)
        estados = {r["modulo"]: r["estado"] for r in auditoria["resultados"]}
        self.assertEqual(estados["veto_favorito_55"], "sin_cambios")
        self.assertEqual(auditoria["proxima_auditoria_con_jornadas"], 30)

    def test_sin_candidatos_dice_sin_cambios(self):
        dc = {"estado": "ok", "partidos": 14, "mejor_peso_extra": 1.0,
              "mejora_rps_vs_actual": 0.007, "candidato": False}
        vetos = {"criterio_vivo": {"aciertos": 4, "esperados": 3.0},
                 "veto_grandes": {"resumen": {}, "ratio": None, "ratio_vivo": None, "candidato": False},
                 "veto_favorito_55": {"resumen": {}, "ratio": None, "ratio_vivo": None, "candidato": False}}
        auditoria = am.construir_auditoria(11, dc, vetos)
        self.assertEqual(auditoria["candidatos"], [])
        self.assertTrue(all(r["estado"] == "sin_cambios" for r in auditoria["resultados"]))


class SemaforosTests(unittest.TestCase):
    def test_dixon_coles_verde_si_iguala_o_bate_al_mercado(self):
        filas = [{"estado": "ok", "partidos": 14, "partidos_con_mercado": 14,
                  "rps_dc": 0.19, "rps_motor": 0.21, "rps_mercado": 0.20,
                  "aciertos_dc": 7}]
        self.assertEqual(am.resumen_dixon_coles(filas)["semaforo"], "verde")
        filas[0].update(rps_dc=0.215)
        self.assertEqual(am.resumen_dixon_coles(filas)["semaforo"], "rojo")
        filas[0].update(rps_dc=0.205)
        self.assertEqual(am.resumen_dixon_coles(filas)["semaforo"], "ambar")

    def test_boleto_ev_ambar_en_el_umbral_de_sanidad(self):
        def fila(ev, jugado):
            return {"estado": "ok", "premios_tabla_real_eur":
                    {"ev": ev, "conservador": 0.0, "jugado": jugado}}
        self.assertEqual(am.resumen_boleto_ev([fila(100, 80)])["semaforo"], "verde")
        self.assertEqual(am.resumen_boleto_ev([fila(50, 100)])["semaforo"], "ambar")
        self.assertEqual(am.resumen_boleto_ev([fila(10, 100)])["semaforo"], "rojo")

    def test_valiente_roja_si_hay_senal_suspendida(self):
        marcador = {"resumen": {"evaluadas": 9, "aciertos": 3, "esperados": 2.5,
                                "estado": "en_sombra", "senales_suspendidas": ["nemesis"],
                                "por_senal": {}}}
        resumen = am.resumen_valiente(marcador, {})
        self.assertEqual(resumen["semaforo"], "rojo")

    def test_valiente_usa_el_backtest_mientras_el_marcador_se_estrena(self):
        backtest = {"resumen": {"aciertos": 4, "esperados": 3.08, "valientes": 10}}
        resumen = am.resumen_valiente({"resumen": {"evaluadas": 0}}, backtest)
        self.assertEqual(resumen["semaforo"], "verde")
        self.assertEqual(resumen["fuente"], "backtest prerregistrado")

    def test_revulsivo_muestra_minima_es_ambar(self):
        filas = [{"estado": "ok", "casos": [
            {"veredicto": "ayudo"}, {"veredicto": "neutro"}]}]
        self.assertEqual(am.resumen_revulsivo(filas)["semaforo"], "ambar")
        filas = [{"estado": "ok", "casos": [{"veredicto": "ayudo"}] * 3 + [{"veredicto": "perjudico"}]}]
        self.assertEqual(am.resumen_revulsivo(filas)["semaforo"], "verde")
        filas = [{"estado": "ok", "casos": [{"veredicto": "perjudico"}] * 3}]
        self.assertEqual(am.resumen_revulsivo(filas)["semaforo"], "rojo")


class CableadoTests(unittest.TestCase):
    def test_enganchado_al_ciclo_de_aprendizaje(self):
        import generar_artefactos_compuerta_aprendizaje as gen
        self.assertTrue(hasattr(gen, "actualizar_aprendizaje_modulos_seguro"))

    def test_artefactos_generados_y_validos(self):
        cuaderno = json.loads((ROOT / "data" / "memoria_ia" / "aprendizaje_modulos.json")
                              .read_text(encoding="utf-8"), strict=True)
        for modulo in ("dixon_coles", "boleto_ev", "valiente", "revulsivo"):
            self.assertIn(modulo, cuaderno["resumen"])
            self.assertIn(cuaderno["resumen"][modulo]["semaforo"], ("verde", "ambar", "rojo"))
        auditoria = json.loads((ROOT / "data" / "memoria_ia" / "auditoria_automatica.json")
                               .read_text(encoding="utf-8"), strict=True)
        self.assertIn("resultados", auditoria)
        self.assertIn("candidatos", auditoria)
        for r in auditoria["resultados"]:
            self.assertIn(r["estado"], ("sin_cambios", "candidato_a_cambio"))

    def test_pestana_laboratorio_en_la_web(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        # pestaña tras Liga 26/27, mismo patron de tabs
        self.assertIn('data-tab="laboratorio"', html)
        self.assertLess(html.index('data-tab="liga"'), html.index('data-tab="laboratorio"'))
        self.assertLess(html.index('data-tab="laboratorio"'), html.index('data-tab="chat"'))
        # carga de los dos JSON y render
        self.assertIn("data/memoria_ia/aprendizaje_modulos.json", html)
        self.assertIn("data/memoria_ia/auditoria_automatica.json", html)
        self.assertIn("function renderLaboratorio()", html)
        self.assertIn("renderLaboratorio();", html)
        # portada de tarjetas + banda de candidato + estado vacio + leyenda
        self.assertIn('id="labCards"', html)
        self.assertIn('id="labCandidato"', html)
        self.assertIn("El cuaderno se estrena al cerrar la próxima jornada.", html)
        self.assertIn("cumple su promesa", html)
        self.assertIn("en vigilancia", html)
        self.assertIn("suspendido o bajo promesa", html)
        # el contexto del chat conoce la auditoria (patron construirContextoIA)
        self.assertIn("bloqueMetaAprendizaje", html)
        self.assertIn("CANDIDATOS A CAMBIO", html)


if __name__ == "__main__":
    unittest.main()
