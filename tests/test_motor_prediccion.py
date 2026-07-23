import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_prediccion_quiniela import (
    ajustar_por_datos_profesionales,
    ajustar_por_aprendizaje_propio,
    ajustar_por_lesiones_laliga,
    ajustar_por_mercado_losilla,
    buscar_lesiones_equipo,
    cobertura_automatica,
    construir_boleto_millonario,
    coste,
    evaluar_riesgo_millonario,
    indice_sorpresa_quinielistica,
    normalizar_pesos_dinamicos,
    prioridad_elige8,
    prioridad_doble,
    riesgos_no_cubiertos_por_presupuesto,
    trazabilidad_datos_partido,
)


def partido(num, probs, incertidumbre=120, sorpresa=60):
    return {
        "num": num,
        "local": f"Local {num}",
        "visitante": f"Visitante {num}",
        "probabilidades": probs,
        "incertidumbre": incertidumbre,
        "probabilidad_sorpresa": sorpresa,
    }


def equipo_competitivo(nombre, estado, motivacion="baja", vivos=None):
    return {
        "equipo": nombre,
        "motivacion_competitiva": motivacion,
        "objetivos": [{"objetivo": "permanencia", "estado": estado}],
        "objetivos_vivos": vivos if vivos is not None else [],
    }


