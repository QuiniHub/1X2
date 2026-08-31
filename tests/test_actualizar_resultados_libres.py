import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_resultados_libres as arl


def evento(local, visitante, hg=None, ag=None, status="Match Finished", fecha="2026-08-16", temporada=None):
    return {
        "strHomeTeam": local,
        "strAwayTeam": visitante,
        "intHomeScore": hg,
        "intAwayScore": ag,
        "strStatus": status,
        "dateEvent": fecha,
        "strSeason": temporada if temporada is not None else arl.TEMPORADA_THESPORTSDB,
    }


def respuesta_ok(payload):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


class ParsearEventosThesportsdbTests(unittest.TestCase):
    def test_partido_terminado_calcula_resultado_y_ganador(self):
        eventos = [evento("Real Sociedad B", "Castellon", 0, 1)]
        salida = arl._parsear_eventos_thesportsdb("Segunda División", eventos)
        self.assertEqual(salida[0]["resultado"], "0-1")
        self.assertEqual(salida[0]["ganador"], "Castellon")

    def test_partido_sin_jugar_no_tiene_resultado(self):
        eventos = [evento("Elche", "Deportivo", None, None, status="Not Started")]
        salida = arl._parsear_eventos_thesportsdb("La Liga", eventos)
        self.assertIsNone(salida[0]["resultado"])
        self.assertIsNone(salida[0]["ganador"])

    def test_empate_no_tiene_ganador(self):
        eventos = [evento("Cadiz", "Celta Fortuna", 0, 0)]
        salida = arl._parsear_eventos_thesportsdb("Segunda División", eventos)
        self.assertEqual(salida[0]["resultado"], "0-0")
        self.assertIsNone(salida[0]["ganador"])


class ObtenerThesportsdbPorRondasTests(unittest.TestCase):
    """Bug real (17/08/2026): eventspastleague.php solo da el ULTIMO
    partido de la liga -el calendario oficial necesita la jornada
    completa (ej. Real Sociedad B 0-1 Castellon, que la Quiniela no
    habia elegido esa semana y por tanto no aparecia en ningun sitio).
    eventsround.php si trae la jornada entera, pero exige recorrer
    varias rondas y el id de Segunda en THESPORTSDB_LIGAS estaba mal
    (4336 es una liga griega, el correcto es 4400)."""

    def test_segunda_usa_el_id_correcto_no_el_de_la_liga_griega(self):
        self.assertEqual(arl.THESPORTSDB_LIGAS["Segunda División"], "4400")

    def test_pide_una_ronda_por_cada_numero_configurado(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"events": [evento("A", "B", 1, 0)]})
            resultados = arl.obtener_thesportsdb_por_rondas("La Liga", "4335", (1, 2))
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(resultados), 2)

    def test_combina_los_partidos_de_todas_las_rondas_pedidas(self):
        respuestas = [
            respuesta_ok({"events": [evento("Real Sociedad B", "Castellon", 0, 1)]}),
            respuesta_ok({"events": [evento("Real Oviedo", "Granada", 0, 0)]}),
        ]
        with patch("actualizar_resultados_libres.requests.get", side_effect=respuestas):
            resultados = arl.obtener_thesportsdb_por_rondas("Segunda División", "4400", (1, 2))
        equipos = {(r["local"], r["visitante"]) for r in resultados}
        self.assertIn(("Real Sociedad B", "Castellon"), equipos)
        self.assertIn(("Real Oviedo", "Granada"), equipos)

    def test_error_de_red_en_una_ronda_no_rompe_las_demas(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                Exception("timeout"),
                respuesta_ok({"events": [evento("A", "B", 2, 1)]}),
            ]
            resultados = arl.obtener_thesportsdb_por_rondas("La Liga", "4335", (1, 2))
        self.assertEqual(len(resultados), 1)


