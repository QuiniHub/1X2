import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aprender_patrones_competitivos as apc


def equipo_vivo(nombre, situacion="en_descenso_con_opciones"):
    return {"equipo": nombre, "objetivos_vivos": [{"estado": situacion}], "situacion_competitiva": situacion, "puntos": 10}


def equipo_cerrado(nombre, puntos=10):
    return {"equipo": nombre, "objetivos_vivos": [], "situacion_competitiva": "no_se_juega_nada_clasificatorio", "puntos": puntos}


def equipo_en_posicion(nombre, posicion):
    return {"equipo": nombre, "objetivos_vivos": [], "situacion_competitiva": "no_se_juega_nada_clasificatorio", "puntos": 0, "posicion": posicion}


def partido(local, visitante, gl, gv, fecha, temporada="2025/2026", **extra):
    signo = "1" if gl > gv else ("X" if gl == gv else "2")
    base = {
        "local": local, "visitante": visitante, "gl": gl, "gv": gv,
        "resultado": f"{gl}-{gv}", "signo": signo, "fecha": fecha, "temporada": temporada,
    }
    base.update(extra)
    return base


class TablaTests(unittest.TestCase):
    def test_aplicar_partido_reparte_puntos(self):
        tabla = apc.tabla_vacia()
        apc.aplicar_partido(tabla, "A", "B", 2, 0)
        apc.aplicar_partido(tabla, "A", "C", 1, 1)
        self.assertEqual(tabla["A"]["puntos"], 4)
        self.assertEqual(tabla["B"]["puntos"], 0)
        self.assertEqual(tabla["C"]["puntos"], 1)
        self.assertEqual(tabla["A"]["pj"], 2)

    def test_tabla_a_lista_ordenada_por_puntos_y_dg(self):
        tabla = apc.tabla_vacia()
        apc.aplicar_partido(tabla, "A", "B", 3, 0)
        apc.aplicar_partido(tabla, "C", "D", 1, 0)
        filas = apc.tabla_a_lista_ordenada(tabla)
        self.assertEqual(filas[0]["equipo"], "A")
        self.assertEqual(filas[0]["posicion"], 1)
        self.assertEqual(filas[0]["dg"], 3)

    def test_tabla_a_lista_ordenada_ignora_equipos_sin_jugar(self):
        tabla = apc.tabla_vacia()
        apc.aplicar_partido(tabla, "A", "B", 1, 0)
        _ = tabla["C"]
        nombres = [f["equipo"] for f in apc.tabla_a_lista_ordenada(tabla)]
        self.assertNotIn("C", nombres)


class ClasificacionHelpersTests(unittest.TestCase):
    def test_objetivo_cerrado_solo_si_no_hay_vivos(self):
        self.assertTrue(apc.objetivo_cerrado(equipo_cerrado("A")))
        self.assertFalse(apc.objetivo_cerrado(equipo_vivo("A")))
        self.assertFalse(apc.objetivo_cerrado(None))

    def test_necesidad_viva_requiere_objetivos_vivos(self):
        self.assertTrue(apc.necesidad_viva(equipo_vivo("A")))
        self.assertFalse(apc.necesidad_viva(equipo_cerrado("A")))

    def test_descenso_vivo_solo_en_situaciones_de_descenso(self):
        self.assertTrue(apc.descenso_vivo(equipo_vivo("A", "riesgo_descenso")))
        self.assertFalse(apc.descenso_vivo(equipo_vivo("A", "defiende_liderato")))
        self.assertFalse(apc.descenso_vivo(equipo_cerrado("A")))

    def test_tier_por_posicion_corta_en_el_10(self):
        self.assertEqual(apc.tier_por_posicion(equipo_en_posicion("A", 1)), "top10")
        self.assertEqual(apc.tier_por_posicion(equipo_en_posicion("A", 10)), "top10")
        self.assertEqual(apc.tier_por_posicion(equipo_en_posicion("A", 11)), "resto")
        self.assertEqual(apc.tier_por_posicion(equipo_en_posicion("A", 22)), "resto")

    def test_tier_por_posicion_sin_posicion_devuelve_none(self):
        self.assertIsNone(apc.tier_por_posicion(equipo_cerrado("A")))
        self.assertIsNone(apc.tier_por_posicion(None))


