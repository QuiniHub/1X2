import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import diagnostico_sistema
import generar_estado_vivo_ia
import motor_prediccion_quiniela


def escribir_jornada(base, numero, signos):
    partidos = [
        {
            "num": idx + 1,
            "local": f"Local {idx + 1}",
            "visitante": f"Visitante {idx + 1}",
            "resultado": "1-0" if signo in {"1", "X", "2"} else "Pendiente",
            "signo_oficial": signo,
        }
        for idx, signo in enumerate(signos)
    ]
    path = base / f"jornada_{numero}.json"
    path.write_text(
        json.dumps(
            {
                "jornada": numero,
                "fecha": "2026-06-08",
                "partidos": partidos,
                "pleno15": {"resultado": "1-0", "signo_oficial": "1"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class JornadaActivaTests(unittest.TestCase):
    def test_jornada_cerrada_mas_reciente_no_vuelve_a_pendiente_antigua(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            jornadas.mkdir(parents=True)
            escribir_jornada(jornadas, 64, ["1"] * 13 + ["Pendiente"])
            escribir_jornada(jornadas, 66, ["1"] * 14)

            original_motor = motor_prediccion_quiniela.JORNADAS
            original_estado = generar_estado_vivo_ia.JORNADAS
            original_diag_jornadas = diagnostico_sistema.JORNADAS
            original_diag_root = diagnostico_sistema.ROOT
            try:
                motor_prediccion_quiniela.JORNADAS = jornadas
                generar_estado_vivo_ia.JORNADAS = jornadas
                diagnostico_sistema.JORNADAS = jornadas
                diagnostico_sistema.ROOT = tmp

                self.assertEqual(motor_prediccion_quiniela.detectar_jornada_activa(), 66)
                jornada_leida = generar_estado_vivo_ia.leer_jornada_actual()
                self.assertEqual(jornada_leida.get("jornada"), 66)
                estado_jornada = generar_estado_vivo_ia.cambios_jornada_actual(jornada_leida)
                self.assertEqual(
                    generar_estado_vivo_ia.estado_publicacion_jornada(estado_jornada),
                    "jornada_cerrada_analizada",
                )

                alertas = []
                resumen = diagnostico_sistema.diagnosticar_jornadas(alertas)
                self.assertEqual(resumen["jornada_actual"]["jornada"], 66)
                self.assertEqual(resumen["jornada_actual"]["cerrados"], 14)
                self.assertFalse(
                    any("jornada 64" in alerta.get("detalle", "").lower() for alerta in alertas)
                )
            finally:
                motor_prediccion_quiniela.JORNADAS = original_motor
                generar_estado_vivo_ia.JORNADAS = original_estado
                diagnostico_sistema.JORNADAS = original_diag_jornadas
                diagnostico_sistema.ROOT = original_diag_root


if __name__ == "__main__":
    unittest.main()
