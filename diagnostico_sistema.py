import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
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


def parse_fecha(valor):
    if not valor:
        return None
    texto = str(valor).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def edad_horas(valor):
    fecha = parse_fecha(valor)
    if not fecha:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - fecha).total_seconds() / 3600, 2)


def signo_valido(valor):
    return str(valor or "").strip().upper() in {"1", "X", "2"}


def extraer_signos_jugada(valor):
    if isinstance(valor, list):
        return [str(s).strip().upper() for s in valor if str(s).strip()]
    texto = str(valor or "").strip().upper()
    if not texto or texto in {"NO VALIDADA", "NO JUGADA", "PENDIENTE"}:
        return []
    partes = [p for p in texto.split() if p]
    if len(partes) > 1:
        return partes
    if re.fullmatch(r"[12X]{14}", texto):
        return list(texto)
    return []


def jugada_historial_valida(jornada):
    signos = extraer_signos_jugada(jornada.get("signos") or jornada.get("nuestra_quiniela"))
    return str(jornada.get("jornada") or "").isdigit() and len(signos) >= 14


def pleno15_cerrado(pleno):
    resultado = str((pleno or {}).get("resultado") or (pleno or {}).get("signo_oficial") or "").strip()
    if not resultado or resultado.lower() == "pendiente":
        return False
    return bool(re.match(r"^\d+\s*-\s*\d+$", resultado))


def jornada_numero(path, data):
    numero = data.get("jornada")
    if isinstance(numero, int):
        return numero
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else 0


def resumen_jornada(path):
    data = cargar_json(path, {})
    partidos = data.get("partidos", [])
    cerrados = [p for p in partidos if signo_valido(p.get("signo_oficial"))]
    pendientes = [p for p in partidos if not signo_valido(p.get("signo_oficial"))]
    actualizados = [p.get("actualizado_en") for p in partidos if p.get("actualizado_en")]
    pleno = data.get("pleno15") or {}
    pleno_cerrado = pleno15_cerrado(pleno)
    return {
        "jornada": jornada_numero(path, data),
        "fecha": data.get("fecha") or "",
        "estado": data.get("estado") or ("cerrada" if len(cerrados) == len(partidos) and partidos else "abierta"),
        "partidos": len(partidos),
        "cerrados": len(cerrados),
        "pendientes": len(pendientes),
        "pendientes_totales_con_pleno15": len(pendientes) + (0 if pleno_cerrado or not pleno else 1),
        "pleno15_cerrado": pleno_cerrado,
        "ultima_actualizacion_partido": max(actualizados) if actualizados else "",
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
    }