class MotorPrediccionTests(unittest.TestCase):
    def test_coste_elige8_es_por_apuesta(self):
        resultado = coste(dobles=2, triples=1, elige8=True)

        self.assertEqual(resultado["apuestas"], 12)
        self.assertEqual(resultado["apuestas_elige8"], 12)
        self.assertEqual(resultado["importe_quiniela"], 9.0)
        self.assertEqual(resultado["importe_elige8"], 6.0)
        self.assertEqual(resultado["importe_total"], 15.0)

    def test_coste_elige8_usa_solo_partidos_marcados(self):
        partidos = [
            {"num": 1, "signo_final": "1X2", "elige8": True},
            {"num": 2, "signo_final": "1X2", "elige8": True},
            {"num": 3, "signo_final": "1X", "elige8": True},
            {"num": 4, "signo_final": "1", "elige8": True},
            {"num": 5, "signo_final": "1", "elige8": True},
            {"num": 6, "signo_final": "X", "elige8": True},
            {"num": 7, "signo_final": "2", "elige8": True},
            {"num": 8, "signo_final": "1", "elige8": True},
        ]

        resultado = coste(dobles=2, triples=2, elige8=True, partidos=partidos)

        self.assertEqual(resultado["apuestas"], 36)
        self.assertEqual(resultado["apuestas_elige8"], 18)
        self.assertEqual(resultado["importe_quiniela"], 27.0)
        self.assertEqual(resultado["importe_elige8"], 9.0)
        self.assertEqual(resultado["importe_total"], 36.0)

    def test_cobertura_automatica_evitar_14_fijos_en_jornada_abierta(self):
        evaluados = [
            partido(i, {"1": 35.0, "X": 34.0, "2": 31.0})
            for i in range(1, 15)
        ]

        dobles, triples, detalle = cobertura_automatica(evaluados)

        self.assertGreaterEqual(dobles, 4)
        self.assertGreaterEqual(triples, 1)
        self.assertIn("Cobertura automatica", detalle)

    def test_cobertura_automatica_respeta_boleto_sencillo_si_no_hay_riesgo(self):
        evaluados = [
            partido(i, {"1": 72.0, "X": 18.0, "2": 10.0}, incertidumbre=45, sorpresa=20)
            for i in range(1, 15)
        ]

        dobles, triples, detalle = cobertura_automatica(evaluados)

        self.assertEqual(dobles, 0)
        self.assertEqual(triples, 0)
        self.assertIn("boleto sencillo", detalle)

    def test_aprendizaje_propio_refuerza_empate_y_riesgo_fragil(self):
        aprendizaje = {
            "ajuste_motor": {
                "partidos_base": 111,
                "muestra": "suficiente",
                "boost_empate_zona_riesgo": 4.0,
                "riesgo_extra_fijo_fragil": 9.0,
                "riesgo_extra_triple_insuficiente": 3.0,
                "umbral_fijo_seguro": 58,
            }
        }
        local = {"tendencias": {"empates_pct": 30}}
        visitante = {"tendencias": {"empates_pct": 28}}

        probs, riesgo, lecturas = ajustar_por_aprendizaje_propio(
            {"1": 48.0, "X": 27.0, "2": 25.0},
            local,
            visitante,
            aprendizaje,
        )

        self.assertGreater(probs["X"], 27.0)
        self.assertGreaterEqual(riesgo, 10.0)
        self.assertTrue(any("Aprendizaje propio" in lectura for lectura in lecturas))

    def test_aprendizaje_no_inventa_porcentaje_empate_sin_memoria(self):
        aprendizaje = {
            "ajuste_motor": {
                "partidos_base": 111,
                "muestra": "suficiente",
                "boost_empate_zona_riesgo": 4.0,
                "riesgo_extra_fijo_fragil": 0.0,
                "riesgo_extra_triple_insuficiente": 0.0,
            }
        }

        probs, riesgo, lecturas = ajustar_por_aprendizaje_propio(
            {"1": 36.0, "X": 34.0, "2": 30.0},
            None,
            None,
            aprendizaje,
        )

        self.assertEqual(probs["X"], 34.0)
        self.assertGreater(riesgo, 0)
        self.assertTrue(any("no se altera el porcentaje" in lectura for lectura in lecturas))

    def test_cobertura_automatica_aplica_minimo_triple_aprendido(self):
        evaluados = [
            partido(1, {"1": 34.0, "X": 33.0, "2": 33.0}, incertidumbre=120, sorpresa=65),
            *[
                partido(i, {"1": 72.0, "X": 18.0, "2": 10.0}, incertidumbre=45, sorpresa=20)
                for i in range(2, 15)
            ],
        ]
        aprendizaje = {
            "ajuste_motor": {
                "partidos_base": 111,
                "muestra": "suficiente",
                "min_triples_auto": 1,
                "min_dobles_auto": 0,
            }
        }

        _, triples, detalle = cobertura_automatica(evaluados, aprendizaje)

        self.assertEqual(triples, 1)
        self.assertIn("Aprendizaje propio aplicado", detalle)

    def test_riesgos_no_cubiertos_por_presupuesto_detecta_fijo_peligroso(self):
        partidos = [
            {
                **partido(1, {"1": 40.0, "X": 32.0, "2": 28.0}, incertidumbre=120, sorpresa=65),
                "tipo": "FIJO",
                "signo_final": "1",
                "indice_sorpresa_quinielistica": 82,
                "cobertura_sorpresa_sugerida": "TRIPLE",
                "tercera_probabilidad": 28.0,
                "calidad_datos": "baja",
            },
            {
                **partido(2, {"1": 70.0, "X": 20.0, "2": 10.0}, incertidumbre=50, sorpresa=20),
                "tipo": "DOBLE",
                "signo_final": "1X",
                "indice_sorpresa_quinielistica": 20,
                "cobertura_sorpresa_sugerida": "FIJO",
                "tercera_probabilidad": 10.0,
                "calidad_datos": "alta",
            },
        ]

        riesgos = riesgos_no_cubiertos_por_presupuesto(partidos)

        self.assertEqual([r["num"] for r in riesgos], [1])
        self.assertIn("no cubierto", riesgos[0]["motivo"])

    def test_indice_sorpresa_detecta_favorito_atacable(self):
        evaluado = partido(1, {"1": 56.0, "X": 24.0, "2": 20.0}, incertidumbre=104, sorpresa=48)
        evaluado["contexto_competitivo_local"] = equipo_competitivo(
            "Local 1",
            "asegurado_matematicamente",
        )
        evaluado["contexto_competitivo_visitante"] = equipo_competitivo(
            "Visitante 1",
            "riesgo_descenso",
            "maxima",
            vivos=[{"objetivo": "permanencia", "estado": "riesgo_descenso"}],
        )
        evaluado["_local"] = {"racha_actual": {"sin_ganar": 3}, "tendencias": {"goles_contra_por_partido": 1.6}}
        evaluado["_visitante"] = {"racha_actual": {"sin_perder": 3}, "tendencias": {"goles_favor_por_partido": 1.4}}
        patrones = {
            "patrones": {
                "visitante_descenso_vs_local_favorito": {"tasa_sorpresa": 70},
                "visitante_necesitado_vs_local_objetivo_cerrado": {"tasa_sorpresa": 60},
                "equipo_necesitado_vs_equipo_sin_objetivo": {"tasa_sorpresa": 65},
            }
        }

        indice = indice_sorpresa_quinielistica(evaluado, patrones)

        self.assertGreaterEqual(indice["indice"], 60)
        self.assertTrue(indice["favorito_atacable"])
        self.assertEqual(indice["favorito"], "1")
        self.assertEqual(indice["cobertura_sugerida"], "DOBLE")
        self.assertIn("X", indice["signos_contra_favorito"])

    def test_prioridad_doble_prioriza_favorito_atacable(self):
        favorito_atacable = partido(1, {"1": 56.0, "X": 24.0, "2": 20.0}, incertidumbre=104, sorpresa=48)
        favorito_atacable["contexto_competitivo_local"] = equipo_competitivo(
            "Local 1",
            "asegurado_matematicamente",
        )
        favorito_atacable["contexto_competitivo_visitante"] = equipo_competitivo(
            "Visitante 1",
            "riesgo_descenso",
            "maxima",
            vivos=[{"objetivo": "permanencia", "estado": "riesgo_descenso"}],
        )
        favorito_atacable["_indice_sorpresa_quinielistica"] = indice_sorpresa_quinielistica(favorito_atacable)

        abierto_generico = partido(2, {"1": 42.0, "X": 31.0, "2": 27.0}, incertidumbre=104, sorpresa=48)
        abierto_generico["_indice_sorpresa_quinielistica"] = indice_sorpresa_quinielistica(abierto_generico)

        self.assertGreater(prioridad_doble(favorito_atacable), prioridad_doble(abierto_generico))

    def test_elige8_prioriza_cobertura_real_y_no_orden(self):
        fijos = [
            {
                **partido(i, {"1": 54.0, "X": 26.0, "2": 20.0}, incertidumbre=95, sorpresa=35),
                "signo_base": "1",
                "signo_final": "1",
            }
            for i in range(1, 9)
        ]
        triple_tardio = {
            **partido(10, {"1": 35.0, "X": 33.0, "2": 32.0}, incertidumbre=120, sorpresa=70),
            "signo_base": "1",
            "signo_final": "1X2",
        }
        doble_tardio = {
            **partido(11, {"1": 50.0, "X": 31.0, "2": 19.0}, incertidumbre=110, sorpresa=55),
            "signo_base": "1",
            "signo_final": "1X",
        }

        seleccionados = {
            p["num"]
            for p in sorted([*fijos, triple_tardio, doble_tardio], key=prioridad_elige8, reverse=True)[:8]
        }

        self.assertIn(10, seleccionados)
        self.assertIn(11, seleccionados)
        self.assertNotEqual(seleccionados, set(range(1, 9)))

    def test_elige8_no_prioriza_un_doble_flojo_sobre_un_fijo_solido(self):
        """Caso real de la jornada 73 (feedback_metodo_prediccion_manual.md,
        regla 1): un doble que cubre una sorpresa poco probable contra un
        gran favorito (aqui, 76% para el "2") tiene MENOS probabilidad
        real de acierto que un fijo solido en otro partido -antes de este
        fix, el doble ganaba siempre por el simple hecho de ser doble."""
        doble_flojo = {
            **partido(20, {"1": 10.0, "X": 14.0, "2": 76.0}, incertidumbre=130, sorpresa=70),
            "signo_base": "2",
            "signo_final": "1X",
        }
        fijo_solido = {
            **partido(21, {"1": 82.0, "X": 10.0, "2": 8.0}, incertidumbre=90, sorpresa=30),
            "signo_base": "1",
            "signo_final": "1",
        }

        self.assertGreater(prioridad_elige8(fijo_solido), prioridad_elige8(doble_flojo))

    def test_trazabilidad_marca_fallback_sin_memoria_de_equipos(self):
        trazabilidad = trazabilidad_datos_partido(
            local=None,
            visitante=None,
            contexto_local=None,
            contexto_visitante=None,
            local_comp=None,
            visitante_comp=None,
        )

        self.assertEqual(trazabilidad["origen_probabilidades"], "fallback_posicion")
        self.assertEqual(trazabilidad["calidad_datos"], "baja")
        self.assertFalse(trazabilidad["memoria_estadistica"]["local"])
        self.assertFalse(trazabilidad["memoria_estadistica"]["visitante"])

    def test_trazabilidad_distingue_contexto_parcial(self):
        trazabilidad = trazabilidad_datos_partido(
            local=None,
            visitante=None,
            contexto_local={"noticias": [{"titulo": "Parte medico"}]},
            contexto_visitante=None,
            local_comp=None,
            visitante_comp=None,
        )

        self.assertEqual(trazabilidad["origen_probabilidades"], "fallback_posicion_con_contexto")
        self.assertEqual(trazabilidad["calidad_datos"], "media_baja")
        self.assertTrue(trazabilidad["noticias_recientes"]["local"])

    def test_datos_profesionales_mezclan_cuotas_y_penalizan_bajas(self):
        datos_partido = {
            "cuotas": {
                "probabilidades_implicitas": {"1": 31.0, "X": 27.0, "2": 42.0},
                "overround": 6.0,
            },
            "bajas": {
                "local": {"impacto_total": 3.0, "titulares_afectados": 1, "lesiones": [{}], "sanciones": [], "dudas": []},
                "visitante": {"impacto_total": 0.0, "titulares_afectados": 0, "lesiones": [], "sanciones": [], "dudas": []},
            },
            "alineaciones": {
                "local": {"titulares_probables": [f"L{i}" for i in range(11)], "confianza": 0.9, "dudas": []},
                "visitante": {"titulares_probables": [f"V{i}" for i in range(9)], "confianza": 0.62, "dudas": ["V9"]},
            },
            "capas_disponibles": {
                "cuotas": True,
                "bajas_estructuradas": True,
                "alineaciones_probables": True,
            },
        }

        probs, riesgo, lecturas, resumen = ajustar_por_datos_profesionales(
            {"1": 46.0, "X": 29.0, "2": 25.0},
            datos_partido,
        )

        self.assertLess(probs["1"], 46.0)
        self.assertGreater(probs["2"], 25.0)
        self.assertGreater(riesgo, 0)
        self.assertTrue(resumen["activo"])
        self.assertTrue(any("Cuotas mercado" in lectura for lectura in lecturas))
        self.assertTrue(any("Bajas local" in lectura for lectura in lecturas))

    def test_mercado_losilla_acerca_las_probs_al_consenso_publico(self):
        probs = {"1": 34.0, "X": 33.0, "2": 33.0}
        mercado = {"1": 6.0, "X": 10.0, "2": 84.0}

        nuevas, riesgo, lecturas = ajustar_por_mercado_losilla(probs, mercado)

        self.assertLess(nuevas["1"], probs["1"])
        self.assertGreater(nuevas["2"], probs["2"])
        self.assertGreater(riesgo, 0)
        self.assertTrue(any("no coincide" in lectura for lectura in lecturas))
        self.assertTrue(any("integrado con peso" in lectura for lectura in lecturas))

    def test_mercado_losilla_sin_datos_no_cambia_nada(self):
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}

        nuevas, riesgo, lecturas = ajustar_por_mercado_losilla(probs, {"1": 0.0, "X": 0.0, "2": 0.0})

        self.assertEqual(nuevas, probs)
        self.assertEqual(riesgo, 0.0)
        self.assertEqual(lecturas, [])

    def test_mercado_losilla_de_acuerdo_con_el_motor_no_suma_riesgo(self):
        probs = {"1": 60.0, "X": 25.0, "2": 15.0}
        mercado = {"1": 88.0, "X": 8.0, "2": 4.0}

        nuevas, riesgo, lecturas = ajustar_por_mercado_losilla(probs, mercado)

        self.assertEqual(riesgo, 0.0)
        self.assertFalse(any("no coincide" in lectura for lectura in lecturas))

    def test_mercado_losilla_calidad_baja_pesa_mucho_mas_que_calidad_alta(self):
        """Con un prior propio de calidad "baja" (fallback puro, sin
        estadistica real), el mercado debe pesar 0.65 en vez del 0.18 fijo
        de antes -motivado por la jornada 73 (2026-07-17): con peso fijo,
        un consenso de mercado del 100% para el "1" solo movia el motor de
        40% a 50.8%, sin corregir casi nada un prior de fallback."""
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        mercado = {"1": 100.0, "X": 0.0, "2": 0.0}

        nuevas_baja, _, lecturas_baja = ajustar_por_mercado_losilla(probs, mercado, calidad_datos="baja")
        nuevas_alta, _, lecturas_alta = ajustar_por_mercado_losilla(probs, mercado, calidad_datos="alta")

        self.assertAlmostEqual(nuevas_baja["1"], 79.0)
        self.assertAlmostEqual(nuevas_alta["1"], 52.0)
        self.assertGreater(nuevas_baja["1"], nuevas_alta["1"])
        self.assertTrue(any("peso 0.65" in lectura for lectura in lecturas_baja))
        self.assertTrue(any("peso 0.20" in lectura for lectura in lecturas_alta))

    def test_mercado_losilla_calidad_media_y_media_baja_intermedias(self):
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        mercado = {"1": 100.0, "X": 0.0, "2": 0.0}

        nuevas_media, _, lecturas_media = ajustar_por_mercado_losilla(probs, mercado, calidad_datos="media")
        nuevas_media_baja, _, lecturas_media_baja = ajustar_por_mercado_losilla(probs, mercado, calidad_datos="media_baja")

        self.assertAlmostEqual(nuevas_media["1"], 61.0)
        self.assertAlmostEqual(nuevas_media_baja["1"], 67.0)
        self.assertTrue(any("peso 0.35" in lectura for lectura in lecturas_media))
        self.assertTrue(any("peso 0.45" in lectura for lectura in lecturas_media_baja))

    def test_mercado_losilla_calidad_profesional_pesa_menos_que_alta(self):
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        mercado = {"1": 100.0, "X": 0.0, "2": 0.0}

        nuevas, _, lecturas = ajustar_por_mercado_losilla(probs, mercado, calidad_datos="profesional")

        self.assertAlmostEqual(nuevas["1"], 49.0)
        self.assertTrue(any("peso 0.15" in lectura for lectura in lecturas))

    def test_mercado_losilla_sin_calidad_datos_usa_peso_por_defecto(self):
        """calidad_datos=None (o un valor no reconocido) conserva el peso
        fijo anterior (0.18) como red de seguridad para llamadas que no lo
        pasen todavia."""
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        mercado = {"1": 100.0, "X": 0.0, "2": 0.0}

        nuevas_none, _, lecturas_none = ajustar_por_mercado_losilla(probs, mercado)
        nuevas_desconocida, _, _ = ajustar_por_mercado_losilla(probs, mercado, calidad_datos="valor_no_existente")

        self.assertAlmostEqual(nuevas_none["1"], 50.8)
        self.assertAlmostEqual(nuevas_desconocida["1"], 50.8)
        self.assertTrue(any("peso 0.18" in lectura for lectura in lecturas_none))

    def test_buscar_lesiones_equipo_encuentra_por_nombre_difuso(self):
        fuente = {"equipos": {"Athletic Club": [{"jugador": "X", "categoria": "lesionado"}]}}

        encontrado = buscar_lesiones_equipo(fuente, "Athletic")

        self.assertEqual(encontrado, [{"jugador": "X", "categoria": "lesionado"}])

    def test_buscar_lesiones_equipo_sin_coincidencia_devuelve_vacio(self):
        fuente = {"equipos": {"Athletic Club": [{"jugador": "X", "categoria": "lesionado"}]}}

        self.assertEqual(buscar_lesiones_equipo(fuente, "Manchester United"), [])
        self.assertEqual(buscar_lesiones_equipo({}, "Athletic"), [])

    def test_lesiones_laliga_mas_bajas_en_visitante_favorece_al_local(self):
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        lesiones_local = [{"categoria": "lesionado"}]
        lesiones_visitante = [{"categoria": "lesionado"}, {"categoria": "lesionado"}, {"categoria": "duda"}]

        nuevas, riesgo, lecturas = ajustar_por_lesiones_laliga(probs, lesiones_local, lesiones_visitante)

        self.assertGreater(nuevas["1"], probs["1"])
        self.assertLess(nuevas["2"], probs["2"])
        self.assertGreater(riesgo, 0)
        self.assertTrue(any("favorece ligeramente al local" in lectura for lectura in lecturas))

    def test_lesiones_laliga_mas_bajas_en_local_favorece_al_visitante(self):
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        lesiones_local = [{"categoria": "lesionado"}, {"categoria": "lesionado"}]
        lesiones_visitante = []

        nuevas, riesgo, lecturas = ajustar_por_lesiones_laliga(probs, lesiones_local, lesiones_visitante)

        self.assertLess(nuevas["1"], probs["1"])
        self.assertGreater(nuevas["2"], probs["2"])
        self.assertGreater(riesgo, 0)
        self.assertTrue(any("favorece ligeramente al visitante" in lectura for lectura in lecturas))

    def test_lesiones_laliga_sin_datos_no_cambia_nada(self):
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}

        nuevas, riesgo, lecturas = ajustar_por_lesiones_laliga(probs, [], [])

        self.assertEqual(nuevas, probs)
        self.assertEqual(riesgo, 0.0)
        self.assertEqual(lecturas, [])

    def test_lesiones_laliga_mismas_bajas_no_cambia_nada(self):
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        lesiones_local = [{"categoria": "lesionado"}, {"categoria": "duda"}]
        lesiones_visitante = [{"categoria": "lesionado"}]

        nuevas, riesgo, lecturas = ajustar_por_lesiones_laliga(probs, lesiones_local, lesiones_visitante)

        self.assertEqual(nuevas, probs)
        self.assertEqual(riesgo, 0.0)
        self.assertEqual(lecturas, [])

    def test_trazabilidad_sube_calidad_con_datos_profesionales(self):
        trazabilidad = trazabilidad_datos_partido(
            local={"equipo": "Local"},
            visitante={"equipo": "Visitante"},
            contexto_local=None,
            contexto_visitante=None,
            local_comp=None,
            visitante_comp=None,
            datos_profesionales={
                "capas_disponibles": {
                    "cuotas": True,
                    "bajas_estructuradas": False,
                    "alineaciones_probables": False,
                    "clasificacion_oficial": False,
                }
            },
        )

        self.assertEqual(trazabilidad["calidad_datos"], "profesional")
        self.assertEqual(trazabilidad["origen_probabilidades"], "estadistica_equipos+datos_profesionales")
        self.assertTrue(trazabilidad["datos_profesionales"]["cuotas"])

    def test_pesos_dinamicos_no_quedan_saturados(self):
        pesos = normalizar_pesos_dinamicos({
            "pesos": {
                "forma_reciente": 0.01,
                "casa_fuera": 0.01,
                "clasificacion": 0.01,
                "goles": 0.35,
                "empate": 0.35,
                "sorpresa": 0.35,
                "motivacion_competitiva": 0.07,
                "necesidad_descenso_ascenso_europa": 0.07,
                "fatiga": 0.02,
                "bajas": 0.02,
            }
        })

        self.assertLessEqual(pesos["pesos"]["empate"], 0.18)
        self.assertLessEqual(pesos["pesos"]["sorpresa"], 0.16)
        self.assertAlmostEqual(sum(pesos["pesos"].values()), 1.0, places=3)
        self.assertTrue(pesos["normalizacion_runtime"]["aplicada"])

    def test_riesgo_millonario_candidato_con_evidencia_contextual(self):
        indice_sorpresa = {
            "favorito": "1",
            "favorito_atacable": True,
            "signo_sorpresa_principal": "2",
            "indice": 78.0,
            "motivos": [
                "margen minimo entre primer y segundo signo",
                "rival del favorito con urgencia de descenso/permanencia",
            ],
        }

        riesgo = evaluar_riesgo_millonario(indice_sorpresa)

        self.assertTrue(riesgo["candidato"])
        self.assertEqual(riesgo["signo_alternativo"], "2")
        self.assertEqual(len(riesgo["motivos_contextuales"]), 1)

    def test_riesgo_millonario_no_candidato_solo_con_ruido_estadistico(self):
        indice_sorpresa = {
            "favorito": "1",
            "favorito_atacable": True,
            "signo_sorpresa_principal": "X",
            "indice": 65.0,
            "motivos": [
                "margen minimo entre primer y segundo signo",
                "ningun signo supera claramente el 45%",
            ],
        }

        riesgo = evaluar_riesgo_millonario(indice_sorpresa)

        self.assertFalse(riesgo["candidato"])
        self.assertEqual(riesgo["signo_alternativo"], "")

    def test_riesgo_millonario_no_candidato_si_no_es_atacable(self):
        indice_sorpresa = {
            "favorito": "1",
            "favorito_atacable": False,
            "signo_sorpresa_principal": "2",
            "indice": 40.0,
            "motivos": ["rival con urgencia de descenso/permanencia"],
        }

        riesgo = evaluar_riesgo_millonario(indice_sorpresa)

        self.assertFalse(riesgo["candidato"])

    def test_construir_boleto_millonario_cambia_solo_los_candidatos(self):
        evaluados = [
            {
                "num": 1, "local": "A", "visitante": "B", "signo_final": "1",
                "riesgo_millonario": {"candidato": True, "signo_alternativo": "2", "justificacion": "..."},
            },
            {
                "num": 2, "local": "C", "visitante": "D", "signo_final": "1X",
                "riesgo_millonario": {"candidato": False, "signo_alternativo": ""},
            },
        ]

        boleto = construir_boleto_millonario(evaluados)

        self.assertEqual(boleto["total_cambios"], 1)
        partido_1 = next(p for p in boleto["partidos"] if p["num"] == 1)
        partido_2 = next(p for p in boleto["partidos"] if p["num"] == 2)
        self.assertEqual(partido_1["signo"], "2")
        self.assertTrue(partido_1["es_cambio_millonario"])
        self.assertEqual(partido_2["signo"], "1X")
        self.assertFalse(partido_2["es_cambio_millonario"])


if __name__ == "__main__":
    unittest.main()
