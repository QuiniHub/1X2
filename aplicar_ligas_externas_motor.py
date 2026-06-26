"""Aplica memoria de ligas externas a predicciones generadas por el motor."""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
MEMORIA_DIR = DATA / "memoria_ia"
LIGAS_EXTERNAS = MEMORIA_DIR / "ligas_externas.json"
APRENDIZAJE_EXTERNAS = MEMORIA_DIR / "aprendizaje_ligas_externas.json"

PRECIO_APUESTA = 1.50
PRECIO_ELIGE8 = 0.50


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el|ac|bk|if)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def puntuacion(candidato, objetivo):
    a = normalizar(candidato)
    b = normalizar(objetivo)
    if not a or not b:
        return 0
    if a == b:
        return 1000
    comunes = set(a.split()) & set(b.split())
    score = len(comunes) * 40
    if a in b or b in a:
        score += 40
    return score


def buscar_equipo(memoria, nombre):
    equipos = (memoria or {}).get("equipos") or {}
    clave = normalizar(nombre)
    if clave in equipos:
        return equipos[clave]
    mejor = None
    mejor_score = 0
    for item in equipos.values():
        score = puntuacion(item.get("equipo") or item.get("clave") or "", nombre)
        if score > mejor_score:
            mejor = item
            mejor_score = score
    return mejor if mejor_score >= 55 else None


def precision_liga(aprendizaje, liga):
    datos = ((aprendizaje or {}).get("ligas") or {}).get(liga or "") or {}
    apariciones = int(datos.get("apariciones") or 0)
    if apariciones <= 0:
        return None, apariciones
    if datos.get("precision") is not None:
        return float(datos.get("precision") or 0), apariciones
    return float(datos.get("aciertos") or 0) / apariciones, apariciones


def valor_equipo(info, condicion):
    if not info:
        return 0.0
    puntos = float(info.get("puntos") or 0)
    posicion = float(info.get("posicion") or 20)
    gf = float(info.get("goles_favor") or 0)
    gc = float(info.get("goles_contra") or 0)
    forma = info.get("ultimos_5_local" if condicion == "local" else "ultimos_5_visitante") or []
    puntos_forma = sum(3 if r == "G" else 1 if r == "E" else 0 for r in forma)
    return puntos * 0.35 + max(0, 22 - posicion) * 1.8 + (gf - gc) * 0.15 + puntos_forma * 1.4


def normalizar_probs(probs):
    datos = {s: max(float((probs or {}).get(s) or 1), 1.0) for s in ("1", "X", "2")}
    total = sum(datos.values()) or 1.0
    return {s: round(datos[s] / total * 100.0, 1) for s in ("1", "X", "2")}


def signo_top(probs):
    return max(("1", "X", "2"), key=lambda s: float((probs or {}).get(s) or 0))


def doble_top(probs):
    top2 = sorted(
        ((s, float((probs or {}).get(s) or 0)) for s in ("1", "X", "2")),
        key=lambda x: x[1],
        reverse=True,
    )[:2]
    signos = {s for s, _ in top2}
    return "".join(s for s in ("1", "X", "2") if s in signos)


def aplicar_a_partido(partido, memoria, aprendizaje):
    local_info = buscar_equipo(memoria, partido.get("local", ""))
    visitante_info = buscar_equipo(memoria, partido.get("visitante", ""))
    if not local_info and not visitante_info:
        return False

    probs = normalizar_probs(partido.get("probabilidades") or {"1": 33.4, "X": 33.3, "2": 33.3})
    lecturas = []
    riesgo_extra = 0.0

    if local_info and visitante_info:
        diff = valor_equipo(local_info, "local") - valor_equipo(visitante_info, "visitante")
        ajuste = max(min(diff * 0.16, 5.0), -5.0)
        probs["1"] += ajuste
        probs["2"] -= ajuste
        probs = normalizar_probs(probs)
        lecturas.append(
            f"Ligas externas: forma/clasificacion ajusta el partido ({local_info.get('liga')} / {visitante_info.get('liga')})."
        )
    else:
        riesgo_extra += 8.0
        lecturas.append("Ligas externas: solo hay memoria completa de uno de los dos equipos; sube incertidumbre.")

    ligas = {info.get("liga") for info in (local_info, visitante_info) if info and info.get("liga")}
    precisiones_bajas = []
    for liga in sorted(ligas):
        precision, muestra = precision_liga(aprendizaje, liga)
        if precision is not None and precision < 0.50:
            precisiones_bajas.append({"liga": liga, "precision": round(precision, 4), "muestra": muestra})

    forzada = ""
    if precisiones_bajas:
        partido["incertidumbre_alta"] = True
        partido["motivo_incertidumbre_alta"] = "Liga externa con menos del 50% de acierto historico."
        valores = sorted(probs.values(), reverse=True)
        tercera = valores[2] if len(valores) > 2 else 0
        forzada = "TRIPLE" if tercera >= 18 or any(p["precision"] < 0.35 for p in precisiones_bajas) else "DOBLE"
        partido["forzar_cobertura_liga_externa"] = forzada
        riesgo_extra += 18.0
        lecturas.append(
            "Ligas externas: precision historica baja en "
            + ", ".join(f"{p['liga']} ({p['precision']:.0%})" for p in precisiones_bajas)
            + f"; se fuerza cobertura {forzada}."
        )

    partido["probabilidades"] = probs
    partido["signo_base"] = signo_top(probs)
    partido["ligas_externas"] = {
        "activo": True,
        "local": local_info or {},
        "visitante": visitante_info or {},
        "precision_baja_ligas": precisiones_bajas,
        "ajustado_en": ahora_iso(),
    }
    ajuste = partido.setdefault("ajuste_ligas_externas", {})
    ajuste.update({"activo": True, "riesgo_extra": riesgo_extra, "lecturas": lecturas})
    partido.setdefault("lecturas_motivacion", [])
    for lectura in lecturas:
        if lectura not in partido["lecturas_motivacion"]:
            partido["lecturas_motivacion"].append(lectura)

    if forzada:
        if forzada == "TRIPLE":
            partido["tipo"] = "TRIPLE"
            partido["signo_final"] = "1X2"
        elif str(partido.get("tipo") or "FIJO").upper() == "FIJO":
            partido["tipo"] = "DOBLE"
            partido["signo_final"] = doble_top(probs)
    return True


