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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import columna_valiente as cv
import test_aud_P4_sombra_snapshot_util as util

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
    """Auditoria 26/11: el marcador lee la columna del snapshot PRE-CIERRE."""

    def _bloque(self, columna=None):
        columna = columna or ["1", "X", "2", "X"] + ["1"] * 10
        masa_col = ["1", "2", "2", "1"] + ["1"] * 10
        return {"estado": "ok", "columna": columna, "columna_masa": masa_col,
                "cambios": [{"num": 2, "local": "A", "visitante": "B", "de": "2", "a": "X", "regla": "R1_sin_dueno"},
                            {"num": 4, "local": "C", "visitante": "D", "de": "1", "a": "X", "regla": "R3_espanol_favorito_fuera"}]}

    def _montar(self, tmp, cerrada=True):
        tmp = Path(tmp)
        (tmp / "pred").mkdir()
        reales = ["1", "X", "2", "1"] + ["1"] * 10
        if not cerrada:
            reales[13] = "Pendiente"
        util.montar_cierre(tmp, 24, {"columna_valiente": self._bloque()},
                           signos={i + 1: r for i, r in enumerate(reales)}, fecha="2026-11-24")
        # el espejo, reescrito con la jornada en juego, dice otra columna: no cuenta
        (tmp / "pred" / "jornada_24.json").write_text(json.dumps(
            {"jornada": 24, "columna_valiente": self._bloque(["2"] * 14)}), encoding="utf-8")
        return tmp

    def _actualizar(self, tmp, etiqueta="2026_2027"):
        ahora = datetime(2026, 11, 27, tzinfo=timezone.utc)
        return cv.actualizar_marcador(tmp / "pred", tmp / "jornadas", tmp / "m.json", etiqueta=etiqueta, ahora=ahora,
                                      dir_snapshots=tmp / "snapshots")

    def test_registra_evalua_y_es_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp)
            r = self._actualizar(tmp)
            self.assertEqual(r["nuevas"], 1)
            self.assertEqual(r["resumen"]["aciertos_valiente"], 13)
            self.assertEqual(r["resumen"]["aciertos_masa"], 13)
            self.assertEqual(r["resumen"]["x_acertadas"], 1)
            self.assertEqual(r["resumen"]["por_regla"]["R1_sin_dueno"]["aciertos"], 1)
            self.assertEqual(r["resumen"]["por_regla"]["R3_espanol_favorito_fuera"]["acertaba_masa"], 1)
            self.assertEqual(r["resumen"]["veredicto"], "en_prueba")
            self.assertEqual(self._actualizar(tmp)["nuevas"], 0)
            # now() en julio de 2027 cambiaba la etiqueta y lo registraba otra vez
            self.assertEqual(self._actualizar(tmp, etiqueta="2027_2028")["nuevas"], 0)
            registros = json.loads((tmp / "m.json").read_text(encoding="utf-8"))["registros"]
            self.assertEqual([x["temporada"] for x in registros], ["2026_2027"])
            self.assertEqual(registros[0]["columna"][:4], ["1", "X", "2", "X"])  # la del snapshot

    def test_jornada_abierta_no_se_registra(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp, cerrada=False)
            self.assertEqual(self._actualizar(tmp)["nuevas"], 0)


