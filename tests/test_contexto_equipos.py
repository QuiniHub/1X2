import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_contexto_equipos


class ContextoEquiposTests(unittest.TestCase):
    def test_equipos_objetivo_incluye_boleto_activo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "jornadas"
            jornadas.mkdir()
            clasificaciones = tmp / "clasificaciones.json"
            clasificaciones.write_text(
                json.dumps({"primera": [{"equipo": "Equipo Liga"}], "segunda": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (jornadas / "jornada_67.json").write_text(
                json.dumps(
                    {
                        "jornada": 67,
                        "partidos": [
                            {"num": 4, "local": "Haití", "visitante": "Escocia"},
                        ],
                        "pleno15": {"local": "España", "visitante": "Cabo Verde"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            original_jornadas = actualizar_contexto_equipos.JORNADAS
            original_clasificaciones = actualizar_contexto_equipos.CLASIFICACIONES
            try:
                actualizar_contexto_equipos.JORNADAS = jornadas
                actualizar_contexto_equipos.CLASIFICACIONES = clasificaciones

                equipos = actualizar_contexto_equipos.equipos_objetivo()
            finally:
                actualizar_contexto_equipos.JORNADAS = original_jornadas
                actualizar_contexto_equipos.CLASIFICACIONES = original_clasificaciones

        indice = {actualizar_contexto_equipos.normalizar(item["equipo"]): item for item in equipos}
        self.assertIn("haiti", indice)
        self.assertIn("escocia", indice)
        self.assertIn("espana", indice)
        self.assertIn("cabo verde", indice)
        self.assertIn("boleto_activo", indice["haiti"]["origenes"])
        self.assertEqual(indice["haiti"]["partido"], 4)


if __name__ == "__main__":
    unittest.main()