class ParesEsperadosCalendarioTests(unittest.TestCase):
    """pares_esperados_calendario() lee de calendario_primera.json/segunda.json
    ya sembrados (ver actualizar_ligas_football_data.py) para saber que
    partidos DEBERIAN existir en cada ronda -sin esto, obtener_thesportsdb_
    backfill() no tendria forma de saber que le falta algo a eventsround.php."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._orig = dict(arl.CALENDARIO_SEMBRADO)
        arl.CALENDARIO_SEMBRADO = {"La Liga": base / "calendario_primera.json"}
        (base / "calendario_primera.json").write_text(json.dumps({
            "jornadas": [
                {"jornada": 1, "partidos": [
                    {"local": "Deportivo Alaves", "visitante": "Getafe CF"},
                    {"local": "Club Atletico de Madrid", "visitante": "Malaga CF"},
                ]},
                {"jornada": 2, "partidos": [
                    {"local": "Athletic Club", "visitante": "Sevilla FC"},
                ]},
            ]
        }), encoding="utf-8")

    def tearDown(self):
        arl.CALENDARIO_SEMBRADO = self._orig
        self._tmp.cleanup()

    def test_devuelve_los_pares_de_las_rondas_pedidas(self):
        pares = arl.pares_esperados_calendario("La Liga", (1,))
        self.assertEqual(pares, [("Deportivo Alaves", "Getafe CF"), ("Club Atletico de Madrid", "Malaga CF")])

    def test_combina_varias_rondas(self):
        pares = arl.pares_esperados_calendario("La Liga", (1, 2))
        self.assertEqual(len(pares), 3)

    def test_liga_sin_calendario_sembrado_devuelve_vacio(self):
        self.assertEqual(arl.pares_esperados_calendario("Segunda División", (1,)), [])

    def test_pares_ya_resueltos_devuelve_solo_los_que_tienen_resultado_real(self):
        # Bug real (31/08/2026): el backfill por equipo gastaba su tope de
        # pares en huecos de eventsround.php que football-data.co.uk ya
        # habia resuelto en el calendario -el unico par sin resolver de
        # verdad (Andorra-Eibar) quedaba fuera del cupo.
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "SD Eibar", "visitante": "Real Valladolid CF", "resultado": "1-0"},
                {"local": "FC Andorra", "visitante": "SD Eibar", "resultado": ""},
                {"local": "Burgos CF", "visitante": "Real Sociedad B", "resultado": "Pendiente"},
            ]}]
        }), encoding="utf-8")
        resueltos = arl.pares_ya_resueltos_calendario("La Liga", (1,))
        self.assertEqual(resueltos, {(arl._clave_equipo("SD Eibar"), arl._clave_equipo("Real Valladolid CF"))})

    def test_con_fecha_devuelve_tambien_la_fecha_del_partido(self):
        # Necesario para que el backfill por equipo pueda saltarse partidos
        # que aun no se han jugado (la causa real del 429 del 31/08/2026:
        # gastar cupo de API buscando resultados de partidos futuros).
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "Deportivo Alaves", "visitante": "Getafe CF", "fecha": "2026-08-15"},
                {"local": "Club Atletico de Madrid", "visitante": "Malaga CF"},
            ]}]
        }), encoding="utf-8")
        pares = arl.pares_esperados_calendario("La Liga", (1,), con_fecha=True)
        self.assertEqual(pares, [
            ("Deportivo Alaves", "Getafe CF", "2026-08-15"),
            ("Club Atletico de Madrid", "Malaga CF", ""),
        ])


class RondasAConsultarTests(unittest.TestCase):
    """Bug real confirmado el 29/08/2026: RONDAS_A_CONSULTAR era una tupla
    fija (1, 2) desde el arranque de temporada -en cuanto empezo a jugarse
    la Jornada 3 (Alaves 1-0 Villarreal, viernes 28/08), el pipeline dejo
    de mirar esa ronda por completo, ni en el fetch normal ni en el propio
    backfill de huecos, aunque el resultado ya estaba disponible en
    TheSportsDB desde el primer momento."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._orig = dict(arl.CALENDARIO_OFICIAL_ESTATICO)
        arl.CALENDARIO_OFICIAL_ESTATICO = {"La Liga": base / "calendario_1a_2627.json"}
        (base / "calendario_1a_2627.json").write_text(json.dumps({
            "jornadas": [
                {"num": 1, "fecha": "2026-08-16"},
                {"num": 2, "fecha": "2026-08-23"},
                {"num": 3, "fecha": "2026-08-30"},
                {"num": 4, "fecha": "2026-09-06"},
            ]
        }), encoding="utf-8")

    def tearDown(self):
        arl.CALENDARIO_OFICIAL_ESTATICO = self._orig
        self._tmp.cleanup()

    def test_incluye_la_ronda_recien_empezada(self):
        # 29/08: la jornada 3 (fecha oficial 30/08) ya se esta jugando de
        # verdad (el primer partido fue el 28/08) y debe estar cubierta.
        hoy = datetime(2026, 8, 29).date()
        self.assertEqual(arl.rondas_a_consultar("La Liga", hoy=hoy), (2, 3))

    def test_no_repite_rondas_ya_muy_antiguas(self):
        hoy = datetime(2026, 8, 29).date()
        self.assertNotIn(1, arl.rondas_a_consultar("La Liga", hoy=hoy, ventana_dias=9))

    def test_incluye_la_ronda_que_esta_a_punto_de_empezar(self):
        # Margen de +2 dias: si la jornada empieza pasado mañana, hay que
        # empezar a consultarla ya (los partidos de viernes de una jornada
        # con fecha "oficial" en domingo).
        hoy = datetime(2026, 9, 4).date()
        self.assertIn(4, arl.rondas_a_consultar("La Liga", hoy=hoy))

    def test_sin_calendario_estatico_cae_al_respaldo_minimo(self):
        arl.CALENDARIO_OFICIAL_ESTATICO = {"La Liga": Path("/no/existe.json")}
        self.assertEqual(arl.rondas_a_consultar("La Liga", hoy=datetime(2026, 8, 29).date()), (1, 2))


