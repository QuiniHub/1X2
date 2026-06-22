import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except Exception:
    requests = None


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = DATA / "datos_profesionales.json"
JORNADAS = DATA / "jornadas"

SECRETS_SOPORTADOS = [
    "QUINIHUB_PRO_DATA_URL",
    "QUINIHUB_PRO_DATA_TOKEN",
    "QUINIHUB_PRO_DATA_FILE",
]


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def temporada_objetivo(fecha=None):
    fecha = fecha or datetime.now()
    inicio = fecha.year if fecha.month >= 7 else fecha.year
    return f"{inicio}/{inicio + 1}"


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
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el|futbol|balompie)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def clave_partido(local, visitante):
    return f"{normalizar(local)}|{normalizar(visitante)}"


def numero_decimal(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if numero <= 1.01:
        return None
    return round(numero, 3)


def normalizar_cuotas(cuotas):
    if not isinstance(cuotas, dict):
        return {}
    alias = {
        "1": ("1", "home", "local", "victoria_local"),
        "X": ("X", "x", "draw", "empate"),
        "2": ("2", "away", "visitante", "victoria_visitante"),
    }
    salida = {}
    for signo, claves in alias.items():
        valor = next((cuotas.get(clave) for clave in claves if clave in cuotas), None)
        decimal = numero_decimal(valor)
        if decimal is not None:
            salida[signo] = decimal

    if len(salida) == 3:
        inversas = {signo: 1.0 / salida[signo] for signo in ("1", "X", "2")}
        suma = sum(inversas.values())
        salida["probabilidades_implicitas"] = {
            signo: round(inversas[signo] / suma * 100, 1)
            for signo in ("1", "X", "2")
        }
        salida["overround"] = round(max((suma - 1.0) * 100, 0.0), 2)

    for clave in ("fuente", "proveedor", "actualizado_en", "mercado", "snapshot"):
        if cuotas.get(clave):
            salida[clave] = cuotas.get(clave)
    return salida


def normalizar_incidencia(item, tipo):
    if isinstance(item, str):
        item = {"jugador": item}
    if not isinstance(item, dict):
        return None
    impacto_defecto = {"lesiones": 1.8, "sanciones": 1.7, "dudas": 0.9}.get(tipo, 1.0)
    try:
        impacto = float(item.get("impacto", impacto_defecto))
    except (TypeError, ValueError):
        impacto = impacto_defecto
    return {
        "jugador": str(item.get("jugador") or item.get("player") or "").strip(),
        "tipo": str(item.get("tipo") or tipo).strip() or tipo,
        "estado": str(item.get("estado") or item.get("status") or "").strip(),
        "impacto": round(max(min(impacto, 5.0), 0.0), 2),
        "titular": bool(item.get("titular") or item.get("starter")),
        "fuente": item.get("fuente") or item.get("source"),
        "actualizado_en": item.get("actualizado_en") or item.get("updated_at"),
    }


def normalizar_bajas_lado(datos):
    datos = datos if isinstance(datos, dict) else {}
    salida = {"lesiones": [], "sanciones": [], "dudas": []}
    for clave in ("lesiones", "sanciones", "dudas"):
        items = datos.get(clave) or []
        if isinstance(items, (str, dict)):
            items = [items]
        salida[clave] = [
            incidencia for incidencia in (normalizar_incidencia(item, clave) for item in items)
            if incidencia
        ]
    incidencias = salida["lesiones"] + salida["sanciones"] + salida["dudas"]
    salida["impacto_total"] = round(sum(float(i.get("impacto") or 0) for i in incidencias), 2)
    salida["titulares_afectados"] = sum(1 for i in incidencias if i.get("titular"))
    for clave in ("fuente", "actualizado_en"):
        if datos.get(clave):
            salida[clave] = datos.get(clave)
    return salida


def normalizar_bajas(bajas):
    if not isinstance(bajas, dict):
        return {}
    return {
        "local": normalizar_bajas_lado(bajas.get("local") or bajas.get("home")),
        "visitante": normalizar_bajas_lado(bajas.get("visitante") or bajas.get("away")),
    }


def normalizar_alineacion_lado(datos):
    if isinstance(datos, list):
        datos = {"titulares_probables": datos}
    datos = datos if isinstance(datos, dict) else {}
    titulares = (
        datos.get("titulares_probables")
        or datos.get("probable")
        or datos.get("once")
        or datos.get("lineup")
        or []
    )
    dudas = datos.get("dudas") or datos.get("doubtful") or []
    if isinstance(titulares, str):
        titulares = [titulares]
    if isinstance(dudas, str):
        dudas = [dudas]
    try:
        confianza = float(datos.get("confianza") or datos.get("confidence") or 0)
    except (TypeError, ValueError):
        confianza = 0.0
    return {
        "confirmada": bool(datos.get("confirmada") or datos.get("confirmed")),
        "confianza": round(max(min(confianza, 1.0), 0.0), 2),
        "titulares_probables": [str(j).strip() for j in titulares if str(j).strip()][:11],
        "dudas": [str(j).strip() for j in dudas if str(j).strip()],
        "fuente": datos.get("fuente") or datos.get("source"),
        "actualizado_en": datos.get("actualizado_en") or datos.get("updated_at"),
    }


def normalizar_alineaciones(alineaciones):
    if not isinstance(alineaciones, dict):
        return {}
    return {
        "local": normalizar_alineacion_lado(alineaciones.get("local") or alineaciones.get("home")),
        "visitante": normalizar_alineacion_lado(alineaciones.get("visitante") or alineaciones.get("away")),
    }


def limpiar_dict(datos, claves):
    if not isinstance(datos, dict):
        return {}
    return {clave: datos.get(clave) for clave in claves if datos.get(clave) not in (None, "")}


def normalizar_calendario(datos):
    return limpiar_dict(
        datos,
        ["fecha", "hora", "temporada", "competicion", "jornada_liga", "sede", "fuente", "actualizado_en", "oficial"],
    )


def normalizar_clasificacion(datos):
    if not isinstance(datos, dict):
        return {}
    salida = {
        "local": limpiar_dict(datos.get("local") or {}, ["posicion", "puntos", "pj", "dg", "forma", "fuente"]),
        "visitante": limpiar_dict(datos.get("visitante") or {}, ["posicion", "puntos", "pj", "dg", "forma", "fuente"]),
    }
    for clave in ("temporada", "competicion", "fuente", "actualizado_en"):
        if datos.get(clave):
            salida[clave] = datos.get(clave)
    return salida


def normalizar_partido(item, jornada=None):
    if not isinstance(item, dict):
        return None
    local = item.get("local") or item.get("home") or item.get("home_team")
    visitante = item.get("visitante") or item.get("away") or item.get("away_team")
    if not local or not visitante:
        return None
    calendario = normalizar_calendario(item.get("calendario") or item)
    partido = {
        "num": item.get("num") or item.get("numero"),
        "jornada": int(item.get("jornada") or jornada or 0),
        "local": str(local).strip(),
        "visitante": str(visitante).strip(),
        "partido_clave": clave_partido(local, visitante),
        "competicion": item.get("competicion") or calendario.get("competicion"),
        "calendario": calendario,
        "cuotas": normalizar_cuotas(item.get("cuotas") or item.get("odds") or {}),
        "bajas": normalizar_bajas(item.get("bajas") or item.get("injuries") or {}),
        "alineaciones": normalizar_alineaciones(item.get("alineaciones") or item.get("lineups") or {}),
        "clasificacion": normalizar_clasificacion(item.get("clasificacion") or item.get("standing") or {}),
    }
    partido["capas_disponibles"] = capas_disponibles(partido)
    return partido


def capas_disponibles(partido):
    cuotas = partido.get("cuotas") or {}
    bajas = partido.get("bajas") or {}
    alineaciones = partido.get("alineaciones") or {}
    clasificacion = partido.get("clasificacion") or {}
    calendario = partido.get("calendario") or {}
    fuente_calendario = str(calendario.get("fuente") or "").lower()
    calendario_marcado_oficial = calendario.get("oficial") is True or "oficial" in fuente_calendario
    return {
        "cuotas": all(signo in cuotas for signo in ("1", "X", "2")),
        "bajas_estructuradas": any(
            (bajas.get(lado) or {}).get("impacto_total", 0) > 0
            for lado in ("local", "visitante")
        ),
        "alineaciones_probables": any(
            (alineaciones.get(lado) or {}).get("titulares_probables")
            for lado in ("local", "visitante")
        ),
        "calendario_oficial": bool(
            calendario_marcado_oficial and calendario.get("fuente") and (calendario.get("fecha") or calendario.get("hora"))
        ),
        "clasificacion_oficial": bool(clasificacion.get("local") or clasificacion.get("visitante")),
    }


def iterar_partidos_payload(payload):
    jornadas = payload.get("jornadas")
    if isinstance(jornadas, dict):
        for jornada, data in jornadas.items():
            for partido in (data or {}).get("partidos", []):
                yield jornada, partido
    elif isinstance(jornadas, list):
        for data in jornadas:
            jornada = (data or {}).get("jornada")
            for partido in (data or {}).get("partidos", []):
                yield jornada, partido
    for partido in payload.get("partidos", []) if isinstance(payload.get("partidos"), list) else []:
        yield partido.get("jornada"), partido


def resumen_partidos(jornadas):
    contadores = {
        "partidos_enriquecidos": 0,
        "cuotas": 0,
        "bajas_estructuradas": 0,
        "alineaciones_probables": 0,
        "calendario_oficial": 0,
        "clasificacion_oficial": 0,
    }
    for jornada in jornadas.values():
        for partido in jornada.get("partidos", []):
            capas = partido.get("capas_disponibles") or {}
            if any(capas.values()):
                contadores["partidos_enriquecidos"] += 1
            for clave in list(contadores):
                if clave != "partidos_enriquecidos" and capas.get(clave):
                    contadores[clave] += 1
    return contadores


def normalizar_payload(payload, origen="externo"):
    payload = payload if isinstance(payload, dict) else {}
    jornadas = {}
    for jornada, raw_partido in iterar_partidos_payload(payload):
        partido = normalizar_partido(raw_partido, jornada=jornada)
        if not partido:
            continue
        clave = str(partido.get("jornada") or jornada or "sin_jornada")
        jornadas.setdefault(clave, {"jornada": partido.get("jornada") or jornada, "partidos": []})
        jornadas[clave]["partidos"].append(partido)

    resumen = resumen_partidos(jornadas)
    estado = "operativo" if resumen["partidos_enriquecidos"] else "sin_datos_profesionales"
    return {
        "version": "1.0",
        "generado_en": payload.get("generado_en") or ahora_iso(),
        "temporada_objetivo": payload.get("temporada_objetivo") or temporada_objetivo(),
        "estado_global": payload.get("estado_global") or estado,
        "origen": origen,
        "proveedores": payload.get("proveedores") or payload.get("fuentes") or {},
        "jornadas": jornadas,
        "resumen": resumen,
        "configuracion": configuracion_publica(),
    }


def configuracion_publica():
    return {
        "secrets_soportados": SECRETS_SOPORTADOS,
        "url_configurada": bool(os.getenv("QUINIHUB_PRO_DATA_URL")),
        "token_configurado": bool(os.getenv("QUINIHUB_PRO_DATA_TOKEN")),
        "archivo_local_configurado": bool(os.getenv("QUINIHUB_PRO_DATA_FILE")),
        "formato": "JSON normalizado con partidos, cuotas 1X2, bajas, alineaciones, calendario y clasificacion.",
    }


def crear_esqueleto_sin_secretos(root=ROOT):
    return {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "temporada_objetivo": temporada_objetivo(),
        "estado_global": "pendiente_secrets",
        "origen": "esqueleto_local",
        "proveedores": {},
        "jornadas": {},
        "resumen": {
            "partidos_enriquecidos": 0,
            "cuotas": 0,
            "bajas_estructuradas": 0,
            "alineaciones_probables": 0,
            "calendario_oficial": 0,
            "clasificacion_oficial": 0,
        },
        "configuracion": configuracion_publica(),
        "siguiente_paso": (
            "Configurar QUINIHUB_PRO_DATA_URL y QUINIHUB_PRO_DATA_TOKEN en GitHub Secrets "
            "para inyectar cuotas, bajas, alineaciones y datos oficiales 2026/2027."
        ),
    }


def buscar_partido(datos, jornada, partido):
    if not isinstance(datos, dict):
        return None
    clave = clave_partido(partido.get("local"), partido.get("visitante"))
    jornadas = datos.get("jornadas") or {}
    candidatos_jornada = []
    if jornada is not None and str(jornada) in jornadas:
        candidatos_jornada.extend((jornadas[str(jornada)] or {}).get("partidos", []))
    for data_jornada in jornadas.values():
        candidatos_jornada.extend((data_jornada or {}).get("partidos", []))
    for candidato in candidatos_jornada:
        if candidato.get("partido_clave") == clave:
            return candidato
    return None


def leer_payload_externo():
    archivo = os.getenv("QUINIHUB_PRO_DATA_FILE")
    if archivo:
        return cargar_json(archivo, {})

    url = os.getenv("QUINIHUB_PRO_DATA_URL")
    if not url:
        return None
    if requests is None:
        raise RuntimeError("requests no esta disponible para leer QUINIHUB_PRO_DATA_URL")
    headers = {"User-Agent": "QuiniHub/1X2 datos-profesionales"}
    token = os.getenv("QUINIHUB_PRO_DATA_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    respuesta = requests.get(url, headers=headers, timeout=30)
    respuesta.raise_for_status()
    return respuesta.json()


def _sin_tiempos_volatiles(data):
    if isinstance(data, dict):
        salida = {}
        for clave, valor in data.items():
            if clave == "generado_en":
                continue
            salida[clave] = _sin_tiempos_volatiles(valor)
        return salida
    if isinstance(data, list):
        return [_sin_tiempos_volatiles(item) for item in data]
    return data


def guardar_si_cambia(path, data):
    anterior = cargar_json(path, {})
    if anterior and _sin_tiempos_volatiles(anterior) == _sin_tiempos_volatiles(data):
        return False
    guardar_json(path, data)
    return True
