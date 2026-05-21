import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
MOTOR = ROOT / "motor_prediccion_quiniela.py"
ESTADO_VIVO = ROOT / "data" / "memoria_ia" / "estado_vivo.json"
ULTIMA_PREDICCION = ROOT / "data" / "predicciones" / "ultima_prediccion.json"


WEB_PRIORITY_HELPERS = r'''
    function valoresProbabilidadOrdenados(partido) {
      return Object.values(partido.probabilidades || {}).sort((a, b) => b - a);
    }

    function margenProbabilidadBoleto(partido) {
      const valores = valoresProbabilidadOrdenados(partido);
      return valores.length > 1 ? valores[0] - valores[1] : 0;
    }

    function terceraProbabilidadBoleto(partido) {
      const valores = valoresProbabilidadOrdenados(partido);
      return valores.length > 2 ? valores[2] : 0;
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
      const margen = margenProbabilidadBoleto(partido);
      let score = Number(partido.incertidumbre || 0) + Number(partido.bonus_competitivo || 0);

      if (partido.riesgo_necesidad) score += 25;
      if (localDescenso || visitanteDescenso) score += 70;
      if (localDescenso && visitanteDescenso) score += 40;
      if ((visitanteDescenso && top === "1") || (localDescenso && top === "2")) score += 85;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) score += 75;
      if (localNecesita && visitanteNecesita) score += 65;
      if ((localDescenso || visitanteDescenso) && localNecesita && visitanteNecesita) score += 55;
      if (top === "X" && localNecesita && visitanteNecesita) score += 35;
      if (partido.riesgo === "Alto") score += 10;
      if (margen < 8) score += 28;
      else if (margen < 16) score += 18;
      return score;
    }

    function prioridadTripleAnalisis(partido) {
      const localComp = partido.contexto_competitivo_local;
      const visitanteComp = partido.contexto_competitivo_visitante;
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const localDescenso = contieneDescensoVivoBoleto(localComp);
      const visitanteDescenso = contieneDescensoVivoBoleto(visitanteComp);
      const top = signoTopProbabilidad(partido.probabilidades || {});
      const tercera = terceraProbabilidadBoleto(partido);
      let score = prioridadCoberturaAnalisis(partido);

      if (tercera >= 18) score += 85;
      else if (tercera >= 14) score += 40;
      else if (tercera < 8) score -= 70;
      else score -= 35;

      if (top === "X" && tercera >= 18) score += 25;
      if (localNecesita && visitanteNecesita) score += 70;
      if ((localDescenso || visitanteDescenso) && localNecesita && visitanteNecesita) score += 45;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) score += 35;
      return score;
    }

    function prioridadDobleAnalisis(partido) {
      const tercera = terceraProbabilidadBoleto(partido);
      const margen = margenProbabilidadBoleto(partido);
      const top = signoTopProbabilidad(partido.probabilidades || {});
      let score = prioridadCoberturaAnalisis(partido);

      if (tercera < 10) score += 45;
      else if (tercera >= 22) score -= 50;
      if (margen < 12) score += 30;
      if (top === "X") score += 8;
      return score;
    }

    function riesgoFijoLegible(valor) {
      const n = Number(valor);
      if (!Number.isFinite(n)) return "sin dato";
      const numero = n.toFixed(0);
      if (n < 85) return `bajo (${numero})`;
      if (n < 130) return `medio (${numero})`;
      if (n < 180) return `alto (${numero})`;
      return `muy alto (${numero})`;
    }
'''


MOTOR_PRIORITY_HELPERS = r'''def tercera_probabilidad(partido):
    valores = sorted((partido.get("probabilidades") or {}).values(), reverse=True)
    return valores[2] if len(valores) > 2 else 0


def prioridad_triple(partido):
    probs = partido.get("probabilidades", {})
    valores = sorted(probs.values(), reverse=True)
    tercera = valores[2] if len(valores) > 2 else 0
    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)
    top = signo_top(probs)
    score = prioridad_cobertura(partido)

    if tercera >= 18:
        score += 85
    elif tercera >= 14:
        score += 40
    elif tercera < 8:
        score -= 70
    else:
        score -= 35

    if top == "X" and tercera >= 18:
        score += 25
    if local_necesita and visitante_necesita:
        score += 70
    if (local_descenso or visitante_descenso) and local_necesita and visitante_necesita:
        score += 45
    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        score += 35
    return score


def prioridad_doble(partido):
    probs = partido.get("probabilidades", {})
    valores = sorted(probs.values(), reverse=True)
    margen = valores[0] - valores[1] if len(valores) > 1 else 0
    tercera = valores[2] if len(valores) > 2 else 0
    top = signo_top(probs)
    score = prioridad_cobertura(partido)

    if tercera < 10:
        score += 45
    elif tercera >= 22:
        score -= 50
    if margen < 12:
        score += 30
    if top == "X":
        score += 8
    return score


'''


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def replace_regex(text, pattern, replacement, desc):
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"No encuentro bloque para {desc}.")
    return updated


