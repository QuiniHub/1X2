# -*- coding: utf-8 -*-
"""Tests de la auditoria del 26/11/2026, paquete P3_aprendizaje.

Cada test falla sin el arreglo correspondiente. Solo usan directorios
temporales: no leen ni escriben data/ real y no acceden a la red.
"""

import contextlib
import inspect
import io
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import actualizar_analisis_ia as aa  # noqa: E402
import actualizar_aprendizaje_ia as apr  # noqa: E402
import actualizar_contexto_equipos as ace  # noqa: E402
import ajustar_aprendizaje_elige8 as ae8  # noqa: E402
import ajustar_estado_vivo_motivacion as aem  # noqa: E402
import alimentar_sorpresas_mercado as asm  # noqa: E402
import aprender_de_historial_resultados as ahr  # noqa: E402
import construir_historial_quinielas as chq  # noqa: E402
import construir_memoria_historica_profunda as cmh  # noqa: E402
import control_calidad_actualizacion as cca  # noqa: E402
import diagnostico_sistema as ds  # noqa: E402
import estudio_efecto_revulsivo as eer  # noqa: E402
import estudio_terceros_espana as ete  # noqa: E402
import estudio_ver_sorpresas as evs  # noqa: E402
import evaluar_valor_senales as evv  # noqa: E402
import generar_contexto_competitivo as gcc  # noqa: E402
import generar_diario_aprendizaje as gda  # noqa: E402
import generar_estado_vivo_ia as gev  # noqa: E402
import normalizar_textos_generados as ntg  # noqa: E402


EQUIPOS_A = [("Equipo%02d Local" % i, "Rival%02d Visitante" % i) for i in range(1, 15)]
EQUIPOS_B = [("Otro%02d Casa" % i, "Distinto%02d Fuera" % i) for i in range(1, 15)]
SIGNOS_14 = "1X21X21X21X21X"


def hacer_jornada(numero, fecha, signos=SIGNOS_14, equipos=None, extra_partido=None):
    equipos = equipos or EQUIPOS_A
    partidos = []
    for i in range(14):
        p = {"num": i + 1, "local": equipos[i][0], "visitante": equipos[i][1], "fecha": fecha}
        p["signo_oficial"] = signos[i] if signos else "Pendiente"
        if extra_partido:
            p.update(extra_partido)
        partidos.append(p)
    return {"jornada": numero, "fecha": fecha, "partidos": partidos}


def hacer_prediccion(numero, signo, generado_en, equipos=None, **extra):
    equipos = equipos or EQUIPOS_A
    pred = {
        "jornada": numero,
        "generado_en": generado_en,
        "partidos": [
            {"num": i + 1, "local": equipos[i][0], "visitante": equipos[i][1], "signo_final": signo,
             "probabilidades": {"1": 50, "X": 30, "2": 20}}
            for i in range(14)
        ],
    }
    pred.update(extra)
    return pred


