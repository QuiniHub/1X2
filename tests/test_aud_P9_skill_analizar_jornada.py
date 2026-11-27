"""Auditoria 26/11, hallazgos 110 y 211: el skill /analizar-jornada describia
el metodo de agosto (sin mercado 0,85, sin congelado al cierre, sin
optimizador, leyendo jornada_N.json por numero).

Comprobacion documental: el skill tiene que nombrar las piezas del metodo
vigente, y lo que nombra tiene que existir en el repo (para que el skill no
vuelva a quedarse atras en silencio cuando se renombre algo).
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SKILL = ROOT / ".claude" / "skills" / "analizar-jornada" / "SKILL.md"


# Auditoria 26/11 (revision): main.yml ejecuta TODA la carpeta tests ANTES del
# pipeline. Un test que falle ahi deja de publicar la web cada 30 minutos, y el
# pipeline (que es quien regeneraria el fichero) ya no se ejecuta. Por eso las
# comprobaciones que no protegen lo que la web carga no corren en el cron
# (GITHUB_EVENT_NAME schedule / workflow_dispatch): corren en local y en
# ci-pr.yml.
EN_CRON_DE_PUBLICACION = os.environ.get("GITHUB_EVENT_NAME") in ("schedule", "workflow_dispatch")


def _texto():
    return SKILL.read_text(encoding="utf-8")


@unittest.skipIf(EN_CRON_DE_PUBLICACION,
                 "test documental: no debe parar la publicacion automatica")
class SkillMetodoVigenteTests(unittest.TestCase):
    def test_cabecera_del_skill_intacta(self):
        texto = _texto()
        self.assertTrue(texto.startswith("---\nname: analizar-jornada\n") or
                        texto.startswith("---\r\nname: analizar-jornada\r\n"))
        self.assertIn("description:", texto.split("---")[1])

    def test_nombra_las_piezas_del_metodo_vigente(self):
        texto = _texto()
        for pieza in (
            "PESO_MERCADO_MANDA",                            # el mercado manda
            "data/backtesting/pre_cierre/jornada_N.json",    # prediccion congelada al cierre
            "cronologia_jornadas",                           # jornadas por fecha
            "optimizador_boleto",                            # base del boleto
            "sorpresa_nombrada",
            "elige8_ev",
            "calendario_primera.json", "calendario_segunda.json",  # tabla de rachas
            "project_protocolo_bote.md",
            "feedback_cubrir_lo_que_se_nombra.md",
            "feedback_rachas_casa_fuera.md",
            "feedback_futbol_primero.md",
        ):
            with self.subTest(pieza=pieza):
                self.assertIn(pieza, texto)

    def test_avisa_de_que_la_numeracion_se_reinicia(self):
        texto = _texto().lower()
        self.assertIn("se reinicia cada", texto)
        self.assertIn("por fecha", texto)
        # la instruccion vieja de leer el fichero "con el numero que toque"
        # solo puede aparecer para prohibirla
        for m in re.finditer(r"n[uú]mero que toque", texto):
            contexto = texto[max(0, m.start() - 120):m.start()]
            self.assertIn("no abrir", contexto)

    def test_ya_no_describe_el_metodo_de_agosto(self):
        texto = _texto()
        self.assertNotIn("solo por margen de mercado", texto)
        self.assertNotIn("motor decía: <signo_final>", texto)
        self.assertNotIn("calidad_datos: <valor>", texto)

    def test_el_elige8_es_calculadora_y_la_apuesta_es_de_marc(self):
        texto = _texto()
        self.assertIn("CALCULADORA", texto)
        self.assertIn("nunca ejecutar la apuesta", texto.lower())

    def test_las_rutas_del_repo_que_cita_existen(self):
        texto = _texto()
        for ruta in (
            "cronologia_jornadas.py", "motor_prediccion_quiniela.py",
            "data/predicciones/ultima_prediccion.json",
            "data/calendario_primera.json", "data/calendario_segunda.json",
            "data/clasificaciones_oficiales.json",
            "data/memoria_ia/contexto_competitivo.json",
            "data/memoria_ia/ceses_actuales.json",
            "data/quinielas_jugadas.json",
            "data/memoria_ia/memoria_socio.json",
            "CUADERNO_OJEADOR.md", "DECISION_LOG.md",
        ):
            with self.subTest(ruta=ruta):
                self.assertIn(ruta.split("/")[-1], texto)
                self.assertTrue((ROOT / ruta).exists(), f"el skill cita {ruta} y no existe")

    def test_las_funciones_y_constantes_que_cita_existen(self):
        import cronologia_jornadas as cj
        for nombre in ("jornada_en_curso_o_proxima", "ultima_jornada_cerrada", "prediccion_del_cierre"):
            with self.subTest(nombre=nombre):
                self.assertIn(nombre, _texto())
                self.assertTrue(callable(getattr(cj, nombre, None)))
        motor = (ROOT / "motor_prediccion_quiniela.py").read_text(encoding="utf-8")
        # El peso es decision de modelado de Marc: aqui NO se fija su valor.
        # Se lee del motor y se exige que el skill cite ese mismo numero.
        m = re.search(r"(?m)^PESO_MERCADO_MANDA\s*=\s*([0-9]+(?:\.[0-9]+)?)", motor)
        self.assertIsNotNone(m, "el motor ya no define PESO_MERCADO_MANDA: revisar el skill")
        peso = m.group(1).rstrip("0").rstrip(".") if "." in m.group(1) else m.group(1)
        self.assertIn(
            peso.replace(".", ","), _texto(),
            f"el motor usa PESO_MERCADO_MANDA = {m.group(1)} y el skill /analizar-jornada "
            f"cita otro peso: actualizar .claude/skills/analizar-jornada/SKILL.md")

    def test_los_bloques_de_la_prediccion_que_cita_existen(self):
        # Fixture minima con las claves que escribe el motor (no se lee la
        # prediccion viva: cambia cada 30 minutos). Lo que se comprueba es que
        # el skill no cite un bloque con un nombre que el codigo ya no escribe.
        fuentes = "".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in ROOT.glob("*.py")
        )
        for bloque in ("optimizador_boleto", "sorpresa_nombrada", "favoritos_en_riesgo",
                       "radar_tormenta", "tercero_valor", "columna_valiente",
                       "elige8_ev", "elige8_modos", "boleto_ev_premio", "boleto_millonario",
                       "alternativas_por_presupuesto", "lectura_contra_masa",
                       "cubierta_por_boleto", "bandera_recomendado_publicable",
                       "alguna_recomendada"):
            with self.subTest(bloque=bloque):
                self.assertIn(bloque, _texto())
                self.assertIn(json.dumps(bloque), fuentes)


if __name__ == "__main__":
    unittest.main()
