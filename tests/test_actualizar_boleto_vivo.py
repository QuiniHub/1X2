import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_boleto_vivo
import actualizar_jornadas_detalle


HTML_QUINIELA15 = """
<html><head><title>Resultados quiniela en directo - jornada 67</title></head><body>
<table>
<tr class="hover:bg-gray-50 transition-colors divide-x divide-gray-100">
  <td class="tnum px-1">1</td>
  <td>
    <span class="block font-medium text-slate-800">EE.UU.</span>
    <span class="block text-xs">(1626.7)</span>
    <span class="block font-medium text-slate-800">Paraguay</span>
  </td>
  <td class="font-bold text-sm md:text-xl"><span>4 - 1</span></td>
</tr>
<tr class="hover:bg-gray-50 transition-colors divide-x divide-gray-100">
  <td class="tnum px-1">14</td>
  <td>
    <span class="block font-medium text-slate-800">Málaga</span>
    <span class="block font-medium text-slate-800">Almería</span>
  </td>
  <td class="font-bold text-sm md:text-xl"><span>Pend.</span></td>
</tr>
<tr class="hover:bg-gray-50 transition-colors divide-x divide-gray-100">
  <td class="tnum px-1">15</td>
  <td>
    <span class="block font-medium text-slate-800">España</span>
    <span class="block font-medium text-slate-800">Cabo Verde</span>
  </td>
  <td class="font-bold text-sm md:text-xl"><span>lunes 15 jun 18:00h</span></td>
  <td class="font-bold text-sm md:text-xl"><span>1-0</span></td>
</tr>
</table></body></html>
"""


class ActualizarBoletoVivoTests(unittest.TestCase):
    def test_parsea_quiniela15_por_casilla(self):
        items = actualizar_boleto_vivo.parsear_quiniela15(HTML_QUINIELA15, "test")
        por_num = {item.num: item for item in items}

        self.assertEqual(actualizar_boleto_vivo.extraer_jornada(HTML_QUINIELA15), 67)
        self.assertEqual(por_num[1].local, "EEUU")
        self.assertEqual(por_num[1].visitante, "Paraguay")
        self.assertEqual(por_num[1].resultado, "4-1")
        self.assertEqual(por_num[14].local, "Malaga CF")
        self.assertEqual(por_num[14].visitante, "UD Almeria")
        self.assertEqual(por_num[15].resultado, "")

    def test_aplica_resultado_y_reemplaza_placeholder(self):
        data = {
            "jornada": 67,
            "estado": "abierta",
            "partidos": [
                {
                    "num": 1,
                    "local": "EEUU",
                    "visitante": "Paraguay",
                    "resultado": "Pendiente",
                    "signo_oficial": "Pendiente",
                },
                {
                    "num": 14,
                    "local": "F1 Hypermotion",
                    "visitante": "F2 Hypermotion",
                    "resultado": "Pendiente",
                    "signo_oficial": "Pendiente",
                },
            ],
            "pleno15": {"num": 15, "local": "España", "visitante": "Cabo Verde"},
        }
        boleto = {
            "jornada": 67,
            "fuente": "test",
            "items": actualizar_boleto_vivo.parsear_quiniela15(HTML_QUINIELA15, "test"),
        }

        cambios = actualizar_boleto_vivo.aplicar_boleto_a_jornada(data, boleto)

        self.assertEqual(data["partidos"][0]["resultado"], "4-1")
        self.assertEqual(data["partidos"][0]["signo_oficial"], "1")
        self.assertEqual(data["partidos"][1]["local"], "Malaga CF")
        self.assertEqual(data["partidos"][1]["visitante"], "UD Almeria")
        self.assertEqual(data["estado"], "en_juego")
        self.assertEqual({c["num"] for c in cambios}, {1, 14})

    def test_main_no_falla_sin_cambios_de_red_mockeados(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "jornadas"
            jornadas.mkdir()
            (jornadas / "jornada_67.json").write_text(
                json.dumps({"jornada": 67, "partidos": [], "pleno15": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            original_jornadas = actualizar_boleto_vivo.JORNADAS
            original_diag = actualizar_boleto_vivo.DIAGNOSTICO
            original_leer = actualizar_boleto_vivo.leer_boleto_vivo
            try:
                actualizar_boleto_vivo.JORNADAS = jornadas
                actualizar_boleto_vivo.DIAGNOSTICO = tmp / "diagnostico.json"
                actualizar_boleto_vivo.leer_boleto_vivo = lambda: {
                    "jornada": 67,
                    "items": [],
                    "fuente": "test",
                    "errores": [],
                }
                actualizar_boleto_vivo.main()
                diag = json.loads((tmp / "diagnostico.json").read_text(encoding="utf-8"))
                self.assertEqual(diag["jornada"], 67)
            finally:
                actualizar_boleto_vivo.JORNADAS = original_jornadas
                actualizar_boleto_vivo.DIAGNOSTICO = original_diag
                actualizar_boleto_vivo.leer_boleto_vivo = original_leer

    def test_fusion_jornada_no_regresa_a_placeholder(self):
        nuevo = {
            "partidos": [
                {"num": 1, "local": "Local 1", "visitante": "Visitante 1"},
                {"num": 14, "local": "Final.2 Playoff", "visitante": "Final.1 Playoff"},
            ],
            "pleno15": {},
        }
        existente = {
            "estado": "en_juego",
            "partidos": [
                {
                    "num": 1,
                    "local": "Local 1",
                    "visitante": "Visitante 1",
                    "resultado": "1-0",
                    "signo_oficial": "1",
                    "fuente_resultado": "quiniela15_resultados",
                },
                {
                    "num": 14,
                    "local": "Malaga CF",
                    "visitante": "UD Almeria",
                    "fuente_equipos": "quiniela15_resultados",
                },
            ],
            "pleno15": {},
        }

        fusionada = actualizar_jornadas_detalle.fusionar_con_existente(nuevo, existente)

        self.assertEqual(fusionada["estado"], "en_juego")
        self.assertEqual(fusionada["partidos"][0]["fuente_resultado"], "quiniela15_resultados")
        self.assertEqual(fusionada["partidos"][1]["local"], "Malaga CF")
        self.assertEqual(fusionada["partidos"][1]["visitante"], "UD Almeria")

    def test_boleto_vivo_recupera_fuente_si_resultado_ya_coincide(self):
        destino = {
            "local": "EEUU",
            "visitante": "Paraguay",
            "resultado": "4-1",
            "signo_oficial": "1",
        }
        origen = actualizar_boleto_vivo.CasillaViva(
            num=1,
            local="EEUU",
            visitante="Paraguay",
            resultado="4-1",
            fuente="quiniela15_resultados",
        )

        cambios = actualizar_boleto_vivo.aplicar_casilla(destino, origen)

        self.assertEqual(cambios, ["fuente_resultado"])
        self.assertEqual(destino["fuente_resultado"], "quiniela15_resultados")


if __name__ == "__main__":
    unittest.main()
