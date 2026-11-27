# -*- coding: utf-8 -*-
"""Contratos estaticos de index.html tras la auditoria del 26/11 (paquete P8_web).

No hay motor de JavaScript en el repo, asi que estos tests leen el texto de
index.html y comprueban que los arreglos siguen ahi (y que no vuelven los
patrones rotos). La comprobacion funcional se hizo en navegador; la lista de
comprobaciones manuales esta en reports/auditoria_2611/P8_web.md.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def funcion(nombre):
    """Texto desde 'function nombre(' hasta la siguiente funcion de primer nivel."""
    inicio = HTML.index(f"function {nombre}(")
    siguiente = re.search(r"\n    (?:async )?function \w+\(", HTML[inicio + 10:])
    return HTML[inicio: inicio + 10 + siguiente.start()] if siguiente else HTML[inicio:]


class BoletoFuenteUnicaTests(unittest.TestCase):
    def test_con_la_estructura_publicada_se_usa_el_boleto_del_motor(self):
        plan = funcion("planAssignments")
        self.assertIn("boletoPublicadoMotor()", plan)
        self.assertIn("publicado.signos[num]", plan)
        self.assertIn("publicado.tipos[num]", plan)

    def test_con_contadores_cambiados_se_parte_del_boleto_publicado(self):
        # Segunda pasada: tocar un contador no puede mover casillas que Marc
        # no ha tocado (bajar un doble movia el triple de P10 a P13).
        plan = funcion("planAssignments")
        self.assertIn("partiendoDelPublicado = true", plan)
        self.assertIn("publicado.tipos[numDe(m)] === 'triple'", plan)
        self.assertIn("publicado.tipos[num] === tipoNuevo", plan)

    def test_se_conserva_la_regla_de_los_sin_dueno_del_16_11(self):
        # Quitarla es decision de modelado (de Marc), no de la auditoria.
        plan = funcion("planAssignments")
        self.assertIn("sinDueno", plan)
        self.assertIn("conDueno", plan)

    def test_una_casilla_vaciada_a_mano_no_se_rellena_sola(self):
        self.assertIn("state.vaciadasAMano.has(String(num)) ? ''", funcion("renderTicket"))
        self.assertIn("state.vaciadasAMano.add(numFila)", HTML)

    def test_los_contadores_tocados_no_se_pisan(self):
        self.assertIn("state.contadoresTocados = true", HTML)
        self.assertIn("!state.contadoresTocados", funcion("init"))
        self.assertNotIn("state.dobles === 0 && state.triples === 0 && !state.generated", HTML)

    def test_los_contadores_arrancan_con_la_estructura_publicada(self):
        init = funcion("init")
        self.assertIn("boletoPublicadoMotor()", init)
        self.assertIn("state.dobles = publicadoInicial.dobles", init)
        self.assertIn("state.triples = publicadoInicial.triples", init)

    def test_respeta_la_x_de_autor_al_repartir_con_otros_contadores(self):
        plan = funcion("planAssignments")
        self.assertIn("cobertura_autor", plan)
        self.assertIn("x_de_autor", plan)


class CosteTests(unittest.TestCase):
    def test_el_elige8_nunca_parte_de_las_apuestas_de_toda_la_quiniela(self):
        coste = funcion("calculateCost")
        self.assertNotIn("let apuestasElige8 = apuestas", coste)
        self.assertIn("let apuestasElige8 = 0", coste)

    def test_con_boleto_real_manda_el_recuento_real_aunque_sea_cero(self):
        coste = funcion("calculateCost")
        self.assertNotIn("real.dobles + real.triples > 0", coste)

    def test_el_interruptor_elige8_refresca_el_panel_de_coste(self):
        inicio = HTML.index("qs('#elige8Toggle').addEventListener('change'")
        manejador = HTML[inicio: HTML.index("qsa('.mode-btn')", inicio)]
        self.assertIn("updateCostPanel()", manejador)

    def test_confirmar_guarda_el_recuento_real(self):
        confirmar = funcion("confirmarQuinielaJugada")
        self.assertIn("dobles: c.dobles", confirmar)
        self.assertNotIn("dobles: state.dobles", confirmar)


class CronologiaChatTests(unittest.TestCase):
    def test_no_quedan_colas_por_numero_en_el_contexto_del_chat(self):
        ctx = funcion("construirContextoIA")
        self.assertNotIn("arr((apr.entradas || [])).slice(-10)", ctx)
        self.assertNotIn("arr(sorpresasM).slice(-6)", ctx)
        self.assertGreaterEqual(ctx.count("ordenarPorFechaReal("), 4)

    def test_el_contexto_se_recorta_por_bloques_y_la_prediccion_va_primero(self):
        ctx = funcion("construirContextoIA")
        bloques = ctx[ctx.index("const bloques = ["):]
        self.assertLess(bloques.index("bloquePredActual"), bloques.index("bloqueMemoriaSocio"))
        self.assertLess(bloques.index("Total cobrado"), bloques.index("bloqueMemoriaSocio"))
        self.assertLess(bloques.index("bloqueMemoriaSocio"), bloques.index("HISTORIAL"))
        self.assertNotIn("contextoCompleto.slice(0, limiteContexto)", HTML)

    def test_el_reintento_413_no_corta_el_preambulo(self):
        self.assertNotIn("m.content.slice(0, 3000) };\n            return m;", HTML)
        self.assertIn("cuerpo.indexOf(MARCA_DATOS)", HTML)
        # La marca tiene que existir en el system prompt y antes de los datos.
        prompt = HTML[HTML.index("const systemPrompt = `"):]
        self.assertLess(prompt.index("DATOS REALES DE TU SISTEMA"), prompt.index("${contexto}"))

    def test_el_reintento_413_cambia_el_manual_largo_por_el_esencial(self):
        # Segunda pasada 27/11: con el manual largo (~7.000 caracteres) el
        # reintento apenas bajaba de tamano y volvia a dar 413.
        groq = funcion("llamarGroq")
        self.assertIn("cuerpo.indexOf('DOCUMENTO OFICIAL: REGLAS COMPLETAS')", groq)
        self.assertIn("MANUAL_ESENCIAL_QUINIELA + '\\n\\n' + cuerpo.slice(finManual)", groq)
        # Las anclas del recorte existen en el prompt y en ese orden.
        prompt = HTML[HTML.index("const systemPrompt = `"):]
        ini = prompt.index("DOCUMENTO OFICIAL: REGLAS COMPLETAS")
        fin = prompt.index("TU PERSONALIDAD:")
        datos = prompt.index("DATOS REALES DE TU SISTEMA")
        self.assertLess(ini, fin)
        self.assertLess(fin, datos)
        self.assertEqual(HTML.count("DOCUMENTO OFICIAL: REGLAS COMPLETAS"), 2)  # prompt + ancla
        # Tamano del reintento: preambulo sin el manual largo + esencial + 1600.
        esencial = HTML[HTML.index("const MANUAL_ESENCIAL_QUINIELA = `"):]
        esencial = esencial[: esencial.index("`;")]
        manual_largo = fin - prompt.rfind("\n", 0, ini - 2)
        preambulo = datos - manual_largo + len(esencial)
        self.assertGreater(manual_largo, 5000)
        self.assertLess(preambulo + 1600, 7000)

    def test_la_sugerencia_cuanto_llevamos_ganado_activa_el_modo_local(self):
        self.assertNotIn("|cuanto llev", HTML)
        self.assertEqual(HTML.count("cu[aá]nto llev|ganado|ganamos"), 2)
        self.assertTrue(re.search("cu[aá]nto llev|ganado|ganamos", "¿Cuánto llevamos ganado?", re.I))


class PremiosTests(unittest.TestCase):
    def test_pendiente_reducida_es_pendiente(self):
        hist = funcion("renderHistory")
        self.assertIn("fuentePremio.startsWith('pendiente')", hist)
        self.assertNotIn("r.fuente_premio === 'pendiente' ||", hist)

    def test_premios_locales_por_temporada_y_jornada(self):
        self.assertNotIn("premiosLocales[String(row.jornada)]", HTML)
        self.assertNotIn("premiosLocales[String(r.jornada)]", HTML)
        self.assertIn("premiosLocales[clavePremioLocal(ref)] =", HTML)

    def test_la_jornada_se_identifica_por_temporada_y_numero(self):
        # Segunda pasada: las filas traen temporada; no se busca solo por numero.
        self.assertNotIn("premioLocalDe(row.jornada)", HTML)
        self.assertNotIn("premioLocalDe(r.jornada)", HTML)
        self.assertIn("normTemporada(j.temporada) === temp", funcion("fechaJornadaJugadaMs"))
        self.assertIn("fechaJornadaJugadaMs(num, temp)", funcion("ordenarPorFechaReal"))
        self.assertIn("data-confirm-temporada=", funcion("renderHistory"))
        self.assertIn("ref.temporada", funcion("refJornada"))

    def test_el_premio_del_pipeline_manda_con_cualquier_fuente_no_pendiente(self):
        # Segunda pasada 27/11: 'escrutinio_versionado' (y las fuentes que
        # vengan) tambien mandan sobre el valor local antiguo.
        manda = funcion("premioDelPipelineManda")
        self.assertIn("fuente !== '' && !fuente.startsWith('pendiente')", manda)
        self.assertNotIn("=== 'confirmado_usuario'", manda)

    def test_el_orden_por_fecha_compara_por_dia_y_coloca_las_filas_sin_fecha(self):
        orden = funcion("ordenarPorFechaReal")
        self.assertIn("Math.floor(ms / DIA)", orden)
        self.assertIn("mejor.r.ms + (x.num - mejor.r.num) * 7 * DIA", orden)
        self.assertNotIn("return Number.isNaN(ms) ? -Infinity : ms;", orden)

    def test_en_mixta_los_contadores_no_cambian_el_elige8_si_el_boleto_no_cambia(self):
        inicio = HTML.index("qsa('[data-counter]')")
        manejador = HTML[inicio: HTML.index("qs('#pleno15')", inicio)]
        self.assertIn("fotoBoleto() === boletoAntes", manejador)
        self.assertIn("state.elige8Set = elige8Antes", manejador)

    def test_los_datos_traen_temporada_en_todas_las_filas(self):
        # CONTRATO CRUZADO: no prueba index.html sino los JSON que escriben
        # otros paquetes (calcular_premios.py y el registro de jugadas). Si
        # falla sin que index.html haya cambiado, el arreglo va en el productor
        # del dato: la web identifica cada jornada por temporada + numero.
        import json
        raiz = ROOT
        hist = json.loads((raiz / "data" / "premios" / "historial_premios.json").read_text(encoding="utf-8"))
        jug = json.loads((raiz / "data" / "quinielas_jugadas.json").read_text(encoding="utf-8"))
        for fila in hist["jornadas"] + jug["jugadas"]:
            self.assertRegex(str(fila.get("temporada")), r"^\d{4}_\d{4}$", fila.get("jornada"))
        claves = [(f["temporada"], f["jornada"]) for f in hist["jornadas"]]
        self.assertEqual(len(claves), len(set(claves)))

    def test_el_chat_se_guarda_por_temporada_y_jornada(self):
        self.assertIn("localStorage.setItem(claveHistorialChat(j)", HTML)
        self.assertNotIn("localStorage.setItem(`quinihub_chat_j${j}`", HTML)

    def test_fecha_validado_usa_el_parser_comun(self):
        self.assertIn("new Date(fechaValidadoMs(valor))", funcion("formatoFechaValidado"))


class TarjetasTests(unittest.TestCase):
    def test_favoritos_en_riesgo_lee_la_clave_que_escribe_el_marcador(self):
        self.assertIn("resumen.esperado ?? resumen.nombrado_esperados", HTML)
        marcador = (ROOT / "ranker_favoritos.py").read_text(encoding="utf-8")
        self.assertIn('"nombrado_esperados"', marcador)

    def test_no_quedan_cifras_de_backtest_escritas_a_mano(self):
        self.assertNotIn("acertó 2 de 15 y perdió 22", HTML)
        self.assertNotIn("0 treces en 22 jornadas", HTML)
        self.assertNotIn("Empieza a contar al cerrar la J24", HTML)
        self.assertNotIn("la de la masa lleva 0)", HTML)

    def test_escapes_en_innerhtml(self):
        self.assertIn("Error: ${escapeHtml(e.message", HTML)
        self.assertNotIn("${gV['0']||'?'}%", HTML)
        self.assertNotIn("`J${j}`, f.partidos,", HTML)
        self.assertNotIn("escapeHtml(tipo), s.valientes, s.aciertos,", HTML)


class SintaxisBasicaTests(unittest.TestCase):
    def test_un_solo_script_inline_y_cierres(self):
        self.assertEqual(HTML.count("<script>"), 1)
        self.assertEqual(len(re.findall(r"<script[ >]", HTML)), HTML.count("</script>"))
        self.assertTrue(HTML.rstrip().endswith("</html>"))

    def test_las_funciones_nuevas_existen_una_sola_vez(self):
        for nombre in ("planAssignments", "boletoPublicadoMotor", "ordenarPorFechaReal",
                       "fechaJornadaJugadaMs", "ensamblarContextoPorBloques", "clavePremioLocal",
                       "premioLocalDe", "temporadaDeFechaMs", "claveHistorialChat", "selectedSigns",
                       "normTemporada", "refJornada"):
            self.assertEqual(HTML.count(f"function {nombre}("), 1, nombre)


if __name__ == "__main__":
    unittest.main()
