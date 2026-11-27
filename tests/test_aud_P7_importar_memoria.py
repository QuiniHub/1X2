"""Auditoria 26/11/2026, paquete P7 (hallazgos 51, 128, 146 y 249).

El importador de quinielas jugadas vive incrustado en
.github/workflows/importar-memoria-quinielas.yml. Este test extrae ese
bloque de Python y lo ejecuta tal cual en un directorio temporal, con un
issue de mentira: si el bloque del workflow se rompe, falla aqui.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "importar-memoria-quinielas.yml"

SIGNOS = ["1", "1X", "2", "1", "X", "1X2", "1", "2", "1", "X2", "1", "1", "12", "1"]


def script_del_workflow():
    texto = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    inicio = texto.index("python - <<'PY'\n") + len("python - <<'PY'\n")
    fin = texto.index("\n          PY\n", inicio)
    return textwrap.dedent(texto[inicio:fin] + "\n")


def jornada_oficial(numero, fecha):
    return {"jornada": numero, "partidos": [
        {"num": n, "local": f"L{n}", "visitante": f"V{n}", "fecha": fecha} for n in range(1, 15)]}


class ImportadorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        (self.dir / "data" / "jornadas").mkdir(parents=True)
        shutil.copy(ROOT / "cronologia_jornadas.py", self.dir / "cronologia_jornadas.py")
        self.memoria = self.dir / "data" / "quinielas_jugadas.json"

    def escribir_memoria(self, jugadas):
        self.memoria.write_text(json.dumps({"version": "1.0", "jugadas": jugadas}), encoding="utf-8")

    def escribir_jornada(self, numero, fecha):
        (self.dir / "data" / "jornadas" / f"jornada_{numero}.json").write_text(
            json.dumps(jornada_oficial(numero, fecha)), encoding="utf-8")

    def importar(self, jugadas, tipo="memoria_quinielas_jugadas"):
        payload = {"tipo": tipo, "jugadas": jugadas}
        cuerpo = "Texto\n```json\n" + json.dumps(payload) + "\n```\n"
        evento = self.dir / "evento.json"
        evento.write_text(json.dumps({"issue": {"body": cuerpo}}), encoding="utf-8")
        entorno = dict(os.environ, GITHUB_EVENT_PATH=str(evento), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-"], input=script_del_workflow(), text=True,
                              capture_output=True, cwd=self.dir, env=entorno, timeout=120)

    def jugadas(self):
        return json.loads(self.memoria.read_text(encoding="utf-8"))["jugadas"]

    def test_el_bloque_del_workflow_es_python_valido(self):
        compile(script_del_workflow(), "importar-memoria-quinielas.yml", "exec")

    def test_no_pisa_ni_hereda_de_la_jugada_de_otra_temporada(self):
        # J5 de la 25/26 con premio declarado; llega la J5 de la 26/27.
        vieja = {"jornada": 5, "signos": ["1"] * 14, "elige8": [], "pleno15": "1-0",
                 "validado_en": "2025-09-13T09:00:00+00:00", "premio_eur": 123.45,
                 "modalidad": "reducida", "nota": "de la temporada pasada", "importe_total": 40.5}
        self.escribir_memoria([vieja])
        self.escribir_jornada(5, "2026-09-09")
        r = self.importar([{"jornada": 5, "signos": SIGNOS, "elige8": [1, 2, 3, 4, 5, 6, 7, 8],
                            "pleno15": "2-1", "validado_en": "2026-09-08T10:00:00.000Z"}])
        self.assertEqual(r.returncode, 0, r.stderr)
        jugadas = self.jugadas()
        self.assertEqual(len(jugadas), 2)
        por_temporada = {j["temporada"]: j for j in jugadas}
        self.assertEqual(set(por_temporada), {"2025_2026", "2026_2027"})
        self.assertEqual(por_temporada["2025_2026"]["premio_eur"], 123.45)
        self.assertEqual(por_temporada["2025_2026"]["signos"], ["1"] * 14)
        nueva = por_temporada["2026_2027"]
        for heredado in ("premio_eur", "modalidad", "nota", "importe_total"):
            self.assertNotIn(heredado, nueva)
        self.assertEqual(nueva["signos"], SIGNOS)
        self.assertEqual(nueva["pleno15"], "2-1")
        # Orden cronologico: la temporada vieja primero aunque el numero coincida.
        self.assertEqual([j["temporada"] for j in jugadas], ["2025_2026", "2026_2027"])

    def test_reimportar_la_misma_jornada_conserva_sus_campos(self):
        self.escribir_jornada(24, "2026-11-24")
        actual = {"jornada": 24, "signos": ["1"] * 14, "elige8": [], "pleno15": "",
                  "validado_en": "2026-11-24T10:00:00+00:00", "premio_eur": 7.5}
        self.escribir_memoria([actual])
        r = self.importar([{"jornada": 24, "signos": SIGNOS, "validado_en": "2026-11-24T12:00:00Z"}])
        self.assertEqual(r.returncode, 0, r.stderr)
        jugadas = self.jugadas()
        self.assertEqual(len(jugadas), 1)
        self.assertEqual(jugadas[0]["premio_eur"], 7.5)
        self.assertEqual(jugadas[0]["signos"], SIGNOS)
        self.assertEqual(jugadas[0]["temporada"], "2026_2027")

    def test_las_jugadas_existentes_reciben_su_temporada_real(self):
        # J76 de la 25/26 se valido en agosto de 2026; J1 de la 26/27, una semana despues.
        self.escribir_memoria([
            {"jornada": 76, "signos": ["1"] * 14, "validado_en": "2026-08-06T10:00:00Z"},
            {"jornada": 1, "signos": ["1"] * 14, "validado_en": "2026-08-15T06:45:14.841Z"},
            {"jornada": 60, "signos": ["1"] * 14, "validado_en": "13/5/2026, 13:12:31"},
        ])
        self.escribir_jornada(25, "2026-11-28")
        r = self.importar([{"jornada": 25, "signos": SIGNOS}])
        self.assertEqual(r.returncode, 0, r.stderr)
        temporadas = {j["jornada"]: j["temporada"] for j in self.jugadas()}
        self.assertEqual(temporadas, {60: "2025_2026", 76: "2025_2026", 1: "2026_2027", 25: "2026_2027"})
        self.assertEqual([j["jornada"] for j in self.jugadas()], [60, 76, 1, 25])

    def test_jugadas_antiguas_sin_temporada_no_se_pisan_entre_si(self):
        # Dos jugadas viejas con el mismo numero, sin 'temporada' y con un
        # validado_en que no se puede interpretar: antes caian las dos en la
        # clave ("", 7) y la segunda borraba a la primera en silencio.
        a = {"jornada": 7, "signos": ["1"] * 14, "validado_en": "sin fecha", "nota": "A"}
        b = {"jornada": 7, "signos": ["2"] * 14, "validado_en": "tampoco", "nota": "B"}
        self.escribir_memoria([a, b])
        self.escribir_jornada(9, "2026-09-20")
        r = self.importar([{"jornada": 9, "signos": SIGNOS, "validado_en": "2026-09-19T10:00:00Z"}])
        self.assertEqual(r.returncode, 0, r.stderr)
        notas = sorted(j.get("nota") for j in self.jugadas() if j["jornada"] == 7)
        self.assertEqual(notas, ["A", "B"])
        self.assertEqual(len(self.jugadas()), 3)

    def test_normaliza_signos_y_rechaza_los_invalidos(self):
        self.escribir_jornada(25, "2026-11-28")
        desordenados = ["2X1", "x1", "11", "XX", "1 2"] + ["1"] * 9
        r = self.importar([{"jornada": 25, "signos": desordenados}])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.jugadas()[0]["signos"][:5], ["1X2", "1X", "1", "X", "12"])
        validos = {"1", "X", "2", "1X", "12", "X2", "1X2"}
        self.assertTrue(set(self.jugadas()[0]["signos"]) <= validos)

    def test_un_signo_con_basura_invalida_la_jugada(self):
        for malos in (["3"] + ["1"] * 13, ["1A"] + ["1"] * 13, [""] + ["1"] * 13, ["1"] * 13):
            if self.memoria.exists():
                self.memoria.unlink()
            r = self.importar([{"jornada": 25, "signos": malos}])
            self.assertNotEqual(r.returncode, 0, malos)
            self.assertFalse(self.memoria.exists())

    def test_jugada_que_no_es_un_objeto_no_revienta(self):
        self.escribir_jornada(25, "2026-11-28")
        r = self.importar(["esto no es una jugada", None, 7, {"jornada": 25, "signos": SIGNOS}])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.jugadas()), 1)

    def test_validado_en_libre_no_se_copia(self):
        self.escribir_jornada(25, "2026-11-28")
        for malo in ("2099-01-01T00:00:00Z", "ayer por la tarde", 12345, {"a": 1}):
            r = self.importar([{"jornada": 25, "signos": SIGNOS, "validado_en": malo}])
            self.assertEqual(r.returncode, 0, r.stderr)
            jugada = self.jugadas()[0]
            self.assertIsInstance(jugada["validado_en"], str)
            self.assertNotEqual(jugada["validado_en"][:4], "2099")
            self.assertEqual(jugada["temporada"], "2026_2027")
            self.memoria.unlink()

    def test_pleno15_solo_admite_un_marcador_de_pleno(self):
        self.escribir_jornada(25, "2026-11-28")
        casos = {"2 -1": "2-1", "m-0": "M-0", "M-M": "M-M", "4-0": "", "texto libre": "", None: ""}
        for entrada, esperado in casos.items():
            r = self.importar([{"jornada": 25, "signos": SIGNOS, "pleno15": entrada}])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.jugadas()[0]["pleno15"], esperado, entrada)
            self.memoria.unlink()

    def test_tipo_desconocido_se_rechaza(self):
        r = self.importar([{"jornada": 25, "signos": SIGNOS}], tipo="otra_cosa")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.memoria.exists())

    def test_funciona_sin_el_modulo_de_cronologia(self):
        (self.dir / "cronologia_jornadas.py").unlink()
        self.escribir_memoria([{"jornada": 76, "signos": ["1"] * 14, "validado_en": "2026-08-06T10:00:00Z"}])
        r = self.importar([{"jornada": 1, "signos": SIGNOS, "validado_en": "2026-08-15T06:45:14.841Z"}])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual({j["jornada"]: j["temporada"] for j in self.jugadas()},
                         {76: "2025_2026", 1: "2026_2027"})


if __name__ == "__main__":
    unittest.main()
