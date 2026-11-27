import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

import cronologia_jornadas


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
MEMORIA = DATA / "memoria_ia"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def buscar(tabla, nombre):
    objetivo = normalizar(nombre)
    for equipo in tabla or []:
        if normalizar(equipo.get("equipo")) == objetivo:
            return equipo
    return None


def parse_resultado(valor):
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(valor or ""))
    return bool(match)


def partidos_jugados_calendario(path):
    calendario = cargar_json(path, {})
    conteo = {}
    for jornada in calendario.get("jornadas", []):
        for partido in jornada.get("partidos", []):
            if not parse_resultado(partido.get("resultado")):
                continue
            for lado in ("local", "visitante"):
                equipo = normalizar(partido.get(lado))
                if equipo:
                    conteo[equipo] = conteo.get(equipo, 0) + 1
    return conteo


def signo_valido(valor):
    return str(valor or "").strip().upper() in {"1", "X", "2"}


def fecha_orden_jornada(data):
    """Ultima fecha ISO real de los partidos de la jornada -la unica forma
    segura de ordenar jornadas de La Quiniela, porque la numeracion se
    reinicia cada temporada (la J76 de 25/26 es numericamente mayor que la
    J4 de 26/27 pero es 4 semanas MAS VIEJA). Bug real (01/09/2026,
    auditoria): este script ordenaba por numero y llevaba semanas gritando
    en falso "la jornada activa es 76 pero la prediccion dice 4",
    manteniendo el score de salud en 65 sin que nada estuviera roto -el
    mismo patron numero-vs-fecha ya corregido 8 veces en otros sitios."""
    fechas = sorted(
        str(p.get("fecha") or "")[:10]
        for p in data.get("partidos", [])
        if re.match(r"^\d{4}-\d{2}-\d{2}", str(p.get("fecha") or ""))
    )
    return fechas[-1] if fechas else ""


def resumen_jornada(path):
    data = cargar_json(path, {})
    partidos = data.get("partidos", [])
    cerrados = sum(1 for p in partidos if signo_valido(p.get("signo_oficial")))
    pendientes = len(partidos) - cerrados
    return {
        "jornada": data.get("jornada") or int(re.search(r"(\d+)", path.stem).group(1)),
        "fecha": data.get("fecha", ""),
        "fecha_orden": fecha_orden_jornada(data),
        "partidos": len(partidos),
        "cerrados": cerrados,
        "pendientes": pendientes,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
    }


