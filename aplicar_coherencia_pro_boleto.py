from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
MOTOR = ROOT / "motor_prediccion_quiniela.py"
CONTEXTO = ROOT / "generar_contexto_competitivo.py"
WORKFLOW = ROOT / ".github" / "workflows" / "main.yml"
ACTUALIZAR = ROOT / "actualizar_todo.py"
VERIFICADOR = ROOT / "verificar_coherencia_pronostico.py"


CONTEXT_OLD = '    salvado = equipo["puntos"] > equipo_descenso["maximo_puntos"]\n'
CONTEXT_NEW = '    salvado = equipo["puntos"] >= equipo_descenso["maximo_puntos"]\n'

MOTOR_FUNC_MARKER = '''def prioridad_cobertura(partido):'''
MOTOR_FUNC_NEW = '''def prioridad_autocritica_cobertura(partido):
    probs = partido.get("probabilidades", {})
    valores = sorted(probs.values(), reverse=True)
    top_prob = valores[0] if valores else 0
    margen = valores[0] - valores[1] if len(valores) > 1 else 0
    tercera = valores[2] if len(valores) > 2 else 0
    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    duelo_necesidades = local_necesita and visitante_necesita
    necesitado_vs_cerrado = (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado)

    score = 0
    if partido.get("riesgo_necesidad_real"):
        score += 35
    if top_prob < 55:
        score += 55
    if margen < 12:
        score += 45
    elif margen < 18:
        score += 25
    if probs.get("X", 0) >= 35:
        score += 20
    if duelo_necesidades:
        score += 60
    if necesitado_vs_cerrado:
        score += 35
    if tercera >= 18 and duelo_necesidades:
        score += 35
    return score


def partido_pide_cobertura_por_autocritica(partido):
    return prioridad_autocritica_cobertura(partido) >= 80


def prioridad_cobertura(partido):'''

MOTOR_DOUBLE_OLD = '''    score = prioridad_cobertura(partido)'''
MOTOR_DOUBLE_NEW = '''    score = prioridad_cobertura(partido) + prioridad_autocritica_cobertura(partido)'''

MOTOR_TRIPLE_OLD = '''    score = prioridad_cobertura(partido)

    if tercera >= 18:'''
MOTOR_TRIPLE_NEW = '''    score = prioridad_cobertura(partido) + prioridad_autocritica_cobertura(partido) * 0.75

    if tercera >= 18:'''

MOTOR_EXPLAIN_OLD = '''    else:
        razones.append("Se deja como fijo porque el signo principal tiene mejor relacion entre probabilidad y riesgo.")'''
MOTOR_EXPLAIN_NEW = '''    else:
        if partido_pide_cobertura_por_autocritica(partido):
            razones.append("Fijo condicionado: el analisis lo marca como peligroso; entra en cola prioritaria de cobertura y debe subir a doble/triple antes que partidos con menos justificacion si el presupuesto lo permite.")
        else:
            razones.append("Se deja como fijo porque el signo principal tiene mejor relacion entre probabilidad y riesgo.")'''

WEB_FUNC_MARKER = '''    function prioridadCoberturaAnalisis(partido) {'''
WEB_FUNC_NEW = '''    function prioridadAutocriticaCobertura(partido) {
      const probs = partido.probabilidades || {};
      const valores = valoresProbabilidadOrdenados(partido);
      const topProb = valores.length ? valores[0] : 0;
      const margen = margenProbabilidadBoleto(partido);
      const tercera = terceraProbabilidadBoleto(partido);
      const localComp = partido.contexto_competitivo_local;
      const visitanteComp = partido.contexto_competitivo_visitante;
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const dueloNecesidades = localNecesita && visitanteNecesita;
      const necesitadoVsCerrado = (localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado);

      let score = 0;
      if (partido.riesgo_necesidad) score += 35;
      if (topProb < 55) score += 55;
      if (margen < 12) score += 45;
      else if (margen < 18) score += 25;
      if ((probs["X"] || 0) >= 35) score += 20;
      if (dueloNecesidades) score += 60;
      if (necesitadoVsCerrado) score += 35;
      if (tercera >= 18 && dueloNecesidades) score += 35;
      return score;
    }

    function partidoPideCoberturaPorAutocritica(partido) {
      return prioridadAutocriticaCobertura(partido) >= 80;
    }

    function prioridadCoberturaAnalisis(partido) {'''

WEB_TRIPLE_OLD = '''      let score = prioridadCoberturaAnalisis(partido);

      if (tercera >= 18) score += 85;'''
WEB_TRIPLE_NEW = '''      let score = prioridadCoberturaAnalisis(partido) + prioridadAutocriticaCobertura(partido) * 0.75;

      if (tercera >= 18) score += 85;'''

WEB_DOUBLE_OLD = '''      let score = prioridadCoberturaAnalisis(partido);

      const localComp = partido.contexto_competitivo_local;'''
WEB_DOUBLE_NEW = '''      let score = prioridadCoberturaAnalisis(partido) + prioridadAutocriticaCobertura(partido);

      const localComp = partido.contexto_competitivo_local;'''

WEB_TEXT_OLD = '''      let lecturaTipo = partido.riesgo_necesidad
        ? "Fijo condicionado: el analisis lo marca como peligroso; si hay mas presupuesto debe subir a doble o triple antes que un partido sin necesidad viva."
        : "Se deja fijo porque el signo principal mantiene ventaja suficiente frente a las alternativas.";'''
