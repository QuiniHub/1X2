import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
MOTOR = ROOT / "motor_prediccion_quiniela.py"

CORE_HELPERS = r'''
    function normalizarCompetitivoTextoBoleto(texto) {
      return norm(String(texto || "").replaceAll("_", " "));
    }

    function textoCompetitivoBoleto(equipo) {
      const objetivos = (equipo?.objetivos || [])
        .map(o => `${o.objetivo || ""} ${o.estado || ""} ${o.lectura || ""}`)
        .join(" ");
      return normalizarCompetitivoTextoBoleto(`${objetivos} ${equipo?.situacion_competitiva || ""} ${equipo?.motivacion_competitiva || ""} ${equipo?.motivacion || ""}`);
    }

    function objetivosVivosBoleto(equipo) {
      if (!equipo) return [];
      const vivosDirectos = Array.isArray(equipo.objetivos_vivos) ? equipo.objetivos_vivos : [];
      const vivosObjetivos = (equipo.objetivos || []).filter(o => o?.vivo === true && o?.terminal !== true);
      return [...vivosDirectos, ...vivosObjetivos];
    }

    function equipoObjetivoCerradoBoleto(equipo) {
      if (!equipo) return false;
      if (objetivosVivosBoleto(equipo).length) return false;
      const objetivos = equipo.objetivos || [];
      if (objetivos.some(o => o?.terminal === true)) return true;
      const texto = textoCompetitivoBoleto(equipo);
      return texto.includes("asegurado matematicamente")
        || texto.includes("campeon matematico")
        || texto.includes("salvado matematicamente")
        || texto.includes("descendido matematicamente")
        || texto.includes("sin opciones matematicas")
        || texto.includes("sin opciones")
        || texto.includes("no se juega nada");
    }

    function equipoNecesidadVivaBoleto(equipo) {
      if (!equipo) return false;
      if (equipoObjetivoCerradoBoleto(equipo)) return false;
      const texto = textoCompetitivoBoleto(equipo);
      const motivacion = valorMotivacionCompetitiva(equipo);
      return objetivosVivosBoleto(equipo).length > 0
        || motivacion >= 2
        || texto.includes("defiende")
        || texto.includes("aspira")
        || texto.includes("riesgo")
        || texto.includes("descenso")
        || texto.includes("permanencia")
        || texto.includes("playoff")
        || texto.includes("ascenso")
        || texto.includes("conference")
        || texto.includes("europa")
        || texto.includes("champions");
    }

    function contieneDescensoVivoBoleto(equipo) {
      if (!equipo || equipoObjetivoCerradoBoleto(equipo)) return false;
      const vivosTexto = objetivosVivosBoleto(equipo)
        .map(o => `${o.objetivo || ""} ${o.estado || ""} ${o.lectura || ""}`)
        .join(" ");
      const texto = normalizarCompetitivoTextoBoleto(`${vivosTexto} ${textoCompetitivoBoleto(equipo)}`);
      return texto.includes("descenso") || texto.includes("permanencia") || texto.includes("salvarse");
    }

    function signoTopProbabilidad(probs) {
      return Object.entries(probs || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || "X";
    }
'''