class AnalizarTemporadaHistoricaTests(unittest.TestCase):
    """Prueba el fix central: la situacion competitiva usada para juzgar cada
    dia debe reconstruirse ANTES de ese dia (con lo jugado hasta entonces),
    nunca con datos de fechas futuras ni con el snapshot de hoy."""

    def setUp(self):
        self._original = dict(apc.ANALIZADORES)
        self.llamadas = []

        def analizador_espia(tabla_previa):
            equipos_vistos = sorted(e["equipo"] for e in tabla_previa)
            self.llamadas.append(equipos_vistos)
            equipos = []
            for e in tabla_previa:
                if e["equipo"] == "Z" and e["puntos"] >= 3:
                    equipos.append(equipo_cerrado("Z", puntos=e["puntos"]))
                elif e["equipo"] == "Y":
                    equipos.append(equipo_vivo("Y"))
                else:
                    equipos.append({"equipo": e["equipo"], "objetivos_vivos": [], "situacion_competitiva": "no_se_juega_nada_clasificatorio", "puntos": e["puntos"]})
            return {"equipos": equipos}

        apc.ANALIZADORES = {"primera": analizador_espia, "segunda": analizador_espia}
        self.addCleanup(lambda: setattr(apc, "ANALIZADORES", self._original))

    def test_no_usa_resultados_futuros_para_juzgar_el_dia_actual(self):
        partidos = [
            partido("Z", "W", 3, 0, "2026-01-01"),
            partido("X", "Y", 3, 0, "2026-01-01"),
            partido("Y", "Z", 1, 1, "2026-01-08"),
        ]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", partidos, patrones)

        self.assertEqual(len(self.llamadas), 1, "el primer dia no tiene tabla previa -no se llama al analizador ese dia")
        self.assertEqual(self.llamadas[0], ["W", "X", "Y", "Z"], "la tabla previa al 01-08 solo refleja el 01-01")

        clave = "necesitado_local_vs_visitante_objetivo_cerrado"
        self.assertIn(clave, patrones)
        self.assertEqual(patrones[clave]["casos"], 1)
        self.assertEqual(patrones[clave]["sorpresas"], 1)

        clave_general = "equipo_necesitado_vs_equipo_sin_objetivo"
        self.assertIn(clave_general, patrones)
        self.assertEqual(patrones[clave_general]["casos"], 1)


class TopVsRestoPatronTests(unittest.TestCase):
    """El analizador-espia aqui es un "paso a traves": conserva la posicion
    real que ya calculo tabla_a_lista_ordenada(), sin objetivos vivos -asi
    se aisla el patron top10-vs-resto de los patrones de objetivos."""

    def setUp(self):
        self._original = dict(apc.ANALIZADORES)

        def analizador_pasa_posicion(tabla_previa):
            equipos = [
                {
                    "equipo": e["equipo"],
                    "objetivos_vivos": [],
                    "situacion_competitiva": "no_se_juega_nada_clasificatorio",
                    "puntos": e["puntos"],
                    "posicion": e["posicion"],
                }
                for e in tabla_previa
            ]
            return {"equipos": equipos}

        apc.ANALIZADORES = {"primera": analizador_pasa_posicion, "segunda": analizador_pasa_posicion}
        self.addCleanup(lambda: setattr(apc, "ANALIZADORES", self._original))

    def test_top10_local_vs_resto_visitante_se_registra(self):
        # Dia 1: fija las 12 posiciones -Equipo01/02 con 3 pts, Equipo03..10
        # con 1 pt (8 equipos, quedan en el top 10 junto a 01/02), Equipo11/12
        # con 0 pts (los unicos fuera del top 10).
        dia1 = [
            partido("Equipo01", "Equipo11", 3, 0, "2026-01-01"),
            partido("Equipo02", "Equipo12", 3, 0, "2026-01-01"),
            partido("Equipo03", "Equipo04", 1, 1, "2026-01-01"),
            partido("Equipo05", "Equipo06", 1, 1, "2026-01-01"),
            partido("Equipo07", "Equipo08", 1, 1, "2026-01-01"),
            partido("Equipo09", "Equipo10", 1, 1, "2026-01-01"),
        ]
        # Dia 2: el 1o de la tabla (Equipo01) recibe al 11o (Equipo11).
        dia2 = [partido("Equipo01", "Equipo11", 1, 1, "2026-01-08")]

        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", dia1 + dia2, patrones)

        clave = "top10_local_vs_resto_visitante"
        self.assertIn(clave, patrones)
        self.assertEqual(patrones[clave]["casos"], 1)
        self.assertEqual(patrones[clave]["sorpresas"], 1)  # empate ("X"), no gana el local del top 10