class NombreBusquedaCortoTests(unittest.TestCase):
    """Bug real (22/08/2026): el primer intento (quitar solo siglas de 2-3
    letras al principio) no cubria "Club Atletico de Madrid" -no empieza
    por ninguna sigla conocida, empieza por "Club "- y Atletico-Malaga
    desaparecio del calendario en produccion aunque el partido ya estaba
    jugado y cerrado. Sustituido por un mapa explicito de los 42 equipos."""

    def test_equipos_del_mapa_explicito(self):
        self.assertEqual(arl._nombre_busqueda_corto("Club Atletico de Madrid"), "Atletico Madrid")
        self.assertEqual(arl._nombre_busqueda_corto("Malaga CF"), "Malaga")
        self.assertEqual(arl._nombre_busqueda_corto("UD Almeria"), "Almeria")
        self.assertEqual(arl._nombre_busqueda_corto("CD Eldense"), "Eldense")
        self.assertEqual(arl._nombre_busqueda_corto("RCD Mallorca"), "Mallorca")
        self.assertEqual(arl._nombre_busqueda_corto("Real Sporting de Gijon"), "Sporting de Gijon")

    def test_equipo_desconocido_usa_el_respaldo_de_siglas(self):
        # Si aparece un equipo nuevo (ascenso/descenso futuro) que aun no
        # este en el mapa, se aplica el respaldo generico de siglas.
        self.assertEqual(arl._nombre_busqueda_corto("UD Un Equipo Nuevo"), "Un Equipo Nuevo")
        self.assertEqual(arl._nombre_busqueda_corto("Atletico Madrid"), "Atletico Madrid")


