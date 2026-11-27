# -*- coding: utf-8 -*-
"""Auditoria 26/11/2026 - paquete P1_motor.

Cada test falla sin el arreglo correspondiente (indice del hallazgo entre
parentesis). No toca data/ ni la red: todo con datos en memoria o en
directorios temporales.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest_dixon_coles
import calibrar_probabilidades
import modelo_dixon_coles
import motor_prediccion_objetivo
import motor_prediccion_quiniela as motor


def _equipos(*nombres):
    return [{"equipo": n} for n in nombres]


LALIGA = _equipos(
    "Real Sociedad B", "Real Sociedad de Futbol", "Real Sporting de Gijon",
    "Club Atletico de Madrid", "Rayo Vallecano de Madrid", "Real Racing Club de Santander",
    "Deportivo Alaves", "RC Deportivo de La Coruna", "Real Madrid CF", "Athletic Club",
    "FC Barcelona", "RCD Espanyol de Barcelona", "RC Celta de Vigo", "RC Celta Fortuna",
    "Real Zaragoza", "Real Betis Balompie", "Albacete Balompie", "Sevilla FC",
)


def _buscar(nombre, items=LALIGA):
    mejor = motor.mejor_coincidencia_equipo(items, nombre, lambda e: e["equipo"])
    return mejor["equipo"] if mejor else None


class BuscadorDeNombresTests(unittest.TestCase):
    """(0) Un token generico no basta para entregar los datos de otro club."""

    def test_equipos_extranjeros_y_de_copa_no_reciben_datos_de_clubes_espanoles(self):
        for nombre in (
            "B. Munich", "B. Dortmund",
            "Sporting Lisboa", "Sporting de Portugal", "Sporting Port.",
            "Cd Atlético Paso", "Atlético Calatayud",
            "Cf Rayo Majadahonda", "Racing Ferrol",
            "R Jaén Cf", "R. Checa", "FF Jaro", "Inter", "Dinamo Zagreb",
        ):
            self.assertIsNone(_buscar(nombre), nombre)

    def test_los_nombres_cortos_espanoles_siguen_casando_con_su_club(self):
        casos = {
            "Sporting": "Real Sporting de Gijon",
            "Sporting Gijón": "Real Sporting de Gijon",
            "Racing": "Real Racing Club de Santander",
            "R. Santander": "Real Racing Club de Santander",
            "Rayo": "Rayo Vallecano de Madrid",
            "Atletico": "Club Atletico de Madrid",
            "At. Madrid": "Club Atletico de Madrid",
            "Atlético de Madrid": "Club Atletico de Madrid",
            "Ath. Club": "Athletic Club",
            "Athletic de Bilbao": "Athletic Club",
            "R. Madrid": "Real Madrid CF",
            "Real Madrid": "Real Madrid CF",
            "Barcelona": "FC Barcelona",
            "Espanyol": "RCD Espanyol de Barcelona",
            "R. Sociedad": "Real Sociedad de Futbol",
            "R. Sociedad B": "Real Sociedad B",
            "Celta": "RC Celta de Vigo",
            "Celta Fortuna": "RC Celta Fortuna",
            "R. Zaragoza": "Real Zaragoza",
            "Betis": "Real Betis Balompie",
            "Albacete": "Albacete Balompie",
            "Alavés": "Deportivo Alaves",
        }
        for nombre, esperado in casos.items():
            self.assertEqual(_buscar(nombre), esperado, nombre)

    def test_deportivo_a_secas_es_el_de_la_coruna_y_no_el_alaves(self):
        self.assertEqual(_buscar("Deportivo"), "RC Deportivo de La Coruna")

    def test_primer_equipo_y_filial_no_se_mezclan(self):
        self.assertEqual(motor.puntuacion_nombre_equipo("Real Sociedad B", "Real Sociedad de Futbol"), 0)
        self.assertEqual(motor.puntuacion_nombre_equipo("RC Celta Fortuna", "RC Celta de Vigo"), 0)

    def test_empate_entre_dos_equipos_distintos_es_ambiguo(self):
        items = _equipos("Union Deportiva Levante Norte", "Levante Norte Union Deportiva Sur")
        valor, score = motor.mejor_coincidencia_nombre(
            [("Villa Norte", "a"), ("Villa Sur", "b")], "Villa"
        )
        self.assertIsNone(valor)
        self.assertEqual(score, 0)
        # dos entradas del MISMO equipo no son empate
        valor, _ = motor.mejor_coincidencia_nombre([("Sevilla FC", "a"), ("Sevilla", "b")], "Sevilla")
        self.assertEqual(valor, "a")
        self.assertTrue(items)

    def test_lesiones_y_contexto_usan_el_mismo_buscador(self):
        fuente = {"equipos": {"R. Sociedad B": [{"jugador": "x"}], "Sporting": [{"jugador": "y"}], "Atlético": [{"jugador": "z"}]}}
        for nombre in ("B. Dortmund", "R Jaén Cf", "R. Zaragoza", "Sporting Lisboa", "Cd Atlético Paso"):
            self.assertEqual(motor.buscar_lesiones_equipo(fuente, nombre), [], nombre)
        self.assertEqual(len(motor.buscar_lesiones_equipo(fuente, "Real Sporting de Gijon")), 1)
        self.assertEqual(len(motor.buscar_lesiones_equipo(fuente, "Club Atletico de Madrid")), 1)
        contexto = {"equipos": {"Real Sporting de Gijon": {"alertas": ["lesiones"]}}}
        self.assertIsNone(motor.buscar_contexto_equipo(contexto, "Sporting de Portugal"))
        self.assertIsNotNone(motor.buscar_contexto_equipo(contexto, "Sporting"))


class PerfilAutonomoTests(unittest.TestCase):
    """(37) El Betis no recibe el perfil de 'Belgica' (clave con mojibake)."""

    PERFILES = {"equipos": {
        "ba lgica": {"equipo": "B?lgica", "partidos_total": 1},
        "betis": {"equipo": "Betis", "partidos_total": 41},
        "r sociedad": {"equipo": "R. Sociedad", "partidos_total": 2},
        "sociedad": {"equipo": "Real Sociedad", "partidos_total": 28},
        "at madrid": {"equipo": "At. Madrid", "partidos_total": 20},
        "madrid": {"equipo": "Real Madrid", "partidos_total": 30},
        "rayo": {"equipo": "Rayo", "partidos_total": 5},
        "r checa": {"equipo": "R. Checa", "partidos_total": 1},
        "sociedad b": {"equipo": "R. Sociedad B", "partidos_total": 9},
        "at madrid f": {"equipo": "At. Madrid (F)", "partidos_total": 7},
        "madrid f": {"equipo": "Real Madrid (F)", "partidos_total": 8},
    }}

    def _equipo(self, nombre):
        perfil = motor.buscar_perfil_autonomo(self.PERFILES, nombre)
        return perfil["equipo"] if perfil else None

    def test_betis_balompie_recibe_el_perfil_del_betis(self):
        self.assertEqual(self._equipo("Real Betis Balompie"), "Betis")

    def test_real_sociedad_recibe_la_muestra_grande(self):
        self.assertEqual(self._equipo("Real Sociedad de Futbol"), "Real Sociedad")
        self.assertEqual(self._equipo("Real Sociedad B"), "R. Sociedad B")

    def test_equipos_de_copa_no_reciben_perfiles_ajenos(self):
        self.assertIsNone(self._equipo("R Jaén Cf"))
        self.assertIsNone(self._equipo("Cf Rayo Majadahonda"))
        self.assertIsNone(self._equipo("Cd Atlético Paso"))

    def test_se_conservan_los_casos_ya_arreglados(self):
        self.assertEqual(self._equipo("Club Atletico de Madrid"), "At. Madrid")
        self.assertEqual(self._equipo("Atletico de Madrid (F)"), "At. Madrid (F)")
        self.assertEqual(self._equipo("Real Madrid CF"), "Real Madrid")


class LigaFTests(unittest.TestCase):
    """(44) 'Femenino' es femenino."""

    def test_femenino_se_reconoce(self):
        for nombre in ("Alavés Femenino", "Alaves Femenino", "Levante Femenina", "Barça Femení", "Alaves (F)", "Madrid CFF"):
            self.assertTrue(motor.es_equipo_liga_f(nombre), nombre)
        for nombre in ("Deportivo Alaves", "Real Madrid CF", "Fenerbahce"):
            self.assertFalse(motor.es_equipo_liga_f(nombre), nombre)

    def test_alaves_femenino_no_recibe_datos_del_masculino(self):
        self.assertIsNone(_buscar("Alavés Femenino"))
        fuente = {"equipos": {"Alavés": [{"jugador": "x"}]}}
        self.assertEqual(motor.buscar_lesiones_equipo(fuente, "Alavés Femenino"), [])

    def test_el_partido_entra_en_el_modelo_de_liga_f(self):
        _, traza = motor.ajustar_por_liga_f(
            {"1": 40.0, "X": 30.0, "2": 30.0}, {"local": "Alavés Femenino", "visitante": "Eibar (F)"}, {}
        )
        self.assertNotEqual(traza.get("motivo"), "no es partido de Liga F")


class SnapshotPreCierreTests(unittest.TestCase):
    """(32, 114) El motor no escribe el snapshot pre-cierre."""

    def test_el_motor_no_importa_ni_llama_al_escritor_del_snapshot(self):
        self.assertFalse(hasattr(motor, "crear_snapshot_prediccion"))
        fuente = (ROOT / "motor_prediccion_quiniela.py").read_text(encoding="utf-8")
        self.assertNotIn("crear_snapshot_prediccion(", fuente)
        self.assertNotIn("import crear_snapshot_prediccion", fuente)


class DerbiTests(unittest.TestCase):
    """(43) Los derbis de la lista se detectan con nombres cortos y largos."""

    def test_derbis(self):
        for local, visitante in (
            ("Real Madrid", "Barcelona"), ("Real Madrid CF", "FC Barcelona"),
            ("At. Madrid", "Real Madrid"), ("Club Atletico de Madrid", "Real Madrid CF"),
            ("Athletic Club", "Real Sociedad"), ("Real Sociedad de Futbol", "Athletic Club"),
            ("Sevilla", "Betis"), ("Sevilla FC", "Real Betis Balompie"),
            ("Espanyol", "Barcelona"), ("RCD Espanyol de Barcelona", "FC Barcelona"),
            ("RC Deportivo de La Coruna", "RC Celta de Vigo"),
        ):
            self.assertTrue(motor.partido_es_derbi({"local": local, "visitante": visitante}), (local, visitante))

    def test_no_derbis(self):
        for local, visitante in (
            ("Real Madrid CF", "Getafe CF"), ("Club Atletico de Madrid", "FC Barcelona"),
            ("Real Sociedad B", "Athletic Club"), ("Deportivo Alaves", "RC Celta de Vigo"),
            ("Rayo Vallecano de Madrid", "Real Madrid CF"),
        ):
            self.assertFalse(motor.partido_es_derbi({"local": local, "visitante": visitante}), (local, visitante))


class DixonColesFalloTests(unittest.TestCase):
    """(140, 164) Un fallo de entrenamiento deja motivo y no se reintenta."""

    def setUp(self):
        self._cargar = modelo_dixon_coles.cargar_partidos
        modelo_dixon_coles.reiniciar_cache()

    def tearDown(self):
        modelo_dixon_coles.cargar_partidos = self._cargar
        modelo_dixon_coles.reiniciar_cache()
        motor._ERROR_DIXON_COLES = None

    def test_fallo_se_cachea_y_queda_en_la_traza(self):
        llamadas = []

        def roto():
            llamadas.append(1)
            raise KeyError("calendario corrupto")

        modelo_dixon_coles.cargar_partidos = roto
        probs = {"1": 50.0, "X": 30.0, "2": 20.0}
        with contextlib.redirect_stdout(io.StringIO()):
            trazas = [
                motor.ajustar_por_dixon_coles(probs, {"local": "Sevilla FC", "visitante": "Getafe CF"})[1]
                for _ in range(14)
            ]
        self.assertEqual(len(llamadas), 1)
        self.assertIn("KeyError", modelo_dixon_coles.error_entrenamiento())
        for traza in trazas:
            self.assertFalse(traza["activo"])
            self.assertTrue(traza["motivo"].startswith("error_entrenamiento"), traza)

    def test_equipo_no_cubierto_no_es_un_error(self):
        _, traza = motor.ajustar_por_dixon_coles(
            {"1": 50.0, "X": 30.0, "2": 20.0}, {"local": "A", "visitante": "B"}, proveedor=lambda l, v: None
        )
        self.assertEqual(traza, {"activo": False, "motivo": "equipo_no_cubierto"})


class CoberturaCapasTests(unittest.TestCase):
    """(141, 140) Alerta cuando falta el mercado o falla Dixon-Coles."""

    def _partido(self, num, mercado=True, dc=None):
        return {
            "num": num,
            "mercado_losilla": {"1": 50.0, "X": 30.0, "2": 20.0} if mercado else {"1": 0.0, "X": 0.0, "2": 0.0},
            "trazabilidad_datos": {"dixon_coles": dc or {"activo": True}},
        }

    def test_todo_cubierto_no_alerta(self):
        r = motor.resumen_cobertura_capas([self._partido(n) for n in range(1, 15)], 25, 25)
        self.assertEqual(r["alertas"], [])
        self.assertTrue(r["mercado"]["completa"])
        self.assertEqual(r["mercado"]["partidos_con_mercado"], 14)
        self.assertEqual(r["dixon_coles"]["partidos_activos"], 14)

    def test_sin_mercado_alerta_alta(self):
        r = motor.resumen_cobertura_capas([self._partido(n, mercado=False) for n in range(1, 15)], 26, 25)
        self.assertFalse(r["mercado"]["completa"])
        self.assertEqual(r["mercado"]["partidos_con_mercado"], 0)
        self.assertEqual(r["mercado"]["jornada_fuente"], 25)
        self.assertEqual([a["nivel"] for a in r["alertas"]], ["alta"])
        self.assertIn("mercado", r["alertas"][0]["titulo"].lower())

    def test_fallo_de_dixon_coles_alerta_pero_equipo_no_cubierto_no(self):
        fallo = {"activo": False, "motivo": "error_entrenamiento: KeyError: 'x'"}
        r = motor.resumen_cobertura_capas([self._partido(n, dc=fallo) for n in range(1, 15)], 25, 25)
        self.assertEqual(len(r["alertas"]), 1)
        self.assertIn("Dixon", r["alertas"][0]["titulo"])
        normal = {"activo": False, "motivo": "equipo_no_cubierto"}
        r = motor.resumen_cobertura_capas([self._partido(n, dc=normal) for n in range(1, 15)], 25, 25)
        self.assertEqual(r["alertas"], [])


class MercadoPorNumeroYEquipoTests(unittest.TestCase):
    """(155) El numero solo no basta para emparejar el mercado."""

    FUENTE = {"probabilidades": {"jornada": 25, "partidos": [
        {"numero": 1, "local": "BETIS", "visitante": "RAYO", "probabilidades_signo": {"1": 70, "X": 18, "2": 12}},
        {"numero": 2, "local": "VALENCIA", "visitante": "R.MADRID", "probabilidades_signo": {"1": 8, "X": 11, "2": 81}},
        {"numero": "x", "local": "ELCHE", "visitante": "AT.MADRID", "probabilidades_signo": {"1": 20, "X": 25, "2": 55}},
    ]}}

    def test_numero_y_equipo_coinciden(self):
        item = motor.partido_losilla_por_numero_o_equipos(
            self.FUENTE, {"num": 1, "local": "Real Betis Balompie", "visitante": "Rayo Vallecano de Madrid"}
        )
        self.assertEqual(item.get("local"), "BETIS")

    def test_mismo_numero_con_otros_equipos_no_hereda_el_mercado(self):
        with contextlib.redirect_stdout(io.StringIO()):
            signos = motor.mercado_losilla_signos(
                self.FUENTE, {"num": 2, "local": "UD Almeria", "visitante": "FC Andorra"}
            )
        self.assertEqual(sum(signos.values()), 0)

    def test_orden_distinto_se_resuelve_por_equipos_y_numero_sucio_no_rompe(self):
        with contextlib.redirect_stdout(io.StringIO()):
            item = motor.partido_losilla_por_numero_o_equipos(
                self.FUENTE, {"num": 1, "local": "Elche CF", "visitante": "Club Atletico de Madrid"}
            )
        self.assertEqual(item.get("local"), "ELCHE")


class RevulsivoDobleTests(unittest.TestCase):
    """(160) Con dos debuts, la traza guarda los dos equipos."""

    def setUp(self):
        self._cache = motor._EFECTOS_REVULSIVO_CACHE
        motor._EFECTOS_REVULSIVO_CACHE = (motor.EFECTO_REVULSIVO_DEBUT_FUERA, motor.EFECTO_REVULSIVO_DEBUT_CASA)

    def tearDown(self):
        motor._EFECTOS_REVULSIVO_CACHE = self._cache

    def test_traza_con_los_dos_eventos(self):
        ceses = [
            {"equipo": "Valencia CF", "fecha_cese": "2026-09-13", "fecha_nuevo": "2026-09-23", "nuevo": "A"},
            {"equipo": "Sevilla FC", "fecha_cese": "2026-09-14", "fecha_nuevo": "2026-09-24", "nuevo": "B"},
        ]
        partido = {"local": "Valencia CF", "visitante": "Sevilla FC", "fecha": "2026-10-11"}
        _, riesgo, lecturas, traza = motor.ajustar_por_revulsivo(
            {"1": 45.0, "X": 28.0, "2": 27.0}, partido, ceses=ceses, contador=lambda e, d, h: 0
        )
        self.assertEqual(len(lecturas), 2)
        self.assertTrue(traza["doble"])
        self.assertEqual([e["lado"] for e in traza["eventos"]], ["local", "visitante"])
        self.assertEqual([e["equipo"] for e in traza["eventos"]], ["Valencia CF", "Sevilla FC"])

    def test_un_solo_evento_no_es_doble(self):
        ceses = [{"equipo": "Valencia CF", "fecha_cese": "2026-09-13", "fecha_nuevo": "2026-09-23", "nuevo": "A"}]
        partido = {"local": "Valencia CF", "visitante": "Sevilla FC", "fecha": "2026-10-11"}
        _, _, _, traza = motor.ajustar_por_revulsivo(
            {"1": 45.0, "X": 28.0, "2": 27.0}, partido, ceses=ceses, contador=lambda e, d, h: 0
        )
        self.assertFalse(traza["doble"])
        self.assertEqual(len(traza["eventos"]), 1)
        self.assertEqual(traza["lado"], "local")


class TemporadaTests(unittest.TestCase):
    """(156, 224) La temporada sale de la fecha real, no de un literal."""

    def test_temporada_de_jornada_por_fecha(self):
        j25 = {"jornada": 25, "partidos": [{"num": 1, "fecha": "2026-11-28"}]}
        j30 = {"jornada": 30, "partidos": [{"num": 1, "fecha": "2025-12-21"}]}
        self.assertEqual(motor.temporada_de_jornada(j25, 25), "2026/2027")
        self.assertEqual(motor.temporada_de_jornada(j30, 30), "2025/2026")
        self.assertEqual(motor.temporada_de_jornada({}, 5, defecto=""), "")

    def test_no_queda_la_temporada_cableada(self):
        for fichero in ("motor_prediccion_quiniela.py", "motor_prediccion_objetivo.py"):
            self.assertNotIn('"2025/2026"', (ROOT / fichero).read_text(encoding="utf-8"), fichero)

    def test_prediccion_en_espera_usa_la_temporada_real_y_no_pisa_si_el_fichero_esta_roto(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "jornadas").mkdir()
            pred = tmp / "predicciones"
            pred.mkdir()
            (tmp / "jornadas" / "jornada_25.json").write_text(json.dumps({
                "jornada": 25,
                "partidos": [{"num": n, "local": f"L{n}", "visitante": f"V{n}", "fecha": "2026-11-28"} for n in range(1, 15)],
            }), encoding="utf-8")
            (tmp / "jornadas" / "jornada_26.json").write_text("{roto", encoding="utf-8")
            data_original, pred_original = motor_prediccion_objetivo.DATA, motor_prediccion_objetivo.PREDICCIONES
            try:
                motor_prediccion_objetivo.DATA = tmp
                motor_prediccion_objetivo.PREDICCIONES = pred
                self.assertTrue(motor_prediccion_objetivo.escribir_prediccion_en_espera(25, {"motivo": "x"}))
                salida = json.loads((pred / "ultima_prediccion.json").read_text(encoding="utf-8"))
                self.assertEqual(salida["temporada"], "2026/2027")
                self.assertEqual(salida["temporada_base"], "2026/2027")
                self.assertEqual(len(salida["partidos"]), 14)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertFalse(motor_prediccion_objetivo.escribir_prediccion_en_espera(26, {"motivo": "x"}))
                intacta = json.loads((pred / "ultima_prediccion.json").read_text(encoding="utf-8"))
                self.assertEqual(intacta["jornada"], 25)
                self.assertFalse((pred / "jornada_26.json").exists())
            finally:
                motor_prediccion_objetivo.DATA = data_original
                motor_prediccion_objetivo.PREDICCIONES = pred_original


class JornadaActivaTests(unittest.TestCase):
    """(157) Sin ficheros de jornada no se devuelve 61: se para."""

    def test_sin_jornadas_lanza_system_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = motor.JORNADAS
            try:
                motor.JORNADAS = Path(tmp)
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        motor.detectar_jornada_activa()
            finally:
                motor.JORNADAS = original


class CalibracionOrdenTests(unittest.TestCase):
    """(162) detalle_reciente en orden cronologico, no alfabetico de fichero."""

    def test_orden_cronologico_y_snapshot_de_otra_temporada_omitido(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            snaps, jornadas = tmp / "pre_cierre", tmp / "jornadas"
            snaps.mkdir()
            jornadas.mkdir()

            def crear(num, fecha, prefijo, snap_prefijo=None, snap_fecha=None):
                partidos = [
                    {"num": n, "local": f"{prefijo}Local{n}", "visitante": f"{prefijo}Visit{n}", "fecha": fecha, "signo_oficial": "1"}
                    for n in range(1, 15)
                ]
                (jornadas / f"jornada_{num}.json").write_text(json.dumps({"jornada": num, "partidos": partidos}), encoding="utf-8")
                sp = snap_prefijo or prefijo
                pred = {"jornada": num, "partidos": [
                    {"num": n, "local": f"{sp}Local{n}", "visitante": f"{sp}Visit{n}", "probabilidades": {"1": 50, "X": 30, "2": 20}}
                    for n in range(1, 15)
                ]}
                (snaps / f"jornada_{num}.json").write_text(json.dumps({
                    "jornada": num, "primer_partido_utc": f"{snap_fecha or fecha}T12:00:00+00:00", "prediccion": pred,
                }), encoding="utf-8")

            crear(70, "2026-07-01", "Viejo")          # temporada anterior
            crear(2, "2026-08-22", "Dos")
            crear(10, "2026-10-10", "Diez")
            crear(3, "2026-08-29", "Tres")
            # snapshot de la J28 de la temporada pasada contra la J28 nueva
            crear(28, "2026-12-13", "Nueva", snap_prefijo="Antigua", snap_fecha="2025-12-14")

            originales = (calibrar_probabilidades.SNAPSHOTS, calibrar_probabilidades.JORNADAS)
            try:
                calibrar_probabilidades.SNAPSHOTS = snaps
                calibrar_probabilidades.JORNADAS = jornadas
                with contextlib.redirect_stdout(io.StringIO()):
                    evaluaciones = calibrar_probabilidades.evaluaciones_snapshots()
            finally:
                calibrar_probabilidades.SNAPSHOTS, calibrar_probabilidades.JORNADAS = originales
            orden = []
            for e in evaluaciones:
                if e["jornada"] not in orden:
                    orden.append(e["jornada"])
            self.assertEqual(orden, [70, 2, 3, 10])
            self.assertEqual(evaluaciones[-1]["jornada"], 10)


class BacktestDixonColesTests(unittest.TestCase):
    """(163) Repetir el backtest no sobrescribe la evidencia versionada."""

    def test_no_pisa_el_fichero_existente(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "backtest_dixon_coles.json"
            self.assertEqual(backtest_dixon_coles.ruta_salida_sin_pisar(salida), salida)
            salida.write_text("{}", encoding="utf-8")
            hoy = datetime(2026, 11, 27, tzinfo=timezone.utc)
            destino = backtest_dixon_coles.ruta_salida_sin_pisar(salida, hoy=hoy)
            self.assertNotEqual(destino, salida)
            self.assertEqual(destino.name, "backtest_dixon_coles_repeticion_20261127.json")

    def test_el_test_b_solo_acepta_ficheros_de_su_temporada(self):
        nueva = {"partidos": [{"num": 1, "fecha": "2026-08-22"}]}
        vieja = {"partidos": [{"num": 1, "fecha": "2025-08-23"}]}
        self.assertEqual(backtest_dixon_coles._temporada_fichero(nueva, 2), backtest_dixon_coles.TEMPORADA_TEST_B)
        self.assertNotEqual(backtest_dixon_coles._temporada_fichero(vieja, 2), backtest_dixon_coles.TEMPORADA_TEST_B)

    def _ejecutar_test_b(self, fecha_jornada_2):
        """Llama a test_b() de verdad sobre un data/ temporal con un unico
        jornada_2.json y una entrada de aprendizaje de la jornada 2."""

        class ModeloFalso:
            def entrenar(self, partidos, fecha):
                return self

            def probabilidades(self, local, visitante):
                return {"1": 0.5, "X": 0.3, "2": 0.2}

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "jornadas").mkdir()
            (data / "jornadas" / "jornada_2.json").write_text(json.dumps({
                "jornada": 2,
                "partidos": [{"num": 1, "local": "Sevilla FC", "visitante": "Getafe CF", "fecha": fecha_jornada_2}],
            }), encoding="utf-8")
            (data / "aprendizaje_ia.json").write_text(json.dumps({"detalle": [{
                "jornada": 2, "partido": "1. Sevilla FC - Getafe CF", "signo_real": "1",
                "probabilidades_usadas": {"1": 50, "X": 30, "2": 20},
            }]}), encoding="utf-8")
            originales = (backtest_dixon_coles.DATA, backtest_dixon_coles.DixonColes)
            try:
                backtest_dixon_coles.DATA = data
                backtest_dixon_coles.DixonColes = ModeloFalso
                return backtest_dixon_coles.test_b([])
            finally:
                backtest_dixon_coles.DATA, backtest_dixon_coles.DixonColes = originales

    def test_test_b_evalua_la_jornada_de_su_temporada(self):
        self.assertEqual(self._ejecutar_test_b("2026-08-22")["partidos_evaluados"], 1)

    def test_test_b_descarta_un_fichero_de_otra_temporada(self):
        # jornada_2.json de la 25/26 (la numeracion se reinicia cada agosto):
        # la entrada de aprendizaje de la J2 de la 26/27 NO se evalua contra el.
        r = self._ejecutar_test_b("2025-08-23")
        self.assertEqual(r["partidos_evaluados"], 0)
        self.assertEqual(r["sin_cobertura_dc"], 0)


class RepartoDelMotorTests(unittest.TestCase):
    """(1) El motor exporta su reparto en un bloque propio y sin ambiguedad."""

    def test_bloque_reparto(self):
        partidos = [
            {"num": 1, "tipo": "FIJO", "signo_final": "1", "signo_base": "1", "cobertura_autor": {"activo": True, "cubierta": False}, "x_de_autor": {"activo": False}},
            {"num": 2, "tipo": "DOBLE", "signo_final": "X2", "signo_base": "2", "cobertura_autor": {"activo": True, "cubierta": True}, "x_de_autor": {"activo": False}},
            {"num": 3, "tipo": "TRIPLE", "signo_final": "1X2", "signo_base": "1", "cobertura_autor": {"activo": False}, "x_de_autor": {"activo": False}},
            {"num": 4, "tipo": "FIJO", "signo_final": "X", "signo_base": "1", "cobertura_autor": {"activo": False}, "x_de_autor": {"activo": True}},
        ]
        r = motor.reparto_del_motor(partidos)
        self.assertEqual(r["triples"], [3])
        self.assertEqual(r["dobles"], {"2": "X2"})
        self.assertEqual(r["x_de_autor"], [4])
        self.assertEqual(r["cobertura_autor_cubierta"], [2])
        self.assertEqual(r["cobertura_autor_sin_cubrir"], [1])
        self.assertEqual(len(r["partidos"]), 4)


class MotivacionFuenteVaciaTests(unittest.TestCase):
    """(152) Sin tablas de clasificacion, la traza lo dice."""

    def test_fuente_vacia_en_la_traza(self):
        partido = {"num": 1, "local": "Sevilla FC", "visitante": "Getafe CF", "probabilidades": {"1": 45.0, "X": 30.0, "2": 25.0}}
        vacia = motor.calcular_ajuste_motivacion(partido, {}, {"clasificaciones": {}})
        self.assertTrue(vacia["clasificacion_losilla"]["fuente_vacia"])
        con_tabla = motor.calcular_ajuste_motivacion(
            partido, {}, {"clasificaciones": {"ligas": {"primera": [{"equipo": "Sevilla", "posicion": 1, "puntos": 30, "pj": 14}]}}}
        )
        self.assertFalse(con_tabla["clasificacion_losilla"]["fuente_vacia"])


class MercadoSoloPorNumeroTests(unittest.TestCase):
    """(155, segunda pasada) Nombres abreviados en los dos lados: el partido
    no se queda sin mercado si el resto de la fuente esta alineada."""

    JORNADA = [
        {"num": 1, "local": "Arsenal", "visitante": "B. Dortmund"},
        {"num": 2, "local": "Real Madrid", "visitante": "Liverpool"},
        {"num": 3, "local": "Sporting Lisboa", "visitante": "PSG"},
        {"num": 4, "local": "FC Barcelona", "visitante": "Juventus"},
        {"num": 5, "local": "Olimpiacos", "visitante": "PSG B"},
    ]

    def _fuente(self, partidos, con_jornada=True):
        fuente = {"probabilidades": {"jornada": 24, "partidos": partidos}}
        return motor.fuente_losilla_con_jornada(fuente, self.JORNADA) if con_jornada else fuente

    def _item(self, numero, local, visitante, p1=40):
        return {"numero": numero, "local": local, "visitante": visitante,
                "probabilidades_signo": {"1": p1, "X": 25, "2": 75 - p1}}

    def _alineada(self):
        return [
            self._item(1, "ARSENAL", "DORTMUND"),
            self._item(2, "R.MADRID", "LIVERPOOL"),
            self._item(3, "SPORTING DE PORTUGAL", "PARIS SG", p1=33),
            self._item(4, "BARCELONA", "JUVENTUS"),
        ]

    def test_los_nombres_no_casan_por_ninguna_via(self):
        # condicion de partida del hallazgo del revisor
        self.assertLess(motor.puntuacion_nombre_equipo("SPORTING DE PORTUGAL", "Sporting Lisboa"), 55)
        self.assertLess(motor.puntuacion_nombre_equipo("PARIS SG", "PSG"), 55)

    def test_abreviaturas_en_los_dos_lados_se_empareja_por_numero(self):
        fuente = self._fuente(self._alineada())
        with contextlib.redirect_stdout(io.StringIO()) as salida:
            item, modo = motor.emparejar_partido_losilla(fuente, self.JORNADA[2])
        self.assertEqual(modo, "solo_por_numero")
        self.assertEqual(item.get("local"), "SPORTING DE PORTUGAL")
        self.assertIn("SOLO POR NUMERO", salida.getvalue())
        traza = {}
        with contextlib.redirect_stdout(io.StringIO()):
            signos = motor.mercado_losilla_signos(fuente, self.JORNADA[2], traza)
        self.assertEqual(signos["1"], 33.0)
        self.assertEqual(traza["emparejamiento"], "solo_por_numero")

    def test_sin_los_partidos_de_la_jornada_no_se_acepta(self):
        fuente = self._fuente(self._alineada(), con_jornada=False)
        with contextlib.redirect_stdout(io.StringIO()):
            item, modo = motor.emparejar_partido_losilla(fuente, self.JORNADA[2])
        self.assertEqual((item, modo), ({}, ""))

    def test_fuente_desordenada_no_se_acepta_por_numero(self):
        # el partido 3 de la fuente es el 2 de la jornada: cambio de orden
        desordenada = [
            self._item(1, "ARSENAL", "DORTMUND"),
            self._item(2, "SPORTING DE PORTUGAL", "PARIS SG"),
            self._item(3, "R.MADRID", "LIVERPOOL"),
            self._item(4, "BARCELONA", "JUVENTUS"),
        ]
        fuente = self._fuente(desordenada)
        with contextlib.redirect_stdout(io.StringIO()):
            item, modo = motor.emparejar_partido_losilla(fuente, self.JORNADA[2])
            self.assertEqual((item, modo), ({}, ""))
            # y el Madrid - Liverpool se encuentra por equipos en el numero 3
            item, modo = motor.emparejar_partido_losilla(fuente, self.JORNADA[1])
        self.assertEqual(modo, "equipos")
        self.assertEqual(item.get("numero"), 3)

    def test_fuente_de_otros_partidos_no_se_acepta_por_numero(self):
        # nada casa con la jornada: no esta alineada, no se hereda el mercado
        ajena = [
            self._item(1, "ALMERIA", "ANDORRA"),
            self._item(2, "MALAGA", "CADIZ"),
            self._item(3, "LEGANES", "HUESCA"),
            self._item(4, "BURGOS", "EIBAR"),
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            item, modo = motor.emparejar_partido_losilla(self._fuente(ajena), self.JORNADA[2])
        self.assertEqual((item, modo), ({}, ""))

    def test_cobertura_de_capas_lista_los_emparejados_por_numero(self):
        partidos = [
            {"num": n, "mercado_losilla": {"1": 40, "X": 30, "2": 30},
             "trazabilidad_datos": {"mercado_losilla_emparejamiento": {
                 "emparejamiento": "solo_por_numero" if n == 3 else "numero_y_equipo"}}}
            for n in range(1, 15)
        ]
        r = motor.resumen_cobertura_capas(partidos, 24, 24)
        self.assertEqual(r["mercado"]["emparejados_solo_por_numero"], [3])
        self.assertTrue(r["mercado"]["completa"])
        self.assertTrue(any(a["titulo"] == "Mercado emparejado solo por numero" for a in r["alertas"]))


class SorpresaPotencialTests(unittest.TestCase):
    """(161) La alerta motivacional usa el vocabulario del indice de sorpresa."""

    def test_con_favorito(self):
        r = motor.marcar_sorpresa_potencial({"indice": 35.0, "favorito": "1", "categoria": "normal", "favorito_atacable": False}, "DOBLE")
        self.assertEqual(r["indice"], 60.0)
        self.assertEqual(r["categoria"], "favorito_atacable")
        self.assertTrue(r["favorito_atacable"])
        self.assertEqual(r["cobertura_sugerida"], "DOBLE")

    def test_sin_favorito(self):
        r = motor.marcar_sorpresa_potencial({"indice": 72.0, "favorito": "X", "categoria": "normal", "favorito_atacable": False})
        self.assertEqual(r["indice"], 72.0)
        self.assertEqual(r["categoria"], "partido_abierto")
        self.assertFalse(r["favorito_atacable"])
        self.assertNotEqual(r["categoria"], "alta")


class AvisoSnapshotTests(unittest.TestCase):
    """(32) El motor recuerda por consola que el snapshot lo escribe otro paso."""

    def test_aviso_en_el_codigo_de_predecir(self):
        import inspect
        fuente = inspect.getsource(motor.predecir)
        self.assertIn("guardar_snapshot_prediccion.py", fuente)
        self.assertIn("AVISO motor: el snapshot pre-cierre NO se ha actualizado", fuente)


if __name__ == "__main__":
    unittest.main()