class RachaPerdedoraPatronTests(unittest.TestCase):
    """Regla 11 (feedback_metodo_prediccion_manual.md): un equipo con racha
    de derrotas no "rebota" mas de lo normal, rinde peor. No depende del
    contexto competitivo (objetivos/tier) -mismo truco de analizador vacio
    que TopVsRestoPatronTests para aislarlo del resto de patrones."""

    def setUp(self):
        self._original = dict(apc.ANALIZADORES)

        def analizador_vacio(tabla_previa):
            return {"equipos": []}

        apc.ANALIZADORES = {"primera": analizador_vacio, "segunda": analizador_vacio}
        self.addCleanup(lambda: setattr(apc, "ANALIZADORES", self._original))

    def test_visitante_con_3_derrotas_seguidas_que_pierde_otra_vez_no_es_sorpresa(self):
        partidos = [
            partido("Rival1", "Perdedor", 2, 0, "2026-01-01"),
            partido("Rival2", "Perdedor", 1, 0, "2026-01-08"),
            partido("Rival3", "Perdedor", 3, 0, "2026-01-15"),
            partido("Rival4", "Perdedor", 1, 0, "2026-01-22"),
        ]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", partidos, patrones)

        clave = "racha_perdedora_visitante_no_rebota"
        self.assertIn(clave, patrones)
        self.assertEqual(patrones[clave]["casos"], 1)
        self.assertEqual(patrones[clave]["sorpresas"], 0)

    def test_visitante_con_3_derrotas_seguidas_que_gana_si_cuenta_como_sorpresa(self):
        partidos = [
            partido("Rival1", "Perdedor", 2, 0, "2026-01-01"),
            partido("Rival2", "Perdedor", 1, 0, "2026-01-08"),
            partido("Rival3", "Perdedor", 3, 0, "2026-01-15"),
            partido("Rival4", "Perdedor", 0, 2, "2026-01-22"),
        ]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", partidos, patrones)

        clave = "racha_perdedora_visitante_no_rebota"
        self.assertEqual(patrones[clave]["casos"], 1)
        self.assertEqual(patrones[clave]["sorpresas"], 1)

    def test_local_con_3_derrotas_seguidas_se_registra_por_separado(self):
        partidos = [
            partido("Perdedor", "Rival1", 0, 2, "2026-01-01"),
            partido("Perdedor", "Rival2", 0, 1, "2026-01-08"),
            partido("Perdedor", "Rival3", 0, 3, "2026-01-15"),
            partido("Perdedor", "Rival4", 1, 1, "2026-01-22"),
        ]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", partidos, patrones)

        clave = "racha_perdedora_local_no_rebota"
        self.assertEqual(patrones[clave]["casos"], 1)
        self.assertEqual(patrones[clave]["sorpresas"], 0)  # empata, no gana -> no es rebote

    def test_menos_de_3_derrotas_seguidas_no_activa_el_patron(self):
        partidos = [
            partido("Rival1", "Equipo", 2, 0, "2026-01-01"),
            partido("Rival2", "Equipo", 1, 0, "2026-01-08"),
            partido("Rival3", "Equipo", 1, 1, "2026-01-15"),
        ]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", partidos, patrones)

        self.assertNotIn("racha_perdedora_visitante_no_rebota", patrones)


