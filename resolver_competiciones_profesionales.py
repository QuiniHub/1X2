import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
MEMORIA = DATA / "memoria_ia"

OUT_RESOLUCION = MEMORIA / "resolucion_competiciones.json"
OUT_OBJETIVO = MEMORIA / "objetivo_motor_autonomo.json"

OBJETIVO = "motor autonomo con datos profesionales, aprendizaje real y probabilidades calibradas"

SELECCIONES = {
    "alemania", "argelia", "argentina", "australia", "belgica", "bosnia", "brasil",
    "canada", "colombia", "corea del sur", "costa de marfil", "croacia", "curazao",
    "ecuador", "escocia", "espana", "estados unidos", "francia", "ghana", "haiti",
    "inglaterra", "japon", "jordania", "marruecos", "mexico", "noruega", "panama",
    "portugal", "qatar", "rd congo", "republica checa", "senegal", "sudafrica",
    "suiza", "uzbekistan",
}

ALIAS = {
    "mexico": "mexico",
    "rep corea": "corea del sur",
    "republica corea": "corea del sur",
    "costa marfil": "costa de marfil",
    "costa de marfil": "costa de marfil",
    "rep checa": "republica checa",
    "rd congo": "rd congo",
    "r d congo": "rd congo",
    "r vallecano": "rayo vallecano madrid",
    "rayo vallecano": "rayo vallecano madrid",
    "r oviedo": "oviedo",
    "r madrid": "madrid",
    "r sociedad": "sociedad",
    "betis": "betis",
    "espanyol": "espanyol barcelona",
    "dep coruna": "deportivo coruna",
    "deportivo la coruna": "deportivo coruna",
}

REQUISITOS = {
    "mundial_2026": {
        "modelo": "modelo_selecciones_mundial_2026",
        "lectura": "Usar memoria de selecciones/Mundial, sede neutral, grupo/fase y fuerza internacional.",
        "datos_minimos": ["resultados", "ranking_elo", "forma_seleccion", "lesiones", "alineaciones", "contexto_grupo"],
    },
    "selecciones": {
        "modelo": "modelo_selecciones_generico",
        "lectura": "Usar fuerza internacional y no clasificacion de liga espanola.",
        "datos_minimos": ["resultados", "ranking_elo", "forma_seleccion", "lesiones", "alineaciones"],
    },
    "primera_division": {
        "modelo": "modelo_liga_espana_primera",
        "lectura": "Usar clasificacion de Primera, forma, casa/fuera, objetivos y bajas.",
        "datos_minimos": ["resultados", "clasificacion", "forma", "casa_fuera", "lesiones", "alineaciones", "xg"],
    },
    "segunda_division": {
        "modelo": "modelo_liga_espana_segunda",
        "lectura": "Usar ascenso, playoff, descenso, dinamica y calidad propia de Segunda.",
        "datos_minimos": ["resultados", "clasificacion", "forma", "casa_fuera", "lesiones", "alineaciones", "xg"],
    },
    "liga_extranjera": {
        "modelo": "modelo_liga_extranjera",
        "lectura": "No usar modelo espanol; exigir clasificacion y datos de la liga real.",
        "datos_minimos": ["resultados", "clasificacion_liga", "forma", "ranking_elo", "lesiones"],
    },
    "desconocida": {
        "modelo": "modelo_conservador_baja_calidad",
        "lectura": "Competicion no resuelta; bajar confianza y pedir fuentes especificas.",
        "datos_minimos": ["resultados", "fuente_competicion", "ranking_elo"],
    },
}


def ahora():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar(nombre):
    texto = str(nombre or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el|futbol|balompie)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
    return ALIAS.get(texto, texto)


def equipos_clasificacion(data, clave):
    salida = set()
    for item in data.get(clave, []) if isinstance(data, dict) else []:
        nombre = normalizar(item.get("equipo") or item.get("nombre") or item.get("team"))
        if nombre:
            salida.add(nombre)
    return salida


def catalogos():
    clasificaciones = cargar_json(ROOT / "clasificaciones.json", {})
    mundial = cargar_json(MEMORIA / "mundial_2026_forma.json", {"equipos": {}})
    equipos_mundial = {normalizar(nombre) for nombre in (mundial.get("equipos") or {}).keys() if nombre}
    selecciones = {normalizar(nombre) for nombre in SELECCIONES} | equipos_mundial
    return {
        "primera": equipos_clasificacion(clasificaciones, "primera"),
        "segunda": equipos_clasificacion(clasificaciones, "segunda"),
        "mundial": equipos_mundial,
        "selecciones": selecciones,
    }


