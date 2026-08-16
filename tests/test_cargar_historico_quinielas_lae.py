import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cargar_historico_quinielas_lae as chq


class FechaIsoDesdeTextoTests(unittest.TestCase):
    def test_fecha_de_la_temporada_nueva(self):
        self.assertEqual(chq.fecha_iso_desde_texto("Domingo, 16 de agosto de 2026"), "2026-08-16")

    def test_fecha_con_prefijo_libre(self):
        self.assertEqual(
            chq.fecha_iso_desde_texto("La Quiniela Domingo, 7 de septiembre de 2025"),
            "2025-09-07",
        )

    def test_texto_sin_fecha_reconocible(self):
        self.assertIsNone(chq.fecha_iso_desde_texto("sin fecha aqui"))
        self.assertIsNone(chq.fecha_iso_desde_texto(""))


class CargarJornadasLocalesTemporadaTests(unittest.TestCase):
    """Bug real (16/08/2026): La Quiniela reinicia su numeracion cada
    temporada, asi que jornada_1.json de 26/27 tiene el mismo nombre de
    archivo que tendria una vieja J1 -cargar_jornadas_locales() etiquetaba
    TODO lo que hubiera en data/jornadas/ como "2025/2026" sin mirar la
    fecha real, y la pestaña "Aprendizaje" nunca mostraba una pestaña
    2026/2027 aunque ya hubiera resultados reales de la jornada 1 nueva."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._original_jornadas_dir = chq.JORNADAS_DIR
        self._original_clasificaciones = chq.CLASIFICACIONES_OFICIALES
        chq.JORNADAS_DIR = Path(self._tmpdir.name) / "jornadas"
        chq.JORNADAS_DIR.mkdir(parents=True, exist_ok=True)
        clasif_path = Path(self._tmpdir.name) / "clasificaciones_oficiales.json"
        clasif_path.write_text(json.dumps({"temporada_detectada": "2026/2027"}), encoding="utf-8")
        chq.CLASIFICACIONES_OFICIALES = clasif_path

    def tearDown(self):
        chq.JORNADAS_DIR = self._original_jornadas_dir
        chq.CLASIFICACIONES_OFICIALES = self._original_clasificaciones

    def _escribir_jornada(self, numero, fecha_texto, partidos=14):
        datos = {
            "jornada": numero,
            "fecha": fecha_texto,
            "partidos": [
                {"num": i + 1, "local": f"Local{i}", "visitante": f"Visitante{i}", "signo_oficial": "1"}
                for i in range(partidos)
            ],
        }
        (chq.JORNADAS_DIR / f"jornada_{numero}.json").write_text(
            json.dumps(datos, ensure_ascii=False), encoding="utf-8"
        )

    def test_jornada_de_temporada_vieja_se_queda_en_2025_2026(self):
        self._escribir_jornada(76, "Domingo, 9 de agosto de 2026")
        jornadas = chq.cargar_jornadas_locales()
        self.assertEqual(jornadas[0]["temporada"], "2025/2026")

    def test_jornada_de_temporada_nueva_usa_la_temporada_detectada(self):
        self._escribir_jornada(1, "Domingo, 16 de agosto de 2026")
        jornadas = chq.cargar_jornadas_locales()
        self.assertEqual(jornadas[0]["temporada"], "2026/2027")

    def test_ambas_temporadas_conviven_en_la_misma_carpeta(self):
        self._escribir_jornada(76, "Domingo, 9 de agosto de 2026")
        self._escribir_jornada(1, "Domingo, 16 de agosto de 2026")
        jornadas = chq.cargar_jornadas_locales()
        por_jornada = {j["jornada"]: j["temporada"] for j in jornadas}
        self.assertEqual(por_jornada[76], "2025/2026")
        self.assertEqual(por_jornada[1], "2026/2027")

    def test_sin_fecha_reconocible_cae_en_2025_2026_por_seguridad(self):
        self._escribir_jornada(4, "La Quiniela Domingo, 7 de septiembre de 2025")
        jornadas = chq.cargar_jornadas_locales()
        self.assertEqual(jornadas[0]["temporada"], "2025/2026")


if __name__ == "__main__":
    unittest.main()