WEB_TEXT_NEW = '''      let lecturaTipo = partidoPideCoberturaPorAutocritica(partido)
        ? "Fijo condicionado: el analisis lo marca como peligroso; entra en cola prioritaria de cobertura y debe subir a doble o triple antes que partidos con menos justificacion si el presupuesto lo permite."
        : "Se deja fijo porque el signo principal mantiene ventaja suficiente frente a las alternativas.";'''


def replace_once(text, old, new, label):
    if old in text:
        return text.replace(old, new, 1), True
    if new in text:
        return text, False
    raise SystemExit(f"No encuentro bloque {label}")


def insert_before(text, marker, block, label):
    if block in text:
        return text, False
    if marker not in text:
        raise SystemExit(f"No encuentro marcador {label}")
    return text.replace(marker, block, 1), True


def patch_contexto():
    text = CONTEXTO.read_text(encoding="utf-8")
    original = text
    text, _ = replace_once(text, CONTEXT_OLD, CONTEXT_NEW, "salvado >= corte descenso")
    if text != original:
        CONTEXTO.write_text(text, encoding="utf-8")
        return ["contexto"]
    return []


def patch_motor():
    text = MOTOR.read_text(encoding="utf-8")
    original = text
    text, ch1 = insert_before(text, MOTOR_FUNC_MARKER, MOTOR_FUNC_NEW, "prioridad_autocritica motor")
    # Only replace the first post-insert triple score occurrence and the later double occurrence safely.
    text, ch2 = replace_once(text, MOTOR_TRIPLE_OLD, MOTOR_TRIPLE_NEW, "triple autocritica motor")
    if MOTOR_DOUBLE_NEW not in text:
        idx = text.find("def prioridad_doble(partido):")
        if idx == -1:
            raise SystemExit("No encuentro prioridad_doble motor")
        head, tail = text[:idx], text[idx:]
        tail, ch3 = replace_once(tail, MOTOR_DOUBLE_OLD, MOTOR_DOUBLE_NEW, "doble autocritica motor")
        text = head + tail
    else:
        ch3 = False
    text, ch4 = replace_once(text, MOTOR_EXPLAIN_OLD, MOTOR_EXPLAIN_NEW, "texto fijo condicionado motor")
    if text != original:
        MOTOR.write_text(text, encoding="utf-8")
        return ["motor"]
    return []


def patch_index():
    text = INDEX.read_text(encoding="utf-8")
    original = text
    text, ch1 = insert_before(text, WEB_FUNC_MARKER, WEB_FUNC_NEW, "prioridadAutocritica web")
    text, ch2 = replace_once(text, WEB_TRIPLE_OLD, WEB_TRIPLE_NEW, "triple autocritica web")
    text, ch3 = replace_once(text, WEB_DOUBLE_OLD, WEB_DOUBLE_NEW, "doble autocritica web")
    text, ch4 = replace_once(text, WEB_TEXT_OLD, WEB_TEXT_NEW, "texto fijo condicionado web")
    if text != original:
        INDEX.write_text(text, encoding="utf-8")
        return ["index"]
    return []


def patch_line_in_list(path, after, line):
    text = path.read_text(encoding="utf-8")
    original = text
    if line in text:
        return []
    if after not in text:
        raise SystemExit(f"No encuentro marcador {after} en {path.name}")
    text = text.replace(after, after + line, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return [path.name]
    return []


def patch_workflows():
    changed = []
    changed += patch_line_in_list(
        WORKFLOW,
        "          python ajustar_coberturas_contexto_global.py\n",
        "          python aplicar_coherencia_pro_boleto.py\n",
    )
    changed += patch_line_in_list(
        ACTUALIZAR,
        '    "ajustar_coberturas_contexto_global.py",\n',
        '    "aplicar_coherencia_pro_boleto.py",\n',
    )
    return changed


def patch_verificador():
    text = VERIFICADOR.read_text(encoding="utf-8")
    original = text
    if '"autocritica_cobertura_web"' not in text:
        text = text.replace(
            '    "prioridad_dobles_web": "prioridadDobleAnalisis(b) - prioridadDobleAnalisis(a)",\n',
            '    "prioridad_dobles_web": "prioridadDobleAnalisis(b) - prioridadDobleAnalisis(a)",\n    "autocritica_cobertura_web": "function prioridadAutocriticaCobertura",\n    "cola_prioritaria_web": "partidoPideCoberturaPorAutocritica",\n',
        )
    if '"autocritica_cobertura_motor"' not in text:
        text = text.replace(
            '    "prioridad_dobles_motor": "def prioridad_doble",\n',
            '    "prioridad_dobles_motor": "def prioridad_doble",\n    "autocritica_cobertura_motor": "def prioridad_autocritica_cobertura",\n    "cola_prioritaria_motor": "partido_pide_cobertura_por_autocritica",\n',
        )
    if text != original:
        VERIFICADOR.write_text(text, encoding="utf-8")
        return ["verificador"]
    return []


def main():
    changed = []
    changed += patch_contexto()
    changed += patch_motor()
    changed += patch_index()
    changed += patch_workflows()
    changed += patch_verificador()
    print("Coherencia pro boleto aplicada:", ", ".join(changed) if changed else "sin cambios")


if __name__ == "__main__":
    main()