def resolver(partido, cats):
    local = normalizar(partido.get("local"))
    visitante = normalizar(partido.get("visitante"))
    if local in cats["primera"] and visitante in cats["primera"]:
        comp, confianza, motivo = "primera_division", 0.94, "Ambos equipos estan en Primera."
    elif local in cats["segunda"] and visitante in cats["segunda"]:
        comp, confianza, motivo = "segunda_division", 0.94, "Ambos equipos estan en Segunda."
    elif local in cats["mundial"] and visitante in cats["mundial"]:
        comp, confianza, motivo = "mundial_2026", 0.90, "Ambos equipos tienen memoria Mundial 2026."
    elif local in cats["selecciones"] and visitante in cats["selecciones"]:
        comp, confianza, motivo = "selecciones", 0.82, "Ambos nombres son selecciones."
    elif local and visitante:
        comp, confianza, motivo = "liga_extranjera", 0.62, "No encaja en Primera/Segunda ni en Mundial; requiere liga especifica."
    else:
        comp, confianza, motivo = "desconocida", 0.40, "Falta informacion de equipos."
    req = REQUISITOS[comp]
    return {
        "competicion": comp,
        "modelo_recomendado": req["modelo"],
        "confianza": confianza,
        "motivo": motivo,
        "lectura": req["lectura"],
        "datos_minimos": req["datos_minimos"],
        "equipos_normalizados": {"local": local, "visitante": visitante},
    }


def anotar_partido(partido, cats):
    salida = dict(partido)
    info = resolver(partido, cats)
    salida["competicion_resuelta"] = info["competicion"]
    salida["modelo_datos_recomendado"] = info["modelo_recomendado"]
    salida["resolucion_competicion"] = info
    return salida


def anotar_archivo(path, cats):
    data = cargar_json(path, {})
    if not isinstance(data, dict) or not data:
        return None, False
    antes = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data["partidos"] = [anotar_partido(p, cats) for p in data.get("partidos", [])]
    if isinstance(data.get("pleno15"), dict) and data["pleno15"]:
        data["pleno15"] = anotar_partido(data["pleno15"], cats)
    data["resolucion_competiciones"] = {
        "generado_en": ahora(),
        "objetivo": OBJETIVO,
        "resumen": dict(Counter(p.get("competicion_resuelta", "desconocida") for p in data.get("partidos", []))),
        "regla": "El motor no debe usar clasificacion espanola para selecciones, Mundial o ligas extranjeras.",
    }
    despues = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if antes != despues:
        guardar_json(path, data)
        return data, True
    return data, False


def archivos_prediccion():
    if not PREDICCIONES.exists():
        return []
    salida = list(PREDICCIONES.glob("jornada_*.json"))
    ultima = PREDICCIONES / "ultima_prediccion.json"
    if ultima.exists():
        salida.append(ultima)
    return sorted(set(salida))


def main():
    cats = catalogos()
    jornadas = []
    cambios_jornadas = []
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data, cambiado = anotar_archivo(path, cats)
        if not data:
            continue
        jornadas.append({
            "jornada": data.get("jornada") or path.stem,
            "fecha": data.get("fecha", ""),
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "competiciones": data.get("resolucion_competiciones", {}).get("resumen", {}),
        })
        if cambiado:
            cambios_jornadas.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    cambios_predicciones = []
    for path in archivos_prediccion():
        _, cambiado = anotar_archivo(path, cats)
        if cambiado:
            cambios_predicciones.append(str(path.relative_to(ROOT)).replace("\\", "/"))

    salida = {
        "version": "1.0",
        "generado_en": ahora(),
        "objetivo": OBJETIVO,
        "catalogos": {
            "primera": len(cats["primera"]),
            "segunda": len(cats["segunda"]),
            "mundial": len(cats["mundial"]),
            "selecciones": len(cats["selecciones"]),
        },
        "requisitos_por_competicion": REQUISITOS,
        "jornadas": jornadas,
        "archivos_anotados": {"jornadas": cambios_jornadas, "predicciones": cambios_predicciones},
    }
    guardar_json(OUT_RESOLUCION, salida)
    guardar_json(OUT_OBJETIVO, {
        "version": "1.0",
        "generado_en": ahora(),
        "objetivo": OBJETIVO,
        "reglas": [
            "No desbloquear la jornada siguiente hasta cerrar y aprender la actual.",
            "Resolver la competicion antes de elegir modelo predictivo.",
            "Exigir datos profesionales minimos por competicion.",
            "Calibrar probabilidades con predicciones pre-cierre y resultados oficiales.",
        ],
    })
    print(f"Resolver profesional: {len(jornadas)} jornadas analizadas, {len(cambios_predicciones)} predicciones anotadas.")


if __name__ == "__main__":
    main()