class RachaPerdedoraVsMotivacionRivalTests(unittest.TestCase):
    """Matiz pedido por Marc (2026-08) tras comprobar con datos reales que el
    Barcelona -ya campeon de LaLiga 2025/26 en la jornada 35- jugo con
    alineacion alternativa y perdio 2 de sus 3 ultimos partidos sin nada en
    juego: un "rebote" de la racha perdedora contra un rival SIN objetivo
    (que puede rotar) no prueba lo mismo que contra uno que se lo juega
    todo. El analizador-espia marca "RivalCerrado" con objetivo cerrado y
    cualquier otro equipo con objetivo vivo."""

    def setUp(self):
        self._original = dict(apc.ANALIZADORES)

        def analizador_espia(tabla_previa):
            equipos = []
            for e in tabla_previa:
                if e["equipo"] == "RivalCerrado":
                    equipos.append(equipo_cerrado("RivalCerrado", puntos=e["puntos"]))
                else:
                    equipos.append(equipo_vivo(e["equipo"]))
            return {"equipos": equipos}

        apc.ANALIZADORES = {"primera": analizador_espia, "segunda": analizador_espia}
        self.addCleanup(lambda: setattr(apc, "ANALIZADORES", self._original))

    def test_visitante_en_racha_ante_rival_local_sin_objetivo_se_separa(self):
        partidos = [
            partido("RivalCerrado", "Otro", 1, 1, "2025-12-25"),  # RivalCerrado ya jugo antes -aparece en tabla_previa del dia decisivo
            partido("Rival1", "Perdedor", 2, 0, "2026-01-01"),
            partido("Rival2", "Perdedor", 1, 0, "2026-01-08"),
            partido("Rival3", "Perdedor", 3, 0, "2026-01-15"),
            partido("RivalCerrado", "Perdedor", 0, 2, "2026-01-22"),  # gana el visitante -"rebote"
        ]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", partidos, patrones)

        clave = "racha_perdedora_visitante_no_rebota_rival_sin_objetivo"
        self.assertIn(clave, patrones)
        self.assertEqual(patrones[clave]["casos"], 1)
        self.assertEqual(patrones[clave]["sorpresas"], 1)  # rebota, pero el rival podia rotar
        self.assertNotIn("racha_perdedora_visitante_no_rebota_rival_motivado", patrones)

    def test_visitante_en_racha_ante_rival_local_motivado_se_separa(self):
        partidos = [
            partido("RivalMotivado", "Otro", 1, 1, "2025-12-25"),  # RivalMotivado ya jugo antes -aparece en tabla_previa del dia decisivo
            partido("Rival1", "Perdedor", 2, 0, "2026-01-01"),
            partido("Rival2", "Perdedor", 1, 0, "2026-01-08"),
            partido("Rival3", "Perdedor", 3, 0, "2026-01-15"),
            partido("RivalMotivado", "Perdedor", 1, 0, "2026-01-22"),  # pierde otra vez, rival se lo jugaba todo
        ]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", partidos, patrones)

        clave = "racha_perdedora_visitante_no_rebota_rival_motivado"
        self.assertIn(clave, patrones)
        self.assertEqual(patrones[clave]["casos"], 1)
        self.assertEqual(patrones[clave]["sorpresas"], 0)
        self.assertNotIn("racha_perdedora_visitante_no_rebota_rival_sin_objetivo", patrones)


class ProbabilidadImplicitaCuotasTests(unittest.TestCase):
    def test_normaliza_a_100_repartiendo_segun_1_sobre_cuota(self):
        p = {"cuota_1": 2.00, "cuota_x": 3.30, "cuota_2": 4.20}
        probs = apc.probabilidad_implicita_cuotas(p)
        self.assertAlmostEqual(sum(probs.values()), 100.0, places=3)
        # cuota mas baja (2.00) debe dar la probabilidad mas alta
        self.assertGreater(probs["1"], probs["X"])
        self.assertGreater(probs["X"], probs["2"])

    def test_sin_las_3_cuotas_devuelve_vacio(self):
        self.assertEqual(apc.probabilidad_implicita_cuotas({"cuota_1": 2.0}), {})


