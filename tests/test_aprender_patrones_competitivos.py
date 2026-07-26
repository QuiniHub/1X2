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


class BrechaTablaVsMercadoTests(unittest.TestCase):
    """Matiz pedido por Marc tras el fallo real de la jornada 74
    (Brommapojkarna-Hammarby, 2026-07-26): una brecha de tabla (top10 vs
    resto) no siempre viene respaldada por el mercado. Reusa el mismo
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

    def test_brecha_confirmada_por_mercado_cuando_cuota_mas_baja_coincide_con_tabla(self):
        # Equipo01 (top10, local) recibe a Equipo11 (resto) -favorito de tabla = "1".
        # Cuota mas baja es cuota_1 -mercado tambien confirma al Equipo01 como favorito.
        dia2 = [partido("Equipo01", "Equipo11", 1, 1, "2026-01-08", cuota_1=1.40, cuota_x=4.50, cuota_2=7.00)]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", self._dia1() + dia2, patrones)

        self.assertIn("brecha_tabla_confirmada_por_mercado", patrones)
        self.assertEqual(patrones["brecha_tabla_confirmada_por_mercado"]["casos"], 1)
        self.assertEqual(patrones["brecha_tabla_confirmada_por_mercado"]["sorpresas"], 1)  # empate, no gano el favorito
        self.assertNotIn("brecha_tabla_sin_respaldo_mercado", patrones)

    def test_brecha_sin_respaldo_de_mercado_cuando_cuota_mas_baja_no_coincide_con_tabla(self):
        # Mismo enfrentamiento (Equipo01 top10 vs Equipo11 resto, favorito de tabla = "1"),
        # pero esta vez la cuota mas baja es la del empate -el mercado NO confirma al
        # favorito de tabla. Este es el caso real de Brommapojkarna-Hammarby (J74).
        dia2 = [partido("Equipo01", "Equipo11", 1, 2, "2026-01-08", cuota_1=2.20, cuota_x=2.05, cuota_2=3.40)]
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", self._dia1() + dia2, patrones)

        self.assertIn("brecha_tabla_sin_respaldo_mercado", patrones)
        self.assertEqual(patrones["brecha_tabla_sin_respaldo_mercado"]["casos"], 1)
        self.assertEqual(patrones["brecha_tabla_sin_respaldo_mercado"]["sorpresas"], 1)  # gano el visitante ("2"), no el favorito de tabla
        self.assertNotIn("brecha_tabla_confirmada_por_mercado", patrones)

    def test_sin_cuotas_no_registra_ninguna_de_las_dos_claves_de_brecha(self):
        dia2 = [partido("Equipo01", "Equipo11", 1, 1, "2026-01-08")]  # sin cuota_1/x/2
        patrones = defaultdict(apc.base_patron)
        apc.analizar_temporada_historica("primera", "2025/2026", self._dia1() + dia2, patrones)

        self.assertNotIn("brecha_tabla_sin_respaldo_mercado", patrones)
        self.assertNotIn("brecha_tabla_confirmada_por_mercado", patrones)
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
