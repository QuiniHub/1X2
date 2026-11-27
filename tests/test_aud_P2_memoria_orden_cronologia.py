# -*- coding: utf-8 -*-
"""Auditoria 26/11, paquete P2_memoria_orden.

Toda la familia es la misma: ordenar por la fecha en TEXTO o por el numero de
jornada en vez de por la fecha real. Los tests fallan (o dan error, si la
funcion no existia) sin su arreglo, con dos excepciones declaradas:
test_sin_dependencias_y_sin_artefacto_devuelve_none es una guarda de no
regresion (ya pasaba) y test_datos_reales_en_orden_cronologico depende de
data/jornadas real y se salta si no existe.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import construir_memoria_ia as cmi
import memoria_autonoma_quiniela as memoria
import modelo_metricas_1x2 as mm
import sincronizar_dinamicas_memoria as sdm


# 'Belgica' con el acento roto (UTF-8 leido como Latin-1), como en jornada_66.
BELGICA_ROTA = "BÃ©lgica"


def escribir(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def leer(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def partidos_jornada(resultado_a, fecha=None, local_1="Equipo A", prefijo=""):
    """14 partidos; el 1 es local_1 contra 'Rival'. Sin fecha por partido si fecha=None."""
    signo = {"1-0": "1", "0-1": "2", "1-1": "X"}[resultado_a]
    filas = [{"num": 1, "local": local_1, "visitante": "Rival", "resultado": resultado_a, "signo_oficial": signo}]
    for idx in range(2, 15):
        filas.append({
            "num": idx,
            "local": f"{prefijo}Local {idx}",
            "visitante": f"{prefijo}Visitante {idx}",
            "resultado": "1-0",
            "signo_oficial": "1",
        })
    if fecha:
        for fila in filas:
            fila["fecha"] = fecha
    return filas


def prediccion(numero, signo_p1, prefijo="", local_1="Equipo A"):
    filas = [{"num": 1, "local": local_1, "visitante": "Rival", "signo_final": signo_p1, "tipo": "FIJO",
              "probabilidades": {"1": 50.0, "X": 30.0, "2": 20.0}}]
    for idx in range(2, 15):
        filas.append({"num": idx, "local": f"{prefijo}Local {idx}", "visitante": f"{prefijo}Visitante {idx}",
                      "signo_final": "1", "tipo": "FIJO", "probabilidades": {"1": 60.0, "X": 25.0, "2": 15.0}})
    return {"jornada": numero, "prediccion_disponible": True, "partidos": filas}


def montar_dos_temporadas(root):
    """J28 y J76 de la 25/26 (fecha solo en texto / agosto) y J1, J2 de la 26/27."""
    jornadas = root / "data" / "jornadas"
    # dic-2025: la cabecera es texto y los partidos no traen fecha
    escribir(jornadas / "jornada_28.json", {
        "jornada": 28, "fecha": "La Quiniela Domingo, 14 de diciembre de 2025",
        "partidos": partidos_jornada("1-0", prefijo="V"),
    })
    # ago-2026, ultima jornada de la 25/26: numero mas alto, NO la mas reciente
    escribir(jornadas / "jornada_76.json", {
        "jornada": 76, "fecha": "2026-08-08",
        "partidos": partidos_jornada("1-0", fecha="2026-08-08", prefijo="V"),
    })
    escribir(jornadas / "jornada_1.json", {
        "jornada": 1, "fecha": "2026-08-15",
        "partidos": partidos_jornada("0-1", fecha="2026-08-15"),
    })
    escribir(jornadas / "jornada_2.json", {
        "jornada": 2, "fecha": "2026-08-22",
        "partidos": partidos_jornada("0-1", fecha="2026-08-22"),
    })


class ModeloMetricasOrdenTests(unittest.TestCase):
    """Hallazgos 2 y 28."""

    def test_fecha_en_texto_de_diciembre_va_antes_que_la_iso_de_agosto(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            montar_dos_temporadas(root)
            filas = mm.iter_closed_matches(root / "data" / "jornadas")
            orden = []
            for fila in filas:
                if not orden or orden[-1] != fila["jornada"]:
                    orden.append(fila["jornada"])
            self.assertEqual(orden, [28, 76, 1, 2])
            self.assertEqual(filas[0]["fecha_orden"], "2025-12-14")
            fechas = [fila["fecha_orden"] for fila in filas]
            self.assertEqual(fechas, sorted(fechas))

    def test_partido_sin_fecha_parseable_se_excluye(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            escribir(root / "data" / "jornadas" / "jornada_5.json", {
                "jornada": 5, "fecha": "sin fecha conocida", "partidos": partidos_jornada("1-0"),
            })
            self.assertEqual(mm.iter_closed_matches(root / "data" / "jornadas"), [])

    def test_estado_de_forma_termina_con_el_partido_mas_reciente(self):
        # Equipo A gana en dic-2025 y ago-2026 (25/26) y pierde las dos de 26/27:
        # su ultimo resultado conocido debe ser la derrota de la J2.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            montar_dos_temporadas(root)
            filas = [f for f in mm.iter_closed_matches(root / "data" / "jornadas") if f["local"] == "Equipo A"]
            self.assertEqual([f["resultado"] for f in filas], ["1-0", "1-0", "0-1", "0-1"])

    def test_datos_reales_en_orden_cronologico(self):
        if not (ROOT / "data" / "jornadas").exists():
            self.skipTest("sin data/jornadas")
        filas = mm.iter_closed_matches()
        fechas = [fila["fecha_orden"] for fila in filas]
        self.assertTrue(all(len(f) == 10 and f[4] == "-" for f in fechas))
        self.assertEqual(fechas, sorted(fechas))


class ModeloMetricasDiagnosticoTests(unittest.TestCase):
    """Hallazgos 48 y 247."""

    def test_sin_dependencias_y_con_artefacto_el_motivo_es_la_dependencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artefacto = root / "data" / "modelo_predictivo" / "modelo_calibrado.joblib"
            artefacto.parent.mkdir(parents=True)
            artefacto.write_bytes(b"x")
            with mock.patch.object(mm, "joblib", None), mock.patch.object(mm, "ERROR_DEPENDENCIAS", "ImportError: sklearn"):
                with self.assertRaises(RuntimeError) as ctx:
                    mm.load_trained_model(root)
            self.assertIn("dependencias_no_disponibles", str(ctx.exception))
            self.assertIn("sklearn", str(ctx.exception))

    def test_sin_dependencias_y_sin_artefacto_devuelve_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(mm, "joblib", None):
                self.assertIsNone(mm.load_trained_model(Path(tmp)))

    def test_partidos_de_la_temporada_no_dependen_del_recorte_de_revisiones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            montar_dos_temporadas(root)
            temporada, n = mm.partidos_cerrados_temporada_actual(root / "data" / "jornadas")
            self.assertEqual(temporada, "2026_2027")
            self.assertEqual(n, 28)  # J1 y J2; J28 y J76 son de la 25/26
            metricas = root / "metricas.json"
            revisiones = root / "revisiones.json"
            escribir(metricas, {"version": "1.0"})
            escribir(revisiones, {"revisiones": [
                {"jornada": 2, "signo_real": "1", "probabilidades_usadas": {"1": 60, "X": 25, "2": 15}},
            ]})
            vacio = root / "vacio"
            vacio.mkdir()
            out = mm.enriquecer_metricas_probabilisticas(
                metricas, revisiones, dir_pre_cierre=vacio, dir_jornadas=root / "data" / "jornadas", guardar=False
            )
            self.assertEqual(out["regla_de_potencia"]["partidos_esta_temporada"], 28)
            self.assertEqual(out["regla_de_potencia"]["temporada"], "2026_2027")
            # sin snapshots no hay ningun partido con prediccion del cierre
            self.assertEqual(out["regla_de_potencia"]["partidos_temporada_con_prediccion_del_cierre"], 0)
            self.assertEqual(out["log_score_por_clase"]["ventana"]["partidos"], 1)


class MemoriaAutonomaTests(unittest.TestCase):
    """Hallazgos 14, 15, 33, 35, 79 y 201."""

    def test_normalizar_repara_mojibake(self):
        self.assertEqual(memoria.normalizar(BELGICA_ROTA), "belgica")
        self.assertEqual(memoria.normalizar("Bélgica"), "belgica")

    def test_parse_fecha_no_inventa_el_1_de_enero(self):
        fecha = memoria.parse_fecha("La Quiniela Domingo, 14 de diciembre de 2025")
        self.assertEqual((fecha.year, fecha.month, fecha.day), (2025, 12, 14))
        self.assertIsNone(memoria.parse_fecha("temporada 2025"))

    def test_temporada_de_la_jornada(self):
        dic = {"jornada": 28, "fecha": "La Quiniela Domingo, 14 de diciembre de 2025", "partidos": []}
        self.assertEqual(memoria.temporada_jornada(dic), "2025_2026")
        ago = {"jornada": 76, "fecha": "2026-08-08", "partidos": []}
        self.assertEqual(memoria.temporada_jornada(ago), "2025_2026")
        nueva = {"jornada": 1, "fecha": "2026-08-15", "partidos": []}
        self.assertEqual(memoria.temporada_jornada(nueva), "2026_2027")

    def test_memoria_completa_en_orden_de_fecha_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            montar_dos_temporadas(root)
            for numero, prefijo in ((28, "V"), (76, "V"), (1, ""), (2, "")):
                escribir(root / "data" / "predicciones" / f"jornada_{numero}.json", prediccion(numero, "1", prefijo))
            originales = {n: getattr(memoria, n) for n in (
                "ROOT", "DATA", "JORNADAS", "PREDICCIONES", "SNAPSHOTS", "MEMORIA", "HISTORIAL_PERMANENTE",
                "PERFILES_EQUIPOS", "RENDIMIENTO_JORNADAS", "TEMPORADAS_DETECTADAS", "ESTADO_AUTONOMIA")}
            try:
                estado = memoria.actualizar_memoria_autonoma(root)
            finally:
                for nombre, valor in originales.items():
                    setattr(memoria, nombre, valor)
            mem = root / "data" / "memoria_ia"

            # 79/201: la ultima jornada es la J2 (22/08/2026), no la J76
            self.assertEqual(estado["ultima_jornada_detectada"], 2)
            self.assertEqual(estado["ultima_jornada_cerrada"], 2)
            rendimiento = leer(mem / "rendimiento_jornadas.json")
            self.assertEqual(rendimiento["resumen"]["ultimas_8_jornadas"], [28, 76, 1, 2])

            # 35/79: temporadas bien etiquetadas
            temporadas = leer(mem / "temporadas_detectadas.json")["temporadas"]
            self.assertEqual(temporadas["2025_2026"]["jornadas_cargadas"], [28, 76])
            self.assertEqual(temporadas["2026_2027"]["jornadas_cargadas"], [1, 2])
            self.assertNotIn("2024_2025", temporadas)

            # 14/35: el historial del perfil acaba en lo mas reciente (dos derrotas)
            perfil = leer(mem / "perfiles_equipos.json")["equipos"]["equipo a"]
            self.assertEqual([h["jornada"] for h in perfil["historial"]], [28, 76, 1, 2])
            self.assertEqual(perfil["forma_reciente"]["racha_actual"]["tipo"], "P")
            self.assertEqual(perfil["forma_reciente"]["racha_actual"]["partidos"], 2)

    def test_clave_de_perfil_sin_mojibake(self):
        historial = {"partidos": [{
            "jornada": 66, "temporada": "2025_2026", "fecha": "2026-06-15", "fecha_iso": "2026-06-15", "num": 1,
            "local": BELGICA_ROTA, "visitante": "Egipto", "resultado": "1-0", "signo_real": "1",
        }]}
        perfiles = memoria.construir_perfiles_equipos(historial)["equipos"]
        self.assertIn("belgica", perfiles)
        self.assertNotIn("ba lgica", perfiles)
        self.assertEqual(perfiles["belgica"]["equipo"], "Bélgica")

    def test_la_prediccion_del_cierre_manda_sobre_el_espejo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jornadas = root / "data" / "jornadas"
            escribir(jornadas / "jornada_1.json", {
                "jornada": 1, "fecha": "2026-08-15", "partidos": partidos_jornada("0-1", fecha="2026-08-15"),
            })
            escribir(jornadas / "jornada_2.json", {
                "jornada": 2, "fecha": "2026-08-22", "partidos": partidos_jornada("0-1", fecha="2026-08-22"),
            })
            # espejo reescrito tras el cierre (ya "sabe" que sale 2)
            escribir(root / "data" / "predicciones" / "jornada_1.json", prediccion(1, "2"))
            escribir(root / "data" / "predicciones" / "jornada_2.json", prediccion(2, "2"))
            # lo que se dijo antes del cierre: 1
            escribir(root / "data" / "backtesting" / "pre_cierre" / "jornada_1.json", {
                "jornada": 1, "primer_partido_utc": "2026-08-15T19:00:00Z", "prediccion": prediccion(1, "1"),
            })
            with mock.patch.object(memoria, "JORNADAS", jornadas), \
                    mock.patch.object(memoria, "PREDICCIONES", root / "data" / "predicciones"), \
                    mock.patch.object(memoria, "SNAPSHOTS", root / "data" / "backtesting" / "pre_cierre"):
                preds = memoria.cargar_predicciones()
            self.assertEqual(preds[1]["partidos"][0]["signo_final"], "1")
            self.assertEqual(preds[1]["origen_prediccion_memoria"], "snapshot_pre_cierre")
            # sin snapshot, el espejo sigue valiendo de respaldo
            self.assertEqual(preds[2]["partidos"][0]["signo_final"], "2")
            self.assertEqual(preds[2]["origen_prediccion_memoria"], "espejo_post_cierre")

    def test_snapshot_de_otra_temporada_no_se_usa(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jornadas = root / "data" / "jornadas"
            escribir(jornadas / "jornada_1.json", {
                "jornada": 1, "fecha": "2026-08-15", "partidos": partidos_jornada("0-1", fecha="2026-08-15"),
            })
            escribir(root / "data" / "predicciones" / "jornada_1.json", prediccion(1, "2"))
            # snapshot "jornada 1" de otra temporada: otros equipos y otra fecha
            nombres = ["Alfa", "Bravo", "Charlie", "Delta", "Eco", "Foxtrot", "Golf", "Hotel", "India",
                       "Juliet", "Kilo", "Lima", "Mike", "Noviembre"]
            otra = prediccion(1, "1")
            for fila, nombre in zip(otra["partidos"], nombres):
                fila["local"] = nombre + " Norte"
                fila["visitante"] = nombre + " Sur"
            escribir(root / "data" / "backtesting" / "pre_cierre" / "jornada_1.json", {
                "jornada": 1, "primer_partido_utc": "2025-08-16T19:00:00Z",
                "prediccion": otra,
            })
            with mock.patch.object(memoria, "JORNADAS", jornadas), \
                    mock.patch.object(memoria, "PREDICCIONES", root / "data" / "predicciones"), \
                    mock.patch.object(memoria, "SNAPSHOTS", root / "data" / "backtesting" / "pre_cierre"):
                preds = memoria.cargar_predicciones()
            self.assertEqual(preds[1]["origen_prediccion_memoria"], "espejo_post_cierre")

    # --- segunda pasada: la prediccion tiene que ser del MISMO partido -----

    def _historial(self, root):
        with mock.patch.object(memoria, "JORNADAS", root / "data" / "jornadas"), \
                mock.patch.object(memoria, "PREDICCIONES", root / "data" / "predicciones"), \
                mock.patch.object(memoria, "SNAPSHOTS", root / "data" / "backtesting" / "pre_cierre"):
            return memoria.construir_historial_permanente()

    def _montar_snapshot_con_relleno(self, root, con_espejo):
        jornadas = root / "data" / "jornadas"
        escribir(jornadas / "jornada_1.json", {
            "jornada": 1, "fecha": "2026-08-15", "partidos": partidos_jornada("0-1", fecha="2026-08-15"),
        })
        # snapshot de 14 partidos: el 1 se predijo sin conocer a los equipos
        snap = prediccion(1, "1")
        snap["partidos"][0]["local"] = "Ganador Octavos 5"
        snap["partidos"][0]["visitante"] = "Ganador Octavos 6"
        # y el 2 con un solo equipo de relleno
        snap["partidos"][1]["visitante"] = "3\u00ba Grupo EFGIJ"
        escribir(root / "data" / "backtesting" / "pre_cierre" / "jornada_1.json", {
            "jornada": 1, "primer_partido_utc": "2026-08-15T19:00:00Z", "prediccion": snap,
        })
        if con_espejo:
            escribir(root / "data" / "predicciones" / "jornada_1.json", prediccion(1, "2"))

    def test_partido_de_relleno_del_snapshot_no_se_atribuye_al_partido_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._montar_snapshot_con_relleno(root, con_espejo=False)
            historial = self._historial(root)
        por_num = {p["num"]: p for p in historial["partidos"]}
        # P1 y P2: la prediccion era para un rival desconocido, no cuenta
        for num in (1, 2):
            self.assertFalse(por_num[num]["prediccion_disponible"])
            self.assertEqual(por_num[num]["probabilidades"], {})
            self.assertIsNone(por_num[num]["surprise_score"])
            self.assertFalse(por_num[num]["acierto"])
        # el resto del snapshot sigue valiendo
        self.assertTrue(por_num[3]["prediccion_disponible"])
        resumen = historial["jornadas"]["1"]
        self.assertEqual(resumen["origen_prediccion"], "snapshot_pre_cierre")
        self.assertEqual(resumen["predicciones_descartadas_otro_partido"], [1, 2])
        self.assertEqual(resumen["predicciones_disponibles"], 12)

    def test_partido_de_relleno_cae_al_espejo_si_el_espejo_es_ese_partido(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._montar_snapshot_con_relleno(root, con_espejo=True)
            historial = self._historial(root)
        por_num = {p["num"]: p for p in historial["partidos"]}
        # P1: el espejo si lleva 'Equipo A - Rival' (y dice 2)
        self.assertTrue(por_num[1]["prediccion_disponible"])
        self.assertEqual(por_num[1]["signo_final"], "2")
        resumen = historial["jornadas"]["1"]
        self.assertEqual(resumen["predicciones_de_respaldo_espejo"], [1, 2])
        self.assertEqual(resumen["predicciones_descartadas_otro_partido"], [])

    def test_prediccion_es_del_partido(self):
        real = {"local": "vaasa PS", "visitante": "SJK"}
        # alias que mismo_equipo no reconoce: con un equipo basta
        self.assertTrue(memoria.prediccion_es_del_partido({"local": "VPS", "visitante": "SJK"}, real))
        # ningun equipo coincide: es otro partido
        self.assertFalse(memoria.prediccion_es_del_partido({"local": "Malmo", "visitante": "Elfsborg"}, real))
        # un equipo de relleno invalida aunque el otro coincida
        self.assertFalse(memoria.prediccion_es_del_partido(
            {"local": "Suiza", "visitante": "3\u00ba Grupo EFGIJ"}, {"local": "Suiza", "visitante": "Argelia"}))
        self.assertFalse(memoria.prediccion_es_del_partido(
            {"local": "F1 Hypermotion", "visitante": "F2 Hypermotion"}, {"local": "Malaga CF", "visitante": "UD Almeria"}))
        # prediccion sin nombres: no hay nada que comparar
        self.assertTrue(memoria.prediccion_es_del_partido({"probabilidades": {"1": 50}}, real))
        self.assertFalse(memoria.prediccion_es_del_partido({}, real))
        # equipos reales que no son relleno
        for nombre in ("F91 Dudelange", "Grupo Desportivo Chaves", "1860 Munich", "Schalke 04"):
            self.assertFalse(memoria.es_equipo_de_relleno(nombre), nombre)

    def test_espejo_de_otra_temporada_no_se_usa(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jornadas = root / "data" / "jornadas"
            # J28 nueva (26/27), aun sin snapshot ni espejo propio
            escribir(jornadas / "jornada_28.json", {
                "jornada": 28, "fecha": "2026-12-06", "partidos": partidos_jornada("0-1", fecha="2026-12-06"),
            })
            # el espejo jornada_28 que queda en el repo es el de la 25/26
            escribir(root / "data" / "predicciones" / "jornada_28.json",
                     prediccion(28, "1", prefijo="V", local_1="Otro Equipo"))
            with mock.patch.object(memoria, "JORNADAS", jornadas), \
                    mock.patch.object(memoria, "PREDICCIONES", root / "data" / "predicciones"), \
                    mock.patch.object(memoria, "SNAPSHOTS", root / "data" / "backtesting" / "pre_cierre"):
                preds = memoria.cargar_predicciones()
                historial = memoria.construir_historial_permanente()
        self.assertNotIn(28, preds)
        self.assertIsNone(historial["jornadas"]["28"]["origen_prediccion"])
        self.assertEqual(historial["jornadas"]["28"]["predicciones_disponibles"], 0)


class ConstruirMemoriaOrdenTests(unittest.TestCase):
    """Hallazgo 18 (y 225 en la parte de construir_memoria_ia)."""

    CALENDARIO = {
        "temporada": "2026/2027",
        "jornadas": [
            # J1: aplazado, se juega el 21/10 (despues de la J3)
            {"jornada": 1, "partidos": [{"local": "Levante UD", "visitante": "Athletic Club", "resultado": "2-0", "fecha": "2026-10-21"}]},
            {"jornada": 2, "partidos": [{"local": "Levante UD", "visitante": "Getafe CF", "resultado": "0-1", "fecha": "2026-09-01"}]},
            {"jornada": 3, "partidos": [{"local": "Sevilla FC", "visitante": "Levante UD", "resultado": "1-0", "fecha": "2026-09-08"}]},
            {"jornada": 4, "partidos": [{"local": "Levante UD", "visitante": "Elche CF", "resultado": None, "fecha": "2026-12-01"}]},
        ],
    }

    def test_el_aplazado_cuenta_cuando_se_jugo(self):
        jugados, pendientes = cmi.partidos_jugados_cronologicos(self.CALENDARIO)
        self.assertEqual([j.get("jornada") for j, _ in jugados], [2, 3, 1])
        self.assertEqual(pendientes, 1)

    def test_jornada_intermedia_sin_fechas_no_va_la_primera(self):
        calendario = {
            "temporada": "2026/2027",
            "jornadas": [
                # J1 con un aplazado que se juega en octubre
                {"jornada": 1, "partidos": [
                    {"local": "Levante UD", "visitante": "Getafe CF", "resultado": "1-0", "fecha": "2026-08-15"},
                    {"local": "Sevilla FC", "visitante": "Elche CF", "resultado": "1-0", "fecha": "2026-08-16"},
                    {"local": "Valencia CF", "visitante": "Athletic Club", "resultado": "1-0", "fecha": "2026-10-21"},
                ]},
                # J2: la fuente no trae fechas (o trae '22 de Agosto' sin anio)
                {"jornada": 2, "partidos": [
                    {"local": "Elche CF", "visitante": "Levante UD", "resultado": "1-0", "fecha": None},
                    {"local": "Getafe CF", "visitante": "Sevilla FC", "resultado": "1-0", "fecha": "22 de Agosto"},
                ]},
                {"jornada": 3, "partidos": [
                    {"local": "Levante UD", "visitante": "Sevilla FC", "resultado": "0-1", "fecha": "2026-08-29"},
                ]},
            ],
        }
        jugados, _ = cmi.partidos_jugados_cronologicos(calendario)
        orden = [(j.get("jornada"), p.get("local")) for j, p in jugados]
        # J2 detras de TODO el fin de semana de la J1, delante de la J3 y del
        # aplazado de octubre (no hereda el 21/10)
        self.assertEqual(orden, [
            (1, "Levante UD"), (1, "Sevilla FC"), (2, "Elche CF"), (2, "Getafe CF"),
            (3, "Levante UD"), (1, "Valencia CF"),
        ])

    def test_primera_jornada_sin_fechas_sigue_la_primera(self):
        calendario = {"jornadas": [
            {"jornada": 1, "partidos": [{"local": "A", "visitante": "B", "resultado": "1-0"}]},
            {"jornada": 2, "partidos": [{"local": "B", "visitante": "A", "resultado": "1-0", "fecha": "2026-08-22"}]},
        ]}
        jugados, _ = cmi.partidos_jugados_cronologicos(calendario)
        self.assertEqual([j.get("jornada") for j, _ in jugados], [1, 2])

    def test_racha_de_analizar_liga_por_fecha_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calendario_primera.json"
            escribir(path, self.CALENDARIO)
            with mock.patch.object(cmi, "partidos_pendientes_en_quiniela", return_value=set()):
                liga = cmi.analizar_liga("primera", path)
            equipos = liga["equipos"]
            equipos = equipos.values() if isinstance(equipos, dict) else equipos
            levante = next(e for e in equipos if e["equipo"] == "Levante UD")
            # por numero de jornada salia G-P-P (2 sin ganar); por fecha es P-P-G
            self.assertEqual(levante["racha_actual"]["sin_ganar"], 0)
            self.assertEqual(levante["racha_actual"]["victorias"], 1)
            self.assertEqual([u["r"] for u in levante["ultimos"]], ["P", "P", "G"])

    def test_no_se_escribe_el_resumen_de_otra_temporada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calendario_primera.json"
            escribir(path, self.CALENDARIO)
            calendarios = {"primera": path}
            self.assertTrue(cmi.calendarios_son_de_temporada("2026/2027", calendarios))
            self.assertFalse(cmi.calendarios_son_de_temporada("2025/2026", calendarios))


class SincronizarDinamicasTests(unittest.TestCase):
    """Hallazgos 18, 187 y 225."""

    def _montar(self, root, temporada_resumen="2026/2027"):
        racha_mala = {"victorias": 0, "empates": 0, "derrotas": 1, "sin_ganar": 7, "sin_perder": 0}
        racha_buena = {"victorias": 0, "empates": 2, "derrotas": 0, "sin_ganar": 4, "sin_perder": 2}
        raiz = root / "clasificaciones.json"
        oficial = root / "data" / "clasificaciones_oficiales.json"
        escribir(raiz, {"temporada_detectada": "2026/2027", "primera": [{"equipo": "Levante UD", "pts": 9, "racha_actual": racha_mala}], "segunda": []})
        escribir(oficial, {"temporada_detectada": "2026/2027", "primera": [{"equipo": "Levante UD", "pts": 9, "racha_actual": racha_buena}], "segunda": []})
        memoria_ok = {"temporada": temporada_resumen, "ligas": {"primera": {"equipos": [{"equipo": "Levante UD", "pts": 0}]}, "segunda": {"equipos": []}}}
        vieja = {"temporada": "2025/2026", "ligas": {"primera": {"equipos": [{"equipo": "Levante UD", "pts": 42}]}, "segunda": {"equipos": []}}}
        escribir(root / "data" / "memoria_ia" / "aprendizaje_global.json", memoria_ok)
        escribir(root / "data" / "temporadas" / "2026_2027" / "resumen_temporada.json", memoria_ok)
        escribir(root / "data" / "temporadas" / "2025_2026" / "resumen_temporada.json", vieja)
        return mock.patch.multiple(
            sdm,
            CLASIFICACIONES=[raiz, oficial],
            APRENDIZAJE_GLOBAL=root / "data" / "memoria_ia" / "aprendizaje_global.json",
            TEMPORADAS=root / "data" / "temporadas",
        ), racha_buena

    def test_manda_la_clasificacion_oficial_recalculada_por_fecha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parche, racha_buena = self._montar(root)
            with parche:
                self.assertEqual(sdm.CLASIFICACIONES[-1].name, "clasificaciones_oficiales.json")
                sdm.main()
            global_ = leer(root / "data" / "memoria_ia" / "aprendizaje_global.json")
            self.assertEqual(global_["ligas"]["primera"]["equipos"][0]["racha_actual"], racha_buena)

    def test_el_orden_por_defecto_deja_la_oficial_la_ultima(self):
        self.assertEqual(sdm.CLASIFICACIONES[-1].name, "clasificaciones_oficiales.json")

    def test_no_toca_la_carpeta_de_la_temporada_pasada(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parche, racha_buena = self._montar(root)
            vieja = root / "data" / "temporadas" / "2025_2026" / "resumen_temporada.json"
            antes = vieja.read_text(encoding="utf-8")
            with parche:
                rutas = sdm.memorias_a_sincronizar()
                sdm.main()
            self.assertNotIn(vieja, rutas)
            self.assertEqual(vieja.read_text(encoding="utf-8"), antes)
            actual = leer(root / "data" / "temporadas" / "2026_2027" / "resumen_temporada.json")
            self.assertEqual(actual["ligas"]["primera"]["equipos"][0]["racha_actual"], racha_buena)

    def test_resumen_que_declara_otra_temporada_no_se_sincroniza(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parche, _ = self._montar(root, temporada_resumen="2025/2026")
            with parche:
                rutas = sdm.memorias_a_sincronizar()
            self.assertEqual([r.name for r in rutas], ["aprendizaje_global.json"])


if __name__ == "__main__":
    unittest.main()
