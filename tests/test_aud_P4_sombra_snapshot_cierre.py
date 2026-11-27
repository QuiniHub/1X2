"""Auditoria 26/11/2026, paquete P4 (modulos en sombra y snapshot pre-cierre).

Cada test falla sin su arreglo:
  * snapshot pre-cierre: inmutable aunque ya haya resultados, no se fabrica a
    posteriori, no se confunde con la jornada del mismo numero de otra
    temporada (guardar_snapshot_prediccion, congelar_bloques_sombra,
    backtesting_pre_cierre, calibracion_x, prior_europeo);
  * marcadores: la temporada sale de la fecha y los nombres femeninos o
    extranjeros casan (senal_valiente);
  * mezcla_benter: no se invierte una mezcla con peso 0,85;
  * aprendizaje_modulos: recaudacion validada, criterio vivo real, tope J100;
  * elige8_ev: aviso segun el veredicto y guarda de prediccion bloqueada.
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import aprendizaje_modulos as am
import backtesting_pre_cierre as bpc
import calibracion_x as cx
import congelar_bloques_sombra as cb
import elige8_ev as e8
import guardar_snapshot_prediccion as gs
import mezcla_benter as mb
import prior_europeo as pe
import senal_valiente as sv
import test_aud_P4_sombra_snapshot_util as util


def _leer(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


class _ConDirectorios(unittest.TestCase):
    """Redirige guardar_snapshot_prediccion a un directorio temporal."""

    AHORA = datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc)   # primer partido: 21/11 16:00 Madrid

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self._orig = (gs.PREDICCIONES, gs.JORNADAS, gs.BACKTEST, gs.ahora_utc)
        gs.PREDICCIONES = self.base / "predicciones"
        gs.JORNADAS = self.base / "jornadas"
        gs.BACKTEST = self.base / "pre_cierre"
        self.ahora = self.AHORA
        gs.ahora_utc = lambda: self.ahora

    def tearDown(self):
        gs.PREDICCIONES, gs.JORNADAS, gs.BACKTEST, gs.ahora_utc = self._orig
        self.tmp.cleanup()

    def _prediccion(self, jornada=23, nombres=None, **extra):
        return {"jornada": jornada, "prediccion_disponible": True,
                "partidos": util.partidos_prediccion(nombres or util.EQUIPOS), **extra}


class SnapshotInmutableTests(_ConDirectorios):
    def test_se_marca_inmutable_aunque_la_jornada_ya_tenga_resultados(self):
        # J23 y J24 reales: la primera ejecucion tras el inicio ya veia signos
        # oficiales, salia por "ya tiene resultados" y no marcaba nunca.
        util.escribir_jornada(gs.JORNADAS, 23, signos={n: ("1" if n <= 5 else "Pendiente") for n in range(1, 15)})
        util.escribir_snapshot(gs.BACKTEST, 23, extra={"inmutable": False})
        r = gs.crear_snapshot_prediccion(self._prediccion())
        self.assertFalse(r["creado"])
        snap = _leer(gs.BACKTEST / "jornada_23.json")
        self.assertTrue(snap["inmutable"])
        self.assertEqual(snap["congelado_en"], self.AHORA.isoformat())

    def test_no_se_fabrica_un_snapshot_despues_del_primer_partido(self):
        util.escribir_jornada(gs.JORNADAS, 23, signos={n: "Pendiente" for n in range(1, 15)})
        r = gs.crear_snapshot_prediccion(self._prediccion())
        self.assertFalse(r["creado"])
        self.assertIn("a posteriori", r["motivo"])
        self.assertFalse((gs.BACKTEST / "jornada_23.json").exists())

    def test_sin_fechas_no_se_fabrica_un_snapshot(self):
        # Sin fecha de ningun partido no se sabe si la jornada ha empezado.
        gs.JORNADAS.mkdir(parents=True, exist_ok=True)
        partidos = [{"num": n, "local": a, "visitante": b, "signo_oficial": "Pendiente"}
                    for n, (a, b) in enumerate(util.EQUIPOS, start=1)]
        (gs.JORNADAS / "jornada_23.json").write_text(json.dumps({"jornada": 23, "partidos": partidos}), encoding="utf-8")
        r = gs.crear_snapshot_prediccion(self._prediccion())
        self.assertFalse(r["creado"])
        self.assertIn("sin fechas", r["motivo"])
        self.assertFalse((gs.BACKTEST / "jornada_23.json").exists())

    def test_antes_del_primer_partido_se_crea_y_se_refresca(self):
        util.escribir_jornada(gs.JORNADAS, 23, signos={n: "Pendiente" for n in range(1, 15)})
        self.ahora = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
        r = gs.crear_snapshot_prediccion(self._prediccion())
        self.assertTrue(r["creado"])
        snap = _leer(gs.BACKTEST / "jornada_23.json")
        self.assertFalse(snap["inmutable"])
        self.assertEqual(snap["temporada"], "2026_2027")   # sale de la fecha de la jornada
        creado = snap["creado_en"]
        self.ahora = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)
        r = gs.crear_snapshot_prediccion(self._prediccion(valiente={"estado": "ok"}))
        self.assertTrue(r["creado"])
        snap = _leer(gs.BACKTEST / "jornada_23.json")
        self.assertEqual(snap["creado_en"], creado)
        self.assertEqual(snap["prediccion"]["valiente"], {"estado": "ok"})

    def test_un_snapshot_del_mismo_numero_de_otra_temporada_no_cuenta(self):
        # 27/28: la J23 nueva se predice antes de su primer partido y en disco
        # sigue el snapshot J23 de la 26/27. No hereda su creado_en ni lo conserva.
        util.escribir_jornada(gs.JORNADAS, 23, fecha="2027-11-20", nombres=util.OTROS_EQUIPOS,
                              signos={n: "Pendiente" for n in range(1, 15)})
        util.escribir_snapshot(gs.BACKTEST, 23, fecha="2026-11-21")
        self.ahora = datetime(2027, 11, 18, 9, 0, tzinfo=timezone.utc)
        r = gs.crear_snapshot_prediccion(self._prediccion(nombres=util.OTROS_EQUIPOS))
        self.assertTrue(r["creado"])
        snap = _leer(gs.BACKTEST / "jornada_23.json")
        self.assertEqual(snap["creado_en"], self.ahora.isoformat())
        self.assertEqual(snap["temporada"], "2027_2028")
        self.assertEqual(snap["prediccion"]["partidos"][0]["local"], "Arsenal")

    def test_snapshot_ajeno_con_la_jornada_ya_empezada_no_se_sustituye_por_uno_falso(self):
        util.escribir_jornada(gs.JORNADAS, 23, fecha="2027-11-20", nombres=util.OTROS_EQUIPOS,
                              signos={n: "Pendiente" for n in range(1, 15)})
        util.escribir_snapshot(gs.BACKTEST, 23, fecha="2026-11-21")
        self.ahora = datetime(2027, 11, 21, 9, 0, tzinfo=timezone.utc)
        r = gs.crear_snapshot_prediccion(self._prediccion(nombres=util.OTROS_EQUIPOS))
        self.assertFalse(r["creado"])
        self.assertIn("otra temporada", r["motivo"])

    def test_marcar_inmutables_vencidos(self):
        util.escribir_snapshot(gs.BACKTEST, 23, fecha="2026-11-21", extra={"inmutable": False})
        util.escribir_snapshot(gs.BACKTEST, 24, fecha="2026-11-24", extra={"inmutable": False})
        util.escribir_snapshot(gs.BACKTEST, 25, fecha="2026-11-28", extra={"inmutable": False})
        ahora = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
        antes = _leer(gs.BACKTEST / "jornada_24.json")["prediccion"]
        self.assertEqual(gs.marcar_inmutables_vencidos(ahora), [23, 24])
        self.assertTrue(_leer(gs.BACKTEST / "jornada_23.json")["inmutable"])
        self.assertEqual(_leer(gs.BACKTEST / "jornada_24.json")["prediccion"], antes)   # solo cambia la etiqueta
        self.assertFalse(_leer(gs.BACKTEST / "jornada_25.json")["inmutable"])          # aun no ha empezado
        self.assertEqual(gs.marcar_inmutables_vencidos(ahora), [])                       # idempotente


class SnapshotDeOtraJornadaTests(unittest.TestCase):
    def test_mismos_equipos_con_nombres_de_otra_fuente(self):
        snap = {"prediccion": {"partidos": util.partidos_prediccion(util.EQUIPOS)}}
        fixture = {"partidos": util.partidos_jornada([(l + " CF", "R. " + v) for l, v in util.EQUIPOS], "2026-11-21")}
        self.assertFalse(gs.snapshot_de_otra_jornada(snap, fixture))

    def test_otros_equipos(self):
        snap = {"prediccion": {"partidos": util.partidos_prediccion(util.EQUIPOS)}}
        self.assertTrue(gs.snapshot_de_otra_jornada(
            snap, {"partidos": util.partidos_prediccion(util.OTROS_EQUIPOS)}))

    def test_nombres_que_no_casan_pero_misma_fecha(self):
        # J22 real (femenina): solo 5 de 14 nombres casaban; la salva la fecha.
        snap = {"primer_partido_utc": "2026-11-21T15:00:00+00:00",
                "prediccion": {"partidos": util.partidos_prediccion(util.EQUIPOS)}}
        self.assertFalse(gs.snapshot_de_otra_jornada(
            snap, {"partidos": util.partidos_jornada(util.OTROS_EQUIPOS, "2026-11-21")}))
        self.assertTrue(gs.snapshot_de_otra_jornada(
            snap, {"partidos": util.partidos_jornada(util.OTROS_EQUIPOS, "2027-11-20")}))

    def test_sin_datos_para_comparar_no_descarta(self):
        self.assertFalse(gs.snapshot_de_otra_jornada({"prediccion": {"partidos": []}}, {"partidos": []}))


class CongelarTests(unittest.TestCase):
    def _montar(self, tmp, nombres_actual):
        tmp = Path(tmp)
        (tmp / "pred").mkdir()
        util.escribir_snapshot(tmp / "snap", 22, {"valiente": {"estado": "ok", "num": 3}}, fecha="2026-11-17")
        actual = {"jornada": 22, "valiente": {"estado": "ok", "num": 9},
                  "partidos": [dict(p, resultado="Pendiente", signo_oficial="Pendiente")
                               for p in util.partidos_prediccion(nombres_actual)]}
        (tmp / "pred" / "jornada_22.json").write_text(json.dumps(actual), encoding="utf-8")
        (tmp / "ultima.json").write_text(json.dumps(actual), encoding="utf-8")
        return tmp

    def test_un_snapshot_de_otra_temporada_no_congela_la_jornada_nueva(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp, util.OTROS_EQUIPOS)
            ahora = datetime(2027, 11, 16, 8, 0, tzinfo=timezone.utc)   # el 17/11/2026 ya es pasado
            r = cb.congelar(22, ahora=ahora, dir_predicciones=tmp / "pred", dir_snapshots=tmp / "snap",
                            ruta_ultima=tmp / "ultima.json")
            self.assertEqual(r["estado"], "snapshot_de_otra_jornada")
            d = _leer(tmp / "pred" / "jornada_22.json")
            self.assertEqual(d["valiente"]["num"], 9)
            self.assertEqual(d["partidos"][0]["local"], "Arsenal")
            self.assertNotIn("prediccion_congelada_al_cierre", d)

    def test_el_snapshot_de_la_misma_jornada_si_congela(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp, util.EQUIPOS)
            ahora = datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)
            r = cb.congelar(22, ahora=ahora, dir_predicciones=tmp / "pred", dir_snapshots=tmp / "snap",
                            ruta_ultima=tmp / "ultima.json")
            self.assertEqual(r["estado"], "congelado")
            self.assertEqual(_leer(tmp / "ultima.json")["valiente"]["num"], 3)


class BacktestingPreCierreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self._orig = (bpc.SNAPSHOTS, bpc.JORNADAS, bpc.ROOT)
        bpc.SNAPSHOTS = self.base / "snap"
        bpc.JORNADAS = self.base / "jor"
        bpc.ROOT = self.base

    def tearDown(self):
        bpc.SNAPSHOTS, bpc.JORNADAS, bpc.ROOT = self._orig
        self.tmp.cleanup()

    def test_orden_cronologico_temporada_y_snapshot_ajeno(self):
        # J76 de la 25/26 (08/08/2026) es ANTERIOR a la J1 de la 26/27 (15/08/2026)
        util.escribir_jornada(bpc.JORNADAS, 76, fecha="2026-08-08")
        util.escribir_snapshot(bpc.SNAPSHOTS, 76, fecha="2026-08-08")
        util.escribir_jornada(bpc.JORNADAS, 1, fecha="2026-08-15", signos={1: "2"})
        util.escribir_snapshot(bpc.SNAPSHOTS, 1, fecha="2026-08-15")
        # J5: en data/jornadas ya esta la de la temporada siguiente
        util.escribir_jornada(bpc.JORNADAS, 5, fecha="2027-09-11", nombres=util.OTROS_EQUIPOS)
        util.escribir_snapshot(bpc.SNAPSHOTS, 5, fecha="2026-09-12")
        jornadas = [bpc.comparar_snapshot(p) for p in sorted(bpc.SNAPSHOTS.glob("jornada_*.json"))]
        salida = bpc.construir_salida(jornadas)
        self.assertEqual([j["jornada"] for j in salida["jornadas"] if j["estado"] != "snapshot_de_otra_jornada"],
                         [76, 1])
        por_num = {j["jornada"]: j for j in salida["jornadas"]}
        self.assertEqual(por_num[76]["temporada"], "2025_2026")
        self.assertEqual(por_num[1]["temporada"], "2026_2027")
        self.assertEqual(por_num[5]["estado"], "snapshot_de_otra_jornada")
        self.assertEqual(por_num[5]["partidos_cerrados"], 0)
        self.assertEqual(salida["resumen"]["jornadas_snapshot"], 2)
        self.assertEqual(salida["resumen"]["partidos_cerrados"], 28)
        self.assertEqual(salida["resumen"]["aciertos"], 27)
        self.assertEqual(salida["resumen"]["snapshots_de_otra_jornada"], [5])
        self.assertEqual(salida["resumen_por_temporada"]["2025_2026"]["aciertos"], 14)
        self.assertEqual(salida["resumen_por_temporada"]["2026_2027"]["aciertos"], 13)


class LaboratorioPorTemporadaTests(unittest.TestCase):
    def _montar(self, tmp):
        tmp = Path(tmp)
        # J5 de la 26/27 con equipos extranjeros y su snapshot
        util.escribir_jornada(tmp / "jor", 5, fecha="2026-09-15", nombres=util.OTROS_EQUIPOS)
        util.escribir_snapshot(tmp / "snap", 5, fecha="2026-09-15", nombres=util.OTROS_EQUIPOS)
        return tmp

    def test_cargar_snapshots_lleva_la_temporada_y_descarta_el_snapshot_ajeno(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp)
            jornadas = cx.cargar_snapshots(tmp / "snap", tmp / "jor", espanoles=set())
            self.assertEqual([(j["jornada"], j["temporada"]) for j in jornadas], [(5, "2026_2027")])
            # la temporada siguiente reescribe jornada_5.json: el snapshot viejo ya no se cruza
            util.escribir_jornada(tmp / "jor", 5, fecha="2027-09-14", nombres=util.EQUIPOS)
            self.assertEqual(cx.cargar_snapshots(tmp / "snap", tmp / "jor", espanoles=set()), [])

    def test_prior_europeo_solo_usa_jornadas_de_su_temporada(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp)
            self.assertEqual(list(pe.cargar_partidos_europeos((5,), tmp / "snap", tmp / "jor")), [5])
            # la J5 de la 27/28 (snapshot y jornada nuevos) NO es de la muestra prerregistrada
            util.escribir_jornada(tmp / "jor", 5, fecha="2027-09-14", nombres=util.OTROS_EQUIPOS)
            util.escribir_snapshot(tmp / "snap", 5, fecha="2027-09-14", nombres=util.OTROS_EQUIPOS)
            self.assertEqual(pe.cargar_partidos_europeos((5,), tmp / "snap", tmp / "jor"), {})

    def test_prior_europeo_conserva_el_veredicto_si_la_muestra_ya_no_esta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp)
            ruta = tmp / "backtest.json"
            guardado = {"version": "1.0", "estado": "con_resultados", "veredicto": "NO_DESPLEGAR",
                        "criterios_prerregistrados": {"fecha": "2026-11-26"},
                        "backtest": {"jornadas": [5, 13], "n_partidos": 28}}
            ruta.write_text(json.dumps(guardado), encoding="utf-8")
            salida = pe.ejecutar(ruta, tmp / "snap", tmp / "jor", jornadas=(5, 13))   # la J13 ya no esta
            self.assertEqual(salida["veredicto"], "NO_DESPLEGAR")
            self.assertEqual(salida["backtest"], guardado["backtest"])
            self.assertEqual(salida["muestra_congelada"]["jornadas_que_faltan"], [13])
            self.assertEqual(_leer(ruta)["backtest"], guardado["backtest"])


class MarcadoresTests(unittest.TestCase):
    def test_nombres_femeninos_y_extranjeros_casan(self):
        self.assertTrue(sv.nombres_casan("Hacken (F)", "Hacken W"))
        self.assertTrue(sv.nombres_casan("Manchester City (F)", "Man. City W"))
        self.assertTrue(sv.nombres_casan("Borussia Dortmund", "B. Dortmund"))
        self.assertFalse(sv.nombres_casan("Real Zaragoza", "SD Huesca"))
        self.assertFalse(sv.nombres_casan("", "Hacken W"))

    def test_signo_real_verificado_con_equipo_femenino(self):
        with tempfile.TemporaryDirectory() as tmp:
            util.escribir_jornada(tmp, 22, nombres=util.EQUIPOS[:7] + [("Hacken W", "Manchester City W")]
                                  + util.EQUIPOS[8:], signos={8: "2"})
            bloque = {"jornada": 22, "num": 8, "local": "Hacken (F)", "visitante": "Manchester City (F)"}
            self.assertEqual(sv._signo_real_verificado(bloque, tmp), "2")
            ajeno = {"jornada": 22, "num": 8, "local": "Real Zaragoza", "visitante": "SD Huesca"}
            self.assertIsNone(sv._signo_real_verificado(ajeno, tmp))
            # con la jornada ya verificada por el snapshot, el num basta
            self.assertEqual(sv._signo_real_verificado(ajeno, tmp, jornada_verificada=True), "2")

    def test_bloques_del_cierre_etiqueta_por_fecha_y_solo_jornadas_cerradas(self):
        with tempfile.TemporaryDirectory() as tmp:
            # J76 de la 25/26 (agosto) y J1 de la 26/27; la J2 sigue abierta
            jor, snap = util.montar_cierre(tmp, 76, {"valiente": {"estado": "ok", "num": 1}}, fecha="2026-08-08")
            util.montar_cierre(tmp, 1, {"valiente": {"estado": "ok", "num": 2}}, fecha="2026-08-15")
            util.montar_cierre(tmp, 2, {"valiente": {"estado": "ok", "num": 3}}, fecha="2026-08-22",
                               signos={14: "Pendiente"})
            vistos = [(t, n, b["num"]) for t, n, b, _p, _d in sv.bloques_del_cierre("valiente", jor, snap, "9999_0000")]
            self.assertEqual(vistos, [("2025_2026", 76, 1), ("2026_2027", 1, 2)])

    def test_jornadas_con_porcentajes_no_corta_en_la_j60(self):
        import inspect
        self.assertGreaterEqual(inspect.signature(sv.jornadas_con_porcentajes).parameters["hasta"].default, 76)
        self.assertGreaterEqual(inspect.signature(am.jornadas_cerradas_temporada).parameters["hasta"].default, 76)


class MezclaBenterTests(unittest.TestCase):
    P_POST = {"1": 0.585, "X": 0.25, "2": 0.165}
    Q = {"1": 0.60, "X": 0.25, "2": 0.15}

    def test_con_peso_085_la_inversion_no_es_fiable(self):
        _, origen, fiable = mb.motor_pre_mercado({}, self.P_POST, self.Q, 0.85)
        self.assertFalse(fiable)
        self.assertEqual(origen, "inversion_no_fiable_peso_alto")
        _, origen, fiable = mb.motor_pre_mercado({}, self.P_POST, self.Q, 0.20)
        self.assertTrue(fiable)

    def test_si_el_motor_exporta_la_probabilidad_pre_mercado_se_lee_tal_cual(self):
        partido = {mb.CLAVE_PRE_MERCADO: {"1": 50.0, "X": 25.0, "2": 25.0}}
        p_pre, origen, fiable = mb.motor_pre_mercado(partido, self.P_POST, self.Q, 0.85)
        self.assertTrue(fiable)
        self.assertEqual(origen, "exportada_por_el_motor")
        self.assertAlmostEqual(p_pre["1"], 0.50, places=6)

    def test_el_dataset_marca_las_filas_y_analizar_no_ajusta_con_ellas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            partidos = []
            for p in util.partidos_prediccion(util.EQUIPOS):
                p["mercado_losilla"] = {"1": 60.0, "X": 25.0, "2": 15.0}
                p["calidad_datos"] = "alta"
                p["ajuste_mercado_losilla"] = {"lecturas": [
                    "Mercado Losilla: consenso publico integrado con peso 0.85 (calidad_datos=alta)."]}
                partidos.append(p)
            util.escribir_jornada(tmp / "jor", 25, fecha="2026-11-28")
            util.escribir_snapshot(tmp / "snap", 25, fecha="2026-11-28", partidos=partidos)
            filas = mb.construir_dataset(tmp / "snap", tmp / "jor")
            self.assertEqual(len(filas), 14)
            self.assertEqual({f["peso_mercado"] for f in filas}, {0.85})   # el peso REAL de la traza
            self.assertFalse(any(f["p_pre_fiable"] for f in filas))
            self.assertEqual(mb.filas_fiables(filas), [])
            salida = mb.analizar(filas=filas)
            self.assertEqual(salida["dataset"]["partidos"], 0)
            self.assertEqual(salida["dataset"]["excluidas_por_inversion_no_fiable"], 14)
            self.assertEqual(salida["dataset"]["jornadas_excluidas"], ["2026/2027:J25"]
                             if "/" in str(filas[0]["temporada"]) else [f"{filas[0]['temporada']}:J25"])
            self.assertEqual(salida["veredicto"], "NO_DESPLEGAR")
            # La nota sale del peso real de las filas excluidas, no de un 0,85 fijo.
            self.assertIn("x6.7 (peso 0.85)", salida["dataset"]["nota_exclusion"])
            for f in filas:
                f["peso_mercado"] = 0.90
            self.assertIn("x10.0 (peso 0.90)", mb.analizar(filas=filas)["dataset"]["nota_exclusion"])

    def test_el_dataset_no_cruza_un_snapshot_con_la_jornada_de_otra_temporada(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            partidos = [dict(p, mercado_losilla={"1": 60.0, "X": 25.0, "2": 15.0})
                        for p in util.partidos_prediccion(util.EQUIPOS)]
            util.escribir_snapshot(tmp / "snap", 5, fecha="2026-09-12", partidos=partidos)
            util.escribir_jornada(tmp / "jor", 5, fecha="2027-09-11", nombres=util.OTROS_EQUIPOS)
            self.assertEqual(mb.construir_dataset(tmp / "snap", tmp / "jor"), [])


class AprendizajeModulosTests(unittest.TestCase):
    CATEGORIAS = {"14": {"acertantes": 152, "premio_eur": 3095.06}, "13": {"acertantes": 3105, "premio_eur": 71.02},
                  "12": {"acertantes": 28917, "premio_eur": 7.63}, "11": {"acertantes": 148971, "premio_eur": 1.48},
                  "10": {"acertantes": 455229, "premio_eur": 0.0}}

    def test_recaudacion_absurda_se_reconstruye_o_se_descarta(self):
        # J23 26/27: 294.030.675 EUR guardados (x100). 3105 x 71,02 / 7,5% = 2,94 M.
        valor = am.recaudacion_validada({"recaudacion_eur": 294030675.0, "categorias": self.CATEGORIAS})
        self.assertAlmostEqual(valor, 2_940_228.0, delta=5000)
        self.assertEqual(am.recaudacion_validada({"recaudacion_eur": 2_940_306.75, "categorias": self.CATEGORIAS}),
                         2_940_306.75)
        self.assertIsNone(am.recaudacion_validada({"recaudacion_eur": 294030675.0, "categorias": {}}))

    def test_escrutinio_placebo_a_cero_no_cuenta(self):
        placebo = {str(c): {"acertantes": 0, "premio_eur": 0.0} for c in (10, 11, 12, 13, 14, 15)}
        self.assertFalse(am.escrutinio_con_acertantes(placebo))
        self.assertTrue(am.escrutinio_con_acertantes(self.CATEGORIAS))

    def test_escrutinios_temporada_no_deja_pasar_la_recaudacion_corrupta(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            registros = {
                1: {"recaudacion_eur": 294030675.0, "categorias": self.CATEGORIAS},
                2: {"recaudacion_eur": 3488166.0,
                    "categorias": {str(c): {"acertantes": 0, "premio_eur": 0.0} for c in (10, 11, 12, 13, 14)}},
            }
            for j, escrutinio in registros.items():
                (tmp / f"jornada_{j}.json").write_text(json.dumps({
                    "jornada": j, "escrutinio": escrutinio,
                    "partidos": [{"numero": n, "porcentajes": {"1": 60.0, "X": 25.0, "2": 15.0}}
                                 for n in range(1, 15)]}), encoding="utf-8")
            fixture = {n: {"signo_oficial": "1"} for n in range(1, 15)}
            orig = (am.ruta_porcentajes, am.fixture_jornada, am.jornada_cerrada)
            am.ruta_porcentajes = lambda j, etiqueta: tmp / f"jornada_{j}.json"
            am.fixture_jornada = lambda j, *a, **k: fixture
            am.jornada_cerrada = lambda f: True
            try:
                escrutinios = am.escrutinios_temporada("2026_2027", [1, 2])
            finally:
                am.ruta_porcentajes, am.fixture_jornada, am.jornada_cerrada = orig
            self.assertEqual([e["jornada"] for e in escrutinios], [1])           # el placebo (J2) no cuenta
            self.assertLess(escrutinios[0]["recaudacion_eur"], 20_000_000)       # y la J1 va reconstruida
            ratios = am.celdas_overdispersion(escrutinios)
            # Con los 294 M sin validar, todos los ratios caen 100 veces (max ~0,0075).
            self.assertTrue(ratios and max(ratios) > 0.3 and min(ratios) > 0.02, ratios)

    def test_auditoria_de_vetos_usa_el_criterio_vivo_real(self):
        llamadas = []

        def falso(aplicar_vetos=False, tipos_vetos=None, senales_suspendidas=None):
            llamadas.append((aplicar_vetos, tipos_vetos and sorted(tipos_vetos), senales_suspendidas))
            return [], {"aciertos": 1, "esperados": 4.28, "jornadas_evaluadas": 25, "veredicto": "ROJO"}

        r = am.auditoria_vetos_valiente(evaluar_criterio=falso, senales_suspendidas={"h2h_caotico"})
        self.assertEqual(len(llamadas), 3)
        for _vetos, _tipos, suspendidas in llamadas:
            self.assertEqual(suspendidas, {"h2h_caotico"})    # antes: None (h2h_caotico volvia a contar)
        self.assertEqual(r["senales_suspendidas"], ["h2h_caotico"])

    def test_por_defecto_las_senales_retiradas_van_suspendidas(self):
        vistos = []

        def falso(aplicar_vetos=False, tipos_vetos=None, senales_suspendidas=None):
            vistos.append(set(senales_suspendidas or ()))
            return [], {"aciertos": 0, "esperados": 0}

        am.auditoria_vetos_valiente(evaluar_criterio=falso)
        for suspendidas in vistos:
            self.assertTrue(set(sv.SENALES_RETIRADAS) <= suspendidas)


class Elige8EvTests(unittest.TestCase):
    def test_el_aviso_sale_del_veredicto_real(self):
        self.assertIn("NO_DESPLEGAR", e8.aviso_publicado("NO_DESPLEGAR"))
        otro = e8.aviso_publicado("DESPLEGAR")
        self.assertNotIn("NO_DESPLEGAR", otro)
        self.assertIn("DESPLEGAR", otro)
        self.assertNotIn("NO_DESPLEGAR", e8.aviso_publicado(None))

    def test_prediccion_bloqueada_retira_el_bloque(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pred = {"jornada": 7, "prediccion_disponible": True, "prediccion_permitida": False,
                    "partidos": util.partidos_prediccion(util.EQUIPOS), "elige8_ev": {"estado": "ok", "viejo": True}}
            (tmp / "ultima_prediccion.json").write_text(json.dumps(pred), encoding="utf-8")
            (tmp / "jornada_7.json").write_text(json.dumps(pred), encoding="utf-8")
            orig = (e8.PREDICCION, sys.argv)
            e8.PREDICCION = tmp / "ultima_prediccion.json"
            sys.argv = ["elige8_ev.py"]
            try:
                e8.main()
            finally:
                e8.PREDICCION, sys.argv = orig
            self.assertNotIn("elige8_ev", _leer(tmp / "ultima_prediccion.json"))
            self.assertNotIn("elige8_ev", _leer(tmp / "jornada_7.json"))


if __name__ == "__main__":
    unittest.main()