class BrechaTablaVsMercadoTests(unittest.TestCase):
    """Matiz pedido por Marc tras el fallo real de la jornada 74
    (Brommapojkarna-Hammarby, 2026-07-26): una brecha de tabla (top10 vs
    resto) no siempre viene con un margen real amplio detras. Version
    corregida tras un primer intento fallido (ver commit siguiente): al
    principio se comparaba "direccion tabla vs direccion mercado", pero el
    caso real tenia tabla Y mercado de acuerdo (los dos favorecian al equipo
    del top 10) -lo que de verdad bajaba la confianza era que la probabilidad
    implicita de mercado para ese favorito era corta (49-58%, no un margen
    amplio), no que el mercado señalara a otro signo. Por eso aqui se mide
    el MARGEN (probabilidad implicita), no la direccion. Reusa el mismo
    analizador-espia de TopVsRestoPatronTests para aislar el patron."""

    def setUp(self):
        self._original = dict(apc.ANALIZADORES)

        def analizador_pasa_posicion(tabla_previa):
            equipos = [
                {
                    "equipo": e["equipo"],
                    "objetivos_vivos": [],
                    "situacion_competitiva": "no_se_juega_nada_clasificatorio",
                    "puntos": e["puntos"],
                    "posicion": e["posicion"],
                }
                for e in tabla_previa
            ]
            return {"equipos": equipos}

        apc.ANALIZADORES = {"primera": analizador_pasa_posicion, "segunda": analizador_pasa_posicion}
        self.addCleanup(lambda: setattr(apc, "ANALIZADORES", self._original))

    def _dia1(self):
        # Mismas 12 posiciones que TopVsRestoPatronTests: Equipo01 queda 1o,
        # Equipo11 queda fuera del top 10.
        return [
            partido("Equipo01", "Equipo11", 3, 0, "2026-01-01"),
            partido("Equipo02", "Equipo12", 3, 0, "2026-01-01"),
            partido("Equipo03", "Equipo04", 1, 1, "2026-01-01"),
            partido("Equipo05", "Equipo06", 1, 1, "2026-01-01"),
            partido("Equipo07", "Equipo08", 1, 1, "2026-01-01"),
            partido("Equipo09", "Equipo10", 1, 1, "2026-01-01"),
        ]

    def test_margen_amplio_cuando_probabilidad_implicita_supera_el_umbral(self):
        # Equipo01 (top10, local) recibe a Equipo11 (resto) -favorito de tabla = "1".
        # Cuotas dan ~66% de probabilidad implicita a "1" -margen amplio, por encima
        # del umbral (55%).
        dia2 = [partido("Equipo01", "Equipo11", 1, 1, "2026-01-08", cuota_1=1.40, cuota_x=4.50, cuota_2=7.00)]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", self._dia1() + dia2, patrones)

        self.assertIn("brecha_tabla_margen_amplio_mercado", patrones)
        self.assertEqual(patrones["brecha_tabla_margen_amplio_mercado"]["casos"], 1)
        self.assertEqual(patrones["brecha_tabla_margen_amplio_mercado"]["sorpresas"], 1)  # empate, no gano el favorito
        self.assertNotIn("brecha_tabla_margen_estrecho_mercado", patrones)

    def test_margen_estrecho_cuando_probabilidad_implicita_no_llega_al_umbral(self):
        # Mismo enfrentamiento (Equipo01 top10 vs Equipo11 resto, favorito de tabla = "1"),
        # pero esta vez las cuotas dan solo ~48% de probabilidad implicita a "1" -mismo
        # favorito de tabla y de mercado, pero SIN margen real amplio. Este es el patron
        # del caso real de Brommapojkarna-Hammarby (J74): tabla y mercado de acuerdo,
        # pero probabilidad corta (49-58%, no >=55% con holgura real).
        dia2 = [partido("Equipo01", "Equipo11", 1, 2, "2026-01-08", cuota_1=2.00, cuota_x=3.30, cuota_2=4.20)]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", self._dia1() + dia2, patrones)

        self.assertIn("brecha_tabla_margen_estrecho_mercado", patrones)
        self.assertEqual(patrones["brecha_tabla_margen_estrecho_mercado"]["casos"], 1)
        self.assertEqual(patrones["brecha_tabla_margen_estrecho_mercado"]["sorpresas"], 1)  # gano el visitante ("2"), no el favorito de tabla
        self.assertNotIn("brecha_tabla_margen_amplio_mercado", patrones)

    def test_sin_cuotas_no_registra_ninguna_de_las_dos_claves_de_brecha(self):
        dia2 = [partido("Equipo01", "Equipo11", 1, 1, "2026-01-08")]  # sin cuota_1/x/2
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", self._dia1() + dia2, patrones)

        self.assertNotIn("brecha_tabla_margen_estrecho_mercado", patrones)
        self.assertNotIn("brecha_tabla_margen_amplio_mercado", patrones)
        # el patron base top10 si se registra siempre, con o sin cuotas
        self.assertIn("top10_local_vs_resto_visitante", patrones)


