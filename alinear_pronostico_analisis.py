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
        p["1"] += 12 + tasa * 0.14;
        p["X"] += 8 + tasa * 0.08;
        p["2"] -= 8;
      }
      if (localCerrado && visitanteNecesita) {
        const tasa = tasaPatronCompetitivo(patrones, "visitante_necesitado_vs_local_objetivo_cerrado");
        p["2"] += 12 + tasa * 0.14;
        p["X"] += 8 + tasa * 0.08;
        p["1"] -= 8;
      }
      if (visitanteDescenso && top === "1") {
        const tasa = tasaPatronCompetitivo(patrones, "visitante_descenso_vs_local_favorito");
        p["X"] += 12 + tasa * 0.10;
        p["2"] += 14 + tasa * 0.14;
        p["1"] -= 14;
      }
      if (localDescenso && top === "2") {
        const tasa = tasaPatronCompetitivo(patrones, "local_descenso_vs_visitante_favorito");
        p["X"] += 12 + tasa * 0.10;
        p["1"] += 14 + tasa * 0.14;
        p["2"] -= 14;
      }
      if (localNecesita && visitanteNecesita) {
        p["X"] += 6;
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

      if (visitanteCerrado && localNecesita) bonus += 18 + tasaPatronCompetitivo(patrones, "necesitado_local_vs_visitante_objetivo_cerrado") * 0.35;
      if (localCerrado && visitanteNecesita) bonus += 18 + tasaPatronCompetitivo(patrones, "visitante_necesitado_vs_local_objetivo_cerrado") * 0.35;
      if (visitanteDescenso && top === "1") bonus += 55 + tasaPatronCompetitivo(patrones, "visitante_descenso_vs_local_favorito") * 0.50;
      if (localDescenso && top === "2") bonus += 55 + tasaPatronCompetitivo(patrones, "local_descenso_vs_visitante_favorito") * 0.50;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) {
        bonus += 16 + tasaPatronCompetitivo(patrones, "equipo_necesitado_vs_equipo_sin_objetivo") * 0.30;
      }
      if (localNecesita && visitanteNecesita) bonus += 14;
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
      let score = Number(partido.incertidumbre || 0);

      if (localDescenso || visitanteDescenso) score += 50;
      if (localDescenso && visitanteDescenso) score += 35;
      if ((visitanteDescenso && top === "1") || (localDescenso && top === "2")) score += 55;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) score += 45;
      if (localNecesita && visitanteNecesita) score += 25;
      if (partido.riesgo === "Alto") score += 8;
      if (margen < 10) score += 22;
      else if (margen < 18) score += 12;
      return score;
    }
'''


def reemplazar_regex(html, patron, nuevo, descripcion):
    actualizado, n = re.subn(patron, nuevo, html, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"No encuentro bloque para {descripcion}.")
    return actualizado


def parchear_index(html):
    core_patron = r"\n    function textoCompetitivoBoleto\(equipo\) \{.*?\n\n    function bonusRiesgoCompetitivo\(localComp, visitanteComp, probs\) \{"
    html = reemplazar_regex(
        html,
        core_patron,
        "\n" + CORE_HELPERS + "\n\n    function bonusRiesgoCompetitivo(localComp, visitanteComp, probs) {",
        "lectura competitiva base",
    )

    patrones_patron = r"\n    function tasaPatronCompetitivo\(patrones, clave\) \{.*?\n\n    function puntosCasaFueraTexto\(equipo, condicion\) \{"
    html = reemplazar_regex(
        html,
        patrones_patron,
        "\n" + PATTERN_HELPERS + "\n\n    function puntosCasaFueraTexto(equipo, condicion) {",
        "patrones aprendidos web",
    )

    llamada = "probs = ajustarPorPatronesAprendidosWeb(probs, contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos);"
    if llamada not in html:
        viejo = '''          let probs = analisis?.probabilidades || { "1": 37, "X": 31, "2": 32 };
          probs = ajustarProbabilidades(probs, p.local, p.visitante, clasif, contextoCompetitivo);

          const riesgo = analisis?.riesgo_sorpresa || "Alto";
'''
        nuevo = '''          let probs = analisis?.probabilidades || { "1": 37, "X": 31, "2": 32 };
          probs = ajustarProbabilidades(probs, p.local, p.visitante, clasif, contextoCompetitivo);
          probs = ajustarPorPatronesAprendidosWeb(probs, contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos);

          const riesgo = analisis?.riesgo_sorpresa || "Alto";
