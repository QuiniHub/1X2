# -*- coding: utf-8 -*-
"""Tests de cronologia_jornadas: fixtures temporales y datos reales del repo."""

import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import cronologia_jornadas as cj  # noqa: E402


EQUIPOS_A = [("Equipo%02d Local" % i, "Rival%02d Visitante" % i) for i in range(1, 15)]
EQUIPOS_B = [("Otro%02d Casa" % i, "Distinto%02d Fuera" % i) for i in range(1, 15)]


def hacer_jornada(numero, fecha_cabecera=None, fechas_partidos=None, signos="1X21X21X21X21X",
                  equipos=None, estado=None):
    equipos = equipos or EQUIPOS_A
    partidos = []
    for i in range(14):
        p = {"num": i + 1, "local": equipos[i][0], "visitante": equipos[i][1]}
        if fechas_partidos is not None:
            p["fecha"] = fechas_partidos[i] if isinstance(fechas_partidos, list) else fechas_partidos
        p["signo_oficial"] = signos[i] if signos else "Pendiente"
        partidos.append(p)
    datos = {"jornada": numero, "partidos": partidos}
    if fecha_cabecera is not None:
        datos["fecha"] = fecha_cabecera
    if estado is not None:
        datos["estado"] = estado
    return datos


def escribir(directorio, nombre, datos):
    ruta = Path(directorio) / nombre
    with open(ruta, "w", encoding="utf-8") as fh:
        if isinstance(datos, str):
            fh.write(datos)
        else:
            json.dump(datos, fh, ensure_ascii=False)
    return ruta


