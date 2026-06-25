"""Genera clasificaciones y situacion competitiva del Mundial 2026.

Lee data/mundial_2026_resultados.json y escribe
 data/memoria_ia/clasificaciones_mundial_2026.json.

Correccion critica: nunca se mezcla una seleccion en un grupo artificial
"sin_grupo" si puede inferirse su grupo real. Los resultados sin grupo solo se
usan cuando ambos equipos pertenecen al mismo grupo del Mundial 2026. Una
seleccion solo se marca eliminada si matematicamente ya no puede alcanzar ni
una posicion util de grupo, considerando que el tercer puesto puede depender de
comparativa externa. Tambien se deduplican resultados repetidos de distintas
fuentes por grupo, pareja de equipos y marcador.
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
PLAZA_UTIL_MINIMA = 3

ALIAS = {"eeuu":"estados unidos","ee uu":"estados unidos","usa":"estados unidos","united states":"estados unidos","estados unidos":"estados unidos","paises bajos":"paises bajos","holanda":"paises bajos","netherlands":"paises bajos","japon":"japon","japón":"japon","costa marfil":"costa de marfil","costa de marfil":"costa de marfil","ivory coast":"costa de marfil","cote divoire":"costa de marfil","curacao":"curazao","curazao":"curazao","curaçao":"curazao","arabia saudi":"arabia saudi","arabia saudí":"arabia saudi","turkiye":"turquia","turkey":"turquia","belgica":"belgica","bélgica":"belgica","tunez":"tunez","túnez":"tunez","espana":"espana","españa":"espana","méxico":"mexico","mexico":"mexico","irak":"irak","iraq":"irak","congo dr":"congo dr","rd congo":"congo dr","congo rd":"congo dr","cabo verde":"cabo verde"}

GRUPOS_MUNDIAL_2026 = {"A":["mexico","sudafrica","corea del sur","chequia"],"B":["suiza","canada","bosnia","qatar"],"C":["brasil","marruecos","haiti","escocia"],"D":["estados unidos","paraguay","australia","turquia"],"E":["alemania","curazao","costa de marfil","ecuador"],"F":["paises bajos","japon","suecia","tunez"],"G":["belgica","egipto","iran","nueva zelanda"],"H":["espana","cabo verde","arabia saudi","uruguay"],"I":["francia","senegal","irak","noruega"],"J":["argentina","argelia","austria","jordania"],"K":["portugal","congo dr","uzbekistan","colombia"],"L":["inglaterra","ghana","panama","croacia"]}
EQUIPO_A_GRUPO = {equipo: grupo for grupo, equipos in GRUPOS_MUNDIAL_2026.items() for equipo in equipos}

# Confirmados sin via matematica de clasificacion en fase de grupos.
# Se fuerza aqui para que el workflow no regenere estos equipos como vivos.
ELIMINADOS_MATEMATICOS_CONFIRMADOS = {"turquia", "tunez", "jordania", "panama", "haiti"}


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


def grupo_por_equipos(local, visitante, grupo_fuente=""):
    grupo_fuente = str(grupo_fuente or "").strip().upper()
    gl = EQUIPO_A_GRUPO.get(local)
    gv = EQUIPO_A_GRUPO.get(visitante)
    if grupo_fuente and grupo_fuente in GRUPOS_MUNDIAL_2026:
        return grupo_fuente if gl == grupo_fuente and gv == grupo_fuente else ""
    if gl and gl == gv:
        return gl
    return ""


def registro_base(equipo, grupo):
    return {"equipo": equipo, "grupo": grupo, "pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "dg": 0, "pts": 0, "partidos": []}


def sumar_partido(tabla, grupo, equipo, rival, gf, gc, fecha, fuente):
    reg = tabla[grupo].setdefault(equipo, registro_base(equipo, grupo))
    reg["pj"] += 1
    reg["gf"] += gf
    reg["gc"] += gc
    reg["dg"] = reg["gf"] - reg["gc"]
    if gf > gc:
        reg["g"] += 1; puntos = 3; signo = "G"
    elif gf == gc:
        reg["e"] += 1; puntos = 1; signo = "E"
    else:
        reg["p"] += 1; puntos = 0; signo = "P"
    reg["pts"] += puntos
    reg["partidos"].append({"fecha": fecha, "rival": rival, "resultado": f"{gf}-{gc}", "signo_equipo": signo, "puntos": puntos, "fuente": fuente})


def ordenar_grupo(registros):
    return sorted(registros, key=lambda r: (int(r.get("pts") or 0), int(r.get("dg") or 0), int(r.get("gf") or 0), -int(r.get("gc") or 0), normalizar_nombre(r.get("equipo"))), reverse=True)


def puntos_maximos(registro):
    restantes = max(PARTIDOS_POR_EQUIPO - int(registro.get("pj") or 0), 0)
    return int(registro.get("pts") or 0) + restantes * 3


def puntos_si_empata(registro):
    restantes = max(PARTIDOS_POR_EQUIPO - int(registro.get("pj") or 0), 0)
    return int(registro.get("pts") or 0) + (1 if restantes else 0)


def situacion_equipo(registro, grupo_ordenado):
    equipo = registro["equipo"]
    pj = int(registro.get("pj") or 0)
    restantes = max(PARTIDOS_POR_EQUIPO - pj, 0)
    pos = next((i + 1 for i, r in enumerate(grupo_ordenado) if r["equipo"] == equipo), None) or 99
    max_pts = puntos_maximos(registro)
    empate_pts = puntos_si_empata(registro)
    rivales = [r for r in grupo_ordenado if r["equipo"] != equipo]
    rivales_actual_superan_max = sum(1 for r in rivales if int(r.get("pts") or 0) > max_pts)
    rivales_max_superan_empate = sum(1 for r in rivales if puntos_maximos(r) > empate_pts)

    if equipo in ELIMINADOS_MATEMATICOS_CONFIRMADOS:
        situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "eliminada", "ninguna", "baja", False, True, "Eliminada por restriccion matematica confirmada: ya no tiene via de clasificacion."
    elif pj >= PARTIDOS_POR_EQUIPO:
        if pos <= CLASIFICAN_DIRECTO:
            situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "ya_clasificada", "ninguna", "baja", False, True, "Grupo completado: posicion de clasificacion directa ya asegurada."
        elif pos == PLAZA_UTIL_MINIMA:
            situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "depende_de_otros_resultados", "depender", "media", True, False, "Grupo completado en tercera posicion: depende de comparativa de terceros."
        else:
            situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "eliminada", "ninguna", "baja", False, True, "Grupo completado en cuarta posicion: sin via matematica de clasificacion."
    elif rivales_actual_superan_max >= PLAZA_UTIL_MINIMA:
        situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "eliminada", "ninguna", "baja", False, True, "Ni ganando todos los partidos restantes puede alcanzar una posicion util de grupo."
    elif restantes == 1 and rivales_max_superan_empate >= CLASIFICAN_DIRECTO:
        situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "necesita_ganar", "ganar", "maxima", True, False, "Con empate queda expuesta; necesita ganar para maximizar pase directo o tercer puesto fuerte."
    elif restantes >= 1 and pos <= CLASIFICAN_DIRECTO and rivales_max_superan_empate <= CLASIFICAN_DIRECTO - 1:
        situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "le_vale_empate", "empatar", "alta", True, False, "Un empate mantiene una posicion de clasificacion directa o muy favorable."
    else:
        situacion, necesidad, motivacion, objetivos_vivos, rotacion, lectura = "depende_de_otros_resultados", "depender", "alta", True, False, "Sigue con opciones matematicas de clasificacion, pero su pase depende tambien de otros marcadores."

    return {"posicion": pos, "partidos_restantes_estimados": restantes, "puntos_maximos": max_pts, "puntos_si_empata_siguiente": empate_pts, "situacion": situacion, "situacion_competitiva": situacion, "necesidad_resultado": necesidad, "motivacion_competitiva": motivacion, "objetivos_vivos": objetivos_vivos, "rotacion_probable": rotacion, "lectura": lectura, "objetivos": [{"objetivo": "clasificacion_mundial_2026", "estado": situacion, "lectura": lectura}]}


def construir_clasificaciones(data):
    tabla = defaultdict(dict)
    descartados = []
    for grupo, equipos in GRUPOS_MUNDIAL_2026.items():
        for equipo in equipos:
            tabla[grupo].setdefault(equipo, registro_base(equipo, grupo))

    partidos_vistos = set()
    for partido in data.get("resultados", []):
        resultado = parsear_resultado(partido.get("resultado"))
        local = normalizar_nombre(partido.get("local"))
        visitante = normalizar_nombre(partido.get("visitante"))
        grupo = grupo_por_equipos(local, visitante, partido.get("grupo"))
        fecha = partido.get("fecha") or ""
        if not resultado or not local or not visitante or not grupo or not fecha:
            descartado = dict(partido); descartado["motivo_descarte_clasificacion"] = "sin_resultado_valido_sin_fecha_o_equipos_de_distinto_grupo"; descartados.append(descartado); continue
        gl, gv = resultado
        clave = (grupo, tuple(sorted([local, visitante])), tuple(sorted([gl, gv])))
        if clave in partidos_vistos:
            continue
        partidos_vistos.add(clave)
        fuente = partido.get("fuente") or ""
        sumar_partido(tabla, grupo, local, visitante, gl, gv, fecha, fuente)
        sumar_partido(tabla, grupo, visitante, local, gv, gl, fecha, fuente)

    grupos = {}; equipos = {}
    for grupo, registros in sorted(tabla.items()):
        ordenados = ordenar_grupo(list(registros.values()))
        filas = []
        for reg in ordenados:
            pj_base = max(reg["pj"], 1)
            tendencias = {"forma_5_pts": sum(p.get("puntos", 0) for p in reg.get("partidos", [])[-5:]), "goles_favor_por_partido": round(reg["gf"] / pj_base, 2) if reg["pj"] else 0.0, "goles_contra_por_partido": round(reg["gc"] / pj_base, 2) if reg["pj"] else 0.0, "empates_pct": round(reg["e"] / pj_base * 100, 2) if reg["pj"] else 0.0}
            fila = {**reg, "tendencias": tendencias, **situacion_equipo(reg, ordenados)}
            filas.append(fila); equipos[normalizar_nombre(reg["equipo"])] = fila
        grupos[grupo] = {"grupo": grupo, "equipos_detectados": len(filas), "clasificacion": filas}

    return {"version": "1.2", "generado_en": ahora_iso(), "fuente": str(FUENTE.relative_to(ROOT)), "criterio": {"fase": "grupos_mundial_2026", "equipos_por_grupo": EQUIPOS_POR_GRUPO, "partidos_por_equipo": PARTIDOS_POR_EQUIPO, "clasificacion_directa": "top_2_grupo", "terceros": "pueden depender de comparativa externa; se marca depende_de_otros_resultados", "eliminacion": "solo si ni ganando todos sus partidos restantes puede alcanzar una posicion util de grupo", "deduplicacion": "grupo + pareja de equipos + marcador"}, "total_grupos": len(grupos), "total_equipos": len(equipos), "grupos": grupos, "equipos": equipos, "descartados": descartados}


def main():
    data = cargar_json(FUENTE, {"resultados": []})
    salida = construir_clasificaciones(data)
    guardar_json(SALIDA, salida)
    print(f"Clasificaciones Mundial 2026 actualizadas: {salida['total_grupos']} grupos, {salida['total_equipos']} selecciones.")


if __name__ == "__main__":
    main()
