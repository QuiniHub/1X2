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
    "celta b": "celta fortuna",
    # Auditoria 26/11 (hallazgo 100): la fuente de resultados reescribe los
    # nombres ('Real Racing Club de Santander' pasa a 'R. Santander') y, sin
    # alias, todos los partidos de Liga del Racing caian en 'liga_extranjera'.
    "r santander": "racing santander",
    "racing santander": "racing santander",
    "r zaragoza": "zaragoza",
    "r valladolid": "valladolid",
    "r sociedad b": "sociedad b",
    "r betis": "betis",
    "sp gijon": "sporting gijon",
    "sporting": "sporting gijon",
    "at madrid": "atletico madrid",
    "atl madrid": "atletico madrid",
    "celta": "celta vigo",
    "osasuna": "ca osasuna",
    "alaves": "deportivo alaves",
    "deportivo": "deportivo coruna",
    "coruna": "deportivo coruna",
    "ceuta": "ad ceuta",
    "rayo": "rayo vallecano madrid",
    "vallecano": "rayo vallecano madrid",
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
    "liga_f": {
        "modelo": "modelo_conservador_baja_calidad",
        "lectura": "Liga F (futbol femenino espanol) -el pipeline no tiene clasificacion, historico ni forma propios para esta competicion. No usar clasificacion/fuerza de Primera o Segunda masculina aunque el club comparta nombre (ej. 'Real Madrid Femenino' no es 'Real Madrid CF').",
        "datos_minimos": ["resultados", "clasificacion_liga_f", "forma"],
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


def es_equipo_liga_f(nombre_crudo, nombre_normalizado):
    """Formato real confirmado en data/jornadas/jornada_3.json (25/08/2026,
    fuente quinielafutbol.info): los partidos de Liga F llevan un sufijo
    "(F)" en el nombre crudo -ej. "Athletic Club (F)", "Real Madrid (F)"- NO
    la palabra "Femenino"/"Femeni" completa como en el nombre oficial del
    club. Se comprueba el nombre CRUDO (antes de que normalizar() quite los
    parentesis) porque es la señal mas precisa; se mantiene tambien el
    chequeo de "femenino"/"femeni" como respaldo por si otra fuente (o LAE
    directamente) lo escribe distinto."""
    if re.search(r"\(\s*f\s*\)\s*$", str(nombre_crudo or ""), re.I):
        return True
    return "femenino" in nombre_normalizado or "femeni" in nombre_normalizado


def resolver(partido, cats):
    local = normalizar(partido.get("local"))
    visitante = normalizar(partido.get("visitante"))
    if es_equipo_liga_f(partido.get("local"), local) or es_equipo_liga_f(partido.get("visitante"), visitante):
        # Se comprueba ANTES que Primera/Segunda: un nombre como "Real Madrid
        # Femenino" no debe colar por compartir "real madrid" con el club
        # masculino -son competiciones y plantillas distintas, sin datos
        # propios en este pipeline (ver Liga F 2026-27, aviso de Marc el
        # 2026-08-25 antes de que empiece la Jornada 3).
        comp, confianza, motivo = "liga_f", 0.35, "Liga F (futbol femenino) -sin fuente de datos propia, no confundir con el club masculino homonimo."
    elif local in cats["primera"] and visitante in cats["primera"]:
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


def _sin_generado_en(bloque):
    return {k: v for k, v in (bloque or {}).items() if k != "generado_en"}


def guardar_si_cambia(path, data):
    """Guarda solo si cambia algo ademas de 'generado_en' (hallazgos 113/188)."""
    anterior = cargar_json(path, None)
    if isinstance(anterior, dict) and _sin_generado_en(anterior) == _sin_generado_en(data):
        return False
    guardar_json(path, data)
    return True


def anotar_archivo(path, cats, congelar=False):
    """Anota la competicion de cada partido de un fichero.

    congelar=True: no se toca un partido que ya tiene competicion_resuelta (se
    usa para jornadas de OTRA temporada: los catalogos salen de la clasificacion
    ACTUAL y reetiquetaban, p. ej., un Girona-Elche de Primera 25/26 como
    'liga_extranjera' porque el Girona esta hoy en Segunda; hallazgo 86).

    El fichero solo se reescribe si cambia algo distinto de la marca de tiempo:
    antes 'generado_en' = ahora() hacia que se guardaran TODOS los ficheros de
    jornada y de prediccion en cada ciclo (hallazgos 113 y 188).
    """
    data = cargar_json(path, {})
    if not isinstance(data, dict) or not data:
        return None, False
    antes = json.dumps(data, ensure_ascii=False, sort_keys=True)

    def anotar(partido):
        if congelar and isinstance(partido, dict) and partido.get("competicion_resuelta"):
            return partido
        return anotar_partido(partido, cats)

    data["partidos"] = [anotar(p) for p in data.get("partidos", [])]
    if isinstance(data.get("pleno15"), dict) and data["pleno15"]:
        data["pleno15"] = anotar(data["pleno15"])
    previo = data.get("resolucion_competiciones") if isinstance(data.get("resolucion_competiciones"), dict) else {}
    bloque = {
        "objetivo": OBJETIVO,
        "resumen": dict(Counter(p.get("competicion_resuelta", "desconocida") for p in data.get("partidos", []))),
        "regla": "El motor no debe usar clasificacion espanola para selecciones, Mundial o ligas extranjeras.",
    }
    if previo and _sin_generado_en(previo) == bloque and previo.get("generado_en"):
        marca = previo["generado_en"]
    else:
        marca = ahora()
    data["resolucion_competiciones"] = {"generado_en": marca, **bloque}
    despues = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if antes != despues:
        guardar_json(path, data)
        return data, True
    return data, False


def temporada_en_curso(hoy=None):
    import cronologia_jornadas

    hoy = hoy or datetime.now(timezone.utc).date()
    return cronologia_jornadas.temporada_de_fecha(hoy)


def temporada_de_jornada(data, numero=None):
    """Temporada ('2026_2027') de un jornada_N.json por su fecha real, o None."""
    import cronologia_jornadas

    if not isinstance(data, dict):
        return None
    fecha = cronologia_jornadas.fecha_real_jornada(data)
    if fecha is None:
        return None
    try:
        numero = int(numero if numero is not None else data.get("jornada"))
    except (TypeError, ValueError):
        numero = None
    return cronologia_jornadas.temporada_de_fecha(fecha, numero)


def prediccion_anotable(path, hoy=None):
    """Un espejo de prediccion solo se anota si es de una jornada VIVA: de la
    temporada en curso, sin cerrar y sin congelar. Los espejos de jornadas
    cerradas, congelados al cierre o de la temporada pasada no se tocan."""
    import cronologia_jornadas

    data = cargar_json(path, {})
    if not isinstance(data, dict) or not data:
        return False
    if data.get("prediccion_congelada_al_cierre"):
        return False
    try:
        numero = int(data.get("jornada"))
    except (TypeError, ValueError):
        m = re.search(r"jornada_(\d+)", Path(path).stem)
        if not m:
            return False
        numero = int(m.group(1))
    jornada = cargar_json(JORNADAS / f"jornada_{numero}.json", {})
    if not isinstance(jornada, dict) or not jornada.get("partidos"):
        return False
    if cronologia_jornadas.jornada_cerrada(jornada):
        return False
    if temporada_de_jornada(jornada, numero) != temporada_en_curso(hoy):
        return False
    if data.get("partidos") and not cronologia_jornadas.misma_jornada(data, jornada):
        return False
    return True


def archivos_prediccion():
    if not PREDICCIONES.exists():
        return []
    salida = list(PREDICCIONES.glob("jornada_*.json"))
    ultima = PREDICCIONES / "ultima_prediccion.json"
    if ultima.exists():
        salida.append(ultima)
    return sorted(p for p in set(salida) if prediccion_anotable(p))


def main():
    cats = catalogos()
    jornadas = []
    cambios_jornadas = []
    actual = temporada_en_curso()
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        m = re.search(r"jornada_(\d+)", path.stem)
        numero = int(m.group(1)) if m else None
        # Los catalogos son de la temporada en curso: las jornadas de otra
        # temporada (o sin fecha) se congelan.
        otra_temporada = temporada_de_jornada(cargar_json(path, {}), numero) != actual
        data, cambiado = anotar_archivo(path, cats, congelar=otra_temporada)
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
    guardar_si_cambia(OUT_RESOLUCION, salida)
    guardar_si_cambia(OUT_OBJETIVO, {
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
