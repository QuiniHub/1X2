import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_jornadas_detalle as jornadas
import actualizar_jornadas_detalle as detalle


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


class FusionResultadosMismoParTests(unittest.TestCase):
    """Bug real 01/09/2026: al renovar los emparejamientos de jornada_5.json
    (legado 25/26 -> reales 26/27), fusionar_con_existente heredaba los
    resultados del archivo viejo POR POSICION y la jornada quedaba "cerrada"
    con 14 signos del año pasado pegados a partidos sin jugar. Los
    resultados solo pueden sobrevivir si el emparejamiento es EL MISMO."""

    def _nuevo(self):
        return {
            "jornada": 5,
            "partidos": [{
                "num": 1, "local": "Borussia Dortmund", "visitante": "Villarreal CF",
                "fecha": "2026-09-08", "resultado": "Pendiente",
                "signo_oficial": "Pendiente", "signo_nuestro": "No jugada",
            }],
            "pleno15": {
                "num": 15, "local": "Liverpool", "visitante": "Atletico",
                "resultado": "Pendiente", "signo_oficial": "Pendiente",
            },
        }

    def test_resultado_no_sobrevive_a_un_cambio_de_equipos(self):
        existente = {
            "partidos": [{
                "num": 1, "local": "Getafe CF", "visitante": "Sevilla FC",
                "resultado": "2-0", "signo_oficial": "1",
            }],
            "pleno15": {"num": 15, "local": "Otro", "visitante": "Par", "resultado": "3-2", "signo_oficial": "1"},
        }
        fusionado = detalle.fusionar_con_existente(self._nuevo(), existente)
        p1 = fusionado["partidos"][0]
        self.assertEqual(p1["resultado"], "Pendiente")
        self.assertEqual(p1["signo_oficial"], "Pendiente")
        self.assertEqual(fusionado["pleno15"]["resultado"], "Pendiente")
        self.assertNotEqual(fusionado.get("estado"), "cerrada")

    def test_resultado_si_sobrevive_con_los_mismos_equipos(self):
        existente = {
            "partidos": [{
                "num": 1, "local": "Borussia Dortmund", "visitante": "Villarreal CF",
                "resultado": "2-1", "signo_oficial": "1",
            }],
        }
        fusionado = detalle.fusionar_con_existente(self._nuevo(), existente)
        self.assertEqual(fusionado["partidos"][0]["resultado"], "2-1")
        self.assertEqual(fusionado["partidos"][0]["signo_oficial"], "1")

    def test_no_se_cierra_una_jornada_con_partidos_en_el_futuro(self):
        import datetime as _dt
        manana = (_dt.date.today() + _dt.timedelta(days=2)).isoformat()
        data = {"partidos": [
            {"num": 1, "local": "A", "visitante": "B", "fecha": manana, "signo_oficial": "1"},
        ]}
        detalle.recalcular_estado_jornada(data)
        self.assertEqual(data["estado"], "en_juego")

    def test_temporada_libertad_se_calcula_de_la_fecha(self):
        # estaba hardcodeada "2025-2026" y el respaldo servia jornadas viejas
        self.assertNotIn("2025-2026", detalle.FUENTE_LIBERTAD)
        self.assertRegex(detalle.temporada_libertad_actual(), r"^\d{4}-\d{4}$")
