"""
Alimenta data/memoria_ia/sorpresas_mercado.json con casos reales de sorpresa:
partidos donde el motor apostó FIJO con alta confianza y el resultado fue diferente,
cruzando el diario de aprendizaje con los snapshots de predicción disponibles.

La función reforzar_ajuste_por_memoria_sorpresas() del motor usa este archivo para
amplificar un 20% los ajustes motivacionales cuando hay >=3 casos similares.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DIARIO = DATA / "memoria_ia" / "diario_aprendizaje.json"
PREDICCIONES = DATA / "predicciones"
SORPRESAS_MERCADO = DATA / "memoria_ia" / "sorpresas_mercado.json"

# Categorías que entiende reforzar_ajuste_por_memoria_sorpresas()
CAT_DERBI = "derbi"
CAT_SIN_PRESION = "partido_sin_presion"
CAT_MOTIVACIONAL = "motivacion_competitiva"
CAT_DESCONOCIDO = "desconocido"

# Pares de rivales históricos (misma lógica que DERBIS_HISTORICOS en el motor)
DERBIS = {
    frozenset(["real madrid", "barcelona"]), frozenset(["atletico", "real madrid"]),
    frozenset(["sevilla", "betis"]), frozenset(["valencia", "levante"]),
    frozenset(["athletic", "real sociedad"]), frozenset(["deportivo", "celta"]),
    frozenset(["atletico", "athletic"]), frozenset(["espanyol", "barcelona"]),
    frozenset(["valladolid", "salamanca"]), frozenset(["malaga", "granada"]),
    frozenset(["oviedo", "sporting"]), frozenset(["villarreal", "valencia"]),
}


def cargar_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def guardar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def es_derbi(local: str, visitante: str) -> bool:
    l = local.lower()
    v = visitante.lower()
    for par in DERBIS:
        nombres = list(par)
        if any(nombres[0] in l or nombres[0] in v for _ in [1]) and \
           any(nombres[1] in l or nombres[1] in v for _ in [1]):
            return True
    return False


def extraer_equipos_de_nombre(nombre_partido: str):
    """'11. Málaga - Castellón' → ('Málaga', 'Castellón')"""
    m = re.match(r"^\d+\.\s*(.+?)\s*[-–]\s*(.+)$", nombre_partido.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", ""


def inferir_categoria_y_alertas(razonamiento: str, riesgo_necesidad: bool,
                                 local: str = "", visitante: str = ""):
    """Infiere la categoría de sorpresa y alertas motivacionales."""
    r = (razonamiento or "").lower()

    # Primero detectar derbis por nombre de equipos
    if es_derbi(local, visitante) or "derbi" in r or "rivalidad hist" in r:
        return CAT_DERBI, ["derbi_todo_puede_pasar"]

    if (
        "sin objetivos" in r
        or "ambos clasificados sin tension" in r
        or "ambos clasificados" in r
        or "ya salvado" in r
        or "sin presion" in r
    ):
        return CAT_SIN_PRESION, ["equipo_sin_objetivos"]

    if (
        riesgo_necesidad
        or "necesita" in r
        or "descenso" in r
        or "salvacion" in r
        or "playoff ascenso" in r
        or "ascenso directo" in r
        or "objetivo cerrado" in r
        or "competicion mas urgencia" in r
        or "mas necesitado" in r
    ):
        return CAT_MOTIVACIONAL, ["equipo_necesitado_vs_objetivo_cerrado"]

    return CAT_DESCONOCIDO, []


def numero_partido_desde_nombre(nombre_partido: str):
    m = re.match(r"^(\d+)\.", nombre_partido.strip())
    return int(m.group(1)) if m else None


def prob_top_desde_partidos(partido_snap: dict) -> float:
    """Calcula probabilidad_top desde el dict de probabilidades si el campo explícito es None."""
    pt = partido_snap.get("probabilidad_top")
    if pt is not None:
        return float(pt)
    probs = partido_snap.get("probabilidades") or {}
    if probs:
        return max(float(v) for v in probs.values())
    return 0.0


def procesar_diario():
    diario = cargar_json(DIARIO, {})
    entradas = diario.get("entradas", [])

    sorpresas = []
    vistas = set()

    for entrada in entradas:
        # Solo fallos de fijo
        if entrada.get("categoria_fallo") != "fallo_fijo":
            continue
        if entrada.get("tipo_apuesta") != "FIJO":
            continue
        if entrada.get("acierto", True):
            continue

        jornada = entrada.get("jornada")
        nombre_partido = entrada.get("partido", "")
        num = numero_partido_desde_nombre(nombre_partido)

        if not jornada or not num:
            continue

        clave = (jornada, num)
        if clave in vistas:
            continue
        vistas.add(clave)

        local, visitante = extraer_equipos_de_nombre(nombre_partido)

        # Intentar enriquecer con snapshot de la jornada
        snap_path = PREDICCIONES / f"jornada_{jornada}.json"
        snapshot = cargar_json(snap_path)
        partido_snap = None
        if snapshot:
            for p in snapshot.get("partidos", []):
                if p.get("num") == num:
                    partido_snap = p
                    break

        razonamiento = (partido_snap or {}).get("razonamiento", "")
        riesgo_necesidad = bool((partido_snap or {}).get("riesgo_necesidad_real", False))
        probabilidad_top = prob_top_desde_partidos(partido_snap) if partido_snap else 0.0

        categoria, alertas = inferir_categoria_y_alertas(
            razonamiento, riesgo_necesidad, local, visitante
        )

        # Incluir siempre los fallos de fijo: el motor necesita casos reales.
        # Los "desconocido" sin alertas no coincidirán con el filtro del motor
        # pero los motivacionales sí. No filtramos por probabilidad mínima.
        sorpresas.append({
            "jornada": jornada,
            "partido": nombre_partido,
            "num_partido": num,
            "local": local,
            "visitante": visitante,
            "pronostico_jugado": entrada.get("pronostico_jugado", ""),
            "signo_real": entrada.get("signo_real", ""),
            "resultado": entrada.get("resultado", ""),
            "categoria_sorpresa": categoria,
            "alerta_motivacion_detectada": alertas[0] if alertas else "",
            "alertas_motivacion_detectadas": alertas,
            "probabilidad_top": round(probabilidad_top, 1),
            "riesgo_necesidad_real": riesgo_necesidad,
            "tiene_snapshot": partido_snap is not None,
            "origen": "diario_aprendizaje_fallo_fijo",
            "registrada_en": datetime.now(timezone.utc).isoformat(),
        })

    return sorpresas


def main():
    print("=== Alimentando sorpresas_mercado.json ===")

    sorpresas_nuevas = procesar_diario()

    actual = cargar_json(SORPRESAS_MERCADO, {"version": "1.0", "sorpresas": []})
    existentes = actual.get("sorpresas", [])

    claves_existentes = {
        (e.get("jornada"), e.get("num_partido")) for e in existentes
    }

    nuevas_añadidas = []
    for s in sorpresas_nuevas:
        clave = (s["jornada"], s["num_partido"])
        if clave not in claves_existentes:
            existentes.append(s)
            nuevas_añadidas.append(s)
            claves_existentes.add(clave)

    resultado = {
        "version": "1.1",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "total_sorpresas": len(existentes),
        "descripcion": (
            "Casos reales donde el motor predijo FIJO y el resultado fue diferente. "
            "Usados por reforzar_ajuste_por_memoria_sorpresas() para amplificar "
            "ajustes motivacionales un 20% cuando hay >=3 casos similares."
        ),
        "sorpresas": existentes,
    }

    guardar_json(SORPRESAS_MERCADO, resultado)

    print(f"  Casos nuevos añadidos: {len(nuevas_añadidas)}")
    print(f"  Total sorpresas en memoria: {len(existentes)}")
    by_cat = {}
    for s in existentes:
        c = s.get("categoria_sorpresa", "?")
        by_cat[c] = by_cat.get(c, 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"    {cat}: {n}")

    if not nuevas_añadidas:
        print("  Sin cambios: el archivo ya estaba actualizado.")


if __name__ == "__main__":
    main()
