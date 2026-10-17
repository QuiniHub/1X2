import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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


if __name__ == "__main__":
    unittest.main()
