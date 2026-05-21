import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia" / "aprendizaje_global.json"
CONTEXTO_EQUIPOS = DATA / "contexto_equipos.json"
CONTEXTO_COMPETITIVO = DATA / "memoria_ia" / "contexto_competitivo.json"
PATRONES_COMPETITIVOS = DATA / "memoria_ia" / "patrones_competitivos.json"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
JUGADAS = DATA / "quinielas_jugadas"

PRECIO_APUESTA = 0.75
IMPORTE_MINIMO = 1.50
PRECIO_ELIGE8 = 0.50


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


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def detectar_jornada_activa():
    candidatas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        numero = data.get("jornada")
        if not isinstance(numero, int):
            m = re.search(r"(\d+)", path.stem)
            numero = int(m.group(1)) if m else 0
        pendientes = sum(1 for p in data.get("partidos", []) if str(p.get("signo_oficial", "")).lower() == "pendiente")
        if pendientes:
            candidatas.append(numero)
    if candidatas:
        return max(candidatas)
    jornadas = [int(re.search(r"(\d+)", p.stem).group(1)) for p in JORNADAS.glob("jornada_*.json")]
    return max(jornadas) if jornadas else 61


def equipos_memoria(memoria):
    equipos = []
    for liga in ("primera", "segunda"):
        equipos.extend(memoria.get("ligas", {}).get(liga, {}).get("equipos", []))
    return equipos


def puntuacion_nombre_equipo(candidato, objetivo):
    base = normalizar(candidato)
    buscado = normalizar(objetivo)
    if not base or not buscado:
        return 0
    if base == buscado:
        return 1000

    base_tokens = base.split()
    buscado_tokens = buscado.split()
    comunes = [token for token in base_tokens if token in buscado_tokens]
    if not comunes:
        return 0

    ambiguos = {"madrid", "barcelona"}
    if len(comunes) == 1 and comunes[0] in ambiguos and max(len(base_tokens), len(buscado_tokens)) > 1:
        return 0

    cobertura_buscado = len(comunes) / max(len(buscado_tokens), 1)
    cobertura_base = len(comunes) / max(len(base_tokens), 1)
    score = len(comunes) * 30 + cobertura_buscado * 45 + cobertura_base * 35
    if base in buscado or buscado in base:
        score += 20
    score -= abs(len(base_tokens) - len(buscado_tokens)) * 8
    return score


def mejor_coincidencia_equipo(items, nombre, getter):
    mejor = None
    mejor_score = 0
    for item in items or []:
        score = puntuacion_nombre_equipo(getter(item), nombre)
        if score > mejor_score:
            mejor = item
            mejor_score = score
    return mejor if mejor_score >= 55 else None


def buscar_equipo(memoria, nombre):
    return mejor_coincidencia_equipo(
        equipos_memoria(memoria),
        nombre,
        lambda equipo: equipo.get("equipo", ""),
    )


def equipos_contexto(contexto):
    return contexto.get("equipos", {})


def buscar_contexto_equipo(contexto, nombre):
    entradas = [
        {"equipo": equipo, "datos": datos}
        for equipo, datos in equipos_contexto(contexto).items()
    ]
    mejor = mejor_coincidencia_equipo(entradas, nombre, lambda item: item.get("equipo", ""))
    return mejor.get("datos") if mejor else None


def equipos_contexto_competitivo(contexto):
    equipos = []
    for liga in ("primera", "segunda"):
        for equipo in (contexto.get(liga) or {}).get("equipos", []):
            equipos.append({**equipo, "liga": liga})
    return equipos


def buscar_contexto_competitivo(contexto, nombre):
    return mejor_coincidencia_equipo(
        equipos_contexto_competitivo(contexto),
        nombre,
        lambda equipo: equipo.get("equipo", ""),
    )


def valor_motivacion(equipo):
    orden = {"baja": 0, "media": 1, "alta": 2, "maxima": 3}
    if not equipo:
        return 0
    return orden.get(str(equipo.get("motivacion_competitiva", "baja")).lower(), 0)


def objetivo_descenso(equipo):
    if not equipo:
        return False
    for objetivo in equipo.get("objetivos", []):
        texto = f"{objetivo.get('objetivo', '')} {objetivo.get('estado', '')}".lower()
        if "descenso" in texto or "riesgo" in texto:
            return True
    return False