def patch_index(html):
    html = replace_regex(
        html,
        r"\n    function prioridadCoberturaAnalisis\(partido\) \{.*?\n    \}\n\n\n    function puntosCasaFueraTexto",
        "\n" + WEB_PRIORITY_HELPERS + "\n\n    function puntosCasaFueraTexto",
        "prioridad de coberturas web",
    )

    html = replace_regex(
        html,
        r"""      const porRiesgo = \[\.\.\.partidos\]\.sort\(\(a, b\) => prioridadCoberturaAnalisis\(b\) - prioridadCoberturaAnalisis\(a\)\);
      const triplesSet = new Set\(porRiesgo\.slice\(0, triples\)\.map\(p => p\.num\)\);
      const doblesSet = new Set\(
        porRiesgo\.filter\(p => !triplesSet\.has\(p\.num\)\)\.slice\(0, dobles\)\.map\(p => p\.num\)
      \);""",
        """      const porTriple = [...partidos].sort((a, b) => prioridadTripleAnalisis(b) - prioridadTripleAnalisis(a));
      const triplesSet = new Set(porTriple.slice(0, triples).map(p => p.num));
      const porDoble = [...partidos]
        .filter(p => !triplesSet.has(p.num))
        .sort((a, b) => prioridadDobleAnalisis(b) - prioridadDobleAnalisis(a));
      const doblesSet = new Set(porDoble.slice(0, dobles).map(p => p.num));""",
        "reparto de triples y dobles web",
    )

    html = re.sub(
        r'<strong>Predicci.n que est. recalibrando:</strong>',
        '<strong>Prediccion base automatica:</strong>',
        html,
        count=1,
    )
    html = replace_regex(
        html,
        r'\$\{pintarListaEstado\("Partidos m.s seguros", estado\.partidos_mas_seguros, x => `<li>\$\{x\.num\}\. \$\{x\.partido\}: \$\{x\.signo\} .*? incertidumbre \$\{x\.incertidumbre\}</li>`\)\}',
        '${pintarListaEstado("Fijos mas defendibles", estado.partidos_mas_seguros, x => `<li>${x.num}. ${x.partido}: ${x.signo} - riesgo de dejarlo fijo ${riesgoFijoLegible(x.riesgo_dejar_fijo ?? x.seguridad_ajustada ?? x.incertidumbre)}</li>`)}',
        "etiqueta de fijos defendibles",
    )
    html = replace_regex(
        html,
        r'\$\{pintarListaEstado\("Partidos trampa o sorpresa", estado\.partidos_trampa_o_sorpresa, x => `<li>\$\{x\.num\}\. \$\{x\.partido\}: base \$\{x\.signo_base\}, incertidumbre \$\{x\.incertidumbre\}, sorpresa \$\{x\.probabilidad_sorpresa \?\? "-"\}%\. \$\{x\.motivo\}</li>`\)\}',
        '${pintarListaEstado("Partidos trampa o sorpresa", estado.partidos_trampa_o_sorpresa, x => `<li>${x.num}. ${x.partido}: base ${x.signo_base}, riesgo de dejarlo fijo ${riesgoFijoLegible(x.riesgo_dejar_fijo ?? x.riesgo_ajustado ?? x.incertidumbre)}, sorpresa ${x.probabilidad_sorpresa ?? "-"}%. ${x.motivo}</li>`)}',
        "etiqueta de trampas",
    )
    html = html.replace(
        'incertidumbre ${x.incertidumbre}.',
        'riesgo de dejarlo fijo ${riesgoFijoLegible(x.riesgo_dejar_fijo ?? x.riesgo_ajustado ?? x.incertidumbre)}.',
    )
    html = html.replace(
        'incertidumbre ${p.incertidumbre || "-"}',
        'riesgo de dejarlo fijo ${riesgoFijoLegible(p.riesgo_dejar_fijo ?? p.riesgo_ajustado ?? p.incertidumbre)}',
    )
    return html


