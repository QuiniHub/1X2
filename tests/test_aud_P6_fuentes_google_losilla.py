# -*- coding: utf-8 -*-
"""Auditoria 26/11, paquete P6_fuentes: buscar_resultados_google (hallazgos 6
y 126), actualizar_fuente_losilla (8, 58 y 248) y la reparacion de
data/mundial_2026_resultados.json. Sin red: todo con textos sinteticos."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_fuente_losilla as losilla
import buscar_resultados_google as google


class VariantesDistintivasTests(unittest.TestCase):
    """Hallazgo 6: 'R. Santander' generaba la variante 'r' y casaba con todo."""

    def test_no_hay_variante_de_primera_palabra(self):
        for nombre in ("R. Santander", "Real Sociedad de Futbol", "Club Atletico de Madrid", "RC Celta", "CA Osasuna"):
            variantes = google.variantes_equipo(nombre)
            for prohibida in ("r", "real", "club", "rc", "ca"):
                self.assertNotIn(prohibida, variantes, f"{nombre} -> {variantes}")

    def test_no_se_casa_por_subcadena(self):
        self.assertFalse(google.contiene_equipo("partido en tirana esta noche", "Iran"))
        self.assertTrue(google.contiene_equipo("hoy juega iran contra otro", "Iran"))

    def test_caso_real_j23_pagina_de_otro_partido_no_da_resultado(self):
        # Texto de la pagina de Flashscore del Atletico-Getafe: no nombra a los
        # equipos buscados. Antes la 'r' casaba y se devolvia el 2-0.
        texto = "Atletico Madrid 2 - 0 Getafe CF Finalizado LaLiga jornada 14 arbitro Hernandez"
        self.assertEqual(google.extraer_resultado_de_texto(texto, "R. Santander", "Real Sociedad de Futbol"), "")

    def test_url_de_otro_partido_se_descarta(self):
        url = "https://www.flashscore.es/partido/futbol/atletico-madrid-jaarqpLQ/getafe-cf-dboeiWOt/"
        self.assertFalse(google.url_nombra_a_los_dos(url, "R. Santander", "Real Sociedad de Futbol"))
        partido = {"local": "R. Santander", "visitante": "Real Sociedad de Futbol", "url": url,
                   "fuente_resultado_url": url, "flashscore_url": url}
        self.assertEqual(google.urls_individuales(partido, ""), [])


class SoloMundialTests(unittest.TestCase):
    """Hallazgos 6 y 126: la pagina consultada es la del Mundial 2026."""

    CLUB = {"num": 5, "local": "R. Santander", "visitante": "Real Sociedad de Futbol",
            "fecha": "2026-11-22", "hora": "14:00", "resultado": "", "signo_oficial": ""}
    MUNDIAL = {"num": 1, "local": "Panama", "visitante": "Inglaterra",
               "fecha": "2026-06-27", "hora": "21:00", "resultado": "", "signo_oficial": ""}

    def test_partido_de_clubes_no_es_candidato(self):
        self.assertFalse(google.partido_candidato(dict(self.CLUB)))
        self.assertTrue(google.partido_candidato(dict(self.MUNDIAL)))

    def test_signo_ya_fijado_no_es_candidato(self):
        self.assertFalse(google.partido_candidato(dict(self.MUNDIAL, signo_oficial="2")))

    def test_upsert_no_guarda_partidos_de_clubes(self):
        data = {"resultados": []}
        self.assertFalse(google.upsert_mundial(data, dict(self.CLUB), "2-0", "x"))
        self.assertEqual(data["resultados"], [])
        self.assertTrue(google.upsert_mundial(data, dict(self.MUNDIAL), "0-1", "x"))
        self.assertEqual(len(data["resultados"]), 1)

    def test_sin_candidatos_no_hay_ninguna_peticion(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            jornadas.mkdir()
            (jornadas / "jornada_23.json").write_text(
                json.dumps({"jornada": 23, "estado": "en_juego", "partidos": [dict(self.CLUB)]}), encoding="utf-8"
            )
            mundial = Path(tmp) / "mundial.json"
            with mock.patch.object(google, "JORNADAS", jornadas), \
                 mock.patch.object(google, "RESULTADOS_MUNDIAL", mundial), \
                 mock.patch.object(google, "descargar", side_effect=AssertionError("no debe haber red")):
                self.assertEqual(google.actualizar_resultados_pendientes(), 0)
            guardado = json.loads((jornadas / "jornada_23.json").read_text(encoding="utf-8"))
            self.assertEqual(guardado["partidos"][0]["resultado"], "")
            self.assertFalse(mundial.exists())

    def test_user_agent_no_suplanta_un_navegador(self):
        ua = google.HEADERS["User-Agent"]
        for palabra in ("Mozilla", "Chrome", "Safari", "AppleWebKit"):
            self.assertNotIn(palabra, ua)


class DatoMundialReparadoTests(unittest.TestCase):
    """Reparacion de datos: fuera las dos entradas de clubes (una falsa)."""

    def test_no_quedan_partidos_fuera_de_las_fechas_del_mundial(self):
        data = json.loads((ROOT / "data" / "mundial_2026_resultados.json").read_text(encoding="utf-8"))
        fuera = [r for r in data["resultados"]
                 if r.get("fecha") and not ("2026-06-11" <= str(r.get("fecha"))[:10] <= "2026-07-19")]
        self.assertEqual(fuera, [])
        self.assertFalse(any("Santander" in str(r.get("local")) for r in data["resultados"]))


def _partido(numero, local, visitante, p1=50.0):
    return {"numero": numero, "local": local, "visitante": visitante,
            "probabilidades_signo": {"1": p1, "X": 25.0, "2": 25.0}}


class FusionLosillaTests(unittest.TestCase):
    """Hallazgo 8: no mezclar la jornada anterior bajo el numero de la nueva."""

    def setUp(self):
        self.previa = {
            "jornada": 25,
            "partidos_1x2": [_partido(n, f"Local{n}", f"Visit{n}") for n in range(1, 15)],
            "pleno_al_15": {"numero": 15, "local": "A", "visitante": "B"},
        }

    def test_jornada_nueva_con_solo_pleno_no_hereda_los_14_partidos(self):
        nuevo = {"jornada": 26, "partidos_1x2": [], "pleno_al_15": {"numero": 15, "local": "C", "visitante": "D"}}
        salida = losilla.fusionar_probabilidades({"probabilidades": self.previa}, nuevo)
        self.assertEqual(salida.get("jornada"), 26)
        self.assertEqual(salida.get("partidos_1x2") or [], [])
        self.assertEqual(salida["pleno_al_15"]["local"], "C")

    def test_misma_jornada_si_rellena_lo_que_falta(self):
        nuevo = {"jornada": 25, "partidos_1x2": [], "pleno_al_15": {"numero": 15, "local": "A", "visitante": "B"}}
        salida = losilla.fusionar_probabilidades({"probabilidades": self.previa}, nuevo)
        self.assertEqual(len(salida["partidos_1x2"]), 14)

    def test_mismo_numero_de_jornada_pero_otros_equipos_no_se_fusiona(self):
        # el numero de jornada se repite cada temporada
        nuevo = {"jornada": 25, "partidos_1x2": [_partido(1, "Otro", "Distinto")]}
        self.assertFalse(losilla.misma_jornada_fuente(self.previa, nuevo))

    def test_cuotas_no_se_recuperan_de_otra_jornada_ni_de_otro_partido(self):
        previo = {"cuotas": {"jornada": 25, "partidos": [
            {"numero": 1, "local": "Betis", "visitante": "Rayo", "cuota_media_1": 1.5, "cuota_media_X": 4.0, "cuota_media_2": 6.0}]}}
        sin_dato = {"numero": 1, "local": "Girona", "visitante": "Elche",
                    "cuota_media_1": None, "cuota_media_X": None, "cuota_media_2": None}
        otra_jornada = losilla.fusionar_cuotas(previo, {"jornada": 26, "partidos": [dict(sin_dato)]})
        self.assertIsNone(otra_jornada["partidos"][0]["cuota_media_1"])
        otro_partido = losilla.fusionar_cuotas(previo, {"jornada": 25, "partidos": [dict(sin_dato)]})
        self.assertIsNone(otro_partido["partidos"][0]["cuota_media_1"])
        mismo = losilla.fusionar_cuotas(previo, {"jornada": 25, "partidos": [
            dict(sin_dato, local="Betis", visitante="Rayo")]})
        self.assertEqual(mismo["partidos"][0]["cuota_media_1"], 1.5)


class EscrutinioLosillaTests(unittest.TestCase):
    """Hallazgo 58: barrido 90..1 y escrutinios no plausibles."""

    def test_la_jornada_se_lee_del_json_y_no_hay_barrido(self):
        texto = json.dumps({"probabilidades": {"jornada": 25}})
        self.assertEqual(losilla.candidatos_jornada_cerrada(texto), [24, 23, 22])

    def test_sin_jornada_conocida_no_se_pide_nada(self):
        self.assertEqual(losilla.candidatos_jornada_cerrada("", None), [])
        self.assertEqual(losilla.candidatos_jornada_cerrada(json.dumps({"jornada": 1})), [])

    def test_acertantes_deben_crecer_al_bajar_de_categoria(self):
        basura = {
            "14": {"acertantes": 0, "premio_euros": 0},
            "13": {"acertantes": 20, "premio_euros": 9000.0},
            "12": {"acertantes": 334, "premio_euros": 400.0},
            "11": {"acertantes": 2, "premio_euros": 50.0},
            "10": {"acertantes": 30000, "premio_euros": 5.0},
        }
        self.assertFalse(losilla.escrutinio_plausible(basura))
        bueno = dict(basura, **{"11": {"acertantes": 4100, "premio_euros": 50.0}})
        self.assertTrue(losilla.escrutinio_plausible(bueno))


class FicheroPrevioIlegibleTests(unittest.TestCase):
    """Hallazgo 248: un JSON truncado no se sustituye por uno vacio."""

    def test_losilla_no_sobrescribe_si_el_previo_no_se_puede_leer(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "fuente_losilla.json"
            ruta.write_text('{"probabilidades": {"jornada": 25, "part', encoding="utf-8")
            # Si no se puede apartar una copia del fichero roto, se aborta.
            with mock.patch.object(Path, "write_bytes", side_effect=OSError("sin permiso")):
                self.assertIsNone(losilla.cargar_anterior_o_abortar(ruta))
            with mock.patch.object(Path, "write_bytes", side_effect=OSError("sin permiso")), \
                 mock.patch.object(losilla, "SALIDA", ruta), \
                 mock.patch.object(losilla, "guardar_json", side_effect=AssertionError("no debe guardar")):
                self.assertEqual(losilla.main(), 1)
            self.assertTrue(ruta.read_text(encoding="utf-8").endswith('"part'))

    def test_si_no_existe_se_empieza_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(losilla.cargar_anterior_o_abortar(Path(tmp) / "no_existe.json"), {})


if __name__ == "__main__":
    unittest.main()