def objetivos_texto(equipo):
    if not equipo:
        return "sin contexto competitivo claro"
    objetivos = []
    for objetivo in equipo.get("objetivos", [])[:3]:
        nombre = str(objetivo.get("objetivo", "")).replace("_", " ")
        estado = str(objetivo.get("estado", "")).replace("_", " ")
        if nombre:
            objetivos.append(f"{nombre} ({estado})")
    return ", ".join(objetivos) if objetivos else "sin objetivo fuerte detectado"


def forma_float(tendencias, clave, divisor):
    try:
        return float(tendencias.get(clave) or 0) / divisor
    except Exception:
        return 0.0


def fuerza(equipo, condicion):
    if not equipo:
        return 0.0
    pj = max(float(equipo.get("pj") or 0), 1.0)
    cond = equipo.get(condicion, {})
    cond_pj = max(float(cond.get("pj") or 0), 1.0)
    tendencias = equipo.get("tendencias", {})
    ppg = float(equipo.get("pts") or 0) / pj
    dg = float(equipo.get("dg") or 0) / pj
    cond_ppg = float(cond.get("pts") or 0) / cond_pj
    forma_5 = forma_float(tendencias, "forma_5_pts", 5.0)
    forma_10 = forma_float(tendencias, "forma_10_pts", 10.0)
    aceleracion = forma_5 - forma_10
    empates = float(tendencias.get("empates_pct") or 0)
    return (
        ppg * 30
        + dg * 12
        + cond_ppg * 20
        + forma_5 * 14
        + forma_10 * 12
        + aceleracion * 6
        + empates * 0.08
    )


def dinamica_texto(equipo):
    if not equipo:
        return ""
    tendencias = equipo.get("tendencias", {})
    forma_5 = float(tendencias.get("forma_5_pts") or 0)
    forma_10 = float(tendencias.get("forma_10_pts") or 0)
    if forma_10 <= 0:
        return "sin dinámica de 10 jornadas suficiente"
    media_5 = forma_5 / 5.0
    media_10 = forma_10 / 10.0
    if media_5 >= media_10 + 0.35:
        etiqueta = "dinámica positiva reciente"
    elif media_5 <= media_10 - 0.35:
        etiqueta = "dinámica negativa reciente"
    else:
        etiqueta = "dinámica estable"
    return f"forma últimos 5/10: {forma_5:.0f}/{forma_10:.0f} puntos, {etiqueta}"


def normalizar_probs(probs):
    probs = {k: max(float(probs.get(k, 1)), 1.0) for k in ("1", "X", "2")}
    total = sum(probs.values()) or 1
    return {k: round(v / total * 100, 1) for k, v in probs.items()}


def aplicar_patron_posicion(probs, memoria, posicion):
    perfil = memoria.get("quiniela", {}).get("historico_csv", {}).get("perfil_por_posicion", {}).get(str(posicion), {})
    if not perfil:
        return probs
    return normalizar_probs({
        "1": probs["1"] * 0.88 + float(perfil.get("1", 33.3)) * 0.12,
        "X": probs["X"] * 0.88 + float(perfil.get("X", 33.3)) * 0.12,
        "2": probs["2"] * 0.88 + float(perfil.get("2", 33.3)) * 0.12,
    })


def calcular_probabilidades(memoria, partido):
    local = buscar_equipo(memoria, partido.get("local", ""))
    visitante = buscar_equipo(memoria, partido.get("visitante", ""))
    fl = fuerza(local, "local")
    fv = fuerza(visitante, "visitante")
    diff = fl - fv

    probs = {
        "1": 37 + max(min(diff * 0.52, 24), -20),
        "X": 29 + max(0, 10 - abs(diff) * 0.20),
        "2": 34 + max(min(-diff * 0.52, 24), -20),
    }

    if local and visitante:
        emp_l = float(local.get("tendencias", {}).get("empates_pct") or 0)
        emp_v = float(visitante.get("tendencias", {}).get("empates_pct") or 0)
        if (emp_l + emp_v) / 2 >= 28:
            probs["X"] += 5
        if float(local.get("gc") or 0) / max(float(local.get("pj") or 1), 1) > 1.35:
            probs["2"] += 3
        if float(visitante.get("gc") or 0) / max(float(visitante.get("pj") or 1), 1) > 1.35:
            probs["1"] += 3

    probs = normalizar_probs(probs)
    probs = aplicar_patron_posicion(probs, memoria, partido.get("num"))
    return probs, local, visitante, round(diff, 2)