class CargarMasaTests(unittest.TestCase):
    """Auditoria 26/11: cargar_masa sin etiqueta buscaba jornada_N en la
    carpeta de CUALQUIER temporada (la mas reciente primero)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self._orig = (cv.PORCENTAJES_DIR, cv.JORNADAS_DIR)
        cv.PORCENTAJES_DIR = self.base / "porcentajes"
        cv.JORNADAS_DIR = self.base / "jornadas"
        carpeta = cv.PORCENTAJES_DIR / "2026_2027"
        carpeta.mkdir(parents=True)
        (carpeta / "jornada_5.json").write_text(json.dumps({
            "jornada": 5, "temporada": "2026_2027",
            "partidos": [{"numero": n, "local": l.upper(), "visitante": v.upper(),
                          "porcentajes": {"1": 60.0, "X": 25.0, "2": 15.0}}
                         for n, (l, v) in enumerate(util.EQUIPOS, start=1)]}), encoding="utf-8")

    def tearDown(self):
        cv.PORCENTAJES_DIR, cv.JORNADAS_DIR = self._orig
        self.tmp.cleanup()

    def test_la_j5_de_la_temporada_siguiente_no_hereda_la_masa_de_la_anterior(self):
        util.escribir_jornada(cv.JORNADAS_DIR, 5, fecha="2027-09-11", nombres=util.OTROS_EQUIPOS)
        self.assertEqual(cv.etiqueta_de_jornada(5), "2027_2028")
        self.assertEqual(cv.cargar_masa(5), {})

    def test_la_jornada_de_su_temporada_si_carga(self):
        util.escribir_jornada(cv.JORNADAS_DIR, 5, fecha="2026-09-12")
        masa = cv.cargar_masa(5, partidos=util.partidos_prediccion(util.EQUIPOS))
        self.assertEqual(len(masa), 14)
        self.assertEqual(masa[1]["1"], 60.0)

    def test_masa_de_otros_equipos_se_descarta(self):
        util.escribir_jornada(cv.JORNADAS_DIR, 5, fecha="2026-09-12")
        self.assertEqual(cv.cargar_masa(5, partidos=util.partidos_prediccion(util.OTROS_EQUIPOS)), {})

    def test_sin_fichero_de_jornada_no_hay_salto_a_otra_temporada(self):
        self.assertEqual(cv.cargar_masa(5), {})
        self.assertEqual(len(cv.cargar_masa(5, "2026_2027")), 14)  # con etiqueta explicita sigue igual


class PublicarBloqueTests(unittest.TestCase):
    def test_escribe_y_retira_en_ultima_y_en_el_espejo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pred = {"jornada": 7, "prediccion_disponible": True, "prediccion_permitida": True}
            (tmp / "ultima.json").write_text(json.dumps(pred), encoding="utf-8")
            (tmp / "jornada_7.json").write_text(json.dumps({"jornada": 7}), encoding="utf-8")
            self.assertEqual(cv.publicar_bloque_sombra("x", {"estado": "ok"}, pred, tmp / "ultima.json"),
                             ["ultima.json", "jornada_7.json"])
            self.assertIn("x", json.loads((tmp / "jornada_7.json").read_text(encoding="utf-8")))
            cv.publicar_bloque_sombra("x", None, pred, tmp / "ultima.json")
            for nombre in ("ultima.json", "jornada_7.json"):
                self.assertNotIn("x", json.loads((tmp / nombre).read_text(encoding="utf-8")))
            self.assertEqual(cv.publicar_bloque_sombra("x", None, pred, tmp / "ultima.json"), [])

    def test_prediccion_publicable(self):
        self.assertTrue(cv.prediccion_publicable({"prediccion_disponible": True, "prediccion_permitida": True}))
        self.assertFalse(cv.prediccion_publicable({"prediccion_disponible": True, "prediccion_permitida": False}))
        self.assertFalse(cv.prediccion_publicable({}))

    def test_veredicto_prerregistrado(self):
        regs = [{"aciertos_valiente": 10, "aciertos_masa": 9, "cambios": []} for _ in range(cv.GRADUACION_MIN_JORNADAS)]
        self.assertEqual(cv.resumen_marcador(regs)["veredicto"], "candidata")
        regs = [{"aciertos_valiente": 8, "aciertos_masa": 10, "cambios": []} for _ in range(cv.GRADUACION_MIN_JORNADAS)]
        self.assertEqual(cv.resumen_marcador(regs)["veredicto"], "suspendida")


if __name__ == "__main__":
    unittest.main()