'''
        if viejo not in html:
            raise SystemExit("No encuentro bloque de probabilidades del boleto IA.")
        html = html.replace(viejo, nuevo, 1)

    if "const riesgoNecesidad = riesgoNecesidadRealBoleto" not in html:
        viejo = '''          const bonusCompetitivo = bonusRiesgoCompetitivo(contextoCompetitivoLocal, contextoCompetitivoVisitante, probs)
            + bonusPatronesAprendidosWeb(contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos, probs);

          return {
'''
        nuevo = '''          const bonusCompetitivo = bonusRiesgoCompetitivo(contextoCompetitivoLocal, contextoCompetitivoVisitante, probs)
            + bonusPatronesAprendidosWeb(contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos, probs);
          const riesgoNecesidad = riesgoNecesidadRealBoleto(contextoCompetitivoLocal, contextoCompetitivoVisitante);

          return {
'''
        if viejo not in html:
            raise SystemExit("No encuentro bloque de bonus competitivo del boleto IA.")
        html = html.replace(viejo, nuevo, 1)

    html = html.replace("riesgo_necesidad: bonusCompetitivo >= 18", "riesgo_necesidad: riesgoNecesidad")
    html = html.replace(
        "const porRiesgo = [...partidos].sort((a, b) => b.incertidumbre - a.incertidumbre);",
        "const porRiesgo = [...partidos].sort((a, b) => prioridadCoberturaAnalisis(b) - prioridadCoberturaAnalisis(a));",
    )
    return html


def parchear_motor(texto):
    cambios = {
        'probs["1"] += 5 + tasa * 0.08': 'probs["1"] += 12 + tasa * 0.14',
        'probs["X"] += 5 + tasa * 0.06': 'probs["X"] += 8 + tasa * 0.08',
        'probs["2"] -= 4': 'probs["2"] -= 8',
        'probs["2"] += 5 + tasa * 0.08': 'probs["2"] += 12 + tasa * 0.14',
        'probs["1"] -= 4': 'probs["1"] -= 8',
        'riesgo_extra += 10 + tasa * 0.20': 'riesgo_extra += 18 + tasa * 0.35',
        'probs["X"] += 12 + tasa * 0.10\n        probs["2"] += 14 + tasa * 0.12\n        probs["1"] -= 10': 'probs["X"] += 12 + tasa * 0.10\n        probs["2"] += 14 + tasa * 0.14\n        probs["1"] -= 14',
        'probs["X"] += 12 + tasa * 0.10\n        probs["1"] += 14 + tasa * 0.12\n        probs["2"] -= 10': 'probs["X"] += 12 + tasa * 0.10\n        probs["1"] += 14 + tasa * 0.14\n        probs["2"] -= 14',
    }
    for viejo, nuevo in cambios.items():
        texto = texto.replace(viejo, nuevo)

    if "Choque de necesidades vivas" not in texto:
        viejo = '''    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        tasa = tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo")
        riesgo_extra += 8 + tasa * 0.15
        lecturas.append(f"Patron general aprendido: necesidad contra objetivo cerrado aumenta sorpresa y exige desconfiar del fijo limpio ({tasa:.1f}%).")

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas
'''
        nuevo = '''    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        tasa = tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo")
        riesgo_extra += 12 + tasa * 0.25
        lecturas.append(f"Patron general aprendido: necesidad contra objetivo cerrado aumenta sorpresa y exige desconfiar del fijo limpio ({tasa:.1f}%).")

    if local_necesita and visitante_necesita:
        probs["X"] += 6
        riesgo_extra += 14
        lecturas.append("Choque de necesidades vivas: el empate y la cobertura amplia ganan valor frente al fijo limpio.")

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas
'''
        if viejo not in texto:
            raise SystemExit("No encuentro bloque final de patrones aprendidos del motor.")
        texto = texto.replace(viejo, nuevo, 1)

    if "def riesgo_necesidad_real" not in texto:
        marcador = '''def coste(dobles, triples, elige8):
'''
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

    if local_descenso or visitante_descenso:
        score += 50
    if local_descenso and visitante_descenso:
        score += 35
    if (visitante_descenso and top == "1") or (local_descenso and top == "2"):
        score += 55
    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        score += 45
    if local_necesita and visitante_necesita:
        score += 25
    if margen < 10:
        score += 22
    elif margen < 18:
        score += 12
    return score


'''
        if marcador not in texto:
            raise SystemExit("No encuentro marcador para insertar prioridad de cobertura.")
        texto = texto.replace(marcador, helpers + marcador, 1)

    if '"riesgo_necesidad_real": riesgo_necesidad_real(local_comp, visitante_comp),' not in texto:
        viejo = '''            "probabilidad_sorpresa": sorpresa,
            "contexto_local": contexto_local,
'''
        nuevo = '''            "probabilidad_sorpresa": sorpresa,
            "riesgo_necesidad_real": riesgo_necesidad_real(local_comp, visitante_comp),
            "contexto_local": contexto_local,
'''
        if viejo not in texto:
            raise SystemExit("No encuentro bloque de evaluados para riesgo real.")
        texto = texto.replace(viejo, nuevo, 1)

    texto = texto.replace(
        'por_riesgo = sorted(evaluados, key=lambda p: p["incertidumbre"], reverse=True)',
        'por_riesgo = sorted(evaluados, key=prioridad_cobertura, reverse=True)',
    )
    return texto


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo_html = parchear_index(html)
    if nuevo_html != html:
        INDEX.write_text(nuevo_html, encoding="utf-8")
        print("Web: pronostico alineado con analisis competitivo.")
    else:
        print("Web: pronostico ya alineado con analisis competitivo.")

    motor = MOTOR.read_text(encoding="utf-8")
    nuevo_motor = parchear_motor(motor)
    if nuevo_motor != motor:
        MOTOR.write_text(nuevo_motor, encoding="utf-8")
        print("Motor: coberturas alineadas con aprendizaje competitivo.")
    else:
        print("Motor: coberturas ya alineadas con aprendizaje competitivo.")


if __name__ == "__main__":
    main()