def ajustar_por_contexto(probs, contexto_local, contexto_visitante):
    probs = dict(probs)
    riesgo_extra = 0
    lecturas = []

    def penalizar(datos, lado):
        nonlocal riesgo_extra
        if not datos:
            return
        alertas = set(datos.get("alertas", []))
        nombre_lado = "local" if lado == "1" else "visitante"
        contrario = "2" if lado == "1" else "1"
        if "lesiones" in alertas or "sanciones" in alertas:
            probs[lado] -= 3
            probs[contrario] += 2
            probs["X"] += 1
            riesgo_extra += 5
            lecturas.append(f"Contexto {nombre_lado}: posibles bajas/sanciones detectadas.")
        if "dudas" in alertas:
            probs[lado] -= 1.5
            probs["X"] += 1.5
            riesgo_extra += 3
            lecturas.append(f"Contexto {nombre_lado}: dudas de disponibilidad o entrenamiento.")
        if "altas" in alertas:
            probs[lado] += 1.5
            riesgo_extra = max(riesgo_extra - 1, 0)
            lecturas.append(f"Contexto {nombre_lado}: posibles altas o regresos.")

    penalizar(contexto_local, "1")
    penalizar(contexto_visitante, "2")
    return normalizar_probs(probs), riesgo_extra, lecturas


def ajustar_por_motivacion(probs, local_comp, visitante_comp):
    probs = dict(probs)
    riesgo_extra = 0
    lecturas = []
    motivacion_local = valor_motivacion(local_comp)
    motivacion_visitante = valor_motivacion(visitante_comp)
    diferencia = motivacion_local - motivacion_visitante

    if diferencia:
        ajuste = max(min(diferencia * 2.2, 6), -6)
        probs["1"] += ajuste
        probs["2"] -= ajuste
        riesgo_extra += min(abs(diferencia) * 3, 8)
        if diferencia > 0:
            lecturas.append(
                f"Motivacion: el local compite con mas urgencia ({objetivos_texto(local_comp)})."
            )
        else:
            lecturas.append(
                f"Motivacion: el visitante compite con mas urgencia ({objetivos_texto(visitante_comp)})."
            )

    if motivacion_local >= 2 and motivacion_visitante >= 2:
        probs["X"] += 2
        riesgo_extra += 3
        lecturas.append("Motivacion: choque de alta presion para ambos; sube el riesgo de empate o resultado cerrado.")

    if objetivo_descenso(local_comp):
        probs["1"] += 1.5
        riesgo_extra += 2
        lecturas.append("Contexto competitivo local: partido condicionado por permanencia/descenso.")
    if objetivo_descenso(visitante_comp):
        probs["2"] += 1.5
        riesgo_extra += 2
        lecturas.append("Contexto competitivo visitante: partido condicionado por permanencia/descenso.")

    return normalizar_probs(probs), riesgo_extra, lecturas



def texto_competitivo_motor(equipo):
    objetivos = " ".join(
        f"{o.get('objetivo', '')} {o.get('estado', '')} {o.get('lectura', '')}"
        for o in (equipo or {}).get("objetivos", [])
    )
    return f"{objetivos} {(equipo or {}).get('situacion_competitiva', '')} {(equipo or {}).get('motivacion_competitiva', '')}".lower()


def objetivo_cerrado_motor(equipo):
    if not equipo:
        return False
    if equipo.get("objetivos_vivos"):
        return False
    texto = texto_competitivo_motor(equipo)
    return any(
        clave in texto
        for clave in (
            "asegurado_matematicamente",
            "campeon_matematico",
            "salvado_matematicamente",
            "descendido_matematicamente",
            "sin_opciones_matematicas",
            "no se juega nada",
        )
    )


def necesidad_viva_motor(equipo):
    if not equipo or objetivo_cerrado_motor(equipo):
        return False
    texto = texto_competitivo_motor(equipo)
    motivacion = str(equipo.get("motivacion_competitiva") or equipo.get("motivacion") or "").lower()
    return bool(equipo.get("objetivos_vivos")) or motivacion in {"alta", "maxima", "máxima"} or any(
        clave in texto
        for clave in (
            "riesgo_descenso",
            "en_descenso_con_opciones",
            "permanencia_por_cerrar",
            "defiende_plaza",
            "aspira_matematicamente",
            "aspira_por_desempate",
            "descenso",
            "permanencia",
            "playoff",
            "ascenso",
            "conference",
            "europa",
            "champions",
        )
    )


def descenso_vivo_motor(equipo):
    return necesidad_viva_motor(equipo) and any(c in texto_competitivo_motor(equipo) for c in ("descenso", "permanencia", "salvarse"))