def escribir(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


class Parchear:
    """Cambia atributos de modulo durante un test y los restaura al salir."""

    def __init__(self, modulo, **valores):
        self.modulo, self.valores, self.previos = modulo, valores, {}

    def __enter__(self):
        for nombre, valor in self.valores.items():
            self.previos[nombre] = getattr(self.modulo, nombre)
            setattr(self.modulo, nombre, valor)
        return self

    def __exit__(self, *exc):
        for nombre, valor in self.previos.items():
            setattr(self.modulo, nombre, valor)
        return False


# --------------------------------------------------------------------------
# 13 / 82: el aprendizaje usa la prediccion del cierre
# --------------------------------------------------------------------------
class PrediccionDelCierreTest(unittest.TestCase):
    def _entorno(self, tmp):
        tmp = Path(tmp)
        return tmp / "jornadas", tmp / "predicciones", tmp / "pre_cierre"

    def test_jornada_cerrada_usa_el_snapshot_y_no_la_regenerada(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas, predicciones, snapshots = self._entorno(tmp)
            escribir(jornadas / "jornada_5.json", hacer_jornada(5, "2026-09-12"))
            # Regenerada (dice 2 en todo); el snapshot del cierre decia 1.
            escribir(predicciones / "jornada_5.json", hacer_prediccion(5, "2", "2026-09-11T08:00:00+00:00"))
            escribir(snapshots / "jornada_5.json", {
                "jornada": 5,
                "primer_partido_utc": "2026-09-12T14:00:00+00:00",
                "prediccion": hacer_prediccion(5, "1", "2026-09-11T07:00:00+00:00"),
            })
            with Parchear(apr, JORNADAS=jornadas, PREDICCIONES=predicciones, SNAPSHOTS=snapshots):
                cargadas = apr.cargar_predicciones_detalladas_por_jornada()
        self.assertEqual(cargadas[5]["origen"], "snapshot_pre_cierre")
        self.assertEqual(apr.signo_prediccion(cargadas[5]["partidos"][1]), "1")

    def test_sin_snapshot_no_vale_una_prediccion_generada_despues_de_empezar(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas, predicciones, snapshots = self._entorno(tmp)
            snapshots.mkdir(parents=True)
            escribir(jornadas / "jornada_5.json", hacer_jornada(5, "2026-09-12"))
            escribir(predicciones / "jornada_5.json", hacer_prediccion(5, "2", "2026-09-14T08:00:00+00:00"))
            with Parchear(apr, JORNADAS=jornadas, PREDICCIONES=predicciones, SNAPSHOTS=snapshots):
                cargadas = apr.cargar_predicciones_detalladas_por_jornada()
        self.assertNotIn(5, cargadas)

    def test_jornada_sin_empezar_usa_la_prediccion_viva(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas, predicciones, snapshots = self._entorno(tmp)
            escribir(jornadas / "jornada_6.json", hacer_jornada(6, "2026-09-19", signos=None))
            escribir(predicciones / "jornada_6.json", hacer_prediccion(6, "2", "2026-09-17T08:00:00+00:00"))
            escribir(snapshots / "jornada_6.json", {
                "jornada": 6,
                "primer_partido_utc": "2026-09-19T14:00:00+00:00",
                "prediccion": hacer_prediccion(6, "1", "2026-09-16T07:00:00+00:00"),
            })
            with Parchear(apr, JORNADAS=jornadas, PREDICCIONES=predicciones, SNAPSHOTS=snapshots):
                cargadas = apr.cargar_predicciones_detalladas_por_jornada()
        self.assertEqual(cargadas[6]["origen"], "prediccion")

    def test_el_registro_de_una_jornada_jugada_no_se_reescribe(self):
        # Revision 27/11: J66/J67 (jugadas por Marc) pasaban de 11 a 10
        # aciertos al compararse con el snapshot; ese registro es de la
        # quiniela real y aqui no se toca. Una jornada no jugada si se
        # actualiza y conserva la temporada.
        with tempfile.TemporaryDirectory() as tmp:
            historial = escribir(Path(tmp) / "historial_premios.json", {"jornadas": [
                {"jornada": 66, "temporada": "2025_2026", "aciertos": 11, "fallos": 3,
                 "partidos_comparados": 14, "boleto": "A", "detalle_partidos": [],
                 "premio_eur": 0.0, "fuente_premio": "confirmado_usuario"},
                {"jornada": 70, "temporada": "2025_2026", "aciertos": 11, "fallos": 3,
                 "partidos_comparados": 14, "boleto": "A", "detalle_partidos": [],
                 "premio_eur": 0.0, "fuente_premio": "pendiente"},
            ]})
            def nuevo(numero, temporada):
                return {"jornada": numero, "temporada": temporada, "aciertos": 10, "fallos": 4,
                        "partidos_comparados": 14, "boleto": "B", "detalle_partidos": [],
                        "premio_eur": 0.0, "fuente_premio": "pendiente", "notas": ""}
            with Parchear(apr, HISTORIAL_PREMIOS=historial):
                cambios = apr.actualizar_historial_premios(
                    {66: nuevo(66, "2025_2026"), 70: nuevo(70, None)},
                    {66: {"2025_2026"}},
                )
            guardado = {r["jornada"]: r for r in json.loads(historial.read_text(encoding="utf-8"))["jornadas"]}
        self.assertEqual(cambios, 1)
        self.assertEqual(guardado[66]["aciertos"], 11)
        self.assertEqual(guardado[66]["boleto"], "A")
        self.assertEqual(guardado[70]["aciertos"], 10)
        self.assertEqual(guardado[70]["temporada"], "2025_2026")

    def test_retroalimentacion_de_factores_no_acumula_sobre_el_fichero_anterior(self):
        fuente = inspect.getsource(apr.registrar_retroalimentacion_factores)
        self.assertNotIn("cargar_json(SALIDA", fuente)
        self.assertIn("cargar_predicciones_detalladas_por_jornada()", fuente)


# --------------------------------------------------------------------------
# 81 / 115 / 120: un solo esquema en sorpresas_mercado.json
# --------------------------------------------------------------------------
class SorpresasMercadoTest(unittest.TestCase):
    def test_la_entrada_del_paso_144_sobrevive_al_paso_192(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            salida = escribir(tmp / "sorpresas_mercado.json", {"version": "1.0", "sorpresas": [
                {"jornada": 12, "numero_partido": 3, "temporada": "2026_2027",
                 "categoria_sorpresa": "racha_rota", "local": "A", "visitante": "B"},
            ]})
            diario = escribir(tmp / "diario.json", {"entradas": []})
            (tmp / "jornadas").mkdir()
            with Parchear(asm, SORPRESAS_MERCADO=salida, DIARIO=diario, JORNADAS=tmp / "jornadas",
                          SNAPSHOTS=tmp / "pre", PREDICCIONES=tmp / "pred"):
                with contextlib.redirect_stdout(io.StringIO()):
                    asm.main()
            guardado = json.loads(salida.read_text(encoding="utf-8"))
        self.assertEqual(len(guardado["sorpresas"]), 1)
        self.assertEqual(guardado["sorpresas"][0]["num_partido"], 3)
        self.assertEqual(guardado["sorpresas"][0]["numero_partido"], 3)

    def test_la_sorpresa_de_mercado_lleva_los_campos_que_pinta_la_web(self):
        # Revision 27/11: al dejar de borrarse, las entradas de mercado
        # llegaban al chat sin partido / pronostico_jugado / resultado y la
        # web pintaba 'undefined'.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            salida = tmp / "sorpresas_mercado.json"
            losilla = escribir(tmp / "losilla.json", {})
            jornada = hacer_jornada(24, "2026-11-24")
            jornada["partidos"][0]["signo_oficial"] = "2"
            jornada["partidos"][0]["resultado"] = "0-1"
            pred_info = {"path": Path("data") / "backtesting" / "pre_cierre" / "jornada_24.json",
                         "partidos": {1: {"signo_final": "1X"}}}
            with Parchear(apr, SORPRESAS_MERCADO=salida, FUENTE_LOSILLA=losilla,
                          mercado_partido_losilla=lambda fuente, j, n: (
                              ("1", 70.0, {"1": 70.0, "X": 18.0, "2": 12.0}) if n == 1 else ("", 0.0, {}))):
                nuevas = apr.registrar_sorpresas_mercado(24, jornada, pred_info)
                repetidas = apr.registrar_sorpresas_mercado(24, jornada, pred_info)
            guardado = json.loads(salida.read_text(encoding="utf-8"))
        self.assertEqual((nuevas, repetidas), (1, 0))
        entrada = guardado["sorpresas"][0]
        self.assertEqual(entrada["origen"], "mercado_favorito_no_gano")
        self.assertTrue(entrada["partido"].startswith("1. "))
        self.assertIn(" - ", entrada["partido"])
        self.assertEqual(entrada["pronostico_jugado"], "1X")
        self.assertEqual(entrada["resultado"], "0-1")
        self.assertTrue(entrada["registrada_en"])
        self.assertNotIn(chr(92), entrada["origen_prediccion"])
        self.assertEqual(entrada["origen_prediccion"], "data/backtesting/pre_cierre/jornada_24.json")

    def test_entrada_antigua_de_mercado_recibe_partido_al_normalizar(self):
        entrada = asm.normalizar_entrada({
            "jornada": 12, "numero_partido": 3, "temporada": "2026_2027",
            "probabilidad_mercado_favorito": 61.0, "local": "A", "visitante": "B"})
        self.assertEqual(entrada["partido"], "3. A - B")
        self.assertEqual(entrada["origen"], "mercado_favorito_no_gano")
        self.assertEqual(entrada["pronostico_jugado"], "")
        self.assertEqual(entrada["resultado"], "")

    def test_el_origen_entra_en_la_clave(self):
        # Mismo partido, dos hechos: sorpresa de mercado y fijo fallado.
        mercado = {"jornada": 12, "num_partido": 3, "temporada": "2026_2027",
                   "origen": "mercado_favorito_no_gano"}
        diario = {"jornada": 12, "num_partido": 3, "temporada": "2026_2027",
                  "origen": "diario_aprendizaje_fallo_fijo"}
        self.assertNotEqual(asm.clave_entrada(mercado), asm.clave_entrada(diario))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            salida = escribir(tmp / "sorpresas_mercado.json", {"sorpresas": [dict(
                mercado, local="A", visitante="B", signo_real="2",
                probabilidad_mercado_favorito=61.0)]})
            diario_f = escribir(tmp / "diario.json", {"entradas": [{
                "jornada": 12, "partido": "3. A - B", "categoria_fallo": "fallo_fijo",
                "tipo_apuesta": "FIJO", "acierto": False, "pronostico_jugado": "1",
                "signo_real": "2", "resultado": "0-1"}]})
            jornadas = tmp / "jornadas"
            escribir(jornadas / "jornada_12.json", hacer_jornada(12, "2026-10-04"))
            with Parchear(asm, SORPRESAS_MERCADO=salida, DIARIO=diario_f, JORNADAS=jornadas,
                          SNAPSHOTS=tmp / "pre", PREDICCIONES=tmp / "pred"):
                with contextlib.redirect_stdout(io.StringIO()):
                    asm.main()
                    asm.main()
            guardado = json.loads(salida.read_text(encoding="utf-8"))
        origenes = sorted(e["origen"] for e in guardado["sorpresas"])
        self.assertEqual(origenes, ["diario_aprendizaje_fallo_fijo", "mercado_favorito_no_gano"])

    def test_fallo_de_fijo_antiguo_no_se_reanade_con_otra_temporada(self):
        # El diario no trae temporada: cuando la temporada siguiente pise
        # jornada_60.json, el fallo antiguo se deduciria como de la nueva.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            salida = escribir(tmp / "sorpresas_mercado.json", {"sorpresas": [{
                "jornada": 60, "num_partido": 4, "numero_partido": 4, "temporada": "2025_2026",
                "partido": "4. Viejo Local - Viejo Visitante", "signo_real": "X",
                "pronostico_jugado": "1", "origen": "diario_aprendizaje_fallo_fijo"}]})
            diario_f = escribir(tmp / "diario.json", {"entradas": [{
                "jornada": 60, "partido": "4. Viejo Local - Viejo Visitante",
                "categoria_fallo": "fallo_fijo", "tipo_apuesta": "FIJO", "acierto": False,
                "pronostico_jugado": "1", "signo_real": "X", "resultado": "1-1"}]})
            jornadas = tmp / "jornadas"
            escribir(jornadas / "jornada_60.json", hacer_jornada(60, "2027-05-09"))
            with Parchear(asm, SORPRESAS_MERCADO=salida, DIARIO=diario_f, JORNADAS=jornadas,
                          SNAPSHOTS=tmp / "pre", PREDICCIONES=tmp / "pred"):
                with contextlib.redirect_stdout(io.StringIO()):
                    asm.main()
            guardado = json.loads(salida.read_text(encoding="utf-8"))
        self.assertEqual(len(guardado["sorpresas"]), 1)
        self.assertEqual(guardado["sorpresas"][0]["temporada"], "2025_2026")

    def test_la_clave_lleva_temporada(self):
        vieja = {"jornada": 5, "num_partido": 2, "temporada": "2026_2027"}
        nueva = {"jornada": 5, "num_partido": 2, "temporada": "2027_2028"}
        self.assertNotEqual(asm.clave_entrada(vieja), asm.clave_entrada(nueva))

    def test_los_dos_escritores_leen_las_dos_claves(self):
        self.assertEqual(apr.numero_partido_sorpresa({"num_partido": 7}), 7)
        self.assertEqual(apr.numero_partido_sorpresa({"numero_partido": "7"}), 7)
        self.assertEqual(asm.numero_partido_entrada({"numero_partido": 7}), 7)

    def test_evaluar_senales_descarta_snapshot_de_otra_temporada(self):
        jornada = hacer_jornada(5, "2027-09-11")
        pred_vieja = hacer_prediccion(5, "1", "2026-09-10T08:00:00+00:00", equipos=EQUIPOS_B)
        snap = {"jornada": 5, "primer_partido_utc": "2026-09-12T14:00:00+00:00", "prediccion": pred_vieja}
        self.assertTrue(evv.snapshot_de_otra_jornada(snap, pred_vieja, jornada))
        pred_buena = hacer_prediccion(5, "1", "2027-09-10T08:00:00+00:00")
        self.assertFalse(evv.snapshot_de_otra_jornada({"jornada": 5}, pred_buena, jornada))


# --------------------------------------------------------------------------
# 31 / 73 / 74 / 105: Elige 8
# --------------------------------------------------------------------------
class Elige8Test(unittest.TestCase):
    def _entorno(self, tmp):
        tmp = Path(tmp)
        jornadas, predicciones = tmp / "jornadas", tmp / "predicciones"
        escribir(jornadas / "jornada_76.json", hacer_jornada(76, "2026-08-07"))
        escribir(jornadas / "jornada_24.json", hacer_jornada(24, "2026-11-24"))
        escribir(jornadas / "jornada_25.json", hacer_jornada(25, "2026-11-29", signos=None, equipos=EQUIPOS_B))
        escribir(predicciones / "jornada_76.json", hacer_prediccion(76, "1", "2026-08-06T08:00:00+00:00"))
        escribir(predicciones / "jornada_24.json", hacer_prediccion(24, "1", "2026-11-23T08:00:00+00:00"))
        escribir(predicciones / "jornada_25.json",
                 hacer_prediccion(25, "1", "2026-11-27T08:00:00+00:00", equipos=EQUIPOS_B))
        escribir(predicciones / "ultima_prediccion.json",
                 hacer_prediccion(25, "1", "2026-11-27T08:00:00+00:00", equipos=EQUIPOS_B))
        return jornadas, predicciones

    def test_solo_se_toca_la_jornada_activa_no_empezada(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas, predicciones = self._entorno(tmp)
            with Parchear(ae8, JORNADAS=jornadas, PREDICCIONES=predicciones):
                rutas = ae8.rutas_prediccion_activa(hoy=date(2026, 11, 27))
                el_dia_del_partido = ae8.rutas_prediccion_activa(hoy=date(2026, 11, 29))
        self.assertEqual(sorted(r.name for r in rutas), ["jornada_25.json", "ultima_prediccion.json"])
        self.assertEqual(el_dia_del_partido, [])

    def test_ultima_prediccion_de_otra_jornada_no_se_toca(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas, predicciones = self._entorno(tmp)
            escribir(predicciones / "ultima_prediccion.json",
                     hacer_prediccion(24, "1", "2026-11-23T08:00:00+00:00"))
            with Parchear(ae8, JORNADAS=jornadas, PREDICCIONES=predicciones):
                rutas = ae8.rutas_prediccion_activa(hoy=date(2026, 11, 27))
        self.assertEqual([r.name for r in rutas], ["jornada_25.json"])

    def test_prediccion_congelada_al_cierre_no_se_reescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Con configuracion.elige8 el script SI recalcula: sin la guarda
            # de 'prediccion_congelada_al_cierre' el fichero se reescribe.
            viva = hacer_prediccion(24, "1", "2026-11-23T08:00:00+00:00",
                                    configuracion={"elige8": True})
            ruta_viva = escribir(Path(tmp) / "viva.json", viva)
            antes_viva = ruta_viva.read_text(encoding="utf-8")
            self.assertTrue(ae8.procesar_prediccion(ruta_viva))
            self.assertNotEqual(ruta_viva.read_text(encoding="utf-8"), antes_viva)

            ruta = escribir(Path(tmp) / "jornada_24.json", hacer_prediccion(
                24, "1", "2026-11-23T08:00:00+00:00", configuracion={"elige8": True},
                prediccion_congelada_al_cierre=True))
            antes = ruta.read_text(encoding="utf-8")
            self.assertFalse(ae8.procesar_prediccion(ruta))
            self.assertEqual(ruta.read_text(encoding="utf-8"), antes)

    def test_memoria_en_orden_cronologico_y_premio_declarado(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            jornadas = tmp / "jornadas"
            escribir(jornadas / "jornada_76.json", hacer_jornada(76, "2026-08-07"))
            escribir(jornadas / "jornada_2.json", hacer_jornada(2, "2026-08-22"))
            jugadas = escribir(tmp / "jugadas.json", {"jugadas": [
                {"jornada": 2, "validado_en": "2026-08-22T10:49:01.278Z", "signos": list(SIGNOS_14),
                 "elige8": [1, 2, 3, 4, 5, 6, 7, 8], "premio_eur": 12.5},
                {"jornada": 76, "validado_en": "7/8/2026, 10:00:00", "signos": list(SIGNOS_14),
                 "elige8": [1, 2, 3, 4, 5, 6, 7, 8]},
            ]})
            with Parchear(ae8, JORNADAS=jornadas, JUGADAS_ARCHIVO=jugadas,
                          HISTORIAL_PREMIOS=tmp / "no_existe.json", MEMORIA_ELIGE8=tmp / "memoria.json"):
                memoria = ae8.construir_memoria_desde_jugadas()
        ultimas = memoria["jornadas"]
        self.assertEqual([j["jornada"] for j in ultimas], [76, 2])
        self.assertEqual(ultimas[-1]["temporada"], "2026_2027")
        self.assertEqual(ultimas[-1]["premio_cobrado"], 12.5)
        self.assertEqual(ultimas[0]["temporada"], "2025_2026")

    def test_jugada_no_se_evalua_contra_la_jornada_de_otra_temporada(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            escribir(jornadas / "jornada_5.json", hacer_jornada(5, "2027-09-11"))
            jugada = {"jornada": 5, "validado_en": "2026-09-08T07:23:25+00:00"}
            with Parchear(ae8, JORNADAS=jornadas):
                self.assertEqual(ae8.datos_jornada_de_la_jugada(jugada), {})


# --------------------------------------------------------------------------
# 16 / 182: estado vivo
# --------------------------------------------------------------------------
class EstadoVivoTest(unittest.TestCase):
    PARTIDO = {"local": "Lider", "visitante": "Colista", "probabilidades": {"1": 62, "X": 22, "2": 16}}

    @staticmethod
    def _cerrado(restantes):
        principal = {"objetivo": "titulo", "estado": "campeon_matematico", "vivo": False, "terminal": True}
        return {"partidos_restantes": restantes, "objetivos_vivos": [], "objetivos": [principal],
                "objetivo_principal": principal}

    @staticmethod
    def _necesitado(restantes):
        principal = {"objetivo": "permanencia", "estado": "riesgo_descenso", "vivo": True}
        return {"partidos_restantes": restantes, "objetivos_vivos": [principal], "objetivos": [principal],
                "objetivo_principal": principal}

    def test_favorito_local_con_objetivo_cerrado_se_penaliza(self):
        penalty, motivos = aem.penalizaciones_competitivas(self.PARTIDO, self._cerrado(4), self._necesitado(4))
        texto = " ".join(motivos)
        self.assertIn("el favorito local tiene objetivo cerrado", texto)
        self.assertIn("necesita puntuar", texto)
        self.assertGreaterEqual(penalty, 22 + 24)

    def test_en_noviembre_no_todo_es_no_fijo_limpio(self):
        penalty, motivos = aem.penalizaciones_competitivas(
            self.PARTIDO, self._necesitado(25), self._necesitado(25))
        self.assertNotIn("no es fijo limpio", " ".join(motivos))
        self.assertEqual(penalty, 0)

    def test_en_la_recta_final_si_cuenta(self):
        _, motivos = aem.penalizaciones_competitivas(self.PARTIDO, self._necesitado(6), self._necesitado(6))
        self.assertIn("no es fijo limpio", " ".join(motivos))

    def test_recta_final_solo_cuando_quedan_diez_o_menos(self):
        self.assertFalse(gev.en_recta_final({"primera": {"equipos": [{"partidos_restantes": 25}]}}))
        self.assertTrue(gev.en_recta_final({"primera": {"equipos": [{"partidos_restantes": 8}]}}))


# --------------------------------------------------------------------------
# 17 / 77 / 121: memoria del chat
# --------------------------------------------------------------------------
class MemoriaHistoricaTest(unittest.TestCase):
    def test_la_temporada_actual_entra_en_el_resumen_de_premios(self):
        premios = [
            {"jornada": 70, "aciertos": 10, "fallos": 4, "premio_eur": 5.0},
            {"jornada": 18, "aciertos": 13, "fallos": 1, "premio_eur": 40.0},
        ]
        jugadas = [
            {"jornada": 70, "validado_en": "2026-06-20T10:00:00Z"},
            {"jornada": 18, "validado_en": "2026-10-31T09:00:00Z"},
        ]
        indice = [
            {"numero": 70, "fecha": date(2026, 6, 21), "temporada": "2025_2026"},
            {"numero": 18, "fecha": date(2026, 10, 31), "temporada": "2026_2027"},
        ]
        resumen = cmh.resumen_premios(premios, jugadas, indice)
        self.assertEqual(resumen["mejor_jornada"]["jornada"], 18)
        self.assertEqual(resumen["mejor_jornada"]["temporada"], "2026_2027")
        self.assertEqual(resumen["total_cobrado_eur"], 45.0)
        self.assertEqual(resumen["temporada_actual"], "2026_2027")
        self.assertEqual(resumen["jornadas_evaluadas"], 2)

    def test_los_patrones_del_chat_salen_del_fichero(self):
        lineas = cmh.lineas_patrones({"patrones": {
            "equipo_necesitado_vs_equipo_sin_objetivo": {"casos": 87, "tasa_sorpresa": 69.0},
        }})
        self.assertEqual(len(lineas), 1)
        self.assertIn("87 casos", lineas[0])
        self.assertIn("69.0%", lineas[0])
        self.assertEqual(cmh.lineas_patrones({}), [])

    def test_sin_cifras_fijas_ni_filtro_por_numero(self):
        cuerpo = inspect.getsource(cmh.construir_memoria)
        self.assertNotIn("294 casos", cuerpo)
        self.assertNotIn("if num < 61", cuerpo)
        self.assertNotIn('["2025_2026"]', cuerpo)


# --------------------------------------------------------------------------
# 19 / 88: contexto competitivo
# --------------------------------------------------------------------------
class ContextoCompetitivoTest(unittest.TestCase):
    def test_el_lider_tiene_el_liderato_como_objetivo_principal(self):
        objetivos = [
            {"objetivo": "permanencia", "estado": "permanencia_por_cerrar", "vivo": True, "distancia_o_colchon": 22},
            {"objetivo": "titulo", "estado": "defiende_liderato", "vivo": True, "distancia_o_colchon": 2},
        ]
        self.assertEqual(gcc.elegir_objetivo_principal(objetivos)["estado"], "defiende_liderato")

    def test_el_que_roza_el_descenso_mira_al_descenso(self):
        objetivos = [
            {"objetivo": "europa", "estado": "aspira_matematicamente", "vivo": True, "distancia_o_colchon": -15},
            {"objetivo": "permanencia", "estado": "riesgo_descenso", "vivo": True, "distancia_o_colchon": 1},
        ]
        self.assertEqual(gcc.elegir_objetivo_principal(objetivos)["estado"], "riesgo_descenso")

    def test_a_dos_de_europa_y_tres_del_descenso_manda_el_descenso(self):
        # Revision 27/11: ordenar solo por distancia sacaba a los equipos de
        # media tabla de 'riesgo_descenso' en cuanto Europa quedaba un punto
        # mas cerca.
        objetivos = [
            {"objetivo": "conference", "estado": "aspira_matematicamente", "vivo": True, "distancia_o_colchon": -2},
            {"objetivo": "descenso", "estado": "riesgo_descenso", "vivo": True, "distancia_o_colchon": 3},
            {"objetivo": "permanencia", "estado": "permanencia_por_cerrar", "vivo": True, "distancia_o_colchon": 30},
        ]
        self.assertEqual(gcc.elegir_objetivo_principal(objetivos)["estado"], "riesgo_descenso")
        # Si el descenso queda lejos, manda lo que esta cerca.
        objetivos[1]["distancia_o_colchon"] = 8
        self.assertEqual(gcc.elegir_objetivo_principal(objetivos)["estado"], "aspira_matematicamente")

    def test_asegurado_mira_a_todos_los_perseguidores_no_solo_al_siguiente(self):
        tabla = [
            {"posicion": 1, "equipo": "Primero", "pj": 36, "puntos": 80},
            {"posicion": 2, "equipo": "Segundo", "pj": 36, "puntos": 70},   # techo 76
            {"posicion": 3, "equipo": "Aplazado", "pj": 30, "puntos": 60},  # techo 84
        ]
        equipos = gcc.preparar_tabla(tabla, 38)
        plaza = gcc.evaluar_plaza(equipos[0], equipos, 1, "champions")
        self.assertEqual(plaza["estado"], "defiende_plaza")
        self.assertEqual(plaza["corte_maximo_puntos"], 84)
        titulo = gcc.evaluar_titulo(equipos[0], equipos)
        self.assertEqual(titulo["estado"], "defiende_liderato")


# --------------------------------------------------------------------------
# 20 / 190: contexto de equipos
# --------------------------------------------------------------------------
class ContextoEquiposTest(unittest.TestCase):
    def test_la_jornada_activa_se_elige_por_fecha_y_no_por_numero(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp)
            escribir(jornadas / "jornada_76.json", hacer_jornada(76, "2026-08-07"))
            escribir(jornadas / "jornada_24.json", hacer_jornada(24, "2026-11-24"))
            escribir(jornadas / "jornada_25.json", hacer_jornada(25, "2026-11-29", signos=None, equipos=EQUIPOS_B))
            with Parchear(ace, JORNADAS=jornadas):
                activa = ace.jornada_activa(hoy=date(2026, 11, 27))
        self.assertEqual(activa["jornada"], 25)

    def test_palabras_completas_y_no_subcadenas(self):
        _, alertas = ace.clasificar_noticias(
            [{"titulo": "El arbitro pita falta y el club resalta a la ciudadania"}], "Real Betis")
        self.assertEqual(alertas, [])
        _, alertas = ace.clasificar_noticias([{"titulo": "Lesiones: dos bajas en el Betis"}], "Real Betis")
        self.assertIn("lesiones", alertas)

    def test_titulares_del_femenino_o_del_filial_no_cuentan(self):
        n = ace.normalizar
        self.assertTrue(ace.titular_de_otro_equipo(n("Parte medico del Barcelona femenino"), "FC Barcelona"))
        self.assertTrue(ace.titular_de_otro_equipo(n("Lesion en el Barca Atletic"), "FC Barcelona"))
        # 'atletic' no puede tirar los titulares que nombran al Atletico.
        self.assertFalse(ace.titular_de_otro_equipo(n("Mbappe, baja ante el Atletico"), "Real Madrid"))
        # Si el equipo buscado ES el femenino, sus titulares valen.
        self.assertFalse(ace.titular_de_otro_equipo(n("Lesion en el Madrid femenino"), "Real Madrid Femenino"))


# --------------------------------------------------------------------------
# 78 / 135: historial de quinielas
# --------------------------------------------------------------------------
class HistorialQuinielasTest(unittest.TestCase):
    def test_signo_nuestro_del_motor_no_convierte_la_jornada_en_validada(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = escribir(Path(tmp) / "jornada_22.json",
                            hacer_jornada(22, "2026-11-14", extra_partido={"signo_nuestro": "1"}))
            resumen = chq.resumen_jornada(ruta)
        self.assertFalse(resumen["validada"])
        self.assertEqual(resumen["nuestra_quiniela"], "No validada")
        self.assertEqual(resumen["temporada"], "2026_2027")
        self.assertTrue(resumen["prediccion_motor"])

    def test_el_historial_no_se_realimenta_con_sus_propias_entradas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            salida = escribir(tmp / "historial.json", {"jornadas": [
                {"jornada": 22, "validada": True, "origen_validacion": "historial_preservado",
                 "nuestra_quiniela": " ".join(SIGNOS_14)},
                {"jornada": 21, "validada": True, "origen_validacion": "confirmado_por_marc_en_chat",
                 "nuestra_quiniela": " ".join(SIGNOS_14)},
            ]})
            jugadas = escribir(tmp / "jugadas.json", {"jugadas": []})
            with Parchear(chq, SALIDA=salida, QUINIELAS_JUGADAS=jugadas):
                validaciones = chq.cargar_validaciones_previas()
        self.assertNotIn(22, validaciones)
        self.assertIn(21, validaciones)

    def test_jugada_de_otra_temporada_no_se_fusiona(self):
        resumen = {"jornada": 5, "temporada": "2027_2028", "validada": False, "nuestra_quiniela": "No validada"}
        validaciones = {5: {"jornada": 5, "validado_en": "2026-09-08T07:23:25+00:00",
                            "signos": list(SIGNOS_14), "origen": "confirmado_por_marc_en_chat"}}
        self.assertFalse(chq.fusionar_validacion(resumen, validaciones)["validada"])


# --------------------------------------------------------------------------
# 80: aprendizaje universal
# --------------------------------------------------------------------------
class AprendizajeUniversalTest(unittest.TestCase):
    def test_orden_y_peso_por_fecha_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp)
            escribir(jornadas / "jornada_76.json", hacer_jornada(76, "2026-08-07"))
            escribir(jornadas / "jornada_2.json", hacer_jornada(2, "2026-08-22"))
            escribir(jornadas / "jornada_24.json", hacer_jornada(24, "2026-11-24"))
            with Parchear(ahr, JORNADAS=jornadas):
                cerradas = ahr.cargar_jornadas_cerradas()
        self.assertEqual([j for j, _, _ in cerradas], [76, 2, 24])
        ultima = len(cerradas) - 1
        self.assertEqual(ahr.peso_jornada(ultima, ultima), 1.0)
        self.assertLess(ahr.peso_jornada(0, ultima), ahr.peso_jornada(1, ultima))
        self.assertEqual(ahr.claves_jornadas(cerradas), ["2025_2026:76", "2026_2027:2", "2026_2027:24"])


# --------------------------------------------------------------------------
# 83: valor de las senales
# --------------------------------------------------------------------------
class ValorSenalesTest(unittest.TestCase):
    def test_una_senal_de_riesgo_no_perjudica_por_marcar_partidos_dificiles(self):
        def ev(con_senal, acierto):
            return {"senales": {"riesgo_sorpresa_sin_cubrir": con_senal}, "acierto_top": acierto, "brier": 0.5}
        evaluaciones = (
            [ev(True, i < 48) for i in range(120)]      # 40% con la senal
            + [ev(False, i < 120) for i in range(200)]  # 60% sin ella
        )
        resultado = evv.evaluar_senal(evaluaciones, "riesgo_sorpresa_sin_cubrir")
        self.assertEqual(resultado["tipo"], "riesgo")
        self.assertEqual(resultado["veredicto"], "marca_partidos_dificiles")
        self.assertNotIn("perjudica", resultado["veredicto"])


# --------------------------------------------------------------------------
# 38 / 84 / 133 / 236 / 237 / 239 / 240: estudios offline
# --------------------------------------------------------------------------
class EstudiosTest(unittest.TestCase):
    FILA = {"temporada": "2026_2027", "jornada": 5, "num": 1, "local": "Equipo01 Local",
            "visitante": "Rival01 Visitante", "fecha": "2026-09-12",
            "probabilidades": {"1": 20, "X": 30, "2": 50}, "signo_real": "1"}

    def test_dataset_a_usa_las_probabilidades_del_cierre(self):
        cierre = {5: {"partidos": [{"num": 1, "local": "Equipo01 Local", "visitante": "Rival01 Visitante",
                                    "probabilidades": {"1": 60, "X": 25, "2": 15}}]}}
        sin_snapshot = dict(self.FILA, jornada=6)
        filas = evs.construir_dataset_motor({"partidos": [self.FILA, sin_snapshot]}, cierre=cierre)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["favorito"], "1")
        self.assertEqual(filas[0]["fuente_probs"], "snapshot_pre_cierre")
        self.assertFalse(filas[0]["sorpresa"])

    def test_snapshot_del_mismo_numero_pero_otro_partido_no_vale(self):
        cierre = {5: {"partidos": [{"num": 1, "local": "Otro01 Casa", "visitante": "Distinto01 Fuera",
                                    "probabilidades": {"1": 60, "X": 25, "2": 15}}]}}
        self.assertEqual(evs.construir_dataset_motor({"partidos": [self.FILA]}, cierre=cierre), [])

    def test_j76_de_agosto_es_de_la_temporada_vieja_y_va_antes(self):
        j76 = dict(self.FILA, jornada=76, fecha="2026-08-08", temporada="2026_2027")
        j1 = dict(self.FILA, jornada=1, fecha="2026-08-15", temporada="2026_2027")
        filas = evs.construir_dataset_motor({"partidos": [j1, j76]})
        self.assertEqual([f["jornada"] for f in filas], [76, 1])
        self.assertEqual(filas[0]["temporada"], "2025_2026")
        self.assertEqual(filas[1]["temporada"], "2026_2027")

    def test_a2b_mide_al_favorito_del_mercado(self):
        filas = [
            {"favorito": "1", "signo_real": "X"},
            {"favorito": "1", "signo_real": "2"},
            {"favorito": "1", "signo_real": "1"},
            {"favorito": "2", "signo_real": "2"},  # coinciden: no cuenta
        ]
        metrica = evs.favorito_mercado_cuando_discrepan(filas, lambda f: {"1": 30, "X": 30, "2": 40})
        self.assertEqual(metrica["n_discrepancias"], 3)
        self.assertEqual(metrica["gana_favorito_mercado"], 1)
        self.assertEqual(metrica["gana_favorito_motor"], 1)
        self.assertEqual(metrica["gana_el_otro_signo"], 1)
        self.assertEqual(metrica["prob_implicita_media_favorito_mercado_pct"], 40.0)

    def test_a7_nemesis_queda_descartada(self):
        self.assertIn("A7_nemesis_en_partido", evs.FEATURES_INVALIDADAS)
        fuente = inspect.getsource(evs.analizar_dataset_motor)
        self.assertNotIn("or 100) <=", fuente)

    def test_la_masa_no_se_corta_en_la_jornada_60(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            escribir(base / "2026_2027" / "jornada_61.json", {"partidos": [
                {"numero": 1, "local": "A", "visitante": "B", "porcentajes": {"1": 50, "X": 30, "2": 20}}]})
            with Parchear(evs, PORCENTAJES_LAE_DIR=base):
                masa, equipos = evs.cargar_masa_lae(con_equipos=True)
        self.assertIn((61, 1), masa)
        self.assertEqual(equipos[(61, 1)], ("A", "B"))

    def test_terceros_lee_el_snapshot_pre_cierre(self):
        fuente = inspect.getsource(ete.construir_dataset)
        self.assertIn("prediccion_del_cierre", fuente)
        self.assertNotIn('"predicciones"', fuente)

    def test_real_madrid_no_es_el_atletico(self):
        self.assertFalse(eer.mismo_equipo("Real Madrid", "Ath Madrid"))
        self.assertTrue(eer.mismo_equipo("Real Madrid", "Real Madrid"))
        self.assertTrue(eer.mismo_equipo("Espanol", "Espanyol"))


# --------------------------------------------------------------------------
# 183 / 184 / 245: diagnostico y control de calidad
# --------------------------------------------------------------------------
class DiagnosticoTest(unittest.TestCase):
    def test_el_respaldo_de_ultima_prediccion_es_por_fecha(self):
        with tempfile.TemporaryDirectory() as tmp:
            predicciones = Path(tmp)
            escribir(predicciones / "jornada_76.json", hacer_prediccion(76, "1", "2026-08-06T08:00:00+00:00"))
            escribir(predicciones / "jornada_24.json", hacer_prediccion(24, "1", "2026-11-23T08:00:00+00:00"))
            with Parchear(cca, PREDICCIONES=predicciones):
                self.assertEqual(cca.ultima_prediccion()["jornada"], 24)
                self.assertFalse(cca.ultima_prediccion_ilegible())
                (predicciones / "ultima_prediccion.json").write_text("{roto", encoding="utf-8")
                self.assertTrue(cca.ultima_prediccion_ilegible())
                self.assertEqual(cca.ultima_prediccion()["jornada"], 24)
            (predicciones / "ultima_prediccion.json").unlink()
            with Parchear(gev, PREDICCIONES=predicciones):
                self.assertEqual(gev.ultima_prediccion_disponible()["jornada"], 24)
        vieja = hacer_prediccion(76, "1", "2026-08-06T08:00:00+00:00")
        nueva = hacer_prediccion(24, "1", "2026-11-23T08:00:00+00:00")
        self.assertEqual(max([vieja, nueva], key=ds.orden_cronologico_prediccion)["jornada"], 24)

    def test_error_al_calcular_la_jornada_objetivo_se_publica(self):
        alertas = []
        with Parchear(cca, jornada_objetivo_real_con_error=lambda: (0, "RuntimeError: roto"),
                      ultima_prediccion=lambda: {"jornada": 24, "partidos": []},
                      ultima_prediccion_ilegible=lambda: False):
            cca.diagnosticar_prediccion(alertas, {"jornada": 24})
        self.assertIn("Jornada objetivo no calculable", [a["titulo"] for a in alertas])

    def test_el_cruce_de_clasificacion_tolera_el_nombre(self):
        self.assertEqual(cca.pj_en_calendario({"cd tenerife": 15, "ce sabadell": 14}, "Tenerife"), 15)
        self.assertEqual(cca.pj_en_calendario({"tenerife": 15}, "Tenerife"), 15)
        self.assertEqual(cca.pj_en_calendario({"real madrid": 15}, "Tenerife"), 0)

    def test_losilla_cuenta_como_fuente_de_mercado(self):
        with tempfile.TemporaryDirectory() as tmp:
            memoria = Path(tmp)
            escribir(memoria / "fuente_losilla.json", {
                "actualizado_en": datetime.now(timezone.utc).isoformat(),
                "probabilidades": {"1": {"1": 50, "X": 30, "2": 20}},
            })
            escribir(memoria / "porcentajes_lae" / "2026_2027" / "jornada_25.json", {"partidos": []})
            with Parchear(ds, MEMORIA=memoria):
                self.assertTrue(ds.mercado_losilla_activo()[0])
                self.assertTrue(ds.porcentajes_lae_activos()[0])
        with tempfile.TemporaryDirectory() as tmp:
            with Parchear(ds, MEMORIA=Path(tmp)):
                self.assertFalse(ds.mercado_losilla_activo()[0])
                self.assertFalse(ds.porcentajes_lae_activos()[0])


# --------------------------------------------------------------------------
# 186 / 238 / 192 / 226 / 220
# --------------------------------------------------------------------------
class VariosTest(unittest.TestCase):
    def test_el_diario_retirado_no_se_puede_ejecutar(self):
        with self.assertRaises(gda.ScriptRetirado):
            gda.actualizar_diario()

    def test_solo_cuentan_los_signos_de_la_columna_oficial(self):
        csv_texto = """jornada,fecha,resultado_oficial
12,2025-05-11,1X21X21X21X21X | P15 1-2
13,Semana 33 - 2025,Pendiente
"""
        signos = aa.signos_oficiales_del_csv(csv_texto)
        self.assertEqual("".join(signos), "1X21X21X21X21X")

    def test_la_forma_se_acumula_por_fecha_real(self):
        partidos = [
            (0, 1, {"fecha": "2026-10-20"}),
            (1, 2, {"fecha": "2026-08-22"}),
            (2, 3, {"fecha": ""}),
        ]
        orden = [item[1] for item in sorted(partidos, key=aa.orden_fecha_partido)]
        self.assertEqual(orden, [2, 1, 3])

    def test_normalizar_textos_recorre_el_origen(self):
        rutas = {ruta.relative_to(ntg.ROOT).as_posix() for ruta in ntg.RUTAS_JSON}
        self.assertTrue({"data/jornadas", "data/premios", "data/temporadas"} <= rutas)


if __name__ == "__main__":
    unittest.main()
