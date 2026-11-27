# -*- coding: utf-8 -*-
"""Auditoria 26/11, paquete P6_fuentes: todo lo que elegia jornada por NUMERO
(hallazgos 55, 132, 142, 143, 144, 168, 76, 87, 204, 219), mas las fuentes
que escribian en la jornada equivocada (56, 59, 60) y el renombrado de equipos
(100). Sin red: jornadas sinteticas en directorios temporales."""

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_boleto_vivo as boleto
import actualizar_detalles_partidos as detalles
import actualizar_fuente_lae as lae
import actualizar_jornadas_detalle as jdetalle
import actualizar_resultados_directo as directo
import aplicar_correcciones_resultados as correcciones
import asegurar_proxima_jornada as asegurar
import datos_profesionales
import jornada_objetivo_quiniela as objetivo


def escribir(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def jornada(numero, fecha, signo="1", n=14, prefijo="Eq"):
    """jornada_N con n partidos el dia `fecha` (ISO) y el signo dado."""
    return {
        "jornada": numero,
        "partidos": [
            {
                "num": i + 1,
                "local": f"{prefijo}{numero}L{i}",
                "visitante": f"{prefijo}{numero}V{i}",
                "fecha": fecha,
                "hora": "18:00",
                "resultado": "1-0" if signo in ("1", "X", "2") else "Pendiente",
                "signo_oficial": signo,
            }
            for i in range(n)
        ],
    }


def montar_dos_temporadas(base):
    """Caso real: J76 de 25/26 (agosto 2026, cerrada) convive con J26 y J27 de
    26/27. El numero mas alto (76) NO es la jornada mas reciente."""
    jornadas = base / "data" / "jornadas"
    escribir(jornadas / "jornada_76.json", jornada(76, "2026-08-08"))
    escribir(jornadas / "jornada_28.json", jornada(28, "2025-12-14"))
    escribir(jornadas / "jornada_25.json", jornada(25, "2026-11-22"))
    escribir(jornadas / "jornada_26.json", jornada(26, "2026-11-29", signo="Pendiente"))
    escribir(jornadas / "jornada_27.json", jornada(27, "2026-12-05", signo="Pendiente"))
    return jornadas


class RespaldoLibertadTests(unittest.TestCase):
    """Hallazgos 55, 132 y 143."""

    def test_pide_las_siguientes_por_fecha_y_no_77_78_79(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = montar_dos_temporadas(Path(tmp))
            with mock.patch.object(jdetalle, "JORNADAS", jornadas):
                self.assertEqual(jdetalle.proximas_jornadas_por_fecha(), [28, 29, 30])

    def test_sin_ficheros_empieza_por_la_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            jornadas.mkdir()
            with mock.patch.object(jdetalle, "JORNADAS", jornadas):
                self.assertEqual(jdetalle.proximas_jornadas_por_fecha(), [1])


class AsegurarProximaJornadaTests(unittest.TestCase):
    """Hallazgos 142 y 168."""

    def test_la_j28_de_26_27_se_guarda_aunque_exista_la_76_y_la_28_vieja(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = montar_dos_temporadas(Path(tmp))
            nueva = jornada(28, "2026-12-12", signo="Pendiente")
            with mock.patch.object(asegurar, "JORNADAS", jornadas):
                self.assertEqual(asegurar.ultima_jornada_por_fecha()["numero"], 27)
                # jornada_28.json existe, pero es de la 25/26: no bloquea.
                self.assertTrue(asegurar.fichero_de_otra_temporada(28, nueva))
                self.assertTrue(asegurar.debe_guardar(28, nueva))

    def test_un_fichero_de_esta_temporada_si_bloquea(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = montar_dos_temporadas(Path(tmp))
            misma = jornada(27, "2026-12-05", signo="Pendiente")
            with mock.patch.object(asegurar, "JORNADAS", jornadas):
                self.assertFalse(asegurar.fichero_de_otra_temporada(27, misma))

    def test_una_jornada_con_fecha_anterior_a_la_ultima_no_se_guarda(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = montar_dos_temporadas(Path(tmp))
            vieja = jornada(77, "2026-08-10", signo="Pendiente")
            with mock.patch.object(asegurar, "JORNADAS", jornadas):
                self.assertFalse(asegurar.debe_guardar(77, vieja))

    def test_no_se_salta_jornadas_si_la_ultima_sigue_abierta(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = montar_dos_temporadas(Path(tmp))
            lejana = jornada(30, "2026-12-26", signo="Pendiente")
            with mock.patch.object(asegurar, "JORNADAS", jornadas):
                self.assertFalse(asegurar.debe_guardar(30, lejana))


class BoletoVivoObjetivoTests(unittest.TestCase):
    """Hallazgos 76 y 144."""

    def test_sin_jornada_de_la_fuente_se_usa_la_que_esta_en_curso_por_fecha(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = montar_dos_temporadas(Path(tmp))
            with mock.patch.object(boleto, "JORNADAS", jornadas):
                self.assertEqual(boleto.jornada_objetivo({}, hoy=date(2026, 11, 28)), 26)
                # numero de la fuente sin fichero: tampoco se cae en la 76
                self.assertEqual(boleto.jornada_objetivo({"jornada": 99}, hoy=date(2026, 11, 28)), 26)

    def test_si_la_fuente_da_una_jornada_con_fichero_manda_la_fuente(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = montar_dos_temporadas(Path(tmp))
            with mock.patch.object(boleto, "JORNADAS", jornadas):
                self.assertEqual(boleto.jornada_objetivo({"jornada": 27}, hoy=date(2026, 11, 28)), 27)

    def test_sin_ninguna_jornada_abierta_no_se_toca_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            escribir(jornadas / "jornada_76.json", jornada(76, "2026-08-08"))
            with mock.patch.object(boleto, "JORNADAS", jornadas):
                self.assertIsNone(boleto.jornada_objetivo({}, hoy=date(2026, 11, 28)))


class RenombradoBoletoVivoTests(unittest.TestCase):
    """Hallazgo 100: la fuente de resultados no reescribe el nombre canonico."""

    def test_misma_pareja_con_otra_grafia_conserva_el_nombre(self):
        destino = {"local": "Real Racing Club de Santander", "visitante": "Villarreal CF"}
        self.assertTrue(boleto.mismo_cruce_con_otro_nombre(destino, "R. Santander", "Villarreal"))
        destino_f = {"local": "Chelsea (F)", "visitante": "Barcelona (F)"}
        self.assertTrue(boleto.mismo_cruce_con_otro_nombre(destino_f, "Chelsea W", "Barcelona W"))

    def test_otro_partido_si_se_renombra(self):
        destino = {"local": "Real Racing Club de Santander", "visitante": "Villarreal CF"}
        self.assertFalse(boleto.mismo_cruce_con_otro_nombre(destino, "Getafe CF", "Villarreal CF"))


class DatosProfesionalesJornadasTests(unittest.TestCase):
    """Hallazgo 87 (parte de seleccion de jornadas)."""

    def test_no_se_elige_la_jornada_de_numero_mas_alto(self):
        with tempfile.TemporaryDirectory() as tmp:
            montar_dos_temporadas(Path(tmp))
            elegidas = datos_profesionales.seleccionar_jornadas_objetivo(
                root=Path(tmp), hoy=date(2026, 11, 28)
            )
            numeros = [int(j.get("jornada")) for j in elegidas]
            self.assertIn(26, numeros)
            self.assertNotIn(76, numeros)


class UltimaJornadaAprendidaRelojFijoTests(unittest.TestCase):
    """Hallazgo 204: el respaldo no puede dar por aprendida una jornada con
    fecha futura. Reloj fijo (antes el test pasaba por casualidad de hora)."""

    def _montar(self, base):
        jornadas = base / "jornadas"
        # J5 26/27: se juega 'manana' respecto al reloj fijado. Todas cerradas
        # en el historial (memoria de la temporada pasada con el mismo numero).
        escribir(jornadas / "jornada_5.json", jornada(5, "2026-09-12", signo="Pendiente"))
        escribir(jornadas / "jornada_6.json", jornada(6, "2026-09-19", signo="Pendiente"))
        historial = base / "historial.json"
        escribir(historial, {"jornadas": [
            {"jornada": 5, "validada": True},
            {"jornada": 6, "validada": True},
        ]})
        jugadas = base / "jugadas.json"
        escribir(jugadas, {"jugadas": []})
        return jornadas, historial, jugadas

    def test_ninguna_jornada_jugada_todavia_devuelve_cero_y_no_el_numero_mayor(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas, historial, jugadas = self._montar(Path(tmp))
            with mock.patch.object(objetivo, "hoy_iso", return_value="2026-09-11"):
                self.assertEqual(objetivo.ultima_jornada_aprendida(historial, jugadas, jornadas), 0)

    def test_con_el_reloj_despues_de_la_j5_la_aprendida_es_la_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas, historial, jugadas = self._montar(Path(tmp))
            with mock.patch.object(objetivo, "hoy_iso", return_value="2026-09-14"):
                self.assertEqual(objetivo.ultima_jornada_aprendida(historial, jugadas, jornadas), 5)

    def test_fichero_antiguo_sin_fecha_por_partido_sigue_contando(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            jornadas = base / "jornadas"
            vieja = jornada(40, "", signo="1")
            for p in vieja["partidos"]:
                p.pop("fecha")
            escribir(jornadas / "jornada_40.json", vieja)
            historial = base / "historial.json"
            escribir(historial, {"jornadas": [{"jornada": 40, "validada": True}]})
            jugadas = base / "jugadas.json"
            escribir(jugadas, {"jugadas": []})
            with mock.patch.object(objetivo, "hoy_iso", return_value="2026-09-11"):
                self.assertEqual(objetivo.ultima_jornada_aprendida(historial, jugadas, jornadas), 40)


class DetallesJornadaObjetivoTests(unittest.TestCase):
    """Hallazgo 219."""

    def test_manda_la_jornada_objetivo_y_no_la_de_la_prediccion_anterior(self):
        with mock.patch.object(objetivo, "jornada_objetivo_prediccion", return_value=25):
            self.assertEqual(detalles.jornada_a_descargar({"jornada": 24}), 25)

    def test_sin_objetivo_se_usa_la_de_la_prediccion(self):
        with mock.patch.object(objetivo, "jornada_objetivo_prediccion", return_value=0):
            self.assertEqual(detalles.jornada_a_descargar({"jornada": 24}), 24)
        with mock.patch.object(objetivo, "jornada_objetivo_prediccion", side_effect=RuntimeError("x")):
            self.assertEqual(detalles.jornada_a_descargar({"jornada": 24}), 24)


class CorreccionesPorEquiposTests(unittest.TestCase):
    """Hallazgo 56."""

    CORRECCION = {
        "jornada": 62, "num": 8, "local": "Valencia", "visitante": "Rayo Vallecano",
        "resultado": "1-1", "signo_oficial": "X", "estado_calendario": "Jugado",
    }

    def test_mismo_numero_con_otros_equipos_no_casa(self):
        otro = {"num": 8, "local": "Sevilla FC", "visitante": "Getafe CF"}
        self.assertFalse(correcciones.mismo_partido(otro, self.CORRECCION))

    def test_mismo_numero_y_mismos_equipos_casa_aunque_cambie_la_grafia(self):
        mismo = {"num": 8, "local": "Valencia CF", "visitante": "Rayo Vallecano de Madrid"}
        self.assertTrue(correcciones.mismo_partido(mismo, self.CORRECCION))

    def test_mismos_equipos_en_otra_casilla_no_casa(self):
        otra_casilla = {"num": 3, "local": "Valencia", "visitante": "Rayo Vallecano"}
        self.assertFalse(correcciones.mismo_partido(otra_casilla, self.CORRECCION))

    def test_la_correccion_vieja_no_pisa_la_jornada_62_de_otra_temporada(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            nueva = jornada(62, "2027-05-15", signo="Pendiente")
            escribir(jornadas / "jornada_62.json", nueva)
            antes = (jornadas / "jornada_62.json").read_text(encoding="utf-8")
            with mock.patch.object(correcciones, "JORNADAS", jornadas):
                self.assertEqual(correcciones.aplicar_en_jornadas([self.CORRECCION]), 0)
                self.assertFalse(correcciones.vigente_para_calendario(self.CORRECCION))
            # sin cambios no se reescribe el fichero
            self.assertEqual((jornadas / "jornada_62.json").read_text(encoding="utf-8"), antes)

    def test_la_correccion_se_sigue_aplicando_a_su_partido(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            data = jornada(62, "2026-05-14", signo="Pendiente")
            data["partidos"][7].update({"local": "Valencia", "visitante": "Rayo Vallecano"})
            escribir(jornadas / "jornada_62.json", data)
            with mock.patch.object(correcciones, "JORNADAS", jornadas):
                self.assertEqual(correcciones.aplicar_en_jornadas([self.CORRECCION]), 1)
                self.assertTrue(correcciones.vigente_para_calendario(self.CORRECCION))
            guardada = json.loads((jornadas / "jornada_62.json").read_text(encoding="utf-8"))
            self.assertEqual(guardada["partidos"][7]["signo_oficial"], "X")

    def test_temporada_declarada_tiene_que_coincidir_con_la_fecha_del_fichero(self):
        data = jornada(62, "2027-05-15", signo="Pendiente")
        con_temporada = dict(self.CORRECCION, temporada="2025/2026")
        self.assertFalse(correcciones.temporada_compatible(data, con_temporada, 62))
        self.assertTrue(correcciones.temporada_compatible(
            jornada(62, "2026-05-14"), con_temporada, 62))


class FuenteLaeTests(unittest.TestCase):
    """Hallazgo 59."""

    def test_la_fecha_en_texto_se_convierte_y_no_se_recorta_a_domingo(self):
        registro = {"jornada": 25, "fecha": "Domingo, 29 de noviembre de 2026"}
        self.assertEqual(lae.fecha_sorteo_lae(registro), "20261129")
        self.assertEqual(lae.fecha_sorteo_lae({"fecha": "sin fecha"}), "")

    def test_combinacion_aislada_y_no_un_trozo_de_un_numero(self):
        self.assertEqual(lae.extraer_combinacion("Combinacion 1X21X2112X1X21 Pleno"), "1X21X2112X1X21")
        self.assertIsNone(lae.extraer_combinacion("id 12121212121212 de sorteo"))
        self.assertIsNone(lae.extraer_combinacion("ref 91X21X2112X1X215"))

    def test_solo_se_consultan_jornadas_abiertas_con_fecha_ya_llegada(self):
        hist = {"jornadas": [
            {"jornada": 25, "estado": "abierta", "fecha": "Domingo, 29 de noviembre de 2026"},
            {"jornada": 24, "estado": "en_juego", "fecha": "Martes, 24 de noviembre de 2026"},
            {"jornada": 23, "estado": "cerrada", "fecha": "Domingo, 22 de noviembre de 2026"},
            {"jornada": 9, "estado": "abierta", "fecha": "texto raro"},
        ]}
        self.assertEqual(
            lae.jornadas_a_consultar(hist, hoy=date(2026, 11, 27)),
            [(24, date(2026, 11, 24))],
        )

    def test_no_se_aplica_si_la_pagina_es_de_otra_jornada(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            historial = base / "historial.json"
            escribir(historial, {"jornadas": [
                {"jornada": 24, "estado": "en_juego", "fecha": "Martes, 24 de noviembre de 2026"},
            ]})
            respuesta = {"jornada": 23, "combinacion": "1X21X2112X1X21"}
            with mock.patch.object(lae, "HISTORIAL", historial), \
                 mock.patch.object(lae, "JORNADAS", base / "jornadas"), \
                 mock.patch.object(lae, "obtener_resultado_oficial_lae", return_value=respuesta), \
                 mock.patch.object(lae, "actualizar_resultado_oficial") as aplicar:
                self.assertEqual(lae.actualizar_resultados_desde_lae(hoy=date(2026, 11, 27)), 0)
                aplicar.assert_not_called()

    def test_no_se_escribe_en_el_fichero_de_otra_temporada(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            escribir(jornadas / "jornada_24.json", jornada(24, "2025-11-16", signo="Pendiente"))
            antes = (jornadas / "jornada_24.json").read_text(encoding="utf-8")
            with mock.patch.object(lae, "JORNADAS", jornadas):
                self.assertFalse(lae.actualizar_resultado_oficial(
                    24, "1X21X2112X1X21", fecha=date(2026, 11, 24)))
            self.assertEqual((jornadas / "jornada_24.json").read_text(encoding="utf-8"), antes)

    def test_el_historial_se_casa_por_jornada_y_fecha(self):
        with tempfile.TemporaryDirectory() as tmp:
            historial = Path(tmp) / "historial.json"
            escribir(historial, {"jornadas": [
                {"jornada": 24, "fecha": "Domingo, 16 de noviembre de 2025", "resultado_oficial": "Pendiente"},
                {"jornada": 24, "fecha": "Martes, 24 de noviembre de 2026", "resultado_oficial": "Pendiente"},
            ]})
            with mock.patch.object(lae, "HISTORIAL", historial):
                lae.actualizar_historial_con_lae(24, "1X21X2112X1X21", fecha=date(2026, 11, 24))
            guardado = json.loads(historial.read_text(encoding="utf-8"))["jornadas"]
            self.assertEqual(guardado[0]["resultado_oficial"], "Pendiente")
            self.assertEqual(guardado[1]["resultado_oficial"], "1X21X2112X1X21")


class ResultadosDirectoTests(unittest.TestCase):
    """Hallazgo 60."""

    def _hoy(self):
        return datetime.now(directo.TZ_COMPETICION).date()

    def test_jornada_cerrada_nombrada_por_la_fuente_no_se_da_por_activa(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            ayer = (self._hoy() - timedelta(days=1)).isoformat()
            escribir(jornadas / "jornada_24.json", jornada(24, ayer, signo="1"))
            with mock.patch.object(directo, "JORNADAS", jornadas):
                self.assertIsNone(directo.jornada_activa_desde_archivos(24))

    def test_jornada_de_otra_temporada_con_el_mismo_numero_no_vale(self):
        vieja = jornada(25, (self._hoy() - timedelta(days=365)).isoformat(), signo="Pendiente")
        self.assertFalse(directo.jornada_abierta_y_reciente(vieja))
        actual = jornada(25, (self._hoy() - timedelta(days=1)).isoformat(), signo="Pendiente")
        self.assertTrue(directo.jornada_abierta_y_reciente(actual))

    def test_desempate_por_fecha_y_no_por_numero(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            hoy = self._hoy()
            # J76 'vieja' a medias (hace 100 dias) y J5 en juego ayer.
            vieja = jornada(76, (hoy - timedelta(days=100)).isoformat(), signo="Pendiente")
            vieja["partidos"][0]["signo_oficial"] = "1"
            nueva = jornada(5, (hoy - timedelta(days=1)).isoformat(), signo="Pendiente")
            nueva["partidos"][0]["signo_oficial"] = "1"
            escribir(jornadas / "jornada_76.json", vieja)
            escribir(jornadas / "jornada_5.json", nueva)
            with mock.patch.object(directo, "JORNADAS", jornadas):
                self.assertEqual(directo.jornada_activa_desde_archivos(None), 5)

    def test_un_signo_fijado_por_otra_fuente_no_se_sobrescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            jornadas = Path(tmp) / "jornadas"
            ayer = (self._hoy() - timedelta(days=1)).isoformat()
            data = jornada(25, ayer, signo="Pendiente")
            data["partidos"][0].update({
                "local": "Rayo Vallecano", "visitante": "Espanyol",
                "resultado": "2-1", "signo_oficial": "1", "fuente_resultado": "lae_oficial",
            })
            data["partidos"][1].update({
                "local": "Getafe", "visitante": "Elche",
                "resultado": "Pendiente", "signo_oficial": "Pendiente",
            })
            escribir(jornadas / "jornada_25.json", data)
            texto = "Jornada 25. Rayo Vallecano 0-3 Espanyol. Getafe 1-1 Elche."
            with mock.patch.object(directo, "JORNADAS", jornadas):
                cambios, _ = directo.actualizar_jornada_quiniela(texto)
            guardada = json.loads((jornadas / "jornada_25.json").read_text(encoding="utf-8"))
            p1, p2 = guardada["partidos"][0], guardada["partidos"][1]
            self.assertEqual((p1["resultado"], p1["signo_oficial"]), ("2-1", "1"))
            self.assertEqual((p2["resultado"], p2["signo_oficial"]), ("1-1", "X"))
            self.assertEqual(p2["fuente_resultado"], directo.FUENTE_DIRECTO)
            self.assertEqual(cambios, 1)

    def test_no_queda_ningun_utcnow(self):
        fuente = (ROOT / "actualizar_resultados_directo.py").read_text(encoding="utf-8")
        self.assertNotIn("utcnow(", fuente)
        self.assertRegex(directo.ahora_utc_iso(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main()