class ParsearFechaTest(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(cj.parsear_fecha("2026-11-24"), date(2026, 11, 24))
        self.assertEqual(cj.parsear_fecha("2026-11-24T20:00:00+00:00"), date(2026, 11, 24))
        self.assertEqual(cj.parsear_fecha("2026-11-24 21:00"), date(2026, 11, 24))
        self.assertEqual(cj.parsear_fecha("  2026-1-5  "), date(2026, 1, 5))

    def test_barras(self):
        self.assertEqual(cj.parsear_fecha("10/05/2026"), date(2026, 5, 10))
        self.assertEqual(cj.parsear_fecha("1/5/2026,"), date(2026, 5, 1))
        self.assertEqual(cj.parsear_fecha("10-05-2026"), date(2026, 5, 10))
        self.assertEqual(cj.parsear_fecha("10/05/26"), date(2026, 5, 10))
        self.assertIsNone(cj.parsear_fecha("10/05"))
        self.assertEqual(cj.parsear_fecha("10/05", anio_por_defecto=2026), date(2026, 5, 10))

    def test_texto_largo(self):
        self.assertEqual(
            cj.parsear_fecha("La Quiniela Domingo, 14 de diciembre de 2025"), date(2025, 12, 14))
        self.assertEqual(cj.parsear_fecha("13 de Mayo de 2026"), date(2026, 5, 13))
        self.assertEqual(cj.parsear_fecha("Domingo, 6 de septiembre de 2026"), date(2026, 9, 6))
        self.assertEqual(cj.parsear_fecha("Sábado, 20 de junio de 2026"), date(2026, 6, 20))

    def test_dia_de_la_semana_no_es_mes(self):
        # 'Martes' empieza como 'marzo' y 'Miercoles' no debe confundir.
        self.assertEqual(cj.parsear_fecha("Martes, 3 de noviembre de 2026"), date(2026, 11, 3))
        self.assertEqual(cj.parsear_fecha("Martes 3 mar 2026"), date(2026, 3, 3))
        self.assertEqual(
            cj.parsear_fecha("Miércoles, 25 de noviembre de 2026"), date(2026, 11, 25))

    def test_sin_anio(self):
        self.assertIsNone(cj.parsear_fecha("13 de Mayo"))
        self.assertEqual(cj.parsear_fecha("13 de Mayo", anio_por_defecto=2026), date(2026, 5, 13))
        # Si el texto trae anio, manda el del texto.
        self.assertEqual(
            cj.parsear_fecha("13 de Mayo de 2026", anio_por_defecto=2030), date(2026, 5, 13))

    def test_mojibake(self):
        self.assertEqual(
            cj.parsear_fecha("MiÃ©rcoles, 25 de noviembre de 2026"), date(2026, 11, 25))
        self.assertEqual(
            cj.parsear_fecha("Mi�rcoles, 25 de noviembre de 2026"), date(2026, 11, 25))
        self.assertEqual(
            cj.parsear_fecha("SÃ¡bado, 20 de junio de 2026"), date(2026, 6, 20))
        self.assertEqual(cj.reparar_mojibake("MiÃ©rcoles"), "Miércoles")
        self.assertEqual(cj.reparar_mojibake("Miércoles"), "Miércoles")

    def test_objetos_y_basura(self):
        self.assertEqual(cj.parsear_fecha(date(2026, 1, 2)), date(2026, 1, 2))
        self.assertEqual(cj.parsear_fecha(datetime(2026, 1, 2, 23, 59)), date(2026, 1, 2))
        for malo in (None, "", "   ", "hola", "Pendiente", 20261124, "31/02/2026",
                     "2026-13-40", "32 de enero de 2026", [], {}):
            self.assertIsNone(cj.parsear_fecha(malo), malo)


class FechaRealJornadaTest(unittest.TestCase):
    def test_primer_partido_es_el_mas_temprano(self):
        fechas = ["2026-12-02"] + ["2026-12-01"] * 5 + ["2026-12-03"] * 8
        datos = hacer_jornada(26, "Miércoles, 2 de diciembre de 2026", fechas)
        self.assertEqual(cj.fecha_real_jornada(datos), date(2026, 12, 1))
        self.assertEqual(cj.fecha_fin_jornada(datos), date(2026, 12, 3))

    def test_sin_fechas_de_partido_usa_cabecera(self):
        datos = hacer_jornada(28, "La Quiniela Domingo, 14 de diciembre de 2025")
        self.assertEqual(cj.fecha_real_jornada(datos), date(2025, 12, 14))
        datos = hacer_jornada(28, "La Quiniela Domingo, 14 de diciembre de 2025", [None] * 14)
        self.assertEqual(cj.fecha_real_jornada(datos), date(2025, 12, 14))
        self.assertEqual(cj.fecha_fin_jornada(datos), date(2025, 12, 14))

    def test_solo_partidos_sin_cabecera(self):
        datos = hacer_jornada(5, None, ["basura", "2026-09-09"] + ["2026-09-08"] * 12)
        self.assertEqual(cj.fecha_real_jornada(datos), date(2026, 9, 8))

    def test_partido_sin_anio_hereda_el_de_la_cabecera(self):
        datos = hacer_jornada(62, "13 de Mayo de 2026", "12 de Mayo")
        self.assertEqual(cj.fecha_real_jornada(datos), date(2026, 5, 12))

    def test_errata_lejana_se_ignora(self):
        fechas = ["2025-11-24"] + ["2026-11-24"] * 13
        datos = hacer_jornada(24, "Miércoles, 25 de noviembre de 2026", fechas)
        self.assertEqual(cj.fecha_real_jornada(datos), date(2026, 11, 24))

    def test_sin_nada(self):
        self.assertIsNone(cj.fecha_real_jornada({}))
        self.assertIsNone(cj.fecha_real_jornada(None))
        self.assertIsNone(cj.fecha_real_jornada({"fecha": "Pendiente", "partidos": "x"}))


class TemporadaTest(unittest.TestCase):
    def test_meses_claros(self):
        self.assertEqual(cj.temporada_de_fecha(date(2026, 11, 24)), "2026_2027")
        self.assertEqual(cj.temporada_de_fecha("2025-12-14"), "2025_2026")
        self.assertEqual(cj.temporada_de_fecha("2026-05-10"), "2025_2026")
        self.assertEqual(cj.temporada_de_fecha("2027-01-03"), "2026_2027")
        self.assertEqual(cj.temporada_de_fecha("2026-09-01", 60), "2026_2027")
        self.assertEqual(cj.temporada_de_fecha("2026-06-07", 2), "2025_2026")

    def test_agosto_sin_numero_corta_a_mediados(self):
        self.assertEqual(cj.temporada_de_fecha("2026-08-07"), "2025_2026")
        self.assertEqual(cj.temporada_de_fecha("2026-08-11"), "2025_2026")
        self.assertEqual(cj.temporada_de_fecha("2026-08-12"), "2026_2027")
        self.assertEqual(cj.temporada_de_fecha("2026-08-15"), "2026_2027")
        self.assertEqual(cj.temporada_de_fecha("2026-07-24"), "2025_2026")

    def test_agosto_con_numero_desambigua(self):
        # J76 de 25/26 (07/08/2026) y J1 de 26/27 (15/08/2026).
        self.assertEqual(cj.temporada_de_fecha("2026-08-07", 76), "2025_2026")
        self.assertEqual(cj.temporada_de_fecha("2026-08-15", 1), "2026_2027")
        # Una J1 adelantada a primeros de agosto sigue siendo temporada nueva.
        self.assertEqual(cj.temporada_de_fecha("2027-08-08", 1), "2027_2028")
        self.assertEqual(cj.temporada_de_fecha("2027-07-31", 1), "2027_2028")
        # Una jornada alta retrasada a finales de agosto sigue siendo la vieja.
        self.assertEqual(cj.temporada_de_fecha("2026-08-20", 77), "2025_2026")
        # Numero intermedio o no numerico: decide la fecha.
        self.assertEqual(cj.temporada_de_fecha("2026-08-20", 25), "2026_2027")
        self.assertEqual(cj.temporada_de_fecha("2026-08-20", "x"), "2026_2027")

    def test_sin_fecha(self):
        self.assertIsNone(cj.temporada_de_fecha(None))
        self.assertIsNone(cj.temporada_de_fecha("hola", 3))

    def test_clave_jornada(self):
        self.assertEqual(cj.clave_jornada(24, "2026-11-24"), ("2026_2027", 24))
        self.assertEqual(cj.clave_jornada("76", date(2026, 8, 7)), ("2025_2026", 76))
        self.assertNotEqual(cj.clave_jornada(1, "2025-08-16"), cj.clave_jornada(1, "2026-08-15"))
        self.assertEqual(cj.clave_jornada(3, None), (None, 3))


class CerradaTest(unittest.TestCase):
    def test_catorce_signos(self):
        self.assertTrue(cj.jornada_cerrada(hacer_jornada(1)))
        self.assertTrue(cj.jornada_cerrada(hacer_jornada(1, signos="1x21x21x21x21x")))

    def test_pendientes_o_incompleta(self):
        self.assertFalse(cj.jornada_cerrada(hacer_jornada(1, signos=None)))
        datos = hacer_jornada(1)
        datos["partidos"][13]["signo_oficial"] = "Pendiente"
        self.assertFalse(cj.jornada_cerrada(datos))
        datos = hacer_jornada(1)
        datos["partidos"][5]["signo_oficial"] = None
        self.assertFalse(cj.jornada_cerrada(datos))
        datos = hacer_jornada(1)
        del datos["partidos"][13]
        self.assertFalse(cj.jornada_cerrada(datos))
        self.assertFalse(cj.jornada_cerrada({}))

    def test_el_pleno15_no_cuenta(self):
        datos = hacer_jornada(1)
        datos["partidos"].append({"num": 15, "local": "A", "visitante": "B",
                                  "signo_oficial": "Pendiente"})
        self.assertTrue(cj.jornada_cerrada(datos))

    def test_estado_cerrada_sin_signos_no_basta(self):
        self.assertFalse(cj.jornada_cerrada(hacer_jornada(1, signos=None, estado="cerrada")))


class IndiceFixturesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # Temporada vieja: numeros altos, fechas anteriores.
        escribir(self.dir, "jornada_75.json",
                 hacer_jornada(75, "Domingo, 2 de agosto de 2026", "2026-08-01", equipos=EQUIPOS_B))
        escribir(self.dir, "jornada_76.json",
                 hacer_jornada(76, "Domingo, 9 de agosto de 2026", "2026-08-07", equipos=EQUIPOS_B))
        escribir(self.dir, "jornada_60.json",
                 hacer_jornada(60, "La Quiniela Domingo, 3 de mayo de 2026", equipos=EQUIPOS_B))
        # Temporada nueva: numeros bajos, fechas posteriores.
        escribir(self.dir, "jornada_1.json",
                 hacer_jornada(1, "Domingo, 16 de agosto de 2026", "2026-08-15", estado="cerrada"))
        escribir(self.dir, "jornada_2.json",
                 hacer_jornada(2, "Domingo, 23 de agosto de 2026", "2026-08-22", estado="cerrada"))
        escribir(self.dir, "jornada_3.json",
                 hacer_jornada(3, "Domingo, 30 de agosto de 2026",
                               ["2026-08-29"] * 7 + ["2026-08-31"] * 7, signos=None,
                               estado="abierta"))
        escribir(self.dir, "jornada_4.json",
                 hacer_jornada(4, "Domingo, 6 de septiembre de 2026", "2026-09-05", signos=None))
        # Sin fecha (dos, para comprobar el orden determinista) y ruido.
        escribir(self.dir, "jornada_90.json", hacer_jornada(90))
        escribir(self.dir, "jornada_9.json", hacer_jornada(9, "Pendiente", signos=None))
        escribir(self.dir, "jornada_50.json", "{esto no es json")
        escribir(self.dir, "jornada_51.json", [1, 2, 3])
        escribir(self.dir, "detalles_j1.json", {"jornada": 1})
        escribir(self.dir, "jornada_1.json.bak", {"jornada": 1})

    def tearDown(self):
        self.tmp.cleanup()

    def test_orden_cronologico_y_sin_fecha_al_final(self):
        idx = cj.indice_jornadas(self.dir)
        self.assertEqual([j["numero"] for j in idx], [60, 75, 76, 1, 2, 3, 4, 9, 90])
        self.assertEqual(idx, cj.indice_jornadas(self.dir))

    def test_claves_del_indice(self):
        idx = {j["numero"]: j for j in cj.indice_jornadas(self.dir)}
        j = idx[76]
        for clave in ("numero", "fecha", "temporada", "cerrada", "ruta"):
            self.assertIn(clave, j)
        self.assertEqual(j["fecha"], date(2026, 8, 7))
        self.assertEqual(j["temporada"], "2025_2026")
        self.assertTrue(j["cerrada"])
        self.assertEqual(Path(j["ruta"]).name, "jornada_76.json")
        self.assertEqual(idx[1]["temporada"], "2026_2027")
        self.assertEqual(idx[60]["fecha"], date(2026, 5, 3))
        self.assertEqual(idx[3]["fecha_fin"], date(2026, 8, 31))
        self.assertFalse(idx[3]["cerrada"])
        self.assertIsNone(idx[90]["fecha"])
        self.assertIsNone(idx[90]["temporada"])

    def test_filtros(self):
        self.assertEqual(
            [j["numero"] for j in cj.jornadas_cronologicas(dir_jornadas=self.dir,
                                                           temporada="2026_2027")],
            [1, 2, 3, 4])
        for etiqueta in ("2025_2026", "2025/2026", "2025-2026", "2025/26"):
            self.assertEqual(
                [j["numero"] for j in cj.jornadas_cronologicas(True, etiqueta, self.dir)],
                [60, 75, 76], etiqueta)
        self.assertEqual(
            [j["numero"] for j in cj.jornadas_cronologicas(solo_cerradas=True,
                                                           dir_jornadas=self.dir)],
            [60, 75, 76, 1, 2, 90])
        self.assertEqual(cj.jornadas_cronologicas(temporada="2030_2031", dir_jornadas=self.dir), [])

    def test_ultima_cerrada_es_por_fecha_no_por_numero(self):
        # Por numero saldria la 90 (sin fecha) o la 76; la real es la J2.
        self.assertEqual(cj.ultima_jornada_cerrada(dir_jornadas=self.dir)["numero"], 2)
        self.assertEqual(cj.ultima_jornada_cerrada("2026-08-10", dir_jornadas=self.dir)["numero"], 76)
        self.assertEqual(
            cj.ultima_jornada_cerrada(date(2026, 8, 15), dir_jornadas=self.dir)["numero"], 1)
        self.assertEqual(
            cj.ultima_jornada_cerrada(temporada="2025_2026", dir_jornadas=self.dir)["numero"], 76)
        self.assertIsNone(cj.ultima_jornada_cerrada("2020-01-01", dir_jornadas=self.dir))

    def test_en_curso_o_proxima(self):
        self.assertEqual(cj.jornada_en_curso_o_proxima(dir_jornadas=self.dir)["numero"], 3)
        # Antes de empezar, en juego y recien acabada sin cerrar: sigue siendo la J3.
        for hoy in ("2026-08-25", "2026-08-30", "2026-09-02"):
            self.assertEqual(
                cj.jornada_en_curso_o_proxima(hoy, dir_jornadas=self.dir)["numero"], 3, hoy)
        # Pasados mas de 3 dias del ultimo partido se salta a la siguiente.
        self.assertEqual(
            cj.jornada_en_curso_o_proxima("2026-09-04", dir_jornadas=self.dir)["numero"], 4)
        self.assertIsNone(cj.jornada_en_curso_o_proxima("2027-01-01", dir_jornadas=self.dir))
        self.assertIsNone(
            cj.jornada_en_curso_o_proxima(temporada="2025_2026", dir_jornadas=self.dir))

    def test_abierta_vieja_no_gana_sin_hoy(self):
        # Un resto sin cerrar de la temporada anterior no es "la proxima".
        escribir(self.dir, "jornada_70.json",
                 hacer_jornada(70, "Domingo, 28 de junio de 2026", "2026-06-26", signos=None,
                               equipos=EQUIPOS_B))
        self.assertEqual(cj.jornada_en_curso_o_proxima(dir_jornadas=self.dir)["numero"], 3)
        self.assertEqual(
            cj.jornada_en_curso_o_proxima("2026-08-28", dir_jornadas=self.dir)["numero"], 3)

    def test_directorio_inexistente_o_vacio(self):
        self.assertEqual(cj.indice_jornadas(self.dir / "no_existe"), [])
        self.assertIsNone(cj.ultima_jornada_cerrada(dir_jornadas=self.dir / "no_existe"))
        self.assertIsNone(cj.jornada_en_curso_o_proxima(dir_jornadas=self.dir / "no_existe"))

    def test_cargar_jornada(self):
        self.assertEqual(cj.cargar_jornada(76, self.dir)["jornada"], 76)
        self.assertEqual(cj.cargar_jornada("76", self.dir)["jornada"], 76)
        self.assertIsNone(cj.cargar_jornada(50, self.dir))
        self.assertIsNone(cj.cargar_jornada(51, self.dir))
        self.assertIsNone(cj.cargar_jornada(999, self.dir))

    def test_no_escribe_nada(self):
        antes = sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in self.dir.iterdir())
        cj.indice_jornadas(self.dir)
        cj.ultima_jornada_cerrada(dir_jornadas=self.dir)
        cj.jornada_en_curso_o_proxima("2026-08-30", dir_jornadas=self.dir)
        cj.prediccion_del_cierre(1, self.dir, self.dir)
        despues = sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in self.dir.iterdir())
        self.assertEqual(antes, despues)


