import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import estudio_ver_sorpresas as evs
from estudio_ver_sorpresas import (
    construir_dataset_motor,
    construir_dataset_cuotas,
    contraste,
    es_entre_semana,
    favorito_de,
    medir_feature,
    parsear_fecha,
    rachas_previas_por_fila,
    tercer_signo_de,
    test_permutacion_varianza,
)


def partido_motor(jornada, num, local, visitante, probs, signo_real,
                  temporada="2026_2027", fecha="2026-10-10"):
    return {
        "temporada": temporada, "jornada": jornada, "num": num,
        "local": local, "visitante": visitante, "fecha": fecha,
        "probabilidades": dict(zip(("1", "X", "2"), probs)),
        "signo_real": signo_real,
    }


class DefinicionSorpresaTests(unittest.TestCase):
    def test_carga_y_definicion_de_sorpresa(self):
        historial = {"partidos": [
            partido_motor(1, 1, "A", "B", (60, 25, 15), "1"),   # favorito gana: no sorpresa
            partido_motor(1, 2, "C", "D", (60, 25, 15), "X"),   # sorpresa (2o signo)
            partido_motor(1, 3, "E", "F", (60, 25, 15), "2"),   # sorpresa maxima (3er signo)
        ]}
        filas = construir_dataset_motor(historial)
        self.assertEqual(len(filas), 3)
        self.assertEqual([f["sorpresa"] for f in filas], [False, True, True])
        self.assertEqual([f["sorpresa_maxima"] for f in filas], [False, False, True])
        self.assertEqual(filas[0]["favorito"], "1")
        self.assertEqual(filas[0]["prob_favorito"], 60.0)

    def test_descarta_filas_sin_resultado_o_sin_probabilidades(self):
        historial = {"partidos": [
            partido_motor(1, 1, "A", "B", (60, 25, 15), ""),       # sin resultado
            {**partido_motor(1, 2, "C", "D", (0, 0, 0), "1")},      # probabilidades rotas
            partido_motor(1, 3, "E", "F", (40, 35, 25), "1"),
        ]}
        filas = construir_dataset_motor(historial)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["local"], "E")

    def test_favorito_cuotas_es_cuota_minima(self):
        historico = {"ligas": {"primera": {"temporadas": {"2023/2024": {"partidos": [
            {"fecha": "2023-09-02", "local": "A", "visitante": "B",
             "cuota_1": 2.4, "cuota_x": 3.2, "cuota_2": 2.9, "signo": "1"},
        ]}}}}}
        filas = construir_dataset_cuotas(historico)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["favorito"], "1")
        self.assertFalse(filas[0]["sorpresa"])

    def test_favorito_y_tercer_signo(self):
        probs = {"1": 20.0, "X": 30.0, "2": 50.0}
        self.assertEqual(favorito_de(probs), "2")
        self.assertEqual(tercer_signo_de(probs), "1")


class FeatureSinteticaTests(unittest.TestCase):
    def test_medir_feature_y_veredicto(self):
        # 40 filas con la feature (75% sorpresa) vs 40 sin (25%): UTILIZABLE
        filas = ([{"sorpresa": i < 30, "marca": True} for i in range(40)]
                 + [{"sorpresa": i < 10, "marca": False} for i in range(40)])
        r = medir_feature(filas, lambda f: f["marca"], "sintetica", "test")
        self.assertEqual(r["n_con"], 40)
        self.assertEqual(r["tasa_sorpresa_con_pct"], 75.0)
        self.assertEqual(r["tasa_sorpresa_sin_pct"], 25.0)
        self.assertEqual(r["veredicto"], "UTILIZABLE")

    def test_veredicto_nada_con_muestra_pequena(self):
        # misma diferencia pero n_con=8 (< 30): jamas UTILIZABLE
        filas = ([{"sorpresa": i < 6, "marca": True} for i in range(8)]
                 + [{"sorpresa": i < 10, "marca": False} for i in range(40)])
        r = medir_feature(filas, lambda f: f["marca"], "sintetica", "test")
        self.assertEqual(r["veredicto"], "NADA")

    def test_none_queda_fuera_de_la_muestra(self):
        filas = [{"sorpresa": True, "marca": True}, {"sorpresa": False, "marca": None}]
        r = medir_feature(filas, lambda f: f["marca"], "sintetica", "test")
        self.assertEqual(r["n_con"], 1)
        self.assertEqual(r["n_sin"], 0)
        self.assertEqual(r["veredicto"], "NADA")

    def test_contraste_sin_muestra(self):
        self.assertEqual(contraste(50.0, 0, 50.0, 10)["veredicto"], "NADA")


