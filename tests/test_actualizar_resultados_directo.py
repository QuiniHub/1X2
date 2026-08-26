import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_resultados_directo as ard
from actualizar_resultados_directo import (
    TZ_COMPETICION,
    buscar_resultado_final,
    candidatos_equipo,
    contiene_equipo,
    inicio_partido,
    partido_ya_deberia_tener_resultado,
    partido_esta_programado_en_futuro,
    sincronizar_calendario_liga,
)


class ResultadosDirectoTests(unittest.TestCase):
    def test_hora_cero_se_trata_como_desconocida_no_inicio_real(self):
        hoy = datetime.now(TZ_COMPETICION).date().isoformat()
        partido = {
            "local": "Equipo A",
            "visitante": "Equipo B",
            "fecha": hoy,
            "hora": "00:00",
        }

        self.assertIsNone(inicio_partido(partido))
        self.assertFalse(partido_ya_deberia_tener_resultado(partido))
        self.assertTrue(partido_esta_programado_en_futuro(partido))

    def test_partido_de_hoy_sin_hora_no_se_cierra_por_scraping(self):
        hoy = datetime.now(TZ_COMPETICION).date().isoformat()

        self.assertTrue(partido_esta_programado_en_futuro({
            "local": "Equipo A",
            "visitante": "Equipo B",
            "fecha": hoy,
            "hora": "--:--",
        }))

    def test_partido_futuro_sin_hora_no_se_cierra_por_scraping(self):
        manana = (datetime.now(TZ_COMPETICION).date() + timedelta(days=1)).isoformat()

        self.assertTrue(partido_esta_programado_en_futuro({
            "local": "Equipo A",
            "visitante": "Equipo B",
            "fecha": manana,
            "hora": "",
        }))

    def test_alias_eeuu_detecta_resultado_con_puntos(self):
        texto = "Resultados quiniela jornada 67 EE.UU. - Paraguay 4 - 1 signo 1 final"

        self.assertEqual(
            buscar_resultado_final(texto, {"local": "EEUU", "visitante": "Paraguay"}),
            "4-1",
        )

    def test_espanyol_no_coincide_con_barcelona_por_la_ciudad_compartida(self):
        # Bug real (26/08/2026): "RCD Espanyol de Barcelona" coincidia con
        # "FC Barcelona" solo porque ambos contienen la palabra "barcelona"
        # -contiene_equipo() partia el nombre en palabras sueltas sin
        # excluir la ciudad cuando hay una palabra mas especifica (aqui,
        # "espanyol") disponible.
        self.assertFalse(contiene_equipo("FC Barcelona", "RCD Espanyol de Barcelona"))
        self.assertNotIn("barcelona", candidatos_equipo("RCD Espanyol de Barcelona"))
        self.assertNotIn("madrid", candidatos_equipo("Rayo Vallecano de Madrid"))
        self.assertNotIn("madrid", candidatos_equipo("Club Atletico de Madrid"))
        # OJO -asimetria conocida y no resuelta del todo: "Real Madrid CF" no
        # tiene ninguna palabra distintiva propia aparte de "madrid" (tras
        # quitar "real"/"cf"), asi que sigue coincidiendo con CUALQUIER texto
        # que contenga "madrid" como substring (ej. "Club Atletico de
        # Madrid") -contiene_equipo(texto, equipo) no filtra el lado
        # "texto", solo el lado "equipo". La proteccion real para este caso
        # residual es la guardia de fecha en sincronizar_calendario_liga
        # (ver test de mas abajo), no esta funcion.
        self.assertTrue(contiene_equipo("Club Atletico de Madrid", "Real Madrid CF"))

    def test_real_madrid_y_barcelona_siguen_coincidiendo_consigo_mismos(self):
        # La palabra de ciudad SI debe quedarse cuando es la unica palabra
        # distintiva del nombre (Real Madrid CF -> "madrid" tras quitar
        # "real"/"cf"; FC Barcelona -> "barcelona" tras quitar "fc") -si no,
        # dejarian de reconocerse a si mismos.
        self.assertTrue(contiene_equipo("Real Madrid CF", "Real Madrid"))
        self.assertTrue(contiene_equipo("FC Barcelona", "Barcelona"))

    def test_sincronizar_calendario_no_escribe_en_una_casilla_con_fecha_futura(self):
        # Mismo caso real: un resultado de OTRO partido ya jugado
        # ("RCD Espanyol de Barcelona 1-2 Real Madrid CF") no debe escribirse
        # sobre "FC Barcelona - Rayo Vallecano de Madrid" (fecha futura,
        # todavia sin jugar), ni aunque la coincidencia de nombres fallara
        # por otra via -la guardia de fecha es la ultima linea de defensa.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            original_data = ard.DATA
            manana = (datetime.now(TZ_COMPETICION).date() + timedelta(days=4)).isoformat()
            try:
                ard.DATA = tmp
                calendario_path = tmp / "calendario_primera.json"
                calendario_path.write_text(json.dumps({
                    "jornadas": [{"jornada": 3, "partidos": [
                        {"local": "FC Barcelona", "visitante": "Rayo Vallecano de Madrid", "fecha": manana, "resultado": "", "estado": "Pendiente"},
                    ]}]
                }, ensure_ascii=False), encoding="utf-8")
                (tmp / "calendario_segunda.json").write_text(json.dumps({"jornadas": []}), encoding="utf-8")

                cambios = sincronizar_calendario_liga([
                    {"local": "RCD Espanyol de Barcelona", "visitante": "Real Madrid CF", "resultado": "1-2"},
                ])

                self.assertEqual(cambios, 0)
                data = json.loads(calendario_path.read_text(encoding="utf-8"))
                partido = data["jornadas"][0]["partidos"][0]
                self.assertEqual(partido["estado"], "Pendiente")
                self.assertEqual(partido["resultado"], "")
            finally:
                ard.DATA = original_data


if __name__ == "__main__":
    unittest.main()