def tasa_patron(patrones, clave):
    try:
        return float((patrones.get("patrones") or {}).get(clave, {}).get("tasa_sorpresa") or 0)
    except Exception:
        return 0.0


def ajustar_por_patrones_aprendidos(probs, patrones, local_comp, visitante_comp):
    probs = dict(probs)
    riesgo_extra = 0.0
    lecturas = []
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)
    top = signo_top(probs)

    if visitante_cerrado and local_necesita:
        tasa = tasa_patron(patrones, "necesitado_local_vs_visitante_objetivo_cerrado")
        probs["1"] += 16 + tasa * 0.16
        probs["X"] += 11 + tasa * 0.09
        probs["2"] -= 12
        riesgo_extra += 24 + tasa * 0.38
        lecturas.append(f"Aprendizaje competitivo: cuando el local necesita y el visitante tiene objetivo cerrado, el fijo visitante se rompe con frecuencia ({tasa:.1f}% en la memoria).")

    if local_cerrado and visitante_necesita:
        tasa = tasa_patron(patrones, "visitante_necesitado_vs_local_objetivo_cerrado")
        probs["2"] += 16 + tasa * 0.16
        probs["X"] += 11 + tasa * 0.09
        probs["1"] -= 12
        riesgo_extra += 24 + tasa * 0.38
        lecturas.append(f"Aprendizaje competitivo: cuando el visitante necesita y el local tiene objetivo cerrado, el 1 fijo no debe ser tranquilo ({tasa:.1f}% de rupturas en memoria).")

    if visitante_descenso and top == "1":
        tasa = tasa_patron(patrones, "visitante_descenso_vs_local_favorito")
        probs["X"] += 16 + tasa * 0.12
        probs["2"] += 18 + tasa * 0.16
        probs["1"] -= 20
        riesgo_extra += 75 + tasa * 0.40
        lecturas.append(f"Aprendizaje de descenso: un visitante que se juega permanencia contra favorito local debe subir a zona prioritaria de cobertura; patron historico {tasa:.1f}%.")

    if local_descenso and top == "2":
        tasa = tasa_patron(patrones, "local_descenso_vs_visitante_favorito")
        probs["X"] += 16 + tasa * 0.12
        probs["1"] += 18 + tasa * 0.16
        probs["2"] -= 20
        riesgo_extra += 75 + tasa * 0.40
        lecturas.append(f"Aprendizaje de descenso: un local que se juega permanencia contra favorito visitante debe subir a zona prioritaria de cobertura; patron historico {tasa:.1f}%.")

    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        tasa = tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo")
        riesgo_extra += 22 + tasa * 0.34
        lecturas.append(f"Patron general aprendido: necesidad contra objetivo cerrado aumenta sorpresa y exige desconfiar del fijo limpio ({tasa:.1f}%).")

    if local_necesita and visitante_necesita:
        probs["X"] += 7
        riesgo_extra += 20
        lecturas.append("Choque de necesidades vivas: el empate y la cobertura amplia ganan valor frente al fijo limpio.")

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas

def signo_top(probs):
    return sorted(probs.items(), key=lambda x: x[1], reverse=True)[0][0]


def doble_top(probs):
    top2 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:2]
    signos = {s for s, _ in top2}
    return "".join(s for s in ("1", "X", "2") if s in signos)


def incertidumbre(probs, local, visitante, diff, riesgo_contexto=0):
    orden = sorted(probs.values(), reverse=True)
    margen = orden[0] - orden[1]
    puntos = 100 - margen + probs["X"] * 0.35
    if abs(diff) < 8:
        puntos += 8
    if local and local.get("racha_actual", {}).get("sin_ganar", 0) >= 3:
        puntos += 4
    if visitante and visitante.get("racha_actual", {}).get("sin_perder", 0) >= 3:
        puntos += 4
    puntos += riesgo_contexto
    return round(puntos, 2)


