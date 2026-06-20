import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_jornadas_detalle as jornadas


def lineas_jornada_fragmentada(numero, fecha_texto, partidos):
    lineas = [f"JORNADA Nº {numero}", fecha_texto, "P.", "Equipos", "Fecha", "Hora"]
    for num, local, visitante in partidos:
        lineas.extend([str(num), local, "-", visitante, "23/06/2026", "00:00"])
    lineas.append("Estado: Jornada programada")
    return lineas


class ActualizarJornadasDetalleTests(unittest.TestCase):
    def test_extrae_jornada_fragmentada_con_pleno(self):
        partidos = [
            (1, "Noruega", "Senegal"),
            (2, "Jordania", "Argelia"),
            (3, "Portugal", "Uzbekistán"),
            (4, "Inglaterra", "Ghana"),
            (5, "Panamá", "Croacia"),
            (6, "Colombia", "RD Congo"),
            (7, "Suiza", "Canadá"),
            (8, "Bosnia", "Qatar"),
            (9, "Escocia", "Brasil"),
            (10, "Marruecos", "Haití"),
            (11, "Sudáfrica", "Rep. Corea"),
            (12, "Curazao", "Costa Marfil"),
            (13, "Ecuador", "Alemania"),
            (14, "IFK Mariehamn", "HJK Helsinki"),
            (15, "Rep. Checa", "México"),
        ]

        extraidas = jornadas.extraer_jornadas_desde_lineas(
            lineas_jornada_fragmentada(69, "Martes, 23 de junio de 2026", partidos)
        )
        jornada_json = jornadas.jornada_a_json(extraidas[0])

        self.assertEqual(extraidas[0]["jornada"], 69)
        self.assertEqual(extraidas[0]["fecha_texto"], "Martes, 23 de junio de 2026")
        self.assertEqual(len(extraidas[0]["items"]), 15)
        self.assertEqual(len(jornada_json["partidos"]), 14)
        self.assertEqual(jornada_json["partidos"][0]["local"], "Noruega")
        self.assertEqual(jornada_json["partidos"][13]["visitante"], "HJK Helsinki")
        self.assertEqual(jornada_json["pleno15"]["local"], "Rep. Checa")
        self.assertEqual(jornada_json["pleno15"]["fecha"], "2026-06-23")


if __name__ == "__main__":
    unittest.main()
