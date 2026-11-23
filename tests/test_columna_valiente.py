"""Tests de la Columna Valiente europea (23/11/2026): deteccion de jornada
europea, reglas R1/R3/R4/R5, gigantes informativos y marcador idempotente."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import columna_valiente as cv

ESP = {cv._norm(n) for n in ("Real Betis Balompie", "Villarreal CF", "RC Celta de Vigo", "Real Sociedad de Futbol",
                             "Real Madrid CF", "FC Barcelona", "Getafe CF")}


def _p(num, local, visitante, motor, signo_final="1"):
    return {"num": num, "local": local, "visitante": visitante,
            "probabilidades": dict(zip(("1", "X", "2"), motor)), "signo_final": signo_final}


def _jornada_europea():
    partidos = [
        _p(1, "Arsenal", "Borussia Dortmund", (63, 22, 15)),
        _p(2, "Feyenoord", "Oporto", (34, 30, 37)),
        _p(3, "Sabah", "FC Barcelona", (17, 22, 61)),
        _p(4, "Slavia Praga", "Villarreal CF", (25, 28, 47)),
        _p(5, "Slovan Bratislava", "Real Betis Balompie", (17, 24, 59)),
        _p(6, "Shakhtar D.", "Fenerbahce", (36, 31, 33)),
    ] + [_p(n, f"L{n}", f"V{n}", (60, 22, 18)) for n in range(7, 15)]
    masa = {1: {"1": 70, "X": 17, "2": 13}, 2: {"1": 32, "X": 31, "2": 37}, 3: {"1": 16, "X": 11, "2": 73},
            4: {"1": 26, "X": 26, "2": 48}, 5: {"1": 18, "X": 21, "2": 61}, 6: {"1": 36, "X": 32, "2": 32}}
    for n in range(7, 15):
        masa[n] = {"1": 82, "X": 10, "2": 8}
    return partidos, masa


class DeteccionTests(unittest.TestCase):
    def test_jornada_europea_y_domestica(self):
        partidos, _ = _jornada_europea()
        self.assertTrue(cv.es_jornada_europea(partidos, ESP)[0])
        domestica = [_p(n, "Real Madrid CF", "Getafe CF", (60, 22, 18)) for n in range(1, 15)]
        self.assertFalse(cv.es_jornada_europea(domestica, ESP)[0])
        bloque = cv.construir_bloque({"jornada": 30, "partidos": domestica}, masa={}, espanoles=ESP)
        self.assertEqual(bloque["estado"], "no_aplica")


class ReglasTests(unittest.TestCase):
    def test_reglas_sobre_la_columna(self):
        partidos, masa = _jornada_europea()
        sorpresa = {"estado": "ok", "num": 5, "signo": "X", "senales": [{"tipo": "empatador", "texto": "Betis empata mucho"}]}
        col, col_masa, cambios, descartes, gigantes = cv.construir_columna(partidos, masa, ESP, sorpresa)
        self.assertEqual(col_masa[2], "2")
        self.assertEqual(col[2], "X")  # R1 sin dueno
        self.assertEqual(col[6], "X")  # R1 sin dueno (favorito 36)
        self.assertEqual(col[4], "X")  # R3 Villarreal favorito fuera al 48 -> no-favorito mas probable (X 28 > 1 25)
        self.assertEqual(col[5], "X")  # R5 sorpresa nombrada (Betis al 61 < 80)
        self.assertEqual(col[3], "2")  # Barca al 73 no es sin dueno ni espanol fuera; gigante solo informativo
        self.assertEqual(col[1], "1")
        reglas = sorted(c["regla"] for c in cambios)
        self.assertEqual(reglas, ["R1_sin_dueno", "R1_sin_dueno", "R3_espanol_favorito_fuera", "R5_sorpresa_nombrada"])
        nums_gigantes = sorted(g["num"] for g in gigantes)
        self.assertEqual(nums_gigantes, [1, 3])  # 70 y 73; los del 82 son intocables y no se listan
        self.assertEqual(descartes, [])

    def test_r4_intocable_frena_a_la_sorpresa_nombrada(self):
        partidos, masa = _jornada_europea()
        sorpresa = {"estado": "ok", "num": 7, "signo": "X", "senales": []}
        col, _, cambios, descartes, _ = cv.construir_columna(partidos, masa, ESP, sorpresa)
        self.assertEqual(col[7], "1")
        self.assertTrue(any(d["num"] == 7 for d in descartes))
        self.assertFalse(any(c["regla"] == "R5_sorpresa_nombrada" for c in cambios))

    def test_tope_de_cambios(self):
        partidos = [_p(n, f"L{n}", f"V{n}", (34, 33, 33)) for n in range(1, 15)]
        masa = {n: {"1": 36, "X": 32, "2": 32} for n in range(1, 15)}
        col, _, cambios, _, _ = cv.construir_columna(partidos, masa, ESP, None)
        self.assertEqual(len(cambios), cv.CAMBIOS_MAX)
        self.assertEqual(sum(1 for s in col.values() if s == "X"), cv.CAMBIOS_MAX)

    def test_bloque_ok_cuenta_x_y_esperados(self):
        partidos, masa = _jornada_europea()
        bloque = cv.construir_bloque({"jornada": 24, "partidos": partidos}, masa=masa, espanoles=ESP)
        self.assertEqual(bloque["estado"], "ok")
        self.assertEqual(bloque["x_en_columna"], 3)
        self.assertEqual(len(bloque["columna"]), 14)
        self.assertGreater(bloque["esperados_masa"], bloque["esperados_valiente"])
        self.assertIn("gigantes_en_riesgo", bloque)


class MarcadorTests(unittest.TestCase):
    def _montar(self, tmp, cerrada=True):
        tmp = Path(tmp)
        (tmp / "pred").mkdir()
        (tmp / "jor").mkdir()
        columna = ["1", "X", "2", "X"] + ["1"] * 10
        masa_col = ["1", "2", "2", "1"] + ["1"] * 10
        bloque = {"estado": "ok", "columna": columna, "columna_masa": masa_col,
                  "cambios": [{"num": 2, "local": "A", "visitante": "B", "de": "2", "a": "X", "regla": "R1_sin_dueno"},
                              {"num": 4, "local": "C", "visitante": "D", "de": "1", "a": "X", "regla": "R3_espanol_favorito_fuera"}]}
        (tmp / "pred" / "jornada_24.json").write_text(json.dumps({"jornada": 24, "columna_valiente": bloque}), encoding="utf-8")
        reales = ["1", "X", "2", "1"] + ["1"] * 10
        if not cerrada:
            reales[13] = "Pendiente"
        partidos = [{"num": i + 1, "local": f"L{i}", "visitante": f"V{i}", "signo_oficial": r} for i, r in enumerate(reales)]
        (tmp / "jor" / "jornada_24.json").write_text(json.dumps({"jornada": 24, "partidos": partidos}), encoding="utf-8")
        return tmp

    def test_registra_evalua_y_es_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp)
            ahora = datetime(2026, 11, 27, tzinfo=timezone.utc)
            r = cv.actualizar_marcador(tmp / "pred", tmp / "jor", tmp / "m.json", etiqueta="2026_2027", ahora=ahora)
            self.assertEqual(r["nuevas"], 1)
            self.assertEqual(r["resumen"]["aciertos_valiente"], 13)
            self.assertEqual(r["resumen"]["aciertos_masa"], 13)
            self.assertEqual(r["resumen"]["x_acertadas"], 1)
            self.assertEqual(r["resumen"]["por_regla"]["R1_sin_dueno"]["aciertos"], 1)
            self.assertEqual(r["resumen"]["por_regla"]["R3_espanol_favorito_fuera"]["acertaba_masa"], 1)
            self.assertEqual(r["resumen"]["veredicto"], "en_prueba")
            r2 = cv.actualizar_marcador(tmp / "pred", tmp / "jor", tmp / "m.json", etiqueta="2026_2027", ahora=ahora)
            self.assertEqual(r2["nuevas"], 0)

    def test_jornada_abierta_no_se_registra(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp, cerrada=False)
            r = cv.actualizar_marcador(tmp / "pred", tmp / "jor", tmp / "m.json", etiqueta="2026_2027")
            self.assertEqual(r["nuevas"], 0)

    def test_veredicto_prerregistrado(self):
        regs = [{"aciertos_valiente": 10, "aciertos_masa": 9, "cambios": []} for _ in range(cv.GRADUACION_MIN_JORNADAS)]
        self.assertEqual(cv.resumen_marcador(regs)["veredicto"], "candidata")
        regs = [{"aciertos_valiente": 8, "aciertos_masa": 10, "cambios": []} for _ in range(cv.GRADUACION_MIN_JORNADAS)]
        self.assertEqual(cv.resumen_marcador(regs)["veredicto"], "suspendida")


if __name__ == "__main__":
    unittest.main()