class CargarPartidosPorTemporadaTests(unittest.TestCase):
    def test_agrupa_y_ordena_por_temporada_y_fecha(self):
        historico = {
            "ligas": {
                "primera": {
                    "temporadas": {
                        "2024/2025": {"partidos": [
                            partido("B", "A", 1, 0, "2025-05-01", temporada="2024/2025"),
                            partido("A", "B", 2, 0, "2025-01-01", temporada="2024/2025"),
                        ]},
                        "2025/2026": {"partidos": [
                            partido("A", "B", 1, 1, "2026-01-01", temporada="2025/2026"),
                        ]},
                    }
                }
            }
        }
        bloques = apc.cargar_partidos_por_temporada(historico, "primera")
        self.assertEqual([t for t, _ in bloques], ["2024/2025", "2025/2026"])
        fechas_2425 = [p["fecha"] for _, partidos in bloques if _ == "2024/2025" for p in partidos]
        self.assertEqual(fechas_2425, ["2025-01-01", "2025-05-01"])

    def test_temporada_sin_partidos_se_omite(self):
        historico = {"ligas": {"primera": {"temporadas": {"2023/2024": {"partidos": []}}}}}
        self.assertEqual(apc.cargar_partidos_por_temporada(historico, "primera"), [])


class EnfrentamientosDirectosTests(unittest.TestCase):
    def test_favorito_por_cuotas_es_la_cuota_mas_baja(self):
        self.assertEqual(apc.favorito_por_cuotas({"cuota_1": 1.5, "cuota_x": 4.0, "cuota_2": 6.0}), "1")
        self.assertEqual(apc.favorito_por_cuotas({"cuota_1": 5.0, "cuota_x": 3.5, "cuota_2": 1.8}), "2")

    def test_favorito_por_cuotas_sin_datos_devuelve_none(self):
        self.assertIsNone(apc.favorito_por_cuotas({"cuota_1": None, "cuota_x": None, "cuota_2": None}))
        self.assertIsNone(apc.favorito_por_cuotas({}))

    def test_clave_par_equipos_es_simetrica(self):
        self.assertEqual(apc.clave_par_equipos("Real Madrid CF", "FC Barcelona"), apc.clave_par_equipos("Barcelona", "Real Madrid"))

    def test_analizar_enfrentamientos_directos_detecta_sorpresa_historica(self):
        historico = {
            "ligas": {
                "primera": {
                    "consolidado": {"partidos": [
                        partido("Real Madrid", "Getafe", 1, 2, "2024-01-01", cuota_1=1.2, cuota_x=6.0, cuota_2=10.0),
                        partido("Getafe", "Real Madrid", 0, 0, "2024-06-01", cuota_1=5.0, cuota_x=3.8, cuota_2=1.6),
                        partido("Real Madrid", "Getafe", 3, 0, "2025-01-01", cuota_1=1.15, cuota_x=6.5, cuota_2=12.0),
                    ]},
                },
                "segunda": {"consolidado": {"partidos": []}},
            }
        }
        resultado = apc.analizar_enfrentamientos_directos(historico)
        clave = apc.clave_par_equipos("Real Madrid", "Getafe")
        self.assertIn(clave, resultado)
        entrada = resultado[clave]
        self.assertEqual(entrada["casos_totales"], 3)
        self.assertEqual(entrada["casos_con_cuotas"], 3)
        self.assertEqual(entrada["sorpresas"], 2)  # 1er y 2o partido: favorito no gana
        self.assertAlmostEqual(entrada["tasa_sorpresa_historica"], 66.7, places=1)

    def test_tasa_none_si_no_hay_suficientes_casos_con_cuotas(self):
        historico = {"ligas": {"primera": {"consolidado": {"partidos": [
            partido("A", "B", 1, 0, "2024-01-01"),
        ]}}}}
        resultado = apc.analizar_enfrentamientos_directos(historico)
        clave = apc.clave_par_equipos("A", "B")
        self.assertIsNone(resultado[clave]["tasa_sorpresa_historica"])


if __name__ == "__main__":
    unittest.main()