def patch_motor(text):
    if "def prioridad_triple(partido):" not in text:
        text = text.replace(
            "\n\ndef coste(dobles, triples, elige8):\n",
            "\n\n" + MOTOR_PRIORITY_HELPERS + "def coste(dobles, triples, elige8):\n",
            1,
        )

    text = replace_regex(
        text,
        r"""    por_riesgo = sorted\(evaluados, key=prioridad_cobertura, reverse=True\)
    triples_set = \{p\["num"\] for p in por_riesgo\[:triples\]\}
    dobles_set = \{p\["num"\] for p in por_riesgo if p\["num"\] not in triples_set\}
    dobles_set = set\(list\(dobles_set\)\[:dobles\]\)""",
        """    por_triple = sorted(evaluados, key=prioridad_triple, reverse=True)
    triples_set = {p["num"] for p in por_triple[:triples]}
    por_doble = sorted(
        [p for p in evaluados if p["num"] not in triples_set],
        key=prioridad_doble,
        reverse=True,
    )
    dobles_set = {p["num"] for p in por_doble[:dobles]}""",
        "reparto de triples y dobles motor",
    )
    return text


def categoria_riesgo(valor):
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return "sin dato"
    if n < 85:
        return "bajo"
    if n < 130:
        return "medio"
    if n < 180:
        return "alto"
    return "muy alto"


def top_desde_probs(partido):
    probs = partido.get("probabilidades") or {}
    if not probs:
        return None
    return max(probs.items(), key=lambda kv: float(kv[1]))[0]


def postprocesar_estado_vivo():
    estado = cargar_json(ESTADO_VIVO, {})
    prediccion = cargar_json(ULTIMA_PREDICCION, {})
    if not estado:
        return False

    pred_por_num = {
        int(p.get("num")): p
        for p in prediccion.get("partidos", [])
        if str(p.get("num", "")).isdigit()
    }

    def enriquecer(item):
        num = int(item.get("num") or 0)
        pred = pred_por_num.get(num, {})
        riesgo = item.get("riesgo_ajustado", item.get("seguridad_ajustada", item.get("incertidumbre", 0)))
        item["riesgo_dejar_fijo"] = round(float(riesgo or 0), 2)
        item["lectura_riesgo_fijo"] = categoria_riesgo(riesgo)
        signo = pred.get("signo_final") or pred.get("signo_base") or top_desde_probs(pred)
        if signo:
            item["signo_base"] = signo
            item["signo"] = signo
        return item

    seguros = [enriquecer(x) for x in estado.get("partidos_mas_seguros", [])]
    seguros_filtrados = [x for x in seguros if x.get("riesgo_dejar_fijo", 999) < 130]
    if not seguros_filtrados and seguros:
        seguros_filtrados = sorted(seguros, key=lambda x: x.get("riesgo_dejar_fijo", 999))[:1]

    trampas = [enriquecer(x) for x in estado.get("partidos_trampa_o_sorpresa", [])]
    dudas = [enriquecer(x) for x in estado.get("dudas_abiertas", [])]

    estado["partidos_mas_seguros"] = seguros_filtrados[:5]
    estado["partidos_trampa_o_sorpresa"] = sorted(
        trampas, key=lambda x: x.get("riesgo_dejar_fijo", 0), reverse=True
    )[:8]
    estado["dudas_abiertas"] = dudas[:7]
    if isinstance(estado.get("prediccion_objetivo"), dict):
        estado["prediccion_objetivo"]["partidos_mas_seguros"] = estado["partidos_mas_seguros"]
        estado["prediccion_objetivo"]["partidos_trampa_o_sorpresa"] = estado["partidos_trampa_o_sorpresa"]
        estado["prediccion_objetivo"]["dudas_abiertas"] = estado["dudas_abiertas"]

    guardar_json(ESTADO_VIVO, estado)
    return True


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo_html = patch_index(html)
    if nuevo_html != html:
        INDEX.write_text(nuevo_html, encoding="utf-8")
        print("Web: triples/dobles priorizados y etiqueta de riesgo aclarada.")
    else:
        print("Web: prioridad y etiquetas ya estaban aplicadas.")

    motor = MOTOR.read_text(encoding="utf-8")
    nuevo_motor = patch_motor(motor)
    if nuevo_motor != motor:
        MOTOR.write_text(nuevo_motor, encoding="utf-8")
        print("Motor: triples y dobles separados por prioridad real.")
    else:
        print("Motor: prioridad de triples/dobles ya estaba aplicada.")

    if postprocesar_estado_vivo():
        print("Estado vivo: riesgo de fijo normalizado para la pestana Analisis.")


if __name__ == "__main__":
    main()