class RachaSinFugaTests(unittest.TestCase):
    def test_racha_solo_usa_partidos_anteriores(self):
        # El equipo A gana 3 veces seguidas SIN ser favorito (sorpresas
        # positivas); en el 4o partido es favorito: racha_favorito=True.
        historial = {"partidos": [
            partido_motor(j, 1, "A", f"R{j}", (30, 30, 40), "1", fecha=f"2026-09-{10+j:02d}")
            for j in range(1, 4)
        ] + [partido_motor(4, 1, "A", "R4", (70, 20, 10), "1", fecha="2026-09-20")]}
        filas = construir_dataset_motor(historial)
        rachas = rachas_previas_por_fila(filas)
        # los 3 primeros: sin historial previo suficiente -> None
        self.assertEqual(rachas[:3], [None, None, None])
        self.assertTrue(rachas[3])

    def test_sin_racha_si_el_favorito_venia_cumpliendo(self):
        historial = {"partidos": [
            partido_motor(j, 1, "A", f"R{j}", (70, 20, 10), "1", fecha=f"2026-09-{10+j:02d}")
            for j in range(1, 5)
        ]}
        filas = construir_dataset_motor(historial)
        self.assertFalse(rachas_previas_por_fila(filas)[3])


class FechasYClusteringTests(unittest.TestCase):
    def test_parsear_fecha_formatos_reales(self):
        self.assertEqual(str(parsear_fecha("2026-10-13")), "2026-10-13")
        self.assertEqual(str(parsear_fecha("10/05/2026")), "2026-05-10")
        self.assertEqual(str(parsear_fecha("13-08-2023")), "2023-08-13")
        self.assertEqual(str(parsear_fecha("13 de Mayo de 2026")), "2026-05-13")
        self.assertEqual(str(parsear_fecha("La Quiniela Domingo, 1 de febrero de 2026")), "2026-02-01")
        self.assertIsNone(parsear_fecha("sin fecha"))

    def test_entre_semana(self):
        self.assertTrue(es_entre_semana(parsear_fecha("2026-10-13")))   # martes
        self.assertFalse(es_entre_semana(parsear_fecha("2026-10-18")))  # domingo
        self.assertFalse(es_entre_semana(None))

    def test_permutacion_detecta_clustering_extremo(self):
        # 10 jornadas: 5 con TODO sorpresas y 5 sin ninguna (clustering maximo,
        # mismo % de favorito en todas: la permutacion debe dar p bajo).
        jornadas = [{"temporada": "t", "jornada": j, "fecha": None,
                     "partidos": [{"pct_favorito": 55.0, "sorpresa": j <= 5}
                                  for _ in range(14)]}
                    for j in range(1, 11)]
        r = test_permutacion_varianza(jornadas, permutaciones=200, semilla=7)
        self.assertLess(r["p_valor"], 0.05)
        self.assertEqual(r["veredicto"], "UTILIZABLE")
        self.assertEqual(r["jornadas"], 10)


def _feature(nombre, veredicto="UTILIZABLE", diff=6.0, z=2.4, n_con=80):
    return {"feature": nombre, "descripcion": "desc " + nombre, "veredicto": veredicto,
            "diff_puntos": diff, "z": z, "n_con": n_con}


