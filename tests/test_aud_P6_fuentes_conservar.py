# -*- coding: utf-8 -*-
"""Auditoria 26/11, paquete P6_fuentes: fuentes que vaciaban o pisaban datos
buenos cuando fallaba la descarga (hallazgos 34, 54, 63, 248), llamadas
inutiles a la red (61, 87, 125), temporadas escritas a mano (62, 189, 242),
falsos positivos (191, 227), competiciones (86, 100, 113, 188) y varios
menores (126, 171, 172, 173, 193). Sin red: todo con datos sinteticos."""

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_clasificaciones_oficiales as clasificaciones
import actualizar_detalles_partidos as detalles
import actualizar_liga_f as liga_f
import actualizar_monitor_temporadas as monitor
import actualizar_resultados_apis as apis
import actualizar_resultados_libres as libres
import cargar_historico_ligas_espana as hist_ligas
import cargar_historico_quinielas_lae as hist_lae
import datos_profesionales
import preparar_temporada_2026_2027 as preparar
import resolver_competiciones_profesionales as resolver
import sincronizar_resultados_jornada as sincronizar


def escribir(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def leer(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 34 / 63: historicos
# --------------------------------------------------------------------------

CSV_BUENO = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
    "SP1,15/08/2025,Girona,Vallecano,1,3,A\n"
    "SP1,16/08/2025,Villarreal,Oviedo,2,0,H\n"
    "SP1,17/08/2025,Celta,Getafe,0,2,A\n"
)


class HistoricoLigasTests(unittest.TestCase):
    def _previo(self, salida):
        with mock.patch.object(hist_ligas, "SALIDA", salida), \
             mock.patch.object(hist_ligas, "descargar_csv", side_effect=lambda l, t: ("u", CSV_BUENO)):
            hist_ligas.main()
        return leer(salida)

    def test_si_falla_toda_la_descarga_no_se_vacia_el_historico(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            previo = self._previo(salida)
            self.assertGreater(hist_ligas.total_partidos(previo), 0)
            antes = salida.read_text(encoding="utf-8")
            with mock.patch.object(hist_ligas, "SALIDA", salida), \
                 mock.patch.object(hist_ligas, "descargar_csv", side_effect=lambda l, t: ("u", None)):
                hist_ligas.main()
            despues = leer(salida)
            self.assertEqual(hist_ligas.total_partidos(despues), hist_ligas.total_partidos(previo))
            for liga in previo["ligas"]:
                self.assertEqual(
                    len(despues["ligas"][liga]["consolidado"]["partidos"]),
                    len(previo["ligas"][liga]["consolidado"]["partidos"]),
                )
            self.assertTrue(antes)

    def test_sin_previo_y_sin_red_no_se_escribe_un_fichero_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            with mock.patch.object(hist_ligas, "SALIDA", salida), \
                 mock.patch.object(hist_ligas, "descargar_csv", side_effect=lambda l, t: ("u", None)):
                hist_ligas.main()
            self.assertFalse(salida.exists())

    def test_una_temporada_que_falla_se_conserva_del_previo(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            previo = self._previo(salida)
            primera_liga = next(iter(hist_ligas.LIGAS))

            def descarga_parcial(liga, temporada):
                if liga == primera_liga and temporada == hist_ligas.TEMPORADAS[0]:
                    return "u", None
                return "u", CSV_BUENO

            with mock.patch.object(hist_ligas, "SALIDA", salida), \
                 mock.patch.object(hist_ligas, "descargar_csv", side_effect=descarga_parcial):
                hist_ligas.main()
            despues = leer(salida)
            self.assertEqual(hist_ligas.total_partidos(despues), hist_ligas.total_partidos(previo))
            self.assertEqual(len(despues["temporadas_conservadas_del_previo"]), 1)


def _jornadas_falsas(n, temporada):
    return [
        {"jornada": i + 1, "temporada": temporada, "fecha": "x", "signos_14": "1" * 14,
         "partidos": [{"signo_oficial": "1"} for _ in range(14)]}
        for i in range(n)
    ]


class HistoricoQuinielasLaeTests(unittest.TestCase):
    def test_temporada_cerrada_en_cache_no_se_vuelve_a_descargar(self):
        previo = {"temporadas": {
            nombre: {"temporada": nombre, "jornadas": _jornadas_falsas(60, nombre), "estadisticas": {}}
            for nombre in hist_lae.TEMPORADAS.values()
        }}
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            escribir(salida, previo)
            with mock.patch.object(hist_lae, "SALIDA", salida), \
                 mock.patch.object(hist_lae, "ids_jornadas") as ids, \
                 mock.patch.object(hist_lae, "post") as post, \
                 mock.patch.object(hist_lae, "cargar_jornadas_locales", return_value=[]), \
                 mock.patch.object(hist_lae.time, "sleep"):
                hist_lae.main()
            ids.assert_not_called()
            post.assert_not_called()
            despues = leer(salida)
            for nombre in hist_lae.TEMPORADAS.values():
                self.assertEqual(len(despues["temporadas"][nombre]["jornadas"]), 60)

    def test_si_falla_webprincipal_se_conserva_lo_que_habia(self):
        # 30 jornadas: por debajo del minimo de cache, asi que SI se intenta
        # descargar; la descarga falla y no se puede perder nada.
        previo = {"temporadas": {
            nombre: {"temporada": nombre, "jornadas": _jornadas_falsas(30, nombre), "estadisticas": {}}
            for nombre in hist_lae.TEMPORADAS.values()
        }}
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            escribir(salida, previo)
            with mock.patch.object(hist_lae, "SALIDA", salida), \
                 mock.patch.object(hist_lae, "ids_jornadas", side_effect=RuntimeError("sin red")), \
                 mock.patch.object(hist_lae, "cargar_jornadas_locales", return_value=[]), \
                 mock.patch.object(hist_lae.time, "sleep"):
                hist_lae.main()
            despues = leer(salida)
            for nombre in hist_lae.TEMPORADAS.values():
                self.assertEqual(len(despues["temporadas"][nombre]["jornadas"]), 30, nombre)

    def test_sin_previo_y_sin_red_no_se_escribe_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "historico.json"
            with mock.patch.object(hist_lae, "SALIDA", salida), \
                 mock.patch.object(hist_lae, "ids_jornadas", side_effect=RuntimeError("sin red")), \
                 mock.patch.object(hist_lae, "cargar_jornadas_locales", return_value=[]), \
                 mock.patch.object(hist_lae.time, "sleep"):
                hist_lae.main()
            self.assertFalse(salida.exists())

    def test_la_temporada_sale_de_la_fecha_real_del_fichero(self):
        j = {"jornada": 3, "partidos": [{"fecha": "2027-08-28"}]}
        self.assertEqual(hist_lae.temporada_de_jornada_local(j, 3), "2027/2028")
        j = {"jornada": 25, "partidos": [{"fecha": "2026-11-28"}]}
        self.assertEqual(hist_lae.temporada_de_jornada_local(j, 25), "2026/2027")
        self.assertIsNone(hist_lae.temporada_de_jornada_local({"partidos": []}, 5))


# --------------------------------------------------------------------------
# 54 / 62: resultados libres
# --------------------------------------------------------------------------

class ResultadosLibresTests(unittest.TestCase):
    PARTIDO = {
        "liga": "La Liga", "local": "Getafe", "visitante": "Elche", "resultado": "1-1",
        "fecha": "2026-11-22", "fuente": "thesportsdb",
    }

    def test_cero_partidos_no_pisa_el_dato_previo_y_deja_aviso(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "resultados_libres.json"
            with mock.patch.object(libres, "OUT", out), mock.patch.object(libres, "DATA", Path(tmp)):
                libres.guardar([self.PARTIDO])
                bueno = leer(out)
                self.assertEqual(bueno["total"], 1)
                libres.guardar([])
                libres.guardar([])
            vacio = leer(out)
            self.assertEqual(len(vacio["partidos"]), 1)
            self.assertEqual(vacio["actualizado_en"], bueno["actualizado_en"])
            self.assertEqual(vacio["ciclos_seguidos_sin_datos"], 2)
            self.assertIn("aviso", vacio)

    def test_cuando_vuelven_los_datos_desaparece_el_aviso(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "resultados_libres.json"
            with mock.patch.object(libres, "OUT", out), mock.patch.object(libres, "DATA", Path(tmp)):
                libres.guardar([])
                libres.guardar([self.PARTIDO])
            data = leer(out)
            self.assertNotIn("aviso", data)
            self.assertEqual(data["por_fuente"], {"thesportsdb": 1})

    def test_prorroga_y_penaltis_no_son_resultado_final(self):
        eventos = [
            {"strStatus": "AET", "strHomeTeam": "A", "strAwayTeam": "B",
             "intHomeScore": "2", "intAwayScore": "1", "dateEvent": "2026-11-20"},
            {"strStatus": "Match Finished", "strHomeTeam": "C", "strAwayTeam": "D",
             "intHomeScore": "1", "intAwayScore": "0", "dateEvent": "2026-11-20"},
        ]
        finales = [p for p in libres._parsear_eventos_thesportsdb("Copa", eventos) if p.get("resultado")]
        self.assertEqual(len(finales), 1)
        self.assertEqual(finales[0]["resultado"], "1-0")
        self.assertNotIn("STATUS_EXTRA_TIME", libres.ESPN_ESTADOS_FINAL_90)
        self.assertNotIn("STATUS_PENALTIES", libres.ESPN_ESTADOS_FINAL_90)

    def test_la_temporada_se_deriva_de_la_fecha(self):
        self.assertEqual(libres.temporada_thesportsdb(date(2026, 11, 27)), "2026-2027")
        self.assertEqual(libres.temporada_thesportsdb(date(2027, 3, 1)), "2026-2027")
        self.assertEqual(libres.temporada_thesportsdb(date(2027, 9, 1)), "2027-2028")
        urls = libres.openfootball_urls(date(2027, 9, 1))
        self.assertTrue(all("/2027-28/" in u for u in urls.values()))

    def test_openfootball_formato_plano(self):
        data = {"matches": [
            {"round": "Matchday 1", "date": "2026-08-15", "team1": "Getafe CF", "team2": "Elche CF",
             "score": {"ft": [2, 1]}},
            {"round": "Matchday 2", "date": "2026-08-22", "team1": "Sevilla FC", "team2": "Valencia CF"},
        ]}
        partidos = libres.parsear_openfootball_plano("La Liga", data)
        self.assertEqual(len(partidos), 1)
        self.assertEqual(partidos[0]["resultado"], "2-1")
        self.assertEqual(partidos[0]["fuente"], "openfootball")


# --------------------------------------------------------------------------
# 248: acumulado ilegible
# --------------------------------------------------------------------------

class ResultadosApisTests(unittest.TestCase):
    def test_fichero_truncado_no_se_sobrescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            roto = Path(tmp) / "mundial.json"
            roto.write_text('{"version": "1.0", "resultados": [{"local": "Espa', encoding="utf-8")
            with mock.patch.object(apis, "RESULTADOS_MUNDIAL", roto), \
                 mock.patch.object(apis, "JORNADAS", Path(tmp) / "jornadas"), \
                 mock.patch.object(apis, "obtener_balldontlie") as f1, \
                 mock.patch.object(apis, "obtener_football_data") as f2, \
                 mock.patch.object(apis, "obtener_openfootball") as f3, \
                 mock.patch.object(apis, "obtener_api_football") as f4:
                apis.actualizar()
            for f in (f1, f2, f3, f4):
                f.assert_not_called()
            self.assertTrue(roto.read_text(encoding="utf-8").endswith("Espa"))


# --------------------------------------------------------------------------
# 61 / 125: Liga F
# --------------------------------------------------------------------------

class Error429(Exception):
    class _R:
        status_code = 429
    response = _R()

    def __str__(self):
        return "429 Client Error: Too many requests"


class LigaFTests(unittest.TestCase):
    def test_user_agent_es_de_cliente_automatizado_y_sin_datos_personales(self):
        ua = liga_f.USER_AGENT.lower()
        for falso in ("mozilla", "chrome", "safari", "applewebkit", "windows nt"):
            self.assertNotIn(falso, ua)
        self.assertIn("bot", ua)
        self.assertNotIn("@", ua)
        self.assertNotIn("marc", ua)

    def _clasificacion(self, carpeta, **extra):
        base = {
            "version": 1, "temporada": liga_f.TEMPORADA, "avisos": [],
            "equipos": [{"equipo": f"E{i}", "puntos": 1, "pj": 1} for i in range(16)],
        }
        base.update(extra)
        escribir(carpeta / "clasificacion.json", base)
        escribir(carpeta / "resultados.json", {"version": 1, "partidos": [{"x": 1}], "avisos": []})

    def test_tras_un_429_solo_se_llama_una_vez_y_no_se_toca_actualizado_en(self):
        ahora = datetime.now(timezone.utc)
        hace_10_dias = (ahora - timedelta(days=10)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            self._clasificacion(carpeta, actualizado_en=hace_10_dias)
            llamadas = []

            def descargar(url):
                llamadas.append(url)
                raise Error429()

            original = liga_f.conservar_previo_con_aviso
            with mock.patch.object(liga_f, "DATA_DIR", carpeta), \
                 mock.patch.object(liga_f, "descargar", side_effect=descargar), \
                 mock.patch.object(liga_f, "motivo_para_no_descargar",
                                   side_effect=lambda: liga_f.__dict__["_motivo"](carpeta)), \
                 mock.patch.object(liga_f, "conservar_previo_con_aviso",
                                   side_effect=lambda aviso: original(aviso, carpeta)):
                liga_f.__dict__["_motivo"] = MOTIVO_ORIGINAL
                self.assertEqual(liga_f.main([]), 1)
                # 429 en la primera fuente: no se prueba la segunda (misma casa)
                self.assertEqual(len(llamadas), 1)
                guardado = leer(carpeta / "clasificacion.json")
                self.assertEqual(guardado["actualizado_en"], hace_10_dias)
                self.assertTrue(guardado["dato_caducado"])
                self.assertGreater(guardado["dias_sin_actualizar"], 9)
                self.assertEqual(len(guardado["equipos"]), 16)
                # ciclo siguiente: dentro de la espera tras 429 no hay red
                self.assertEqual(liga_f.main([]), 0)
                self.assertEqual(len(llamadas), 1)

    def test_dato_reciente_no_se_vuelve_a_descargar(self):
        ahora = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            self._clasificacion(carpeta, actualizado_en=(ahora - timedelta(hours=1)).isoformat())
            self.assertIsNotNone(liga_f.motivo_para_no_descargar(carpeta, ahora))
            self._clasificacion(carpeta, actualizado_en=(ahora - timedelta(hours=5)).isoformat())
            self.assertIsNone(liga_f.motivo_para_no_descargar(carpeta, ahora))

    def test_pasada_la_espera_tras_429_se_vuelve_a_intentar(self):
        ahora = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            self._clasificacion(
                carpeta,
                actualizado_en=(ahora - timedelta(days=2)).isoformat(),
                ultimo_intento=(ahora - timedelta(hours=7)).isoformat(),
                avisos=["Descarga fallida x: 429 Client Error"],
            )
            self.assertIsNone(liga_f.motivo_para_no_descargar(carpeta, ahora))

    def test_temporada_derivada_de_la_fecha(self):
        temporada, fuentes = liga_f.temporada_y_fuentes(date(2027, 9, 10))
        self.assertEqual(temporada, "2027/2028")
        self.assertTrue(any("2027%E2%80%9328_Liga_F" in f for f in fuentes))
        self.assertEqual(liga_f.temporada_y_fuentes(date(2027, 2, 1))[0], "2026/2027")


MOTIVO_ORIGINAL = liga_f.motivo_para_no_descargar


# --------------------------------------------------------------------------
# 87 / 189 / 242: datos profesionales
# --------------------------------------------------------------------------

class _Respuesta:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class ApiPlanFree:
    """Imita el plan Free: fixtures de la temporada en curso -> error 'plan'."""

    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(url)
        if url.endswith("/status"):
            return _Respuesta({"response": {"subscription": {"plan": "Free", "active": True},
                                            "requests": {"current": 1, "limit_day": 100}}})
        return _Respuesta({"errors": {"plan": "Free plans do not have access to this season, try from 2022 to 2024."},
                           "response": []})


class DatosProfesionalesPlanTests(unittest.TestCase):
    def _root(self, tmp):
        root = Path(tmp)
        hoy = datetime.now(timezone.utc).date()
        partidos = [
            {"num": i + 1, "local": f"L{i}", "visitante": f"V{i}",
             "fecha": (hoy + timedelta(days=1)).isoformat(), "hora": "18:00",
             "signo_oficial": "Pendiente"}
            for i in range(14)
        ]
        escribir(root / "data" / "jornadas" / "jornada_25.json", {"jornada": 25, "partidos": partidos})
        return root

    def test_plan_sin_acceso_corta_a_la_primera_y_el_ciclo_siguiente_no_usa_la_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            cliente = ApiPlanFree()
            payload = datos_profesionales.leer_api_football_payload(
                "https://v3.football.api-sports.io", "token-test", root=root, requester=cliente)
            fixtures = [c for c in cliente.calls if c.endswith("/fixtures")]
            # antes: una peticion por partido y liga (~20 fallidas por ciclo)
            self.assertEqual(len(fixtures), 1)
            api = payload["proveedores"]["api_football"]
            self.assertIn("plan_no_cubre_season", api)

            # se guarda el diagnostico como lo haria el pipeline
            escribir(root / "data" / "datos_profesionales.json",
                     datos_profesionales.normalizar_payload(payload, origen="api_football"))
            cliente2 = ApiPlanFree()
            payload2 = datos_profesionales.leer_api_football_payload(
                "https://v3.football.api-sports.io", "token-test", root=root, requester=cliente2)
            self.assertEqual(cliente2.calls, [])
            api2 = payload2["proveedores"]["api_football"]
            self.assertEqual(api2["peticiones_en_este_ciclo"], 0)
            self.assertIn("plan_no_cubre_season", api2)

    def test_el_bloqueo_caduca_para_poder_detectar_un_cambio_de_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            viejo = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            escribir(root / "data" / "datos_profesionales.json", {"proveedores": {"api_football": {
                "plan_no_cubre_season": {
                    "season": datos_profesionales.temporada_api_football(),
                    "comprobado_en": viejo, "motivo": "plan",
                }}}})
            self.assertIsNone(datos_profesionales.bloqueo_plan_vigente(root))

    def test_temporada_objetivo_de_enero_a_junio(self):
        self.assertEqual(datos_profesionales.temporada_objetivo(datetime(2027, 2, 10)), "2026/2027")
        self.assertEqual(datos_profesionales.temporada_objetivo(datetime(2026, 11, 27)), "2026/2027")
        self.assertEqual(datos_profesionales.temporada_objetivo(datetime(2027, 7, 1)), "2027/2028")


# --------------------------------------------------------------------------
# 191 / 227: monitor de temporadas
# --------------------------------------------------------------------------

class MonitorTemporadasTests(unittest.TestCase):
    SIGUIENTE = {"inicio": 2027, "slug": "2027_2028"}

    def test_indicios_de_laliga_en_noviembre_no_detectan_la_temporada_siguiente(self):
        self.assertFalse(monitor.temporada_siguiente_detectada(
            False, True, self.SIGUIENTE, hoy=date(2026, 11, 27)))

    def test_football_data_con_partidos_vale_siempre(self):
        self.assertTrue(monitor.temporada_siguiente_detectada(
            True, False, self.SIGUIENTE, hoy=date(2026, 11, 27)))

    def test_laliga_cuenta_cuando_ya_puede_existir_el_calendario(self):
        self.assertTrue(monitor.temporada_siguiente_detectada(
            False, True, self.SIGUIENTE, hoy=date(2027, 7, 5)))
        self.assertFalse(monitor.temporada_siguiente_detectada(
            False, False, self.SIGUIENTE, hoy=date(2027, 7, 5)))


# --------------------------------------------------------------------------
# 86 / 100 / 113 / 188: competiciones
# --------------------------------------------------------------------------

CATS = {
    "primera": {resolver.normalizar(n) for n in (
        "Real Racing Club de Santander", "Villarreal CF", "Real Sociedad de Futbol", "Getafe CF")},
    "segunda": {resolver.normalizar(n) for n in (
        "Real Sociedad B", "CD Tenerife", "Real Sporting de Gijon", "Girona FC", "Real Zaragoza")},
    "mundial": set(),
    "selecciones": set(),
}


class ResolverCompeticionesTests(unittest.TestCase):
    def test_nombres_reescritos_por_la_fuente_siguen_siendo_liga_espanola(self):
        casos = [
            ("R. Santander", "Villarreal CF", "primera_division"),
            ("R. Santander", "Real Sociedad de Futbol", "primera_division"),
            ("R. Sociedad B", "Tenerife", "segunda_division"),
            ("R. Sociedad B", "Sporting Gijon", "segunda_division"),
        ]
        for local, visitante, esperado in casos:
            info = resolver.resolver({"local": local, "visitante": visitante}, CATS)
            self.assertEqual(info["competicion"], esperado, (local, visitante))

    def test_un_club_extranjero_no_se_cuela_por_los_alias(self):
        info = resolver.resolver({"local": "Sporting CP", "visitante": "Villarreal CF"}, CATS)
        self.assertEqual(info["competicion"], "liga_extranjera")

    def test_segunda_pasada_sin_cambios_no_reescribe_el_fichero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jornada_25.json"
            escribir(path, {"jornada": 25, "partidos": [
                {"num": 1, "local": "R. Santander", "visitante": "Villarreal CF", "fecha": "2026-11-28"}]})
            _, cambiado = resolver.anotar_archivo(path, CATS)
            self.assertTrue(cambiado)
            primera = path.read_text(encoding="utf-8")
            with mock.patch.object(resolver, "ahora", return_value="2099-01-01T00:00:00+00:00"):
                _, cambiado = resolver.anotar_archivo(path, CATS)
            self.assertFalse(cambiado)
            self.assertEqual(path.read_text(encoding="utf-8"), primera)

    def test_jornada_de_otra_temporada_no_se_reetiqueta_con_la_tabla_actual(self):
        # Girona-Elche de Primera 25/26; hoy el Girona esta en Segunda.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jornada_60.json"
            escribir(path, {"jornada": 60, "partidos": [
                {"num": 1, "local": "Girona FC", "visitante": "Elche CF", "fecha": "2026-05-03",
                 "competicion_resuelta": "primera_division"}]})
            data, _ = resolver.anotar_archivo(path, CATS, congelar=True)
            self.assertEqual(data["partidos"][0]["competicion_resuelta"], "primera_division")
            data, _ = resolver.anotar_archivo(path, CATS, congelar=False)
            self.assertEqual(data["partidos"][0]["competicion_resuelta"], "liga_extranjera")

    def test_espejo_congelado_o_de_jornada_cerrada_no_se_anota(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            jornadas = base / "jornadas"
            partidos = [
                {"num": i + 1, "local": f"L{i}", "visitante": f"V{i}", "fecha": "2026-11-28",
                 "signo_oficial": "Pendiente"} for i in range(14)
            ]
            escribir(jornadas / "jornada_25.json", {"jornada": 25, "partidos": partidos})
            cerrados = [dict(p, signo_oficial="1", fecha="2026-11-22") for p in partidos]
            escribir(jornadas / "jornada_24.json", {"jornada": 24, "partidos": cerrados})
            viva = base / "pred_25.json"
            escribir(viva, {"jornada": 25, "partidos": partidos})
            congelada = base / "pred_25c.json"
            escribir(congelada, {"jornada": 25, "partidos": partidos, "prediccion_congelada_al_cierre": True})
            cerrada = base / "pred_24.json"
            escribir(cerrada, {"jornada": 24, "partidos": cerrados})
            with mock.patch.object(resolver, "JORNADAS", jornadas):
                hoy = date(2026, 11, 27)
                self.assertTrue(resolver.prediccion_anotable(viva, hoy=hoy))
                self.assertFalse(resolver.prediccion_anotable(congelada, hoy=hoy))
                self.assertFalse(resolver.prediccion_anotable(cerrada, hoy=hoy))


# --------------------------------------------------------------------------
# 126 / 173, 171, 172, 193
# --------------------------------------------------------------------------

class SincronizarResultadosTests(unittest.TestCase):
    def test_un_confirmado_de_clubes_fuera_del_mundial_no_es_fuente(self):
        with tempfile.TemporaryDirectory() as tmp:
            mundial = Path(tmp) / "mundial.json"
            escribir(mundial, {"resultados": [
                {"fecha": "2026-11-22", "local": "R. Santander", "visitante": "Real Sociedad de Futbol",
                 "resultado": "2-0", "confianza": "confirmado"},
                {"fecha": "2026-06-20", "local": "Espana", "visitante": "Uruguay",
                 "resultado": "1-0", "confianza": "confirmado"},
            ]})
            with mock.patch.object(sincronizar, "MUNDIAL", mundial),                  mock.patch.object(sincronizar, "ROOT", Path(tmp)), \
                 mock.patch.object(sincronizar, "HISTORIAL_PRIMERA", Path(tmp) / "no1.json"), \
                 mock.patch.object(sincronizar, "HISTORIAL_SEGUNDA", Path(tmp) / "no2.json"):
                fuentes = sincronizar.cargar_fuentes_confirmadas()
            self.assertEqual(len(fuentes), 1)
            self.assertNotIn("santander", json.dumps(fuentes).lower())


class DetallesPartidosTests(unittest.TestCase):
    def test_los_porcentajes_de_tecnicos_se_llaman_por_su_nombre(self):
        resumen = detalles.resumir_partido(
            {"tecnico1": 50, "tecnicoX": 30, "tecnico2": 20, "local": "A", "visitante": "B"}, 0)
        self.assertIn("prob_tecnicos", resumen)
        self.assertEqual(resumen["prob_tecnicos"], resumen["prob_lae"])


class ClasificacionesTests(unittest.TestCase):
    def _tablas(self, primera):
        return {
            "primera": [{"equipo": primera}],
            "segunda": [
                {"equipo": "CD Leganes", "pj": 10, "e": 2, "puntos": 12, "dg": 0, "gf": 5},
                {"equipo": "SD Huesca", "pj": 10, "e": 3, "puntos": 9, "dg": 0, "gf": 4},
            ],
        }

    def test_la_correccion_leganes_huesca_no_se_aplica_fuera_de_25_26(self):
        tablas = clasificaciones.aplicar_correcciones_resultados(
            self._tablas("Real Racing Club de Santander"), hoy=date(2026, 11, 27))
        self.assertEqual([e["pj"] for e in tablas["segunda"]], [10, 10])
        # tabla 'tipo 25/26' (sin Racing) pero con fecha posterior: tampoco
        tablas = clasificaciones.aplicar_correcciones_resultados(
            self._tablas("Girona FC"), hoy=date(2027, 10, 1))
        self.assertEqual([e["pj"] for e in tablas["segunda"]], [10, 10])

    def test_dentro_de_25_26_se_sigue_aplicando(self):
        tablas = clasificaciones.aplicar_correcciones_resultados(
            self._tablas("Girona FC"), hoy=date(2026, 5, 20))
        self.assertEqual(sorted(e["pj"] for e in tablas["segunda"]), [11, 11])

    def test_la_publica_hereda_y_limpia_la_marca_de_dato_conservado(self):
        oficial = {"primera": [], "segunda": [], "validado_en": "2026-11-20T10:00:00",
                   "conserva_datos_previos": True, "aviso": "x", "ultimo_intento": "2026-11-27T10:00:00"}
        publica = clasificaciones.fusionar_clasificacion_publica(oficial, {})
        self.assertTrue(publica["conserva_datos_previos"])
        self.assertEqual(publica["validado_en"], "2026-11-20T10:00:00")
        oficial_ok = {"primera": [], "segunda": [], "validado_en": "2026-11-27T12:00:00"}
        publica = clasificaciones.fusionar_clasificacion_publica(oficial_ok, publica)
        self.assertNotIn("conserva_datos_previos", publica)
        self.assertNotIn("aviso", publica)


class PrepararTemporadaTests(unittest.TestCase):
    def test_real_madrid_y_real_sociedad_se_reconocen(self):
        self.assertEqual(preparar.canonico("Real Madrid"), "Real Madrid CF")
        self.assertEqual(preparar.canonico("Real Sociedad"), "Real Sociedad de Futbol")


if __name__ == "__main__":
    unittest.main()