PATTERN_HELPERS = r'''
    function tasaPatronCompetitivo(patrones, clave) {
      return Number(patrones?.patrones?.[clave]?.tasa_sorpresa || 0);
    }

    function ajustarPorPatronesAprendidosWeb(probs, localComp, visitanteComp, patrones) {
      const p = { ...probs };
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localDescenso = contieneDescensoVivoBoleto(localComp);
      const visitanteDescenso = contieneDescensoVivoBoleto(visitanteComp);
      const top = signoTopProbabilidad(p);

      if (visitanteCerrado && localNecesita) {
        const tasa = tasaPatronCompetitivo(patrones, "necesitado_local_vs_visitante_objetivo_cerrado");
        p["1"] += 16 + tasa * 0.16;
        p["X"] += 11 + tasa * 0.09;
        p["2"] -= 12;
      }
      if (localCerrado && visitanteNecesita) {
        const tasa = tasaPatronCompetitivo(patrones, "visitante_necesitado_vs_local_objetivo_cerrado");
        p["2"] += 16 + tasa * 0.16;
        p["X"] += 11 + tasa * 0.09;
        p["1"] -= 12;
      }
      if (visitanteDescenso && top === "1") {
        const tasa = tasaPatronCompetitivo(patrones, "visitante_descenso_vs_local_favorito");
        p["X"] += 16 + tasa * 0.12;
        p["2"] += 18 + tasa * 0.16;
        p["1"] -= 20;
      }
      if (localDescenso && top === "2") {
        const tasa = tasaPatronCompetitivo(patrones, "local_descenso_vs_visitante_favorito");
        p["X"] += 16 + tasa * 0.12;
        p["1"] += 18 + tasa * 0.16;
        p["2"] -= 20;
      }
      if (localNecesita && visitanteNecesita) {
        p["X"] += 7;
      }
      return normalizarProbabilidades(p);
    }

    function bonusPatronesAprendidosWeb(localComp, visitanteComp, patrones, probs) {
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localDescenso = contieneDescensoVivoBoleto(localComp);
      const visitanteDescenso = contieneDescensoVivoBoleto(visitanteComp);
      const top = signoTopProbabilidad(probs);
      let bonus = 0;

      if (visitanteCerrado && localNecesita) bonus += 24 + tasaPatronCompetitivo(patrones, "necesitado_local_vs_visitante_objetivo_cerrado") * 0.38;
      if (localCerrado && visitanteNecesita) bonus += 24 + tasaPatronCompetitivo(patrones, "visitante_necesitado_vs_local_objetivo_cerrado") * 0.38;
      if (visitanteDescenso && top === "1") bonus += 72 + tasaPatronCompetitivo(patrones, "visitante_descenso_vs_local_favorito") * 0.55;
      if (localDescenso && top === "2") bonus += 72 + tasaPatronCompetitivo(patrones, "local_descenso_vs_visitante_favorito") * 0.55;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) {
        bonus += 22 + tasaPatronCompetitivo(patrones, "equipo_necesitado_vs_equipo_sin_objetivo") * 0.34;
      }
      if (localNecesita && visitanteNecesita) bonus += 20;
      return Math.round(bonus * 10) / 10;
    }

    function riesgoNecesidadRealBoleto(localComp, visitanteComp) {
      return equipoNecesidadVivaBoleto(localComp)
        || equipoNecesidadVivaBoleto(visitanteComp)
        || contieneDescensoVivoBoleto(localComp)
        || contieneDescensoVivoBoleto(visitanteComp);
    }

    function prioridadCoberturaAnalisis(partido) {
      const localComp = partido.contexto_competitivo_local;
      const visitanteComp = partido.contexto_competitivo_visitante;
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const localDescenso = contieneDescensoVivoBoleto(localComp);
      const visitanteDescenso = contieneDescensoVivoBoleto(visitanteComp);
      const top = signoTopProbabilidad(partido.probabilidades || {});
      const valores = Object.values(partido.probabilidades || {}).sort((a, b) => b - a);
      const margen = valores.length > 1 ? valores[0] - valores[1] : 0;
      let score = Number(partido.incertidumbre || 0) + Number(partido.bonus_competitivo || 0);

      if (partido.riesgo_necesidad) score += 25;
      if (localDescenso || visitanteDescenso) score += 70;
      if (localDescenso && visitanteDescenso) score += 40;
      if ((visitanteDescenso && top === "1") || (localDescenso && top === "2")) score += 85;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) score += 75;
      if (localNecesita && visitanteNecesita) score += 45;
      if (partido.riesgo === "Alto") score += 10;
      if (margen < 8) score += 28;
      else if (margen < 16) score += 18;
      return score;
    }
'''


def replace_one(text, old, new, desc):
    if old not in text:
        raise SystemExit(f"No encuentro bloque para {desc}.")
    return text.replace(old, new, 1)


def replace_regex(text, pattern, new, desc):
    updated, count = re.subn(pattern, new, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"No encuentro bloque para {desc}.")
    return updated


def pattern_helpers(preservar_prioridad):
    helpers = PATTERN_HELPERS.strip("\n")
    if preservar_prioridad:
        helpers = re.sub(
            r"\n\n    function prioridadCoberturaAnalisis\(partido\) \{.*?\n    \}",
            "",
            helpers,
            count=1,
            flags=re.S,
        )
    return helpers