class ObtenerThesportsdbBackfillTests(unittest.TestCase):
    """Bug real (22/08/2026): 6 de los 11 partidos de la Jornada 1 de
    Segunda faltaban en eventsround.php sin haberse aplazado nunca -el
    mismo problema que ya se vio con Atletico-Malaga (19/08) pero sin
    ningun aplazamiento real detras, asi que la lista fija de "aplazados
    conocidos" del fix anterior no lo cubria. obtener_thesportsdb_backfill()
    generaliza eso: compara contra el calendario oficial ya sembrado y solo
    pregunta por lo que eventsround.php no trajo en absoluto."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._orig = dict(arl.CALENDARIO_SEMBRADO)
        arl.CALENDARIO_SEMBRADO = {"La Liga": base / "calendario_primera.json"}
        (base / "calendario_primera.json").write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "Deportivo Alaves", "visitante": "Getafe CF"},
                {"local": "Club Atletico de Madrid", "visitante": "Malaga CF"},
            ]}]
        }), encoding="utf-8")

    def tearDown(self):
        arl.CALENDARIO_SEMBRADO = self._orig
        self._tmp.cleanup()

    def test_solo_busca_los_pares_que_eventsround_no_trajo(self):
        ya_obtenidos = [{"local": "Deportivo Alaves", "visitante": "Getafe CF", "resultado": "3-0"}]
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"event": [evento("Atletico Madrid", "Malaga", 2, 0)]})
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), ya_obtenidos)
        mock_get.assert_called_once()
        self.assertEqual(resultados[0]["resultado"], "2-0")

    def test_no_repite_llamada_para_un_partido_ya_obtenido_con_nombre_acentuado(self):
        # Bug real (29/08/2026): TheSportsDB devuelve "Alavés" (con acento)
        # mientras que el calendario sembrado usa "Alaves" (sin acento) -sin
        # quitar acentos en _clave_equipo(), estas dos claves no coincidian
        # y el partido, YA encontrado por eventsround.php, se trataba igual
        # como un "hueco" y disparaba una busqueda de backfill innecesaria.
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "Deportivo Alaves", "visitante": "Getafe CF"},
            ]}]
        }), encoding="utf-8")
        ya_obtenidos = [{"local": "Deportivo Alavés", "visitante": "Getafe CF", "resultado": "3-0"}]
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), ya_obtenidos)
        mock_get.assert_not_called()
        self.assertEqual(resultados, [])

    def test_descarta_eventos_de_otra_temporada(self):
        # Bug real (29/08/2026): searchevents.php busca por nombre de
        # equipo sin acotar temporada -"Alaves vs Villarreal" devolvio,
        # ademas del partido real de esta temporada, uno de 2024 con
        # marcador distinto, y se aceptaron los dos sin filtrar.
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "Deportivo Alaves", "visitante": "Villarreal CF"},
            ]}]
        }), encoding="utf-8")
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"event": [
                evento("Deportivo Alaves", "Villarreal", 1, 1, fecha="2024-02-10", temporada="2023-2024"),
                evento("Deportivo Alaves", "Villarreal", 1, 0, fecha="2026-08-28"),
            ]})
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), [])
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["resultado"], "1-0")
        self.assertEqual(resultados[0]["fecha"], "2026-08-28")

    def test_no_repite_llamada_para_un_partido_que_eventsround_ya_trajo_aunque_este_pendiente(self):
        # Si eventsround.php SI menciono el partido (aunque siga sin
        # resultado, un partido futuro de verdad), no hace falta gastar
        # una llamada extra en buscarlo -solo se rellenan huecos reales.
        ya_obtenidos = [
            {"local": "Deportivo Alaves", "visitante": "Getafe CF", "resultado": "3-0"},
            {"local": "Club Atletico de Madrid", "visitante": "Malaga CF", "resultado": None},
        ]
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), ya_obtenidos)
        mock_get.assert_not_called()
        self.assertEqual(resultados, [])

    def test_par_sin_evento_encontrado_no_rompe_los_demas(self):
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "X", "visitante": "Y"},
                {"local": "A", "visitante": "B"},
            ]}]
        }), encoding="utf-8")
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            # "X vs Y" no tiene siglas de club que quitar, asi que la
            # consulta corta y la completa son identicas -se intenta dos
            # veces (ambas vacias) antes de pasar al siguiente par.
            mock_get.side_effect = [
                respuesta_ok({"event": None}),
                respuesta_ok({"event": None}),
                respuesta_ok({"event": [evento("A", "B", 1, 0)]}),
            ]
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), [])
        self.assertEqual(len(resultados), 1)

    def test_reintenta_sin_siglas_de_club_si_el_nombre_completo_no_encuentra_nada(self):
        # Bug real (22/08/2026): searchevents.php no encuentra "UD Almeria
        # vs CD Eldense" (nombres canonicos, con siglas) pero si "Almeria
        # vs Eldense" (sin siglas) -se prueba primero la version corta.
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "UD Almeria", "visitante": "CD Eldense"},
            ]}]
        }), encoding="utf-8")
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"event": [evento("Almeria", "Eldense", 3, 0)]})
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), [])
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs["params"]["e"], "Almeria vs Eldense")
        self.assertEqual(resultados[0]["resultado"], "3-0")

    def test_error_de_red_en_un_par_no_rompe_los_demas(self):
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "X", "visitante": "Y"},
                {"local": "A", "visitante": "B"},
            ]}]
        }), encoding="utf-8")
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [Exception("timeout"), respuesta_ok({"event": [evento("A", "B", 1, 0)]})]
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), [])
        self.assertEqual(len(resultados), 1)


def equipo_busqueda(id_team, nombre, liga="Spanish La Liga 2"):
    return {"idTeam": id_team, "strTeam": nombre, "strLeague": liga}


def evento_completo(local, visitante, hg, ag, id_league="4400", temporada=None, status="FT"):
    return {
        "strHomeTeam": local,
        "strAwayTeam": visitante,
        "intHomeScore": hg,
        "intAwayScore": ag,
        "strStatus": status,
        "dateEvent": "2026-08-30",
        "idLeague": id_league,
        "strSeason": temporada if temporada is not None else arl.TEMPORADA_THESPORTSDB,
    }


class ObtenerThesportsdbBackfillPorEquipoTests(unittest.TestCase):
    """Bug real (31/08/2026): "FC Andorra vs Eibar" (Jornada 3 de Segunda)
    no aparecia ni en eventsround.php ni en searchevents.php (la busqueda
    de texto libre no reconoce esa cadena exacta, confirmado en vivo:
    0 resultados) pese a que el partido SI existe en TheSportsDB. Las
    clasificaciones oficiales (AS.com) ya contaban el partido, pero
    calendario_segunda.json se quedaba con "Pendiente" indefinidamente."""

    def test_encuentra_el_partido_via_ultimos_eventos_del_equipo(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                respuesta_ok({"teams": [equipo_busqueda("138280", "FC Andorra")]}),
                respuesta_ok({"results": [evento_completo("FC Andorra", "Eibar", 0, 1)]}),
            ]
            resultados = arl.obtener_thesportsdb_backfill_por_equipo(
                "Segunda División", "4400", [("FC Andorra", "SD Eibar")]
            )
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["resultado"], "0-1")

    def test_ignora_eventos_de_un_equipo_homonimo_de_otra_categoria(self):
        # Bug potencial: "RCD Mallorca" (nuestro calendario simulado) puede
        # resolver via searchteams.php a "Mallorca B", el filial real que
        # juega en una categoria distinta (Segunda RFEF, no Segunda
        # Division) -sus ultimos partidos tienen un idLeague diferente y
        # deben descartarse, no colarse como si fueran el partido buscado.
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                respuesta_ok({"teams": [equipo_busqueda("146799", "Mallorca B", liga="Spanish Segunda RFEF Group 3")]}),
                respuesta_ok({"results": [
                    evento_completo("Mallorca B", "Ceuta B", 2, 1, id_league="5001")
                ]}),
                respuesta_ok({"teams": []}),
            ]
            resultados = arl.obtener_thesportsdb_backfill_por_equipo(
                "Segunda División", "4400", [("RCD Mallorca", "AD Ceuta FC")]
            )
        self.assertEqual(resultados, [])

    def test_descarta_eventos_de_otra_temporada(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                respuesta_ok({"teams": [equipo_busqueda("138280", "FC Andorra")]}),
                respuesta_ok({"results": [
                    evento_completo("FC Andorra", "Eibar", 2, 1, temporada="2024-2025"),
                ]}),
                respuesta_ok({"teams": [equipo_busqueda("134626", "Eibar")]}),
                respuesta_ok({"results": [
                    evento_completo("FC Andorra", "Eibar", 2, 1, temporada="2024-2025"),
                ]}),
            ]
            resultados = arl.obtener_thesportsdb_backfill_por_equipo(
                "Segunda División", "4400", [("FC Andorra", "SD Eibar")]
            )
        self.assertEqual(resultados, [])

    def test_par_sin_equipo_encontrado_no_rompe_los_demas(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                respuesta_ok({"teams": []}),
                respuesta_ok({"teams": []}),
                respuesta_ok({"teams": [equipo_busqueda("138161", "Burgos")]}),
                respuesta_ok({"results": [evento_completo("Burgos", "Real Sociedad B", 1, 1)]}),
            ]
            resultados = arl.obtener_thesportsdb_backfill_por_equipo(
                "Segunda División", "4400",
                [("X", "Y"), ("Burgos CF", "Real Sociedad B")],
            )
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["resultado"], "1-1")

    def test_busca_el_nombre_completo_no_el_recortado_de_siglas(self):
        # Bug real (31/08/2026): "FC Andorra" recortado a "Andorra" (el
        # respaldo de siglas que SI funciona bien en searchevents.php)
        # resuelve en searchteams.php a la SELECCION NACIONAL de Andorra,
        # no al club -searchteams.php necesita el nombre oficial completo.
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"teams": []})
            arl.obtener_thesportsdb_backfill_por_equipo(
                "Segunda División", "4400", [("FC Andorra", "SD Eibar")]
            )
        self.assertEqual(mock_get.call_args_list[0].kwargs["params"]["t"], "FC Andorra")

    def test_un_429_espera_una_vez_y_se_recupera(self):
        # Bug real (31/08/2026, segunda vuelta): el limite de la clave
        # publica de TheSportsDB es POR MINUTO, y el propio ciclo (rondas +
        # searchevents) lo agota justo antes de llegar aqui -el primer 429
        # no significa "API caida" sino "espera a que se reinicie la
        # ventana". Confirmado en vivo: la misma peticion daba 429 durante
        # el ciclo y 200 un minuto despues.
        resp_429 = MagicMock()
        resp_429.status_code = 429
        with patch("actualizar_resultados_libres.requests.get") as mock_get, \
                patch("actualizar_resultados_libres.time.sleep") as mock_sleep:
            mock_get.side_effect = [
                resp_429,
                respuesta_ok({"teams": [equipo_busqueda("138280", "FC Andorra")]}),
                respuesta_ok({"results": [evento_completo("FC Andorra", "Eibar", 0, 1)]}),
            ]
            resultados = arl.obtener_thesportsdb_backfill_por_equipo(
                "Segunda División", "4400", [("FC Andorra", "SD Eibar")]
            )
        mock_sleep.assert_called_once_with(arl.ESPERA_TRAS_429_SEGUNDOS)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["resultado"], "0-1")

    def test_un_segundo_429_tras_la_espera_si_detiene_la_pasada(self):
        # La espera es UNA por pasada -si tras esperar el minuto entero la
        # API sigue cortada, es un corte de verdad (no la ventana por
        # minuto) y seguir insistiendo par a par solo lo empeora.
        resp_429 = MagicMock()
        resp_429.status_code = 429
        with patch("actualizar_resultados_libres.requests.get") as mock_get, \
                patch("actualizar_resultados_libres.time.sleep") as mock_sleep:
            mock_get.return_value = resp_429
            resultados = arl.obtener_thesportsdb_backfill_por_equipo(
                "Segunda División", "4400",
                [("FC Andorra", "SD Eibar"), ("Burgos CF", "Real Sociedad B")],
            )
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()
        self.assertEqual(resultados, [])

    def test_no_supera_el_tope_de_pares_por_llamada(self):
        # Tope duro: no crece sin limite con el numero de partidos aun
        # pendientes de la ronda (la mayoria de "faltantes" en un ciclo real
        # son simplemente partidos que no se han jugado todavia, no huecos
        # de verdad -sin tope, cada ciclo gastaria el cupo entero de la API
        # gratuita en pares que de todas formas no van a encontrar nada).
        pares = [(f"Local{i}", f"Visitante{i}") for i in range(20)]
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"teams": []})
            arl.obtener_thesportsdb_backfill_por_equipo("Segunda División", "4400", pares)
        # 2 busquedas de equipo (local y visitante) por cada par permitido.
        self.assertLessEqual(mock_get.call_count, arl.LIMITE_BACKFILL_POR_EQUIPO * 2)


if __name__ == "__main__":
    unittest.main()
