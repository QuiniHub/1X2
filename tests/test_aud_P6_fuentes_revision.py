# -*- coding: utf-8 -*-
"""Auditoria 26/11, paquete P6_fuentes: segunda pasada (problemas del revisor).

Sin red: todo con ficheros temporales y datos sinteticos.
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import actualizar_fuente_losilla as losilla
import actualizar_jornadas_detalle as jdetalle
import actualizar_resultados_directo as directo
import asegurar_proxima_jornada as asegurar
import cargar_historico_ligas_espana as hist_ligas
import cargar_historico_quinielas_lae as hist_lae


def escribir(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def leer(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def partido(num, local, visitante, fecha, resultado="Pendiente", signo="Pendiente"):
    return {
        "num": num, "local": local, "visitante": visitante, "fecha": fecha, "hora": "18:00",
        "resultado": resultado, "signo_oficial": signo, "signo_nuestro": "No jugada",
    }


def jornada_28_vieja():
    """jornada_28.json de la 25/26 (14/12/2025), cerrada."""
    partidos = [partido(i, f"Viejo{i}L", f"Viejo{i}V", "2025-12-14", "1-0", "1") for i in range(1, 15)]
    partidos[0].update({"local": "Betis", "visitante": "Getafe", "resultado": "3-0", "signo_oficial": "1"})
    partidos[1].update({"local": "Malaga", "visitante": "Cadiz"})
    return {"jornada": 28, "fecha": "14/12/2025", "estado": "cerrada", "partidos": partidos,
            "pleno15": partido(15, "Sevilla", "Oviedo", "2025-12-14", "2-1", "2-1")}


def jornada_28_nueva_fuente():
    """J28 de la 26/27 tal como la da la fuente: mismo cruce en la casilla 1
    (Betis - Getafe, sin jugar) y un placeholder en la casilla 2."""
    items = [partido(i, f"Nuevo{i}L", f"Nuevo{i}V", "2026-12-12") for i in range(1, 16)]
    items[0].update({"local": "Betis", "visitante": "Getafe"})
    items[1].update({"local": "Por determinar", "visitante": "Por determinar"})
    return {"jornada": 28, "fecha_texto": "12/12/2026", "items": items}


class JornadasDetalleOtraTemporadaTests(unittest.TestCase):
    """Revision del 55: la J28 nueva no se fusiona con jornada_28.json de 25/26."""

    def _ejecutar(self, tmp, existente):
        data = Path(tmp) / "data"
        jornadas = data / "jornadas"
        escribir(jornadas / "jornada_28.json", existente)
        with mock.patch.object(jdetalle, "DATA", data), \
             mock.patch.object(jdetalle, "JORNADAS", jornadas), \
             mock.patch.object(jdetalle, "extraer_jornadas", return_value=[jornada_28_nueva_fuente()]), \
             mock.patch.object(jdetalle, "proximas_jornadas_por_fecha", return_value=[]), \
             mock.patch.object(jdetalle, "actualizar_legado"):
            jdetalle.main()
        return data, leer(jornadas / "jornada_28.json")

    def test_no_hereda_equipos_ni_resultados_de_la_temporada_anterior(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, guardada = self._ejecutar(tmp, jornada_28_vieja())
            p1, p2 = guardada["partidos"][0], guardada["partidos"][1]
            # Mismo cruce en la misma casilla, pero es OTRO partido.
            self.assertEqual((p1["local"], p1["resultado"], p1["signo_oficial"]), ("Betis", "Pendiente", "Pendiente"))
            # El placeholder no se rellena con los equipos de hace un anio.
            self.assertNotEqual(p2["local"], "Malaga")
            self.assertTrue(jdetalle.es_placeholder_equipo(p2["local"]))
            self.assertNotEqual(guardada.get("estado"), "cerrada")
            # Y el fichero viejo queda archivado, no perdido.
            archivo = data / "temporadas" / "2025_2026" / "jornadas" / "jornada_28.json"
            self.assertTrue(archivo.exists())
            self.assertEqual(leer(archivo)["partidos"][0]["resultado"], "3-0")

    def test_misma_temporada_sigue_fusionando(self):
        misma = jornada_28_vieja()
        for p in misma["partidos"]:
            p["fecha"] = "2026-12-12"
        misma["fecha"] = "12/12/2026"
        with tempfile.TemporaryDirectory() as tmp:
            data, guardada = self._ejecutar(tmp, misma)
            p1, p2 = guardada["partidos"][0], guardada["partidos"][1]
            self.assertEqual((p1["resultado"], p1["signo_oficial"]), ("3-0", "1"))
            self.assertEqual(p2["local"], "Malaga")
            self.assertFalse((data / "temporadas").exists())

    def test_el_archivo_ya_guardado_no_se_pisa(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            archivo = data / "temporadas" / "2025_2026" / "jornadas" / "jornada_28.json"
            escribir(archivo, {"marca": "original"})
            self._ejecutar(tmp, jornada_28_vieja())
            self.assertEqual(leer(archivo), {"marca": "original"})


class AsegurarArchivaTests(unittest.TestCase):
    """asegurar_proxima_jornada archiva el fichero de 25/26 antes de pisarlo."""

    def test_archiva_antes_de_sobrescribir(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            jornadas = data / "jornadas"
            escribir(jornadas / "jornada_28.json", jornada_28_vieja())
            ultima = {"jornada": 27, "partidos": [partido(i, f"A{i}", f"B{i}", "2026-12-05") for i in range(1, 15)]}
            escribir(jornadas / "jornada_27.json", ultima)
            fuente = jornada_28_nueva_fuente()
            nueva = {"jornada": 28, "fecha": "12/12/2026", "partidos": fuente["items"][:14], "pleno15": fuente["items"][14]}
            with mock.patch.object(asegurar, "DATA", data), \
                 mock.patch.object(asegurar, "JORNADAS", jornadas), \
                 mock.patch.object(asegurar, "descargar_html", return_value="<html></html>"), \
                 mock.patch.object(asegurar, "html_a_lineas", return_value=[]), \
                 mock.patch.object(asegurar, "parsear_jornadas_publicadas", return_value=[{"jornada": 28}]), \
                 mock.patch.object(asegurar, "jornada_a_json", return_value=nueva):
                asegurar.main()
            self.assertEqual(leer(jornadas / "jornada_28.json")["partidos"][0]["resultado"], "Pendiente")
            archivo = data / "temporadas" / "2025_2026" / "jornadas" / "jornada_28.json"
            self.assertTrue(archivo.exists())
            self.assertEqual(leer(archivo)["partidos"][0]["resultado"], "3-0")


CSV_3 = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
    "SP1,15/08/2025,Girona,Vallecano,1,3,A\n"
    "SP1,16/08/2025,Villarreal,Oviedo,2,0,H\n"
    "SP1,17/08/2025,Celta,Getafe,0,2,A\n"
)
CSV_1 = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
    "SP1,15/08/2026,Girona,Vallecano,1,3,A\n"
)


class HistoricoLigasVentanaTests(unittest.TestCase):
    """La guardia 'menos partidos que antes' no congela el fichero cuando se
    desplaza la ventana de temporadas (entra una a medias, sale una completa)."""

    def test_al_desplazar_la_ventana_se_guarda(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            with mock.patch.object(hist_ligas, "SALIDA", salida), \
                 mock.patch.object(hist_ligas, "descargar_csv", side_effect=lambda l, t: ("u", CSV_3)):
                hist_ligas.main()
            previo = leer(salida)
            total_previo = hist_ligas.total_partidos(previo)

            def descarga(liga, temporada):
                return "u", (CSV_1 if temporada == "2627" else CSV_3)

            with mock.patch.object(hist_ligas, "SALIDA", salida), \
                 mock.patch.object(hist_ligas, "TEMPORADAS", ["2425", "2526", "2627"]), \
                 mock.patch.object(hist_ligas, "descargar_csv", side_effect=descarga):
                hist_ligas.main()
            despues = leer(salida)
            self.assertLess(hist_ligas.total_partidos(despues), total_previo)
            for liga in despues["ligas"].values():
                self.assertIn("2026/2027", liga["temporadas"])
                self.assertNotIn("2023/2024", liga["temporadas"])

    def test_una_temporada_recortada_sigue_sin_bajar(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            with mock.patch.object(hist_ligas, "SALIDA", salida), \
                 mock.patch.object(hist_ligas, "descargar_csv", side_effect=lambda l, t: ("u", CSV_3)):
                hist_ligas.main()
            total_previo = hist_ligas.total_partidos(leer(salida))
            with mock.patch.object(hist_ligas, "SALIDA", salida), \
                 mock.patch.object(hist_ligas, "descargar_csv", side_effect=lambda l, t: ("u", CSV_1)):
                hist_ligas.main()
            self.assertEqual(hist_ligas.total_partidos(leer(salida)), total_previo)


class HistoricoQuinielasLocalesAntiguasTests(unittest.TestCase):
    def test_un_fichero_local_anterior_a_25_26_no_crea_ni_mezcla_temporada(self):
        antigua = {"jornada": 3, "temporada": "2024/2025", "fecha": "x", "signos_14": "2" * 14,
                   "partidos": [{"signo_oficial": "2"} for _ in range(14)]}
        nueva = {"jornada": 4, "temporada": "2026/2027", "fecha": "x", "signos_14": "1" * 14,
                 "partidos": [{"signo_oficial": "1"} for _ in range(14)]}
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            with mock.patch.object(hist_lae, "SALIDA", salida), \
                 mock.patch.object(hist_lae, "ids_jornadas", side_effect=RuntimeError("sin red")), \
                 mock.patch.object(hist_lae, "cargar_jornadas_locales", return_value=[antigua, nueva]), \
                 mock.patch.object(hist_lae.time, "sleep"):
                hist_lae.main()
            despues = leer(salida)
            self.assertIn("2026/2027", despues["temporadas"])
            self.assertNotIn("2024/2025", despues["temporadas"])


class DirectoRevisionTests(unittest.TestCase):
    def _hoy(self):
        return datetime.now(directo.TZ_COMPETICION).date()

    def _jornada(self, numero, fecha, con_hora=True):
        partidos = [partido(i, f"J{numero}L{i}", f"J{numero}V{i}", fecha) for i in range(1, 15)]
        if not con_hora:
            for p in partidos:
                p.pop("hora", None)
                p.pop("fecha", None)
        partidos[0].update({"resultado": "1-0", "signo_oficial": "1"})
        return {"jornada": numero, "partidos": partidos}

    def test_dos_jornadas_en_juego_una_sin_horas_no_revienta(self):
        # El revisor temia un TypeError (None frente a datetime) al ordenar.
        # primer_inicio es texto ISO o "" (nunca None), asi que no puede
        # fallar; este test lo deja fijado.
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            ayer = (self._hoy() - timedelta(days=1)).isoformat()
            escribir(jornadas / "jornada_24.json", self._jornada(24, ayer, con_hora=False))
            escribir(jornadas / "jornada_25.json", self._jornada(25, ayer))
            with mock.patch.object(directo, "JORNADAS", jornadas):
                self.assertEqual(directo.jornada_activa_desde_archivos(None), 25)

    def _caso_signo_sin_marcador(self, texto):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        jornadas = Path(tmp.name) / "jornadas"
        ayer = (self._hoy() - timedelta(days=1)).isoformat()
        data = self._jornada(25, ayer)
        data["partidos"][0].update({
            "local": "Rayo Vallecano", "visitante": "Espanyol",
            "resultado": "Pendiente", "signo_oficial": "1", "fuente_resultado": "lae_oficial",
        })
        escribir(jornadas / "jornada_25.json", data)
        with mock.patch.object(directo, "JORNADAS", jornadas):
            cambios, actualizados = directo.actualizar_jornada_quiniela(texto)
        return cambios, actualizados, leer(jornadas / "jornada_25.json")["partidos"][0]

    def test_rellena_solo_el_marcador_si_el_signo_coincide(self):
        cambios, actualizados, p1 = self._caso_signo_sin_marcador("Jornada 25. Rayo Vallecano 2-1 Espanyol.")
        self.assertEqual(cambios, 1)
        self.assertEqual((p1["resultado"], p1["signo_oficial"], p1["fuente_resultado"]), ("2-1", "1", "lae_oficial"))
        self.assertEqual(len(actualizados), 1)

    def test_si_el_signo_no_coincide_no_toca_nada_ni_lo_pasa_al_calendario(self):
        cambios, actualizados, p1 = self._caso_signo_sin_marcador("Jornada 25. Rayo Vallecano 0-3 Espanyol.")
        self.assertEqual(cambios, 0)
        self.assertEqual((p1["resultado"], p1["signo_oficial"]), ("Pendiente", "1"))
        self.assertEqual(actualizados, [])


class LosillaFicheroIlegibleTests(unittest.TestCase):
    """Un fichero ilegible se aparta (copia) y la fuente sigue viva."""

    def test_se_guarda_copia_y_se_sigue_con_previo_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "fuente_losilla.json"
            roto = '{"probabilidades": {"jornada": 25, "part'
            ruta.write_text(roto, encoding="utf-8")
            self.assertEqual(losilla.cargar_anterior_o_abortar(ruta), {})
            copias = list(Path(tmp).glob("fuente_losilla.json.corrupto-*"))
            self.assertEqual(len(copias), 1)
            self.assertEqual(copias[0].read_text(encoding="utf-8"), roto)
            # El original no se toca aqui: solo lo sustituye un guardado bueno.
            self.assertEqual(ruta.read_text(encoding="utf-8"), roto)

    def test_si_no_se_puede_copiar_se_aborta_sin_sobrescribir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "fuente_losilla.json"
            ruta.write_text("{roto", encoding="utf-8")
            with mock.patch.object(Path, "write_bytes", side_effect=OSError("disco lleno")):
                self.assertIsNone(losilla.cargar_anterior_o_abortar(ruta))
            with mock.patch.object(Path, "write_bytes", side_effect=OSError("disco lleno")), \
                 mock.patch.object(losilla, "SALIDA", ruta), \
                 mock.patch.object(losilla, "guardar_json", side_effect=AssertionError("no debe guardar")):
                self.assertEqual(losilla.main(), 1)
            self.assertEqual(ruta.read_text(encoding="utf-8"), "{roto")


if __name__ == "__main__":
    unittest.main()