def patch_index(html):
    core_new = "\n" + CORE_HELPERS.strip("\n") + "\n\n    function bonusRiesgoCompetitivo(localComp, visitanteComp, probs) {"
    if "function normalizarCompetitivoTextoBoleto" in html:
        html = replace_regex(
            html,
            r"\n    function normalizarCompetitivoTextoBoleto\(texto\) \{.*?\n\n    function bonusRiesgoCompetitivo\(localComp, visitanteComp, probs\) \{",
            core_new,
            "helpers competitivos web",
        )
    else:
        html = replace_regex(
            html,
            r"\n    function textoCompetitivoBoleto\(equipo\) \{.*?\n\n    function bonusRiesgoCompetitivo\(localComp, visitanteComp, probs\) \{",
            core_new,
            "helpers competitivos web",
        )

    if "function valoresProbabilidadOrdenados(partido)" in html:
        pattern_new = "\n" + pattern_helpers(preservar_prioridad=True) + "\n\n    function valoresProbabilidadOrdenados(partido) {"
        html = replace_regex(
            html,
            r"\n    function tasaPatronCompetitivo\(patrones, clave\) \{.*?\n\n    function valoresProbabilidadOrdenados\(partido\) \{",
            pattern_new,
            "patrones web",
        )
    else:
        pattern_new = "\n" + pattern_helpers(preservar_prioridad=False) + "\n\n    function puntosCasaFueraTexto(equipo, condicion) {"
        html = replace_regex(
            html,
            r"\n    function tasaPatronCompetitivo\(patrones, clave\) \{.*?\n\n    function puntosCasaFueraTexto\(equipo, condicion\) \{",
            pattern_new,
            "patrones web",
        )

    call = "probs = ajustarPorPatronesAprendidosWeb(probs, contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos);"
    if call not in html:
        html = replace_one(
            html,
            '''          let probs = analisis?.probabilidades || { "1": 37, "X": 31, "2": 32 };
          probs = ajustarProbabilidades(probs, p.local, p.visitante, clasif, contextoCompetitivo);

          const riesgo = analisis?.riesgo_sorpresa || "Alto";
''',
            '''          let probs = analisis?.probabilidades || { "1": 37, "X": 31, "2": 32 };
          probs = ajustarProbabilidades(probs, p.local, p.visitante, clasif, contextoCompetitivo);
          probs = ajustarPorPatronesAprendidosWeb(probs, contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos);

          const riesgo = analisis?.riesgo_sorpresa || "Alto";
''',
            "ajuste de probabilidades antes del signo",
        )

    if "const riesgoNecesidad = riesgoNecesidadRealBoleto" not in html:
        html = replace_one(
            html,
            '''          const bonusCompetitivo = bonusRiesgoCompetitivo(contextoCompetitivoLocal, contextoCompetitivoVisitante, probs)
            + bonusPatronesAprendidosWeb(contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos, probs);

          return {
''',
            '''          const bonusCompetitivo = bonusRiesgoCompetitivo(contextoCompetitivoLocal, contextoCompetitivoVisitante, probs)
            + bonusPatronesAprendidosWeb(contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos, probs);
          const riesgoNecesidad = riesgoNecesidadRealBoleto(contextoCompetitivoLocal, contextoCompetitivoVisitante);

          return {
''',
            "riesgo real de necesidad",
        )

    html = html.replace("riesgo_necesidad: bonusCompetitivo >= 18", "riesgo_necesidad: riesgoNecesidad")
    html = html.replace(
        "const porRiesgo = [...partidos].sort((a, b) => b.incertidumbre - a.incertidumbre);",
        "const porRiesgo = [...partidos].sort((a, b) => prioridadCoberturaAnalisis(b) - prioridadCoberturaAnalisis(a));",
    )
    html = html.replace(
        "No es un fijo tranquilo: queda como signo base solo si faltan dobles/triples, porque la necesidad competitiva obliga a revisar cobertura.",
        "Fijo condicionado: el analisis lo marca como peligroso; si hay mas presupuesto debe subir a doble o triple antes que un partido sin necesidad viva.",
    )
    return html