def explicar(
    partido,
    probs,
    signo,
    local,
    visitante,
    diff,
    tipo,
    contexto_local=None,
    contexto_visitante=None,
    lecturas_contexto=None,
    local_comp=None,
    visitante_comp=None,
    lecturas_motivacion=None,
    prob_sorpresa=None,
):
    razones = []
    razones.append(f"Probabilidades IA: 1={probs['1']}%, X={probs['X']}%, 2={probs['2']}%.")
    if local:
        t = local.get("tendencias", {})
        razones.append(
            f"{partido.get('local')} llega con {local.get('pts', 0)} puntos, "
            f"{dinamica_texto(local)} y "
            f"{t.get('goles_favor_por_partido', 0)} goles a favor por partido."
        )
    if visitante:
        t = visitante.get("tendencias", {})
        razones.append(
            f"{partido.get('visitante')} llega con {visitante.get('pts', 0)} puntos, "
            f"{dinamica_texto(visitante)} y "
            f"{t.get('goles_contra_por_partido', 0)} goles encajados por partido."
        )
    if abs(diff) < 8:
        razones.append("El partido queda equilibrado por fuerza reciente, asi que sube el riesgo de empate o sorpresa.")
    if tipo == "TRIPLE":
        razones.append("Se protege con triple porque es de los partidos con mas incertidumbre del boleto.")
    elif tipo == "DOBLE":
        razones.append("Se protege con doble porque el segundo signo tiene peso suficiente para cubrir una desviacion razonable.")
    else:
        razones.append("Se deja como fijo porque el signo principal tiene mejor relacion entre probabilidad y riesgo.")
    lecturas_contexto = lecturas_contexto or []
    if contexto_local:
        razones.append(contexto_local.get("resumen", ""))
    if contexto_visitante:
        razones.append(contexto_visitante.get("resumen", ""))
    razones.extend(lecturas_contexto)
    lecturas_motivacion = lecturas_motivacion or []
    razones.extend(lecturas_motivacion)
    if local_comp or visitante_comp:
        razones.append(
            f"Objetivos: {partido.get('local')} ({objetivos_texto(local_comp)}) frente a "
            f"{partido.get('visitante')} ({objetivos_texto(visitante_comp)})."
        )
    if prob_sorpresa is not None:
        razones.append(f"Riesgo de azar/sorpresa estimado: {prob_sorpresa}%.")
    razones.append(f"Decision final: {signo}.")
    return " ".join(razones)


def probabilidad_sorpresa(probs, incertidumbre_puntos):
    top = max(float(v) for v in probs.values())
    base = 100 - top
    extra = max(min((float(incertidumbre_puntos) - 90) * 0.25, 12), 0)
    return round(max(min(base + extra, 70), 18), 1)


def riesgo_necesidad_real(local_comp, visitante_comp):
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


def tercera_probabilidad(partido):
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


def coste(dobles, triples, elige8):
    apuestas = 2 ** dobles * 3 ** triples
    importe_quiniela = max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO)
    importe_elige8 = PRECIO_ELIGE8 if elige8 else 0.0
    return {
        "apuestas": apuestas,
        "importe_quiniela": round(importe_quiniela, 2),
        "importe_elige8": round(importe_elige8, 2),
        "importe_total": round(importe_quiniela + importe_elige8, 2),
    }