class ExtraerCandidatasTests(unittest.TestCase):
    """La funcion que decide que features pasan a candidatas (auditoria
    26/11, hallazgo 241: no tenia ningun test)."""

    def test_solo_pasan_las_utilizables_que_suben_la_tasa(self):
        bloque_a = {"features": [
            _feature("A3_masa_favorito_caro"),
            _feature("A4_sobrecompra", veredicto="DEBIL"),
            _feature("A6_empatador", diff=-5.0),       # utilizable pero BAJA la tasa
            _feature("A7_nemesis", diff=None),
        ]}
        buenas, todas = evs.extraer_candidatas(bloque_a, {"features": []})
        self.assertEqual([c["feature"] for c in buenas], ["A3_masa_favorito_caro"])
        self.assertEqual(len(todas), 1)
        self.assertEqual(buenas[0]["estado"], "candidata_pendiente_de_backtest_de_senal")

    def test_las_bandas_de_probabilidad_y_cuota_nunca_son_candidatas(self):
        buenas, todas = evs.extraer_candidatas(
            {"features": [_feature("A1_banda_prob_favorito", diff=15.0, z=5.0)]},
            {"features": [_feature("B1_banda_cuota_favorito", diff=12.0, z=6.0)]})
        self.assertEqual(buenas, [])
        self.assertEqual(todas, [])

    def test_descarta_la_que_cambia_de_signo_en_el_otro_dataset(self):
        bloque_a = {"features": [_feature("A9_favorito_visitante", diff=7.0)]}
        bloque_b = {"features": [_feature("B2_favorito_visitante", veredicto="NADA", diff=-3.0)]}
        buenas, todas = evs.extraer_candidatas(bloque_a, bloque_b)
        self.assertEqual(buenas, [])
        self.assertEqual(todas[0]["estado"], "descartada_por_incoherencia_entre_datasets")
        self.assertFalse(todas[0]["coherente_entre_datasets"])

    def test_la_incoherencia_tambien_se_mira_desde_el_dataset_b(self):
        bloque_a = {"features": [_feature("A10_entre_semana", veredicto="NADA", diff=-2.0)]}
        bloque_b = {"features": [_feature("B3_entre_semana", diff=4.0)]}
        buenas, todas = evs.extraer_candidatas(bloque_a, bloque_b)
        self.assertEqual(buenas, [])
        self.assertEqual([c["feature"] for c in todas], ["B3_entre_semana"])

    def test_coherente_si_la_gemela_va_en_la_misma_direccion_o_no_existe(self):
        bloque_a = {"features": [_feature("A5_racha_favorito", diff=5.0),
                                 _feature("A8_h2h_caotico", diff=9.0)]}
        bloque_b = {"features": [_feature("B4_racha_favorito", veredicto="DEBIL", diff=1.0)]}
        buenas, _ = evs.extraer_candidatas(bloque_a, bloque_b)
        self.assertEqual([c["feature"] for c in buenas], ["A5_racha_favorito", "A8_h2h_caotico"])