def jornadas_estado():
    resumenes = []
    for path in sorted(JORNADAS.glob("jornada_*.json"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
        resumenes.append(resumen_jornada(path))
    resumenes.sort(key=lambda r: (r.get("fecha_orden") or "", r.get("jornada") or 0))
    actual = resumenes[-1] if resumenes else None
    ultima = resumenes[-1] if resumenes else None
    return resumenes, actual, ultima


def orden_cronologico_prediccion(pred):
    """Clave de orden por FECHA real (primer partido y, si no, generado_en).

    Auditoria 26/11: el respaldo elegia la prediccion de NUMERO mas alto. En
    data/predicciones conviven jornada_1..25 (26/27) y jornada_61..76 (25/26),
    asi que con ultima_prediccion.json roto se habria usado la J76 de agosto.
    """
    fecha = cronologia_jornadas.fecha_real_jornada(pred or {})
    generado = cronologia_jornadas.parsear_fecha((pred or {}).get("generado_en"))
    return (fecha or generado or date.min, str((pred or {}).get("generado_en") or ""))


def ultima_prediccion_ilegible():
    """True si ultima_prediccion.json existe pero no se puede leer o esta vacio."""
    path = PREDICCIONES / "ultima_prediccion.json"
    return path.exists() and not cargar_json(path, {})


def ultima_prediccion():
    pred = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    if pred:
        return pred
    candidatas = []
    for path in PREDICCIONES.glob("jornada_*.json"):
        data = cargar_json(path, {})
        if data.get("jornada"):
            candidatas.append(data)
    return max(candidatas, key=orden_cronologico_prediccion, default={})


def prediccion_retenida_por_compuerta(pred):
    if not pred:
        return False
    estado = str(pred.get("estado") or "").lower()
    estado_objetivo = pred.get("estado_jornada_objetivo") or {}
    return (
        pred.get("prediccion_disponible") is False
        or pred.get("publicar_prediccion") is False
        or pred.get("prediccion_permitida") is False
        or estado_objetivo.get("en_espera") is True
        or "bloqueada" in estado
        or "aprendiendo" in estado
    )


def pj_en_calendario(calendario, nombre_equipo):
    """Partidos con resultado del equipo en el calendario, cruzando el nombre
    de forma tolerante.

    Auditoria 26/11: el cruce era por nombre normalizado EXACTO y en Segunda
    4 de 22 equipos no cruzaban ('Tenerife' vs 'CD Tenerife', 'Sabadell' vs
    'CE Sabadell', 'Eldense', 'Celta Fortuna'): para ellos pj_calendario era
    0 y la alerta critica de clasificacion congelada no podia saltar.
    Si el nombre exacto no esta, se acepta una coincidencia tolerante UNICA.
    """
    clave = normalizar(nombre_equipo)
    if clave in calendario:
        return calendario[clave]
    parecidos = [k for k in calendario if cronologia_jornadas.mismo_equipo(nombre_equipo, k)]
    if len(parecidos) == 1:
        return calendario[parecidos[0]]
    return 0


def diagnosticar_clasificacion(alertas):
    clasif = cargar_json(ROOT / "clasificaciones.json", {})
    primera = clasif.get("primera", [])
    segunda = clasif.get("segunda", [])

    if len(primera) != 20:
        alertas.append({"nivel": "critica", "titulo": "Primera incompleta", "detalle": f"Hay {len(primera)} equipos; deben ser 20."})
    if len(segunda) != 22:
        alertas.append({"nivel": "critica", "titulo": "Segunda incompleta", "detalle": f"Hay {len(segunda)} equipos; deben ser 22."})

    for liga, equipos in (("primera", primera), ("segunda", segunda)):
        puntos_previos = None
        for equipo in equipos:
            puntos = int(equipo.get("puntos", equipo.get("pts", 0)) or 0)
            if puntos_previos is not None and puntos > puntos_previos:
                alertas.append({"nivel": "alta", "titulo": f"Clasificación {liga} desordenada", "detalle": f"{equipo.get('equipo')} aparece con más puntos que el equipo anterior."})
                break
            puntos_previos = puntos

    calendarios = {
        "primera": partidos_jugados_calendario(DATA / "calendario_primera.json"),
        "segunda": partidos_jugados_calendario(DATA / "calendario_segunda.json"),
    }
    for liga, equipos in (("primera", primera), ("segunda", segunda)):
        calendario = calendarios.get(liga, {})
        for equipo in equipos:
            pj_tabla = int(equipo.get("pj", 0) or 0)
            pj_calendario = pj_en_calendario(calendario, equipo.get("equipo"))
            if pj_calendario > pj_tabla:
                alertas.append({
                    "nivel": "critica",
                    "titulo": f"Clasificacion {liga} congelada",
                    "detalle": f"{equipo.get('equipo')} tiene {pj_tabla} PJ en tabla, pero el calendario ya tiene {pj_calendario} resultados.",
                })
                break

    ahora = datetime.now(timezone.utc)
    if datetime(2026, 5, 18, tzinfo=timezone.utc) <= ahora <= datetime(2026, 7, 1, tzinfo=timezone.utc):
        leganes = buscar(segunda, "CD Leganes")
        huesca = buscar(segunda, "SD Huesca")
        if not leganes or int(leganes.get("pj", 0)) < 40 or int(leganes.get("puntos", 0)) < 43:
            alertas.append({"nivel": "critica", "titulo": "Leganés no actualizado", "detalle": "Debe aparecer con el 0-0 ante Huesca ya sumado: 40 PJ y 43 puntos."})
        if not huesca or int(huesca.get("pj", 0)) < 40 or int(huesca.get("puntos", 0)) < 37:
            alertas.append({"nivel": "critica", "titulo": "Huesca no actualizado", "detalle": "Debe aparecer con el 0-0 ante Leganés ya sumado: 40 PJ y 37 puntos."})

    return {
        "primera_equipos": len(primera),
        "segunda_equipos": len(segunda),
        "segunda_control": {
            "racing": buscar(segunda, "Real Racing Club de Santander"),
            "deportivo": buscar(segunda, "RC Deportivo de La Coruna"),
            "leganes": buscar(segunda, "CD Leganes"),
            "huesca": buscar(segunda, "SD Huesca"),
        },
    }


def diagnosticar_contexto(alertas):
    contexto = cargar_json(MEMORIA / "contexto_competitivo.json", {})
    return {
        "generado_en": contexto.get("generado_en"),
    }


def jornada_objetivo_real():
    """La jornada que el motor DEBE predecir, con la misma logica que el
    pipeline (jornada_objetivo_quiniela): no la de fecha maxima cargada, que
    daba falsos positivos ("la activa es 23 pero la prediccion dice 22") en
    cuanto se cargaba una jornada futura (auditoria 16/11/2026)."""
    return jornada_objetivo_real_con_error()[0]


def jornada_objetivo_real_con_error():
    """(numero, error). Auditoria 26/11: ante cualquier excepcion se devolvia
    0 en silencio y el control volvia a la jornada de fecha maxima (el falso
    positivo del 16/11) sin dejar rastro. Ahora el error se devuelve para
    que diagnosticar_prediccion lo publique como alerta."""
    try:
        from jornada_objetivo_quiniela import jornada_objetivo_prediccion
        return int(jornada_objetivo_prediccion() or 0), None
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def diagnosticar_prediccion(alertas, jornada_actual):
    if ultima_prediccion_ilegible():
        alertas.append({
            "nivel": "critica",
            "titulo": "ultima_prediccion.json ilegible",
            "detalle": "data/predicciones/ultima_prediccion.json existe pero esta vacio o no es JSON valido; se usa como respaldo la prediccion guardada mas reciente por fecha.",
        })
    pred = ultima_prediccion()
    retenida = prediccion_retenida_por_compuerta(pred)
    objetivo, error_objetivo = jornada_objetivo_real_con_error()
    if error_objetivo:
        alertas.append({
            "nivel": "media",
            "titulo": "Jornada objetivo no calculable",
            "detalle": (
                "No se pudo calcular la jornada objetivo del motor "
                f"({error_objetivo}); el control compara contra la jornada activa por fecha "
                "y puede dar un aviso falso de prediccion antigua."
            ),
        })
    if objetivo:
        jornada_actual = {"jornada": objetivo}
    if jornada_actual and int(pred.get("jornada", 0) or 0) != int(jornada_actual.get("jornada", 0)) and not retenida:
        alertas.append({
            "nivel": "alta",
            "titulo": "Predicción de jornada antigua",
            "detalle": f"La jornada activa es {jornada_actual.get('jornada')} pero la última predicción dice {pred.get('jornada')}.",
        })
    if len(pred.get("partidos", [])) not in (0, 14):
        alertas.append({"nivel": "alta", "titulo": "Predicción incompleta", "detalle": f"Tiene {len(pred.get('partidos', []))} partidos; deben ser 14."})
    return {
        "jornada": pred.get("jornada"),
        "generado_en": pred.get("generado_en"),
        "partidos": len(pred.get("partidos", [])),
        "resumen": pred.get("resumen", {}),
        "retenida_por_compuerta": retenida,
        "motivo_bloqueo": pred.get("motivo_bloqueo") or pred.get("mensaje"),
    }


def diagnosticar_jornadas(alertas):
    resumenes, actual, ultima = jornadas_estado()
    if not ultima:
        alertas.append({"nivel": "critica", "titulo": "No hay jornadas", "detalle": "No existe ninguna jornada de quiniela cargada."})
    elif ultima.get("partidos") != 14:
        alertas.append({"nivel": "critica", "titulo": "Última jornada incompleta", "detalle": f"La jornada {ultima.get('jornada')} tiene {ultima.get('partidos')} partidos normales."})
    return {
        "total": len(resumenes),
        "actual": actual,
        "ultima": ultima,
        "ultimas_5": resumenes[-5:],
    }


def puntuar(alertas):
    if any(a.get("nivel") == "critica" for a in alertas):
        return "critico", 0
    if any(a.get("nivel") == "alta" for a in alertas):
        return "revisar", 65
    if any(a.get("nivel") == "media" for a in alertas):
        return "operativo_con_avisos", 82
    return "operativo", 100


def actualizar_diagnostico(control):
    diagnostico = cargar_json(DATA / "diagnostico_sistema.json", {})
    diagnostico["control_calidad"] = control
    diagnostico["prediccion"] = control["prediccion"]
    if control["estado"] == "critico":
        diagnostico["estado"] = "critico_actualizacion"
        diagnostico["score_salud"] = min(int(diagnostico.get("score_salud", 100) or 100), 45)
    elif control["estado"] == "revisar":
        diagnostico["estado"] = "requiere_revision_datos"
        diagnostico["score_salud"] = min(int(diagnostico.get("score_salud", 100) or 100), 70)
    elif control["estado"] == "operativo_con_avisos":
        diagnostico["estado"] = "operativo_con_avisos"
        diagnostico["score_salud"] = min(int(diagnostico.get("score_salud", 100) or 100), 82)
    diagnostico["generado_en"] = control["generado_en"]
    diagnostico.setdefault("alertas", [])
    diagnostico["alertas"] = control["alertas"] + diagnostico["alertas"]
    guardar_json(DATA / "diagnostico_sistema.json", diagnostico)
    guardar_json(MEMORIA / "diagnostico_sistema.json", diagnostico)


def main():
    alertas = []
    jornadas = diagnosticar_jornadas(alertas)
    clasificacion = diagnosticar_clasificacion(alertas)
    contexto = diagnosticar_contexto(alertas)
    prediccion = diagnosticar_prediccion(alertas, jornadas.get("actual") or jornadas.get("ultima"))
    estado, score = puntuar(alertas)
    control = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "estado": estado,
        "score": score,
        "alertas": alertas,
        "jornadas": jornadas,
        "clasificacion": clasificacion,
        "contexto_competitivo": contexto,
        "prediccion": prediccion,
        "regla": "Si esto marca critico, no se debe confiar en el análisis hasta que se corrija la fuente o la tabla.",
    }
    guardar_json(DATA / "control_calidad_actualizacion.json", control)
    actualizar_diagnostico(control)
    print(DATA / "control_calidad_actualizacion.json")
    if alertas:
        for alerta in alertas:
            print(f"[{alerta.get('nivel')}] {alerta.get('titulo')}: {alerta.get('detalle')}")
    else:
        print("Control de calidad OK: datos críticos coherentes.")


if __name__ == "__main__":
    main()
