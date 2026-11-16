import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_ligas_football_data as fd
import aplicar_correcciones_resultados as corr


def calendario_base():
    return {
        "competicion": "primera",
        "jornadas": [
            {"jornada": 9, "partidos": [
                {"local": "Rayo Vallecano de Madrid", "visitante": "Athletic Club", "fecha": "2026-10-11",
                 "resultado": "0-0", "estado": "Jugado"},
                {"local": "Valencia CF", "visitante": "Athletic Club", "fecha": "2026-10-18",
                 "resultado": "0-0", "estado": "Jugado"},
            ]},
        ],
    }


class PartidoSuspendidoTests(unittest.TestCase):
    """Caso real: Rayo-Athletic 11/10/2026, suspendido al minuto 25 con 0-0,
    quedo como "Jugado 0-0" en calendario_primera.json y contaminaba la forma
    de los dos equipos (auditoria 16/11/2026)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self._orig_data = corr.DATA
        self._orig_jornadas = corr.JORNADAS
        corr.DATA = self.base
        corr.JORNADAS = self.base / "jornadas"
        (self.base / "jornadas").mkdir()
        (self.base / "calendario_primera.json").write_text(json.dumps(calendario_base()), encoding="utf-8")
        (self.base / "calendario_segunda.json").write_text(json.dumps({"competicion": "segunda", "jornadas": []}), encoding="utf-8")

    def tearDown(self):
        corr.DATA = self._orig_data
        corr.JORNADAS = self._orig_jornadas
        self._tmp.cleanup()

    def test_la_correccion_marca_el_partido_como_suspendido_sin_resultado(self):
        correccion = {"local": "Rayo Vallecano de Madrid", "visitante": "Athletic Club",
                      "resultado": "Pendiente", "estado_calendario": "Suspendido", "motivo": "suspendido al 25'"}
        cambios = corr.aplicar_en_calendarios([correccion])
        self.assertEqual(cambios, 1)
        cal = json.loads((self.base / "calendario_primera.json").read_text(encoding="utf-8"))
        rayo = cal["jornadas"][0]["partidos"][0]
        self.assertEqual(rayo["resultado"], "")
        self.assertEqual(rayo["estado"], "Suspendido")
        # el otro 0-0 (Valencia-Athletic, real) no se toca
        self.assertEqual(cal["jornadas"][0]["partidos"][1]["estado"], "Jugado")
        # sin 'jornada' en la correccion, los ficheros de la Quiniela no se tocan
        self.assertEqual(corr.aplicar_en_jornadas([correccion]), 0)

    def test_football_data_no_vuelve_a_marcar_jugado_un_suspendido(self):
        cal = calendario_base()
        cal["jornadas"][0]["partidos"][0].update({"resultado": "", "estado": "Suspendido"})
        ruta = self.base / "cal.json"
        ruta.write_text(json.dumps(cal), encoding="utf-8")
        original = fd.LIGAS["primera"]["calendario"]
        fd.LIGAS["primera"]["calendario"] = ruta
        try:
            resultados = [{"local": "Rayo Vallecano de Madrid", "visitante": "Athletic Club",
                           "resultado": "0-0", "fecha": "2026-10-11"}]
            _, cambios, _, _ = fd.actualizar_calendario("primera", resultados)
        finally:
            fd.LIGAS["primera"]["calendario"] = original
        self.assertEqual(cambios, 0)
        despues = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(despues["jornadas"][0]["partidos"][0]["estado"], "Suspendido")
        self.assertEqual(despues["jornadas"][0]["partidos"][0]["resultado"], "")


if __name__ == "__main__":
    unittest.main()