def patch_motor(text):
    replacements = {
        'probs["1"] += 5 + tasa * 0.08': 'probs["1"] += 16 + tasa * 0.16',
        'probs["X"] += 5 + tasa * 0.06': 'probs["X"] += 11 + tasa * 0.09',
        'probs["2"] -= 4': 'probs["2"] -= 12',
        'probs["2"] += 5 + tasa * 0.08': 'probs["2"] += 16 + tasa * 0.16',
        'probs["1"] -= 4': 'probs["1"] -= 12',
        'riesgo_extra += 10 + tasa * 0.20': 'riesgo_extra += 24 + tasa * 0.38',
        'probs["X"] += 12 + tasa * 0.10\n        probs["2"] += 14 + tasa * 0.12\n        probs["1"] -= 10': 'probs["X"] += 16 + tasa * 0.12\n        probs["2"] += 18 + tasa * 0.16\n        probs["1"] -= 20',
        'probs["X"] += 12 + tasa * 0.10\n        probs["1"] += 14 + tasa * 0.12\n        probs["2"] -= 10': 'probs["X"] += 16 + tasa * 0.12\n        probs["1"] += 18 + tasa * 0.16\n        probs["2"] -= 20',
        'riesgo_extra += 8 + tasa * 0.15': 'riesgo_extra += 22 + tasa * 0.34',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    if "Choque de necesidades vivas" not in text:
        text = replace_one(
            text,
            '''    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        tasa = tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo")
        riesgo_extra += 22 + tasa * 0.34
        lecturas.append(f"Patron general aprendido: necesidad contra objetivo cerrado aumenta sorpresa y exige desconfiar del fijo limpio ({tasa:.1f}%).")

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas
''',
            '''    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        tasa = tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo")
        riesgo_extra += 22 + tasa * 0.34
        lecturas.append(f"Patron general aprendido: necesidad contra objetivo cerrado aumenta sorpresa y exige desconfiar del fijo limpio ({tasa:.1f}%).")

    if local_necesita and visitante_necesita:
        probs["X"] += 7
        riesgo_extra += 20
        lecturas.append("Choque de necesidades vivas: el empate y la cobertura amplia ganan valor frente al fijo limpio.")

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas
''',
            "choque de necesidades del motor",
        )

    if "def riesgo_necesidad_real" not in text:
        helpers = '''def riesgo_necesidad_real(local_comp, visitante_comp):
    return (
        necesidad_viva_motor(local_comp)
        or necesidad_viva_motor(visitante_comp)
        or descenso_vivo_motor(local_comp)
        or descenso_vivo_motor(visitante_comp)
    )


def prioridad_cobertura(partido):
    probs = partido.get("probabilidades", {})
    valores = sorted(probs.values(), reverse=True)
    margen = valores[0] - valores[1] if len(valores) > 1 else 0
    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)
    top = signo_top(probs)
    score = float(partido.get("incertidumbre", 0))

    if partido.get("riesgo_necesidad_real"):
        score += 25
    if local_descenso or visitante_descenso:
        score += 70
    if local_descenso and visitante_descenso:
        score += 40
    if (visitante_descenso and top == "1") or (local_descenso and top == "2"):
        score += 85
    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        score += 75
    if local_necesita and visitante_necesita:
        score += 45
    if margen < 8:
        score += 28
    elif margen < 16:
        score += 18
    return score


'''
        text = replace_one(text, "def coste(dobles, triples, elige8):\n", helpers + "def coste(dobles, triples, elige8):\n", "prioridad de cobertura motor")

    if '"riesgo_necesidad_real": riesgo_necesidad_real(local_comp, visitante_comp),' not in text:
        text = replace_one(
            text,
            '''            "probabilidad_sorpresa": sorpresa,
            "contexto_local": contexto_local,
''',
            '''            "probabilidad_sorpresa": sorpresa,
            "riesgo_necesidad_real": riesgo_necesidad_real(local_comp, visitante_comp),
            "contexto_local": contexto_local,
''',
            "campo riesgo real evaluado",
        )

    text = text.replace(
        'por_riesgo = sorted(evaluados, key=lambda p: p["incertidumbre"], reverse=True)',
        'por_riesgo = sorted(evaluados, key=prioridad_cobertura, reverse=True)',
    )
    return text


def main():
    html = INDEX.read_text(encoding="utf-8")
    patched_html = patch_index(html)
    if patched_html != html:
        INDEX.write_text(patched_html, encoding="utf-8")
        print("Web: pronostico y analisis alineados sin tocar layout.")
    else:
        print("Web: ya estaba alineada.")

    motor = MOTOR.read_text(encoding="utf-8")
    patched_motor = patch_motor(motor)
    if patched_motor != motor:
        MOTOR.write_text(patched_motor, encoding="utf-8")
        print("Motor: prioridad de cobertura alineada con necesidad competitiva.")
    else:
        print("Motor: ya estaba alineado.")


if __name__ == "__main__":
    main()