def diagnosticar_jornadas(alertas):
    res = []
    for path in sorted(JORNADAS.glob("jornada_*.json"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
        res.append(resumen_jornada(path))
    abiertas = [j for j in res if j["pendientes"] > 0]
    en_juego = [j for j in abiertas if j["cerrados"] > 0]
    jornada_actual = max(en_juego, key=lambda j: (j["jornada"], j["cerrados"]), default=None)
    if not jornada_actual:
        jornada_actual = max(abiertas, key=lambda j: j["jornada"], default=None)
    proxima = max(abiertas, key=lambda j: j["jornada"], default=None)

    if jornada_actual and jornada_actual["pendientes"] > 0:
        pleno_txt = " y el Pleno al 15 pendiente" if not jornada_actual.get("pleno15_cerrado") else ""
        alertas.append({
            "nivel": "media",
            "titulo": "Jornada actual incompleta",
            "detalle": f"La jornada {jornada_actual['jornada']} tiene {jornada_actual['cerrados']} partidos cerrados, {jornada_actual['pendientes']} partidos normales pendientes{pleno_txt}.",
            "accion": "Mantener lectura provisional y no cerrar aprendizaje fuerte hasta completar todos los resultados.",
        })

    return {
        "total_jornadas": len(res),
        "jornada_actual": jornada_actual,
        "proxima_jornada": proxima,
        "ultimas": res[-5:],
    }


def diagnosticar_memoria(alertas):
    jugadas = cargar_json(DATA / "quinielas_jugadas.json", {"jugadas": []}).get("jugadas", [])
    historial = cargar_json(DATA / "historial_quinielas.json", {"jornadas": []}).get("jornadas", [])
    jugadas_validas = [j for j in jugadas if jugada_historial_valida(j)]
    historico_validadas = [j for j in historial if jugada_historial_valida(j)]
    signos_en_jornadas = 0
    jornadas_con_signos = 0
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        jugados = [
            p for p in data.get("partidos", [])
            if str(p.get("signo_nuestro") or "").strip()
            and "NO JUGADA" not in str(p.get("signo_nuestro") or "").upper()
        ]
        if jugados:
            jornadas_con_signos += 1
            signos_en_jornadas += len(jugados)

    persistidas = len(jugadas_validas) + len(historico_validadas) + jornadas_con_signos
    if persistidas == 0:
        alertas.append({
            "nivel": "alta",
            "titulo": "No hay boletos nuestros en memoria real",
            "detalle": "La web puede tener validaciones guardadas solo en el navegador, pero no hay jugadas persistidas ni en data/quinielas_jugadas.json ni en data/historial_quinielas.json.",
            "accion": "Persistir las quinielas jugadas en Quinielas o en Historial para que la IA aprenda de aciertos, fallos, dobles, triples, Elige 8 y Pleno al 15.",
        })

    return {
        "jugadas_persistidas_json": len(jugadas_validas),
        "jornadas_validadas_historial": len(historico_validadas),
        "jornadas_memoria_real_total": persistidas,
        "jornadas_con_signo_nuestro": jornadas_con_signos,
        "signos_nuestros_en_jornadas": signos_en_jornadas,
        "estado": "sin_memoria_propia" if persistidas == 0 else "memoria_propia_disponible",
        "fuentes_validas": [
            "data/quinielas_jugadas.json",
            "data/historial_quinielas.json",
            "data/jornadas/jornada_*.json signo_nuestro",
        ],
        "nota": "Las validaciones guardadas solo en localStorage del navegador no son visibles para GitHub Actions hasta pasarlas a Quinielas o Historial persistente.",
    }


def top_prob(partido):
    probs = partido.get("probabilidades") or {}
    orden = sorted(((k, float(v)) for k, v in probs.items()), key=lambda x: x[1], reverse=True)
    return orden[0] if orden else ("", 0.0)


def margen(partido):
    probs = sorted([float(v) for v in (partido.get("probabilidades") or {}).values()], reverse=True)
    if len(probs) < 2:
        return 0.0
    return round(probs[0] - probs[1], 2)


def diagnosticar_prediccion(alertas):
    pred = cargar_json(DATA / "predicciones" / "jornada_63.json", {})
    if not pred:
        pred = cargar_json(DATA / "predicciones" / "ultima_prediccion.json", {})
    partidos = pred.get("partidos", [])
    resumen = pred.get("resumen") or {}
    fijos = resumen.get("fijos", 0)
    dobles = resumen.get("dobles", 0)
    triples = resumen.get("triples", 0)

    riesgos = []
    for p in partidos:
        signo, prob = top_prob(p)
        x_prob = float((p.get("probabilidades") or {}).get("X", 0))
        inc = float(p.get("incertidumbre") or 0)
        if inc >= 110 or prob < 42 or x_prob >= 33 or margen(p) < 8:
            riesgos.append({
                "num": p.get("num"),
                "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
                "signo": p.get("signo_final") or signo,
                "probabilidad_top": prob,
                "margen": margen(p),
                "incertidumbre": inc,
                "motivo": "Partido con margen corto, empate alto o incertidumbre elevada.",
            })

    if partidos and fijos >= 14 and dobles == 0 and triples == 0:
        alertas.append({
            "nivel": "media",
            "titulo": "Prediccion demasiado rigida",
            "detalle": "La prediccion actual sale con 14 fijos. Eso no refleja bien la incertidumbre real de una quiniela.",
            "accion": "Usar dobles/triples en los partidos de mayor incertidumbre antes de validar.",
        })
    if len(riesgos) >= 5:
        alertas.append({
            "nivel": "media",
            "titulo": "Jornada con azar alto",
            "detalle": f"Hay {len(riesgos)} partidos con riesgo de sorpresa, empate o margen corto.",
            "accion": "Marcar trampas y no usar esos partidos como Elige 8 salvo que cambie el contexto.",
        })

    return {
        "jornada": pred.get("jornada"),
        "generado_en": pred.get("generado_en"),
        "configuracion": pred.get("configuracion") or {},
        "resumen": resumen,
        "partidos": len(partidos),
        "riesgo_azar": "alto" if len(riesgos) >= 5 else "medio" if len(riesgos) >= 3 else "bajo",
        "partidos_trampa": sorted(riesgos, key=lambda p: p["incertidumbre"], reverse=True)[:8],
    }


def diagnosticar_clasificaciones(alertas):
    clasif = cargar_json(ROOT / "clasificaciones.json", {})
    salida = {}
    for liga, total_partidos in (("primera", 38), ("segunda", 42)):
        equipos = clasif.get(liga, [])
        duplicados = []
        vistos = set()
        desorden = []
        pj_excesivos = []
        puntos_anteriores = None
        for e in equipos:
            nombre = str(e.get("equipo") or "").strip()
            clave = nombre.lower()
            if clave in vistos:
                duplicados.append(nombre)
            vistos.add(clave)
            puntos = int(e.get("puntos", e.get("pts", 0)) or 0)
            if puntos_anteriores is not None and puntos > puntos_anteriores:
                desorden.append(nombre)
            puntos_anteriores = puntos
            if int(e.get("pj") or 0) > total_partidos:
                pj_excesivos.append(nombre)
        if len(equipos) not in (20, 22):
            alertas.append({
                "nivel": "alta",
                "titulo": f"Numero raro de equipos en {liga}",
                "detalle": f"Hay {len(equipos)} equipos cargados.",
                "accion": "Revisar fuente de clasificacion antes de recalcular memoria.",
            })
        if duplicados or desorden or pj_excesivos:
            alertas.append({
                "nivel": "alta",
                "titulo": f"Clasificacion {liga} necesita revision",
                "detalle": "Hay duplicados, orden de puntos incoherente o partidos jugados excesivos.",
                "accion": "Bloquear prediccion fuerte hasta corregir la tabla.",
            })
        salida[liga] = {
            "equipos": len(equipos),
            "duplicados": duplicados,
            "posibles_desordenes": desorden[:5],
            "pj_excesivos": pj_excesivos,
            "top_3": [
                {
                    "posicion": e.get("posicion"),
                    "equipo": e.get("equipo"),
                    "puntos": e.get("puntos", e.get("pts")),
                }
                for e in equipos[:3]
            ],
        }
    return salida


def diagnosticar_fuentes(alertas):
    memoria = cargar_json(MEMORIA / "aprendizaje_global.json", {})
    estado = cargar_json(MEMORIA / "estado_vivo.json", {})
    contexto = cargar_json(DATA / "contexto_equipos.json", {})
    edad_memoria = edad_horas(memoria.get("generado_en"))
    edad_estado = edad_horas(estado.get("generado_en"))
    edad_contexto = edad_horas(contexto.get("generado_en"))

    if edad_contexto is not None and edad_contexto > float(contexto.get("ttl_horas") or 6) + 1:
        alertas.append({
            "nivel": "media",
            "titulo": "Noticias de equipos algo antiguas",
            "detalle": f"El contexto de equipos tiene {edad_contexto} horas.",
            "accion": "Refrescar noticias antes de valorar bajas, sanciones o altas.",
        })

    modulos = {
        "resultados_directo": {
            "estado": "conectado_fragil",
            "detalle": "Lee quiniela15.com y dondeverlo.es; no es API oficial con consenso.",
        },
        "noticias_equipos": {
            "estado": "conectado_rss",
            "detalle": "Google News RSS por titulares; util para alertas, no garantiza partes medicos oficiales.",
        },
        "cuotas": {"estado": "pendiente_api", "detalle": "No hay cuotas reales integradas en el motor activo."},
        "xg": {"estado": "pendiente_fuente", "detalle": "El archivo xG es plantilla, no dato vivo."},
        "lesiones_sanciones_alineaciones": {
            "estado": "parcial",
            "detalle": "Se infiere por noticias; falta API o fuente oficial estructurada.",
        },
        "arbitros_clima": {"estado": "pendiente", "detalle": "No influye todavia en probabilidades reales."},
        "porcentajes_apostados": {"estado": "pendiente", "detalle": "No hay consenso de apostantes integrado."},
    }

    alertas.append({
        "nivel": "media",
        "titulo": "Fuentes deportivas incompletas",
        "detalle": "Cuotas, xG, alineaciones, sanciones oficiales, arbitros y porcentajes apostados aun no son datos vivos completos.",
        "accion": "Conectar APIs o datasets autorizados para subir calidad predictiva.",
    })

    return {
        "memoria_horas": edad_memoria,
        "estado_vivo_horas": edad_estado,
        "contexto_equipos_horas": edad_contexto,
        "modulos": modulos,
    }


def puntuar(alertas):
    penalizacion = {"critica": 25, "alta": 14, "media": 7, "baja": 3}
    score = 100 - sum(penalizacion.get(a.get("nivel"), 5) for a in alertas)
    score = max(score, 0)
    if score >= 82:
        estado = "operativo_con_alertas"
    elif score >= 65:
        estado = "necesita_mejoras"
    else:
        estado = "critico_para_prediccion_fuerte"
    return score, estado


def main():
    alertas = []
    jornadas = diagnosticar_jornadas(alertas)
    memoria = diagnosticar_memoria(alertas)
    prediccion = diagnosticar_prediccion(alertas)
    clasificaciones = diagnosticar_clasificaciones(alertas)
    fuentes = diagnosticar_fuentes(alertas)
    score, estado = puntuar(alertas)

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "estado": estado,
        "score_salud": score,
        "lectura": (
            "Sistema util para prediccion probabilistica y aprendizaje, "
            "pero no perfecto: debe controlar azar, fuentes incompletas y memoria propia persistente."
        ),
        "jornadas": jornadas,
        "memoria_quinielas": memoria,
        "prediccion": prediccion,
        "clasificaciones": clasificaciones,
        "fuentes": fuentes,
        "alertas": alertas,
        "acciones_prioritarias": [
            "Persistir quinielas jugadas nuestras en data/quinielas_jugadas.json o data/historial_quinielas.json.",
            "No validar 14 fijos si el diagnostico detecta varios partidos trampa.",
            "Conectar fuente fiable de resultados/clasificaciones o usar consenso de fuentes.",
            "Integrar cuotas, xG, alineaciones y sanciones como datos estructurados.",
            "Backtesting: guardar prediccion previa al cierre y comparar contra resultado real.",
        ],
    }

    guardar_json(DATA / "diagnostico_sistema.json", salida)
    guardar_json(MEMORIA / "diagnostico_sistema.json", salida)
    print(DATA / "diagnostico_sistema.json")


if __name__ == "__main__":
    main()
