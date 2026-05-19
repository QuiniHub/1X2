import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
PREDICCIONES = DATA / "predicciones"

ESTADOS_VIVOS = {
    "defiende_liderato",
    "defiende_plaza",
    "aspira_matematicamente",
    "aspira_por_desempate_o_fallo_ajeno",
    "en_descenso_con_opciones",
    "riesgo_descenso",
    "permanencia_por_cerrar",
}

ESTADOS_CERRADOS = {
    "campeon_matematico",
    "asegurado_matematicamente",
    "salvado_matematicamente",
    "descendido_matematicamente",
    "sin_opciones_matematicas",
    "no_se_juega_nada_clasificatorio",
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "�" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar_nombre(nombre):
    texto = unicodedata.normalize("NFKD", reparar_mojibake(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"\b(cf|fc|rcd|rc|cd|ud|sd|club|real|de|del|la|el|balompie|futbol)\b", "", texto)
    return re.sub(r"[^a-z0-9]", "", texto)


def crear_indice_competitivo(contexto):
    indice = {}
    for liga in ("primera", "segunda"):
        for equipo in ((contexto.get(liga) or {}).get("equipos") or []):
            registro = {**equipo, "liga": liga}
            claves = {equipo.get("clave"), normalizar_nombre(equipo.get("equipo"))}
            for clave in claves:
                if clave:
                    indice[clave] = registro
    return indice


def buscar_contexto_equipo(nombre, indice):
    clave = normalizar_nombre(nombre)
    if not clave:
        return None
    if clave in indice:
        return indice[clave]
    for clave_indice, equipo in indice.items():
        if len(clave) >= 4 and (clave in clave_indice or clave_indice in clave):
            return equipo
    return None


def valor_motivacion(equipo):
    orden = {"baja": 0, "media": 1, "alta": 2, "maxima": 3}
    if not equipo:
        return 0
    return orden.get(str(equipo.get("motivacion_competitiva", equipo.get("motivacion", "baja"))).lower(), 0)


def objetivos_vivos(equipo):
    if not equipo:
        return []
    vivos = [obj for obj in equipo.get("objetivos_vivos", []) if obj]
    if vivos:
        return vivos
    return [obj for obj in equipo.get("objetivos", []) if obj.get("estado") in ESTADOS_VIVOS or obj.get("vivo") is True]


def objetivo_principal(equipo):
    if not equipo:
        return {}
    return equipo.get("objetivo_principal") or (equipo.get("objetivos") or [{}])[0] or {}


def estado_principal(equipo):
    return str(objetivo_principal(equipo).get("estado", ""))


def equipo_cerrado(equipo):
    if not equipo:
        return False
    if objetivos_vivos(equipo):
        return False
    estado = estado_principal(equipo)
    return estado in ESTADOS_CERRADOS or objetivo_principal(equipo).get("terminal") is True


def equipo_con_necesidad(equipo):
    if not equipo or equipo_cerrado(equipo):
        return False
    if objetivos_vivos(equipo):
        return True
    texto = f"{estado_principal(equipo)} {objetivo_principal(equipo).get('objetivo', '')}".lower()
    return any(p in texto for p in ("riesgo", "descenso", "permanencia", "defiende", "aspira", "playoff", "ascenso"))


def objetivo_texto(equipo):
    if not equipo:
        return "sin contexto competitivo claro"
    obj = objetivo_principal(equipo)
    nombre = str(obj.get("objetivo", "situacion")).replace("_", " ")
    estado = str(obj.get("estado", "sin estado")).replace("_", " ")
    lectura = reparar_mojibake(obj.get("lectura", ""))
    return f"{nombre} ({estado}). {lectura}".strip()


def top_probabilidad(partido):
    probs = partido.get("probabilidades") or {}
    orden = sorted(((signo, float(valor)) for signo, valor in probs.items()), key=lambda x: x[1], reverse=True)
    return orden[0] if orden else ("", 0.0)


def margen_probabilidad(partido):
    probs = sorted([float(v) for v in (partido.get("probabilidades") or {}).values()], reverse=True)
    if len(probs) < 2:
        return 0.0
    return round(probs[0] - probs[1], 2)


def contexto_partido(partido, indice):
    return (
        buscar_contexto_equipo(partido.get("local"), indice),
        buscar_contexto_equipo(partido.get("visitante"), indice),
    )


def lado_signo(signo):
    if signo == "1":
        return "local"
    if signo == "2":
        return "visitante"
    return "empate"


def penalizaciones_competitivas(partido, local_ctx, visitante_ctx):
    signo, prob = top_probabilidad(partido)
    probs = partido.get("probabilidades") or {}
    x_prob = float(probs.get("X", 0) or 0)
    margen = margen_probabilidad(partido)
    lado = lado_signo(signo)
    local_need = equipo_con_necesidad(local_ctx)
    visitor_need = equipo_con_necesidad(visitante_ctx)
    local_closed = equipo_cerrado(local_ctx)
    visitor_closed = equipo_cerrado(visitante_ctx)
    penalty = 0.0
    motivos = []

    if local_need and visitor_need:
        penalty += 38
        motivos.append("los dos equipos tienen objetivo vivo; no es fijo limpio")
    elif local_need or visitor_need:
        penalty += 8

    if lado == "1" and visitor_need:
        penalty += 22
        motivos.append(f"{partido.get('visitante')} necesita puntuar: {objetivo_texto(visitante_ctx)}")
    if lado == "2" and local_need:
        penalty += 22
        motivos.append(f"{partido.get('local')} necesita puntuar: {objetivo_texto(local_ctx)}")

    if lado == "1" and local_need and visitor_closed:
        penalty -= 16
        motivos.append("la necesidad del local apoya el 1 y el visitante tiene objetivo cerrado")
    if lado == "2" and visitor_need and local_closed:
        penalty -= 16
        motivos.append("la necesidad del visitante apoya el 2 y el local tiene objetivo cerrado")

    if lado == "1" and local_closed and visitor_need:
        penalty += 24
        motivos.append("el favorito local tiene objetivo cerrado y el visitante se juega puntos")
    if lado == "2" and visitor_closed and local_need:
        penalty += 24
        motivos.append("el favorito visitante tiene objetivo cerrado y el local se juega puntos")

    if prob < 55:
        penalty += 7
        motivos.append("probabilidad principal por debajo del 55%")
    if x_prob >= 32:
        penalty += 8
        motivos.append("empate con peso alto")
    if margen < 10:
        penalty += 8
        motivos.append("margen corto entre signos")

    return penalty, motivos


def seguridad_ajustada(partido, indice):
    local_ctx, visitante_ctx = contexto_partido(partido, indice)
    signo, prob = top_probabilidad(partido)
    inc = float(partido.get("incertidumbre") or 999)
    margen = margen_probabilidad(partido)
    penalty, motivos = penalizaciones_competitivas(partido, local_ctx, visitante_ctx)
    score = inc - margen * 0.35 - prob * 0.08 + penalty
    return round(score, 2), motivos, local_ctx, visitante_ctx


def es_seguro_aceptable(item):
    texto = " ".join(item.get("motivos", [])).lower()
    if "no es fijo limpio" in texto:
        return False
    if "necesita puntuar" in texto:
        return False
    if "objetivo cerrado" in texto and "se juega puntos" in texto:
        return False
    if item.get("prob", 0) < 50 and "apoya" not in texto:
        return False
    return True


def motivo_seguro(partido, motivos):
    if motivos:
        return "Seguro relativo, pero revisado por motivacion: " + "; ".join(motivos[:2]) + "."
    return "Baja incertidumbre ajustada y sin necesidad competitiva fuerte en contra del signo base."


def motivo_trampa_ajustado(partido, motivos):
    if motivos:
        return "; ".join(motivos[:3]) + "."
    probs = partido.get("probabilidades") or {}
    if float(probs.get("X", 0) or 0) >= 32:
        return "Empate con mucho peso; no debe tratarse como fijo tranquilo."
    if margen_probabilidad(partido) < 10:
        return "Probabilidades muy juntas; cualquier signo alternativo puede tener valor."
    return "Incertidumbre competitiva alta por mezcla de probabilidad, contexto y objetivos vivos."


def construir_listas(prediccion, contexto):
    indice = crear_indice_competitivo(contexto)
    evaluados = []
    for partido in prediccion.get("partidos", []):
        if int(partido.get("num", 0) or 0) > 14:
            continue
        score, motivos, local_ctx, visitante_ctx = seguridad_ajustada(partido, indice)
        signo, prob = top_probabilidad(partido)
        riesgo_extra = 0
        texto_motivos = " ".join(motivos).lower()
        if "no es fijo limpio" in texto_motivos:
            riesgo_extra += 45
        if "necesita puntuar" in texto_motivos:
            riesgo_extra += 12
        evaluados.append({
            "partido": partido,
            "score_seguridad": score,
            "score_riesgo": round(score + float(partido.get("probabilidad_sorpresa") or 0) * 0.25 + riesgo_extra, 2),
            "motivos": motivos,
            "local_ctx": local_ctx,
            "visitante_ctx": visitante_ctx,
            "signo": partido.get("signo_final") or partido.get("signo_base") or signo,
            "prob": prob,
        })

    candidatos_seguros = [item for item in evaluados if es_seguro_aceptable(item)]
    seguros = []
    for item in sorted(candidatos_seguros, key=lambda x: (x["score_seguridad"], -margen_probabilidad(x["partido"])))[:5]:
        p = item["partido"]
        seguros.append({
            "num": p.get("num"),
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "signo": item["signo"],
            "probabilidad_top": item["prob"],
            "incertidumbre": p.get("incertidumbre"),
            "seguridad_ajustada": item["score_seguridad"],
            "motivo": motivo_seguro(p, item["motivos"]),
        })

    trampas = []
    for item in sorted(evaluados, key=lambda x: x["score_riesgo"], reverse=True)[:8]:
        p = item["partido"]
        trampas.append({
            "num": p.get("num"),
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "signo_base": item["signo"],
            "probabilidad_top": item["prob"],
            "incertidumbre": p.get("incertidumbre"),
            "probabilidad_sorpresa": p.get("probabilidad_sorpresa"),
            "riesgo_ajustado": item["score_riesgo"],
            "motivo": motivo_trampa_ajustado(p, item["motivos"]),
        })

    dudas = []
    for item in sorted(evaluados, key=lambda x: x["score_riesgo"], reverse=True)[:7]:
        p = item["partido"]
        pregunta = motivo_trampa_ajustado(p, item["motivos"])
        dudas.append({
            "num": p.get("num"),
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "pregunta": pregunta,
        })

    return seguros, trampas, dudas


def main():
    estado = cargar_json(MEMORIA / "estado_vivo.json", {})
    prediccion = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    contexto = cargar_json(MEMORIA / "contexto_competitivo.json", {})
    if not estado or not prediccion or not contexto:
        raise SystemExit("Faltan estado vivo, prediccion o contexto competitivo para ajustar seguridad.")

    seguros, trampas, dudas = construir_listas(prediccion, contexto)
    estado["partidos_mas_seguros"] = seguros
    estado["partidos_trampa_o_sorpresa"] = trampas
    estado["dudas_abiertas"] = dudas
    if isinstance(estado.get("prediccion_objetivo"), dict):
        estado["prediccion_objetivo"]["partidos_mas_seguros"] = seguros
        estado["prediccion_objetivo"]["partidos_trampa_o_sorpresa"] = trampas
        estado["prediccion_objetivo"]["dudas_abiertas"] = dudas
    estado.setdefault("que_modifica_para_jornada_objetivo", []).append(
        "La lista de partidos mas seguros se recalcula con motivacion competitiva: un rival que necesita puntuar deja de ser tratado como fijo tranquilo."
    )
    guardar_json(MEMORIA / "estado_vivo.json", estado)
    print("Estado vivo ajustado por motivacion competitiva: partidos seguros/trampa recalculados.")


if __name__ == "__main__":
    main()
