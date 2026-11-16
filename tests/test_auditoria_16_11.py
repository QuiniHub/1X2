"""Tests de la auditoria del 16/11/2026: cobertura de autor (empatadores),
pesos congelados, snapshot pre-cierre refrescado, control de calidad con la
jornada objetivo real y escrutinio placebo."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import motor_prediccion_quiniela as motor
import construir_memoria_ia as memoria
import guardar_snapshot_prediccion as snap
import actualizar_fuente_losilla as losilla


ESTUDIO = {
    "cadiz": {"equipo": "cadiz", "x_pct": 30.0, "x_casa_pct": 31.0, "x_fuera_pct": 29.0, "pj_2627": 12, "x_2627_pct": 50.0},
    "vallecano": {"equipo": "vallecano", "x_pct": 35.7, "x_casa_pct": 44.4, "x_fuera_pct": 27.0, "pj_2627": 12, "x_2627_pct": 33.3},
    "barcelona": {"equipo": "barcelona", "x_pct": 9.9, "x_casa_pct": 8.0, "x_fuera_pct": 12.0, "pj_2627": 12, "x_2627_pct": 0.0},
}


class CoberturaDeAutorTests(unittest.TestCase):
    def test_empatador_con_x_viva_pide_cobertura_con_la_x(self):
        traza = motor.cobertura_de_autor({"1": 53, "X": 29, "2": 18}, "SD Eibar", "Cadiz CF", ESTUDIO)
        self.assertTrue(traza and traza["activo"])
        self.assertEqual(traza["equipo"], "Cadiz CF")

    def test_sin_empatador_o_sin_x_viva_no_hay_cobertura(self):
        self.assertIsNone(motor.cobertura_de_autor({"1": 70, "X": 18, "2": 12}, "FC Barcelona", "Getafe CF", ESTUDIO))
        self.assertIsNone(motor.cobertura_de_autor({"1": 60, "X": 24, "2": 16}, "SD Eibar", "Cadiz CF", ESTUDIO))  # X < 28
        self.assertIsNone(motor.cobertura_de_autor({"1": 30, "X": 40, "2": 30}, "Rayo Vallecano de Madrid", "Celta", ESTUDIO))  # X ya es top

    def test_el_doble_de_un_empatador_lleva_la_x_aunque_sea_tercera(self):
        probs = {"1": 50, "X": 22, "2": 28}
        self.assertIsNone(motor.cobertura_de_autor(probs, "Real Sociedad", "Rayo Vallecano de Madrid", ESTUDIO))  # 22 < 28
        probs = {"1": 46, "X": 26, "2": 28}
        self.assertEqual(motor.doble_top(probs), "12")
        self.assertIsNone(motor.cobertura_de_autor(probs, "Real Sociedad", "Rayo Vallecano de Madrid", ESTUDIO))
        probs = {"1": 44, "X": 28, "2": 28}
        traza = motor.cobertura_de_autor(probs, "Real Sociedad", "Rayo Vallecano de Madrid", ESTUDIO)
        self.assertTrue(traza)
        signo = "".join(s for s in ("1", "X", "2") if s in {motor.signo_top(probs), "X"})
        self.assertEqual(signo, "1X")


class PesosCongeladosTests(unittest.TestCase):
    def test_modo_congelado_no_ajusta_ni_decae(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "pesos.json"
            ruta.write_text(json.dumps({"version": "1.2", "modo": "congelado", "motivo_congelacion": "test",
                                        "pesos": {"empate": 0.1748, "sorpresa": 0.1554, "goles": 0.2069}}), encoding="utf-8")
            original = memoria.PESOS_DINAMICOS
            memoria.PESOS_DINAMICOS = ruta
            try:
                quiniela = {"nuestras_quinielas": {"partidos_validados": 546, "fallos": 178, "jornadas_validadas": 39,
                                                   "por_tipo": {"FIJO": {"fallos": 71, "total": 180}}, "fallos_por_categoria": {"empate_no_cubierto": 64}}}
                salida = memoria.construir_pesos_dinamicos(quiniela, [])
            finally:
                memoria.PESOS_DINAMICOS = original
        self.assertEqual(salida["modo"], "congelado")
        self.assertEqual(salida["pesos"]["empate"], 0.1748)
        self.assertEqual(salida["pesos"]["goles"], 0.2069)
        self.assertEqual(salida["ajustes"][0]["delta"], 0)
        self.assertEqual(salida["muestra"]["partidos_validados"], 546)


class SnapshotRefrescadoTests(unittest.TestCase):
    def _montar(self, tmp, fecha, hora):
        snap.JORNADAS = Path(tmp) / "jornadas"
        snap.BACKTEST = Path(tmp) / "pre_cierre"
        snap.JORNADAS.mkdir()
        (snap.JORNADAS / "jornada_30.json").write_text(json.dumps({"jornada": 30, "partidos": [
            {"num": 1, "fecha": fecha, "hora": hora, "signo_oficial": "Pendiente"}]}), encoding="utf-8")

    def setUp(self):
        self._orig = (snap.JORNADAS, snap.BACKTEST, snap.ahora_utc)

    def tearDown(self):
        snap.JORNADAS, snap.BACKTEST, snap.ahora_utc = self._orig

    def test_se_refresca_antes_del_primer_partido_y_se_congela_despues(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._montar(tmp, "2026-11-21", "14:00")
            snap.ahora_utc = lambda: datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
            r1 = snap.crear_snapshot_prediccion({"jornada": 30, "partidos": [{"num": 1, "signo_final": "1"}]})
            self.assertTrue(r1["creado"]); self.assertFalse(r1["inmutable"])
            r2 = snap.crear_snapshot_prediccion({"jornada": 30, "partidos": [{"num": 1, "signo_final": "1X"}]})
            self.assertTrue(r2["creado"])  # cambio la prediccion: se refresca
            guardado = json.loads((snap.BACKTEST / "jornada_30.json").read_text(encoding="utf-8"))
            self.assertEqual(guardado["prediccion"]["partidos"][0]["signo_final"], "1X")
            self.assertFalse(guardado["inmutable"])
            # mismo contenido: no reescribe
            r3 = snap.crear_snapshot_prediccion({"jornada": 30, "partidos": [{"num": 1, "signo_final": "1X"}]})
            self.assertFalse(r3["creado"])
            # ya empezo el primer partido: congelado, aunque la prediccion cambie
            snap.ahora_utc = lambda: datetime(2026, 11, 21, 13, 30, tzinfo=timezone.utc)
            r4 = snap.crear_snapshot_prediccion({"jornada": 30, "partidos": [{"num": 1, "signo_final": "2"}]})
            self.assertFalse(r4["creado"])
            guardado = json.loads((snap.BACKTEST / "jornada_30.json").read_text(encoding="utf-8"))
            self.assertEqual(guardado["prediccion"]["partidos"][0]["signo_final"], "1X")
            self.assertTrue(guardado["inmutable"])


class EscrutinioPlausibleTests(unittest.TestCase):
    def test_placebo_se_rechaza(self):
        placebo = {c: {"acertantes": int(c), "premio_euros": 7.5} for c in ("14", "13", "12", "11", "10")}
        self.assertFalse(losilla.escrutinio_plausible(placebo))
        self.assertIsNone(losilla.construir_registro_escrutinio(20, placebo, "u", "f"))

    def test_escrutinio_real_se_acepta(self):
        real = {"14": {"acertantes": 6, "premio_euros": 80079.2}, "13": {"acertantes": 185, "premio_euros": 1369.75},
                "12": {"acertantes": 2301, "premio_euros": 110.13}, "11": {"acertantes": 17496, "premio_euros": 14.48},
                "10": {"acertantes": 89116, "premio_euros": 3.41}}
        self.assertTrue(losilla.escrutinio_plausible(real))
        self.assertIsNotNone(losilla.construir_registro_escrutinio(20, real, "u", "f"))

    def test_premio_que_crece_al_bajar_de_categoria_se_rechaza(self):
        raro = {"14": {"acertantes": 6, "premio_euros": 100.0}, "13": {"acertantes": 50, "premio_euros": 900.0},
                "12": {"acertantes": 500, "premio_euros": 10.0}}
        self.assertFalse(losilla.escrutinio_plausible(raro))


if __name__ == "__main__":
    unittest.main()
