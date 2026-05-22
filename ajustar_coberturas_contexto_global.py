from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
MOTOR = ROOT / "motor_prediccion_quiniela.py"
WORKFLOW = ROOT / ".github" / "workflows" / "main.yml"
VERIFICADOR = ROOT / "verificar_coherencia_pronostico.py"

WEB_TRIPLE_OLD = '''      if (top === "X" && tercera >= 18) score += 25;
      if (localNecesita && visitanteNecesita) score += 70;
      if ((localDescenso || visitanteDescenso) && localNecesita && visitanteNecesita) score += 45;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) score += 35;
      return score;'''

WEB_TRIPLE_NEW = '''      const dueloNecesidades = localNecesita && visitanteNecesita;
      const necesitadoVsCerrado = (localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado);
      const ambosCerrados = localCerrado && visitanteCerrado;

      if (top === "X" && tercera >= 18) score += 25;
      if (dueloNecesidades) score += 95;
      if ((localDescenso || visitanteDescenso) && dueloNecesidades) score += 60;
      if (necesitadoVsCerrado) {
        score -= 55;
        if (tercera >= 22 && margenProbabilidadBoleto(partido) <= 10) score += 25;
      }
      if (ambosCerrados) score -= 35;
      return score;'''

WEB_DOUBLE_OLD = '''      if (tercera < 10) score += 45;
      else if (tercera >= 22) score -= 50;
      if (margen < 12) score += 30;
      if (top === "X") score += 8;
      return score;'''

WEB_DOUBLE_NEW = '''      const localComp = partido.contexto_competitivo_local;
      const visitanteComp = partido.contexto_competitivo_visitante;
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const dueloNecesidades = localNecesita && visitanteNecesita;
      const necesitadoVsCerrado = (localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado);

      if (tercera < 10) score += 45;
      else if (tercera >= 22) score -= 50;
      if (margen < 12) score += 30;
      if (necesitadoVsCerrado) score += 55;
      if (dueloNecesidades && margen < 14) score += 25;
      if (top === "X") score += 8;
      return score;'''

MOTOR_TRIPLE_OLD = '''    if top == "X" and tercera >= 18:
        score += 25
    if local_necesita and visitante_necesita:
        score += 70
    if (local_descenso or visitante_descenso) and local_necesita and visitante_necesita:
        score += 45
    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        score += 35
    return score'''

MOTOR_TRIPLE_NEW = '''    duelo_necesidades = local_necesita and visitante_necesita
    necesitado_vs_cerrado = (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado)
    ambos_cerrados = local_cerrado and visitante_cerrado
    margen = valores[0] - valores[1] if len(valores) > 1 else 0

    if top == "X" and tercera >= 18:
        score += 25
    if duelo_necesidades:
        score += 95
    if (local_descenso or visitante_descenso) and duelo_necesidades:
        score += 60
    if necesitado_vs_cerrado:
        score -= 55
        if tercera >= 22 and margen <= 10:
            score += 25
    if ambos_cerrados:
        score -= 35
    return score'''

MOTOR_DOUBLE_OLD = '''    if tercera < 10:
        score += 45
    elif tercera >= 22:
        score -= 50
    if margen < 12:
        score += 30
    if top == "X":
        score += 8
    return score'''

MOTOR_DOUBLE_NEW = '''    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    duelo_necesidades = local_necesita and visitante_necesita
    necesitado_vs_cerrado = (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado)

    if tercera < 10:
        score += 45
    elif tercera >= 22:
        score -= 50
    if margen < 12:
        score += 30
    if necesitado_vs_cerrado:
        score += 55
    if duelo_necesidades and margen < 14:
        score += 25
    if top == "X":
        score += 8
    return score'''


def replace_block(text, old, new, label):
    if old in text:
        return text.replace(old, new), True
    if new in text:
        return text, False
    raise SystemExit(f"No encuentro bloque {label}")


def patch_file(path, replacements):
    text = path.read_text(encoding="utf-8")
    original = text
    changed_labels = []
    for label, old, new in replacements:
        text, changed = replace_block(text, old, new, label)
        if changed:
            changed_labels.append(label)
    if text != original:
        path.write_text(text, encoding="utf-8")
    return changed_labels


def patch_workflow():
    text = WORKFLOW.read_text(encoding="utf-8")
    original = text
    marker = "          python corregir_elige8_web.py\n"
    insertion = "          python ajustar_coberturas_contexto_global.py\n"
    if insertion not in text:
        if marker not in text:
            raise SystemExit("No encuentro donde insertar ajustar_coberturas_contexto_global.py en workflow")
        text = text.replace(marker, marker + insertion)
    if text != original:
        WORKFLOW.write_text(text, encoding="utf-8")
        return ["workflow"]
    return []


def patch_verificador():
    text = VERIFICADOR.read_text(encoding="utf-8")
    original = text
    checks = {
        '"duelo_necesidades_web"': '"duelo_necesidades_web": "dueloNecesidades",',
        '"necesitado_vs_cerrado_web"': '"necesitado_vs_cerrado_web": "necesitadoVsCerrado",',
        '"duelo_necesidades_motor"': '"duelo_necesidades_motor": "duelo_necesidades",',
        '"necesitado_vs_cerrado_motor"': '"necesitado_vs_cerrado_motor": "necesitado_vs_cerrado",',
    }
    # Insert lightweight checks near existing priority checks when possible.
    if '"prioridad_triples_web"' in text and checks['"duelo_necesidades_web"'] not in text:
        text = text.replace('"prioridad_triples_web": "prioridadTripleAnalisis(b) - prioridadTripleAnalisis(a)",', '"prioridad_triples_web": "prioridadTripleAnalisis(b) - prioridadTripleAnalisis(a)",\n    "duelo_necesidades_web": "dueloNecesidades",\n    "necesitado_vs_cerrado_web": "necesitadoVsCerrado",')
    if '"prioridad_triples_motor"' in text and checks['"duelo_necesidades_motor"'] not in text:
        text = text.replace('"prioridad_triples_motor": "def prioridad_triple",', '"prioridad_triples_motor": "def prioridad_triple",\n    "duelo_necesidades_motor": "duelo_necesidades",\n    "necesitado_vs_cerrado_motor": "necesitado_vs_cerrado",')
    if text != original:
        VERIFICADOR.write_text(text, encoding="utf-8")
        return ["verificador"]
    return []


def main():
    changed = []
    changed += [f"index:{x}" for x in patch_file(INDEX, [
        ("triple web", WEB_TRIPLE_OLD, WEB_TRIPLE_NEW),
        ("doble web", WEB_DOUBLE_OLD, WEB_DOUBLE_NEW),
    ])]
    changed += [f"motor:{x}" for x in patch_file(MOTOR, [
        ("triple motor", MOTOR_TRIPLE_OLD, MOTOR_TRIPLE_NEW),
        ("doble motor", MOTOR_DOUBLE_OLD, MOTOR_DOUBLE_NEW),
    ])]
    changed += patch_workflow()
    changed += patch_verificador()
    print("Coberturas revisadas con contexto global:", ", ".join(changed) if changed else "sin cambios")


if __name__ == "__main__":
    main()
