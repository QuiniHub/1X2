import json
import tempfile
import unittest
from pathlib import Path

from bloqueo_jornada import estado_bloqueo_jornada


def guardar(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def jornada(num, con_resultados=False):
    partidos = []
    for idx in range(1, 15):
        partido = {"num": idx, "local": f"Local {idx}", "visitante": f"Visitante {idx}"}
        if con_resultados:
            partido["resultado"] = "1-0" if idx % 2 else "0-1"
            partido["signo_oficial"] = "1" if idx % 2 else "2"
        partidos.append(partido)
    return {"jornada": num, "partidos": partidos}


def escribir_aprendizaje_completo(base, num):
    revisiones = []
    entradas = []
    for idx in range(1, 15):
        revisiones.append({
            "jornada": num,
            "num": idx,
            "partido_id": f"j{num}_p{idx}",
            "signo_predicho": "1",
            "signo_real": "1",
            "acierto": True,
            "probabilidad_signo_real": 60,
            "brier_score": 0.2,
            "ranking_signo_real": 1,
        })
        entradas.append({
            "jornada": num,
            "num": idx,
            "partido_id": f"j{num}_p{idx}",
            "acierto": True,
        })

    guardar(base / "memoria_ia" / "revisiones_prediccion_resultado.json", {
        "version": "1.0",
        "generado_en": "2026-06-20T10:00:00+00:00",
        "revisiones": revisiones,
    })
    guardar(base / "memoria_ia" / "diario_aprendizaje.json", {
        "version": "1.0",
        "generado_en": "2026-06-20T10:00:00+00:00",
        "total_entradas": len(entradas),
        "entradas": entradas,
    })
    guardar(base / "memoria_ia" / "metricas_probabilisticas.json", {
        "version": "1.0",
        "generado_en": "2026-06-20T10:00:00+00:00",
        "partidos_evaluados": 14,
    })
    guardar(base / "memoria_ia" / "fiabilidad_equipos.json", {
        "version": "1.0",
        "generado_en": "2026-06-20T10:00:00+00:00",
        "equipos": {"Local 1": {"partidos_evaluados": 1}},
    })
    guardar(base / "memoria_ia" / "pesos_dinamicos.json", {
        "version": "1.2",
        "generado_en": "2026-06-20T10:00:00+00:00",
        "pesos": {"empate": 0.1},
    })


class BloqueoJornadaTests(unittest.TestCase):
    def test_bloquea_si_la_anterior_no_tiene_resultados_completos(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            guardar(base / "jornadas" / "jornada_98.json", jornada(98, con_resultados=False))

            estado = estado_bloqueo_jornada(99, base)

            self.assertTrue(estado["bloqueada"])
            self.assertEqual(estado["estado_jornada_anterior"], "pendiente")
            self.assertFalse(estado["resultados_completos_anterior"])
            self.assertIn("no tiene 14 resultados", estado["motivo_bloqueo"])

    def test_bloquea_si_hay_resultados_pero_no_aprendizaje(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            guardar(base / "jornadas" / "jornada_98.json", jornada(98, con_resultados=True))

            estado = estado_bloqueo_jornada(99, base)

            self.assertTrue(estado["bloqueada"])
            self.assertEqual(estado["estado_jornada_anterior"], "cerrada")
            self.assertTrue(estado["resultados_completos_anterior"])
            self.assertFalse(estado["aprendizaje_aplicado_anterior"])
            self.assertIn("falta aprendizaje", estado["motivo_bloqueo"])

    def test_desbloquea_si_la_anterior_esta_cerrada_y_aprendida(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            guardar(base / "jornadas" / "jornada_98.json", jornada(98, con_resultados=True))
            escribir_aprendizaje_completo(base, 98)

            estado = estado_bloqueo_jornada(99, base)

            self.assertFalse(estado["bloqueada"])
            self.assertEqual(estado["estado_jornada_anterior"], "aprendida")
            self.assertTrue(estado["resultados_completos_anterior"])
            self.assertTrue(estado["aprendizaje_aplicado_anterior"])
            self.assertEqual(estado["estado_prediccion_actual"], "jugable")


if __name__ == "__main__":
    unittest.main()