class EquiposTest(unittest.TestCase):
    def test_normalizar(self):
        self.assertEqual(cj.normalizar_equipo("RC Celta de Vigo"), "celta vigo")
        self.assertEqual(cj.normalizar_equipo("Cádiz CF"), "cadiz")
        self.assertEqual(cj.normalizar_equipo("NÃ¡poles"), "napoles")
        self.assertEqual(cj.normalizar_equipo(None), "")

    def test_mismo_equipo(self):
        iguales = [
            ("B. Dortmund", "Borussia Dortmund"),
            ("Man. City", "Manchester City"),
            ("At. Madrid (F)", "Atlético de Madrid (F)"),
            ("Chelsea W", "Chelsea (F)"),
            ("Edf Logroño", "Logroño (F)"),
            ("Nápoles", "Napoles"),
            ("Real Sociedad de Futbol", "Real Sociedad"),
            ("CD Castellon", "Castellón"),
        ]
        for a, b in iguales:
            self.assertTrue(cj.mismo_equipo(a, b), (a, b))
            self.assertTrue(cj.mismo_equipo(b, a), (b, a))
        distintos = [
            ("Real Madrid", "Atletico de Madrid"),
            ("Real Madrid", "Real Sociedad"),
            ("Betis", "B."),
            ("Arsenal", "Feyenoord"),
            ("Valencia", ""),
            ("Valencia", None),
        ]
        for a, b in distintos:
            self.assertFalse(cj.mismo_equipo(a, b), (a, b))

    def test_misma_jornada(self):
        a = hacer_jornada(24)
        b = hacer_jornada(24, signos=None)
        self.assertTrue(cj.misma_jornada(a, b))
        self.assertTrue(cj.misma_jornada(a["partidos"], b))
        self.assertFalse(cj.misma_jornada(a, hacer_jornada(24, equipos=EQUIPOS_B)))

    def test_misma_jornada_tolera_orden_y_nombres(self):
        a = hacer_jornada(24)
        b = hacer_jornada(24)
        b["partidos"].reverse()
        b["partidos"][0]["local"] = b["partidos"][0]["local"].upper() + " CF"
        self.assertTrue(cj.misma_jornada(a, b))
        # Cuatro partidos cambiados por la LAE: sigue siendo la misma.
        c = hacer_jornada(24, equipos=EQUIPOS_A[:10] + EQUIPOS_B[10:])
        self.assertTrue(cj.misma_jornada(a, c))
        # Solo seis en comun: no.
        d = hacer_jornada(24, equipos=EQUIPOS_A[:6] + EQUIPOS_B[6:])
        self.assertFalse(cj.misma_jornada(a, d))

    def test_local_y_visitante_cruzados_no_cuentan(self):
        a = hacer_jornada(24)
        b = hacer_jornada(24, equipos=[(v, l) for l, v in EQUIPOS_A])
        self.assertFalse(cj.misma_jornada(a, b))

    def test_sin_equipos(self):
        self.assertFalse(cj.misma_jornada({}, hacer_jornada(1)))
        self.assertFalse(cj.misma_jornada(None, None))
        self.assertFalse(cj.misma_jornada({"partidos": [{"num": 1}]}, hacer_jornada(1)))
        self.assertEqual(cj.coincidencia_equipos({}, {}), (0, 0))


class PrediccionDelCierreFixturesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jor = Path(self.tmp.name) / "jornadas"
        self.snap = Path(self.tmp.name) / "pre_cierre"
        self.jor.mkdir()
        self.snap.mkdir()
        escribir(self.jor, "jornada_24.json",
                 hacer_jornada(24, "Miércoles, 25 de noviembre de 2026", "2026-11-24"))

    def tearDown(self):
        self.tmp.cleanup()

    def _snapshot(self, numero=24, equipos=None, primer=None, jornada=24, pred_extra=None):
        pred = hacer_jornada(jornada, signos=None, equipos=equipos)
        pred["marca"] = "foto"
        if pred_extra:
            pred.update(pred_extra)
        snap = {"tipo": "prediccion_pre_cierre", "jornada": jornada, "prediccion": pred}
        if primer:
            snap["primer_partido_utc"] = primer
        escribir(self.snap, "jornada_%d.json" % numero, snap)

    def _pred(self, numero=24):
        return cj.prediccion_del_cierre(numero, self.snap, self.jor)

    def test_mismos_equipos(self):
        self._snapshot()
        pred = self._pred()
        self.assertEqual(pred["marca"], "foto")
        self.assertEqual(cj.snapshot_del_cierre(24, self.snap, self.jor)["prediccion"], pred)
        self.assertEqual(self._pred("24")["marca"], "foto")

    def test_no_existe(self):
        self.assertIsNone(self._pred())
        self.assertIsNone(self._pred(99))

    def test_snapshot_de_otra_temporada(self):
        # Misma J24 pero de la temporada anterior: otros equipos, otra fecha.
        self._snapshot(equipos=EQUIPOS_B, primer="2025-11-25T20:00:00+00:00")
        self.assertIsNone(self._pred())
        self._snapshot(equipos=EQUIPOS_B)
        self.assertIsNone(self._pred())

    def test_equipos_renombrados_pero_misma_fecha(self):
        self._snapshot(equipos=EQUIPOS_B, primer="2026-11-24T20:00:00+00:00")
        self.assertEqual(self._pred()["marca"], "foto")
        # Partido de madrugada UTC: un dia de diferencia sigue valiendo.
        self._snapshot(equipos=EQUIPOS_B, primer="2026-11-25T00:30:00+00:00")
        self.assertEqual(self._pred()["marca"], "foto")
        self._snapshot(equipos=EQUIPOS_B, primer="2026-11-28T13:00:00+00:00")
        self.assertIsNone(self._pred())

    def test_numero_declarado_distinto(self):
        self._snapshot(numero=24, jornada=23)
        self.assertIsNone(self._pred())

    def test_sin_fichero_de_jornada_no_se_puede_comprobar(self):
        self._snapshot(numero=30, jornada=30)
        self.assertIsNone(self._pred(30))

    def test_snapshot_roto_o_sin_prediccion(self):
        escribir(self.snap, "jornada_24.json", "{roto")
        self.assertIsNone(self._pred())
        escribir(self.snap, "jornada_24.json", {"jornada": 24, "prediccion": None})
        self.assertIsNone(self._pred())
        escribir(self.snap, "jornada_24.json", [1])
        self.assertIsNone(self._pred())


