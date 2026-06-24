"""Genera clasificaciones y situacion competitiva del Mundial 2026.

Lee data/mundial_2026_resultados.json y escribe
 data/memoria_ia/clasificaciones_mundial_2026.json.

El calculo usa solo resultados confirmados ya presentes en el sistema. La situacion
competitiva se estima con logica conservadora de fase de grupos: top 2 directo,
terceros con dependencia externa, 4 equipos por grupo y 3 partidos por seleccion.
"""

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FUENTE = DATA / "mundial_2026_resultados.json"
SALIDA = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"

PARTIDOS_POR_EQUIPO = 3
EQUIPOS_POR_GRUPO = 4
CLASIFICAN_DIRECTO = 2

ALIAS = {
    "eeuu": "estados unidos",
    "ee uu": "estados unidos",
    "usa": "estados unidos",
    "united states": "estados unidos",
    "estados unidos": "estados unidos",
    "paises bajos": "paises bajos",
    "holanda": "paises bajos",
    "netherlands": "paises bajos",
    "japon": "japon",
    "costa marfil": "costa de marfil",
    "costa de marfil": "costa de marfil",
    "ivory coast": "costa de marfil",
    "cote divoire": "costa de marfil",
    "curacao": "curazao",
    "curazao": "curazao",
    "curaçao": "curazao",
    "arabia saudi": "arabia saudi",
    "turkiye": "turquia",
    "turkey": "turquia",
    "belgica": "belgica",
    "tunez": "tunez",
    "espana": "espana",
    "méxico": "mexico",
    "mexico": "mexico",
}


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


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def normalizar_nombre(nombre):
    texto = str(nombre or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
    return ALIAS.get(texto, texto)


def parsear_resultado(resultado):
    m = re.match(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$", str(resultado or ""))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def registro_base(equipo, grupo):
    return {
        "equipo": equipo,
        "grupo": grupo,
        "pj": 0,
        "g": 0,
        "e": 0,
        "p": 0,
        "gf": 0,
        "gc": 0,
        "dg": 0,
        "pts": 0,
        "partidos": [],
    }


def sumar_partido(tabla, grupo, equipo, rival, gf, gc, fecha, fuente):
    reg = tabla[grupo].setdefault(equipo, registro_base(equipo, grupo))
    reg["pj"] += 1
    reg["gf"] += gf
    reg["gc"] += gc
    reg["dg"] = reg["gf"] - reg["gc"]
    if gf > gc:
        reg["g"] += 1
        puntos = 3
        signo = "G"
    elif gf == gc:
        reg["e"] += 1
        puntos = 1
        signo = "E"
    else:
        reg["p"] += 1
        puntos = 0
        signo = "P"
    reg["pts"] += puntos
    reg["partidos"].append({
        "fecha": fecha,
        "rival": rival,
        "resultado": f"{gf}-{gc}",
        "signo_equipo": signo,
        "puntos": puntos,
        "fuente": fuente,
    })


def ordenar_grupo(registros):
    return sorted(
        registros,
        key=lambda r: (
            int(r.get("pts") or 0),
            int(r.get("dg") or 0),
            int(r.get("gf") or 0),
            -int(r.get("gc") or 0),
            normalizar_nombre(r.get("equipo")),
        ),
        reverse=True,
    )


def puntos_maximos(registro):
    restantes = max(PARTIDOS_POR_EQUIPO - int(registro.get("pj") or 0), 0)
    return int(registro.get("pts") or 0) + restantes * 3


def puntos_si_empata(registro):
    restantes = max(PARTIDOS_POR_EQUIPO - int(registro.get("pj") or 0), 0)
    return int(registro.get("pts") or 0) + (1 if restantes else 0)


def situacion_equipo(registro, grupo_ordenado):
    equipo = registro["equipo"]
    pts = int(registro.get("pts") or 0)
    pj = int(registro.get("pj") or 0)
    restantes = max(PARTIDOS_POR_EQUIPO - pj, 0)
    pos = next((i + 1 for i, r in enumerate(grupo_ordenado) if r["equipo"] == equipo), None) or 99
    max_pts = puntos_maximos(registro)
    empate_pts = puntos_si_empata(registro)
    rivales = [r for r in grupo_ordenado if r["equipo"] != equipo]
    rivales_max_superan = sum(1 for r in rivales if puntos_maximos(r) > pts)
    rivales_actual_superan_max = sum(1 for r in rivales if int(r.get("pts") or 0) > max_pts)
    rivales_max_superan_empate = sum(1 for r in rivales if puntos_maximos(r) > empate_pts)

    if pj >= PARTIDOS_POR_EQUIPO:
        if pos <= CLASIFICAN_DIRECTO:
            situacion = "ya_clasificada"
            necesidad = "ninguna"
            motivacion = "baja"
            lectura = "Grupo completado: posicion de clasificacion directa ya asegurada."
            objetivos_vivos = False
            rotacion = True
        elif pos == 3:
            situacion = "depende_de_otros_resultados"
            necesidad = "depender"
            motivacion = "media"
            lectura = "Grupo completado en tercera posicion: depende de comparativa de terceros y otros resultados."
            objetivos_vivos = True
            rotacion = False
        else:
            situacion = "eliminada"
            necesidad = "ninguna"
            motivacion = "baja"
            lectura = "Grupo completado sin posicion util de clasificacion."
            objetivos_vivos = False
            rotacion = True
    elif rivales_max_superan <= CLASIFICAN_DIRECTO - 1:
        situacion = "ya_clasificada"
        necesidad = "ninguna"
        motivacion = "baja"
        lectura = "Ventaja matematica suficiente para tener el pase directo virtualmente cerrado."
        objetivos_vivos = False
        rotacion = True
    elif rivales_actual_superan_max >= EQUIPOS_POR_GRUPO - 1:
        situacion = "eliminada"
        necesidad = "ninguna"
        motivacion = "baja"
        lectura = "Ni ganando todos los partidos restantes puede alcanzar una posicion util del grupo."
        objetivos_vivos = False
        rotacion = True
    elif restantes == 1 and rivales_max_superan_empate >= CLASIFICAN_DIRECTO:
        situacion = "necesita_ganar"
        necesidad = "ganar"
        motivacion = "maxima"
        lectura = "Con empate quedaria expuesta; necesita ganar para depender de si misma o sostener opciones fuertes."
        objetivos_vivos = True
        rotacion = False
    elif restantes >= 1 and rivales_max_superan_empate <= CLASIFICAN_DIRECTO - 1:
        situacion = "le_vale_empate"
        necesidad = "empatar"
        motivacion = "alta"
        lectura = "Un empate deja la clasificacion directa o una posicion muy favorable practicamente controlada."
        objetivos_vivos = True
        rotacion = False
    else:
        situacion = "depende_de_otros_resultados"
        necesidad = "depender"
        motivacion = "alta"
        lectura = "Sigue con opciones, pero su pase no depende solo del marcador propio."
        objetivos_vivos = True
        rotacion = False

    return {
        "posicion": pos,
        "partidos_restantes_estimados": restantes,
        "puntos_maximos": max_pts,
        "puntos_si_empata_siguiente": empate_pts,
        "situacion": situacion,
        "situacion_competitiva": situacion,
        "necesidad_resultado": necesidad,
        "motivacion_competitiva": motivacion,
        "objetivos_vivos": objetivos_vivos,
        "rotacion_probable": rotacion,
        "lectura": lectura,
        "objetivos": [
            {
                "objetivo": "clasificacion_mundial_2026",
                "estado": situacion,
                "lectura": lectura,
            }
        ],
    }


def construir_clasificaciones(data):
    tabla = defaultdict(dict)
    descartados = []
    for partido in data.get("resultados", []):
        resultado = parsear_resultado(partido.get("resultado"))
        grupo = str(partido.get("grupo") or "sin_grupo").strip() or "sin_grupo"
        local = normalizar_nombre(partido.get("local"))
        visitante = normalizar_nombre(partido.get("visitante"))
        if not resultado or not local or not visitante:
            descartados.append(partido)
            continue
        gl, gv = resultado
        fecha = partido.get("fecha") or ""
        fuente = partido.get("fuente") or ""
        sumar_partido(tabla, grupo, local, visitante, gl, gv, fecha, fuente)
        sumar_partido(tabla, grupo, visitante, local, gv, gl, fecha, fuente)

    grupos = {}
    equipos = {}
    for grupo, registros in sorted(tabla.items()):
        ordenados = ordenar_grupo(list(registros.values()))
        filas = []
        for reg in ordenados:
            situacion = situacion_equipo(reg, ordenados)
            fila = {
                **reg,
                **situacion,
            }
            filas.append(fila)
            equipos[normalizar_nombre(reg["equipo"])] = fila
        grupos[grupo] = {
            "grupo": grupo,
            "equipos_detectados": len(filas),
            "clasificacion": filas,
        }

    return {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "fuente": str(FUENTE.relative_to(ROOT)),
        "criterio": {
            "fase": "grupos_mundial_2026",
            "equipos_por_grupo": EQUIPOS_POR_GRUPO,
            "partidos_por_equipo": PARTIDOS_POR_EQUIPO,
            "clasificacion_directa": "top_2_grupo",
            "terceros": "pueden depender de comparativa externa; se marca depende_de_otros_resultados",
        },
        "total_grupos": len(grupos),
        "total_equipos": len(equipos),
        "grupos": grupos,
        "equipos": equipos,
        "descartados": descartados,
    }


def main():
    data = cargar_json(FUENTE, {"resultados": []})
    salida = construir_clasificaciones(data)
    guardar_json(SALIDA, salida)
    print(f"Clasificaciones Mundial 2026 actualizadas: {salida['total_grupos']} grupos, {salida['total_equipos']} selecciones.")


if __name__ == "__main__":
    main()