def predecir(jornada=None, dobles=0, triples=0, elige8=False, validar=False):
    memoria = cargar_json(MEMORIA, {})
    contexto = cargar_json(CONTEXTO_EQUIPOS, {})
    contexto_competitivo = cargar_json(CONTEXTO_COMPETITIVO, {})
    patrones_competitivos = cargar_json(PATRONES_COMPETITIVOS, {})
    jornada = jornada or detectar_jornada_activa()
    data = cargar_json(JORNADAS / f"jornada_{jornada}.json", {})
    partidos_base = [p for p in data.get("partidos", []) if int(p.get("num", 0)) <= 14]
    if not partidos_base:
        raise SystemExit(f"No hay partidos para jornada {jornada}")

    evaluados = []
    for partido in partidos_base:
        probs, local, visitante, diff = calcular_probabilidades(memoria, partido)
        contexto_local = buscar_contexto_equipo(contexto, partido.get("local", ""))
        contexto_visitante = buscar_contexto_equipo(contexto, partido.get("visitante", ""))
        probs, riesgo_contexto, lecturas_contexto = ajustar_por_contexto(probs, contexto_local, contexto_visitante)
        local_comp = buscar_contexto_competitivo(contexto_competitivo, partido.get("local", ""))
        visitante_comp = buscar_contexto_competitivo(contexto_competitivo, partido.get("visitante", ""))
        probs, riesgo_motivacion, lecturas_motivacion = ajustar_por_motivacion(probs, local_comp, visitante_comp)
        probs, riesgo_patrones, lecturas_patrones = ajustar_por_patrones_aprendidos(
            probs, patrones_competitivos, local_comp, visitante_comp
        )
        lecturas_motivacion.extend(lecturas_patrones)
        inc = incertidumbre(probs, local, visitante, diff, riesgo_contexto + riesgo_motivacion + riesgo_patrones)
        sorpresa = probabilidad_sorpresa(probs, inc)
        evaluados.append({
            **partido,
            "probabilidades": probs,
            "signo_base": signo_top(probs),
            "incertidumbre": inc,
            "probabilidad_sorpresa": sorpresa,
            "riesgo_necesidad_real": riesgo_necesidad_real(local_comp, visitante_comp),
            "contexto_local": contexto_local,
            "contexto_visitante": contexto_visitante,
            "lecturas_contexto": lecturas_contexto,
            "contexto_competitivo_local": local_comp,
            "contexto_competitivo_visitante": visitante_comp,
            "lecturas_motivacion": lecturas_motivacion,
            "_local": local,
            "_visitante": visitante,
            "_diff": diff,
        })

    por_triple = sorted(evaluados, key=prioridad_triple, reverse=True)
    triples_set = {p["num"] for p in por_triple[:triples]}
    por_doble = sorted(
        [p for p in evaluados if p["num"] not in triples_set],
        key=prioridad_doble,
        reverse=True,
    )
    dobles_set = {p["num"] for p in por_doble[:dobles]}

    elige8_set = set()
    if elige8:
        elige8_set = {p["num"] for p in sorted(evaluados, key=lambda p: p["incertidumbre"])[:8]}

    partidos = []
    for partido in sorted(evaluados, key=lambda p: p["num"]):
        if partido["num"] in triples_set:
            signo = "1X2"
            tipo = "TRIPLE"
        elif partido["num"] in dobles_set:
            signo = doble_top(partido["probabilidades"])
            tipo = "DOBLE"
        else:
            signo = partido["signo_base"]
            tipo = "FIJO"

        partidos.append({
            "num": partido["num"],
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "probabilidades": partido["probabilidades"],
            "signo_base": partido["signo_base"],
            "signo_final": signo,
            "tipo": tipo,
            "incertidumbre": partido["incertidumbre"],
            "probabilidad_sorpresa": partido["probabilidad_sorpresa"],
            "elige8": partido["num"] in elige8_set,
            "razonamiento": explicar(
                partido,
                partido["probabilidades"],
                signo,
                partido["_local"],
                partido["_visitante"],
                partido["_diff"],
                tipo,
                partido.get("contexto_local"),
                partido.get("contexto_visitante"),
                partido.get("lecturas_contexto"),
                partido.get("contexto_competitivo_local"),
                partido.get("contexto_competitivo_visitante"),
                partido.get("lecturas_motivacion"),
                partido.get("probabilidad_sorpresa"),
            ),
        })

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "temporada_base": memoria.get("temporada", "2025/2026"),
        "estado": "validada" if validar else "prediccion_no_validada",
        "configuracion": {
            "dobles": dobles,
            "triples": triples,
            "elige8": elige8,
        },
        "coste": coste(dobles, triples, elige8),
        "partidos": partidos,
        "contexto_equipos": {
            "generado_en": contexto.get("generado_en"),
            "fuentes": contexto.get("fuentes", []),
        },
        "contexto_competitivo": {
            "generado_en": contexto_competitivo.get("generado_en"),
            "reglas": contexto_competitivo.get("reglas", {}),
        },
        "pleno15": data.get("pleno15"),
        "resumen": {
            "fijos": sum(1 for p in partidos if p["tipo"] == "FIJO"),
            "dobles": sum(1 for p in partidos if p["tipo"] == "DOBLE"),
            "triples": sum(1 for p in partidos if p["tipo"] == "TRIPLE"),
            "elige8_seleccionados": sum(1 for p in partidos if p["elige8"]),
        },
    }

    destino = (JUGADAS if validar else PREDICCIONES) / f"jornada_{jornada}.json"
    guardar_json(destino, salida)
    if validar:
        guardar_json(JUGADAS / "ultima_validada.json", salida)
    else:
        guardar_json(PREDICCIONES / "ultima_prediccion.json", salida)
    print(destino)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jornada", type=int, default=None)
    parser.add_argument("--dobles", type=int, default=0)
    parser.add_argument("--triples", type=int, default=0)
    parser.add_argument("--elige8", action="store_true")
    parser.add_argument("--validar", action="store_true")
    args = parser.parse_args()
    predecir(args.jornada, args.dobles, args.triples, args.elige8, args.validar)


if __name__ == "__main__":
    main()