def multiplicador(signos):
    total = 1
    for signo in signos:
        total *= max(len("".join(s for s in "1X2" if s in str(signo or "").upper())), 1)
    return total


def recalcular_resumen_y_coste(data):
    partidos = data.get("partidos") or []
    dobles = sum(1 for p in partidos if str(p.get("tipo") or "").upper() == "DOBLE")
    triples = sum(1 for p in partidos if str(p.get("tipo") or "").upper() == "TRIPLE")
    fijos = sum(1 for p in partidos if str(p.get("tipo") or "FIJO").upper() == "FIJO")
    data.setdefault("resumen", {}).update({"fijos": fijos, "dobles": dobles, "triples": triples})
    data.setdefault("configuracion", {}).update({"dobles": dobles, "triples": triples})
    signos = [p.get("signo_final") or p.get("signo_base") or "1" for p in partidos]
    apuestas = multiplicador(signos)
    elige8_signos = [p.get("signo_final") or p.get("signo_base") or "1" for p in partidos if p.get("elige8")]
    apuestas_elige8 = multiplicador(elige8_signos) if elige8_signos else 0
    importe_quiniela = max(apuestas * PRECIO_APUESTA, PRECIO_APUESTA) if partidos else 0
    data["coste"] = {
        "apuestas": apuestas,
        "apuestas_elige8": apuestas_elige8,
        "importe_quiniela": round(importe_quiniela, 2),
        "importe_elige8": round(apuestas_elige8 * PRECIO_ELIGE8, 2),
        "importe_total": round(importe_quiniela + apuestas_elige8 * PRECIO_ELIGE8, 2),
    }


def aplicar_ligas_externas_a_prediccion(path):
    data = cargar_json(path, {})
    if not data or not data.get("partidos"):
        return 0
    memoria = cargar_json(LIGAS_EXTERNAS, {})
    aprendizaje = cargar_json(APRENDIZAJE_EXTERNAS, {})
    cambios = 0
    for partido in data.get("partidos") or []:
        if aplicar_a_partido(partido, memoria, aprendizaje):
            cambios += 1
    if cambios:
        data["ligas_externas_motor"] = {"activo": True, "partidos_ajustados": cambios, "actualizado_en": ahora_iso()}
        recalcular_resumen_y_coste(data)
        guardar_json(path, data)
    return cambios


def aplicar_ligas_externas_en_archivos(jornada=None):
    rutas = []
    ultima = PREDICCIONES / "ultima_prediccion.json"
    if ultima.exists():
        rutas.append(ultima)
    if jornada:
        jornada_path = PREDICCIONES / f"jornada_{jornada}.json"
        if jornada_path.exists():
            rutas.append(jornada_path)
    cambios = []
    for ruta in dict.fromkeys(rutas):
        total = aplicar_ligas_externas_a_prediccion(ruta)
        if total:
            cambios.append(f"{ruta.relative_to(ROOT)}:{total}")
    return cambios


if __name__ == "__main__":
    cambios = aplicar_ligas_externas_en_archivos()
    print("Ligas externas aplicadas: " + (", ".join(cambios) if cambios else "sin cambios"))