class DatosRealesTest(unittest.TestCase):
    """Comprobaciones contra data/ tal como esta en el repo.

    El pipeline ira pisando jornada_N.json cuando la 26/27 llegue a J28 y
    cuando empiece la 27/28. Por eso cada comprobacion con numero fijo se
    ancla tambien a la FECHA conocida de esa jornada (ANCLAS): si el fichero
    ya es de otra temporada, la comprobacion pasa a ser la de su nueva fecha.
    """

    CORTE_2026 = date(2026, 8, 12)
    # Fechas reales conocidas el 27/11/2026 (primer partido).
    ANCLAS = {
        28: date(2025, 12, 14), 60: date(2026, 5, 3), 61: date(2026, 5, 10),
        62: date(2026, 5, 13), 64: date(2026, 5, 23), 74: date(2026, 7, 24),
        75: date(2026, 8, 1), 76: date(2026, 8, 7), 1: date(2026, 8, 15),
        6: date(2026, 9, 11), 24: date(2026, 11, 24),
    }

    @classmethod
    def setUpClass(cls):
        cls.idx = cj.indice_jornadas()
        cls.por_numero = {j["numero"]: j for j in cls.idx}

    def _es_la_de_la_auditoria(self, numero):
        j = self.por_numero.get(numero)
        return j is not None and j["fecha"] == self.ANCLAS[numero]

    def test_indice_cubre_todos_los_ficheros(self):
        ficheros = [p for p in cj.DIR_JORNADAS.iterdir()
                    if p.name.startswith("jornada_") and p.name.endswith(".json")
                    and p.stem.split("_")[1].isdigit()]
        self.assertEqual(len(self.idx), len(ficheros))
        self.assertGreaterEqual(len(self.idx), 76)
        self.assertEqual(len(self.por_numero), len(self.idx))
        for n in range(1, 77):
            self.assertIn(n, self.por_numero)

    def test_todas_las_jornadas_reales_tienen_fecha(self):
        sin_fecha = [j["numero"] for j in self.idx if j["fecha"] is None]
        self.assertEqual(sin_fecha, [])

    def test_fechas_ancla(self):
        # Formatos distintos: 'La Quiniela Domingo, 14 de diciembre de 2025',
        # '10/05/2026', '13 de Mayo de 2026', ISO en partidos, y jornadas
        # (J6, J74, J75) cuyo partido 1 no es el primero que se juega.
        vistas = 0
        for numero, fecha in self.ANCLAS.items():
            j = self.por_numero[numero]
            if j["fecha"] is not None and j["fecha"] > date(2026, 12, 31):
                continue  # el pipeline ya piso ese numero con otra temporada
            if numero >= 28 and j["fecha"] >= self.CORTE_2026:
                continue
            self.assertEqual(j["fecha"], fecha, numero)
            vistas += 1
        self.assertGreaterEqual(vistas, 1)

    def test_orden_cronologico_estricto(self):
        fechas = [j["fecha"] for j in self.idx if j["fecha"] is not None]
        for anterior, siguiente in zip(fechas, fechas[1:]):
            self.assertLess(anterior, siguiente)

    def test_temporadas_de_todos_los_ficheros(self):
        # J1-J27 son 2026_2027 y J28-J76 son 2025_2026 (foto del 27/11/2026).
        for n in range(1, 28):
            j = self.por_numero[n]
            if j["fecha"] < date(2027, 7, 1):
                self.assertEqual(j["temporada"], "2026_2027", n)
                self.assertGreaterEqual(j["fecha"], date(2026, 8, 15), n)
        for n in range(28, 77):
            j = self.por_numero[n]
            if j["fecha"] < self.CORTE_2026:
                self.assertEqual(j["temporada"], "2025_2026", n)
            else:
                # La 26/27 ya ha llegado a ese numero y piso el fichero.
                self.assertNotEqual(j["temporada"], "2025_2026", n)
        # Y al reves: toda jornada anterior al reinicio es de la 25/26.
        for j in self.idx:
            if date(2025, 8, 12) <= j["fecha"] < self.CORTE_2026:
                self.assertEqual(j["temporada"], "2025_2026", j["numero"])
                self.assertGreaterEqual(j["numero"], 28)
            elif self.CORTE_2026 <= j["fecha"] < date(2027, 7, 1):
                self.assertEqual(j["temporada"], "2026_2027", j["numero"])

    def test_reinicio_de_agosto_2026(self):
        if not (self._es_la_de_la_auditoria(76) and self._es_la_de_la_auditoria(1)):
            self.skipTest("jornada_76/jornada_1 ya no son las del reinicio de 2026")
        numeros = [j["numero"] for j in self.idx]
        self.assertEqual(numeros.index(76) + 1, numeros.index(1))
        self.assertEqual(self.por_numero[76]["temporada"], "2025_2026")
        self.assertEqual(self.por_numero[1]["temporada"], "2026_2027")
        # Con la foto del 10/08/2026 la ultima cerrada era la J76, no "la mayor"
        # ni "la menor"; una semana despues, la J1.
        self.assertEqual(cj.ultima_jornada_cerrada("2026-08-10")["numero"], 76)
        self.assertEqual(cj.ultima_jornada_cerrada("2026-08-18")["numero"], 1)

    def test_la_temporada_no_depende_del_numero_fuera_de_verano(self):
        for j in self.idx:
            if j["fecha"].month not in (7, 8):
                self.assertEqual(cj.temporada_de_fecha(j["fecha"]), j["temporada"], j["numero"])

    def test_filtro_por_temporada(self):
        t25 = cj.jornadas_cronologicas(temporada="2025/2026")
        t26 = cj.jornadas_cronologicas(temporada="2026_2027")
        self.assertTrue(all(j["temporada"] == "2025_2026" for j in t25))
        self.assertTrue(all(j["temporada"] == "2026_2027" for j in t26))
        # Dentro de una temporada el orden cronologico SI coincide con el numero.
        for grupo in (t25, t26):
            numeros = [j["numero"] for j in grupo]
            self.assertEqual(numeros, sorted(numeros))
        if self._es_la_de_la_auditoria(1):
            self.assertEqual([j["numero"] for j in t26][:27], list(range(1, 28)))
        if self._es_la_de_la_auditoria(28):
            self.assertEqual([j["numero"] for j in t25][0], 28)
            self.assertEqual([j["numero"] for j in t25][-1], 76)

    def test_cerradas_y_ultima_cerrada(self):
        for j in self.idx:
            if j["fecha"] <= date(2026, 11, 24):
                self.assertTrue(j["cerrada"], j["numero"])
        if self._es_la_de_la_auditoria(24):
            self.assertEqual(cj.ultima_jornada_cerrada("2026-11-27")["numero"], 24)
        ultima = cj.ultima_jornada_cerrada()
        self.assertGreaterEqual(ultima["fecha"], date(2026, 11, 24))
        self.assertNotEqual(ultima["temporada"], "2025_2026")
        self.assertEqual(ultima, cj.jornadas_cronologicas(solo_cerradas=True)[-1])

    def test_en_curso_o_proxima(self):
        for hoy in (None, "2026-11-27"):
            proxima = cj.jornada_en_curso_o_proxima(hoy)
            if proxima is None:
                continue
            self.assertFalse(proxima["cerrada"])
            self.assertNotEqual(proxima["temporada"], "2025_2026")
            self.assertGreater(proxima["fecha"], date(2026, 11, 24))

    def test_jornadas_distintas_no_se_confunden(self):
        datos = {n: cj.cargar_jornada(n) for n in (1, 2, 24, 28, 60, 75, 76)}
        for a in datos:
            for b in datos:
                self.assertEqual(cj.misma_jornada(datos[a], datos[b]), a == b, (a, b))

    def test_prediccion_del_cierre_j24_es_la_foto_del_24_11(self):
        if not self._es_la_de_la_auditoria(24):
            self.skipTest("jornada_24.json ya no es la J24 del 24/11/2026")
        pred = cj.prediccion_del_cierre(24)
        self.assertIsNotNone(pred)
        self.assertEqual(pred["jornada"], 24)
        self.assertTrue(pred["generado_en"].startswith("2026-11-24"), pred["generado_en"])
        self.assertEqual(len(pred["partidos"]), 14)
        self.assertEqual(pred["partidos"][0]["local"], "Arsenal")
        self.assertTrue(cj.misma_jornada(pred, cj.cargar_jornada(24)))
        snap = cj.snapshot_del_cierre(24)
        self.assertTrue(snap["primer_partido_utc"].startswith("2026-11-24"))
        # La foto es de antes del primer partido.
        self.assertLess(pred["generado_en"], snap["primer_partido_utc"])

    def test_snapshots_reales(self):
        validos = 0
        for ruta in cj.DIR_SNAPSHOTS.glob("jornada_*.json"):
            numero = int(ruta.stem.split("_")[1])
            pred = cj.prediccion_del_cierre(numero)
            j = self.por_numero[numero]
            with open(ruta, encoding="utf-8") as fh:
                crudo = json.load(fh)
            creado = cj.parsear_fecha(crudo.get("creado_en"))
            if pred is None:
                # Solo se rechaza un snapshot que de verdad es de otra jornada
                # real: el fichero jornada_N ya es de otra temporada.
                self.assertFalse(cj.misma_jornada(crudo.get("prediccion"), cj.cargar_jornada(numero)),
                                 numero)
                self.assertGreater(abs((j["fecha"] - creado).days), 30, numero)
                continue
            validos += 1
            # La foto se creo antes de acabar la jornada y pocos dias antes de empezar.
            self.assertLessEqual(creado, j["fecha_fin"], numero)
            self.assertLessEqual((j["fecha"] - creado).days, 14, numero)
        self.assertGreaterEqual(validos, 1)

    def test_snapshot_cruzado_con_otra_temporada_se_rechaza(self):
        # Simula el reinicio: cada snapshot real frente a un jornada_N que en
        # realidad es otra jornada (otra temporada con el mismo numero).
        with tempfile.TemporaryDirectory() as tmp:
            for numero, ajena in ((24, 60), (1, 76), (76, 1)):
                otra = cj.cargar_jornada(ajena)
                otra["jornada"] = numero
                escribir(tmp, "jornada_%d.json" % numero, otra)
                self.assertIsNone(cj.prediccion_del_cierre(numero, dir_jornadas=tmp), numero)

    def test_sin_snapshot(self):
        self.assertIsNone(cj.prediccion_del_cierre(987))


class SinRelojTest(unittest.TestCase):
    def test_el_modulo_no_consulta_el_reloj(self):
        fuente = Path(cj.__file__).read_text(encoding="utf-8")
        for prohibido in ("date.today", "datetime.now", "utcnow", "time.time", "import time"):
            self.assertNotIn(prohibido, fuente, prohibido)

    def test_el_modulo_no_escribe(self):
        fuente = Path(cj.__file__).read_text(encoding="utf-8")
        self.assertEqual(fuente.count("open("), 1)
        self.assertIn('open(ruta, encoding="utf-8")', fuente)
        for prohibido in ("write_text", "write_bytes", "mkdir(", "json.dump(", "os.remove", "unlink("):
            self.assertNotIn(prohibido, fuente, prohibido)


if __name__ == "__main__":
    unittest.main()