class LecturaDeFuentesTests(unittest.TestCase):
    """cargar_mercado_pre_cierre y cargar_masa_lae sobre un directorio
    temporal (nunca el data/ real)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self._guardado = (evs.PRE_CIERRE_DIR, evs.PORCENTAJES_LAE_DIR)
        evs.PRE_CIERRE_DIR = self.base / "pre_cierre"
        evs.PORCENTAJES_LAE_DIR = self.base / "porcentajes_lae"
        evs.PRE_CIERRE_DIR.mkdir()
        (evs.PORCENTAJES_LAE_DIR / "2026_2027").mkdir(parents=True)

    def tearDown(self):
        evs.PRE_CIERRE_DIR, evs.PORCENTAJES_LAE_DIR = self._guardado
        self._tmp.cleanup()

    def test_mercado_sale_del_campo_prediccion_del_snapshot(self):
        (evs.PRE_CIERRE_DIR / "jornada_7.json").write_text(json.dumps({
            "jornada": 7,
            "prediccion": {"jornada": 7, "partidos": [
                {"num": 1, "local": "Cadiz CF", "visitante": "Levante UD",
                 "mercado_losilla": {"1": 45.0, "X": 29.0, "2": 26.0}},
                {"num": 2, "local": "Real Oviedo", "visitante": "Burgos CF"},        # sin mercado
                {"num": 3, "local": "SD Eibar", "visitante": "Granada CF",
                 "mercado_losilla": {"1": "n/d", "X": 30, "2": 30}},                 # mercado roto
            ]},
        }), encoding="utf-8")
        mercado = evs.cargar_mercado_pre_cierre()
        self.assertEqual(list(mercado), [(7, 1)])
        self.assertEqual(mercado[(7, 1)]["mercado"], {"1": 45.0, "X": 29.0, "2": 26.0})
        self.assertEqual(len(mercado[(7, 1)]["claves"]), 2)

    def test_masa_lae_por_jornada_y_numero(self):
        (evs.PORCENTAJES_LAE_DIR / "2026_2027" / "jornada_3.json").write_text(json.dumps({
            "partidos": [
                {"numero": 4, "porcentajes": {"1": 71, "X": 18, "2": 11}},
                {"numero": 5, "porcentajes": {"1": 50, "X": None, "2": 20}},  # incompleto
            ],
        }), encoding="utf-8")
        masa = evs.cargar_masa_lae("2026_2027")
        self.assertEqual(masa, {(3, 4): {"1": 71.0, "X": 18.0, "2": 11.0}})
        self.assertEqual(evs.cargar_masa_lae("1999_2000"), {})


class SinFugaDeFuturoTests(unittest.TestCase):
    def test_cambiar_un_resultado_no_altera_la_racha_de_esa_fila_ni_de_las_anteriores(self):
        # La racha de la fila i solo puede depender de los resultados < i: si
        # se cambia el resultado de la fila i (y de las siguientes), las
        # rachas calculadas hasta i inclusive no pueden moverse.
        def historial(signo_ultimos):
            partidos = [
                partido_motor(j, 1, "A", f"R{j}", (30, 30, 40), "1", fecha=f"2026-09-{j:02d}")
                for j in range(1, 4)
            ]
            partidos += [
                partido_motor(4, 1, "A", "R4", (70, 20, 10), signo_ultimos, fecha="2026-09-20"),
                partido_motor(5, 1, "A", "R5", (70, 20, 10), signo_ultimos, fecha="2026-09-27"),
            ]
            return {"partidos": partidos}

        gana = rachas_previas_por_fila(construir_dataset_motor(historial("1")))
        pierde = rachas_previas_por_fila(construir_dataset_motor(historial("2")))
        self.assertEqual(gana[:4], pierde[:4])
        self.assertTrue(gana[3])

    def test_un_partido_de_fecha_posterior_no_cuenta_aunque_venga_antes_en_el_fichero(self):
        # El historial llega desordenado: el dataset debe ordenarse por fecha
        # antes de calcular rachas.
        previos = [
            partido_motor(j, 1, "A", f"R{j}", (30, 30, 40), "1", fecha=f"2026-09-{j:02d}")
            for j in range(1, 4)
        ]
        objetivo = partido_motor(4, 1, "A", "R4", (70, 20, 10), "1", fecha="2026-09-20")
        ordenado = construir_dataset_motor({"partidos": previos + [objetivo]})
        desordenado = construir_dataset_motor({"partidos": [objetivo] + previos})
        self.assertEqual([f["jornada"] for f in desordenado], [f["jornada"] for f in ordenado])
        self.assertEqual(rachas_previas_por_fila(desordenado), rachas_previas_por_fila(ordenado))


if __name__ == "__main__":
    unittest.main()
