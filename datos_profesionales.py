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

API_FOOTBALL_LIGAS_DEFECTO = {
    "140": "LaLiga EA Sports",
    "141": "LaLiga Hypermotion",
    "1": "FIFA World Cup",
}

API_FOOTBALL_ALIAS = {
    "alemania": "germany",
    "argelia": "algeria",
    "argentina": "argentina",
    "australia": "australia",
    "belgica": "belgium",
    "brasil": "brazil",
    "canada": "canada",
    "colombia": "colombia",
    "corea del sur": "south korea",
    "costa de marfil": "ivory coast",
    "croacia": "croatia",
    "ecuador": "ecuador",
    "escocia": "scotland",
    "espana": "spain",
    "eeuu": "united states",
    "estados unidos": "united states",
    "francia": "france",
    "ghana": "ghana",
    "inglaterra": "england",
    "japon": "japan",
    "jordania": "jordan",
    "marruecos": "morocco",
    "mexico": "mexico",
    "noruega": "norway",
    "paises bajos": "netherlands",
    "paraguay": "paraguay",
    "portugal": "portugal",
    "senegal": "senegal",
    "suecia": "sweden",
    "suiza": "switzerland",
    "tunez": "tunisia",
    "turquia": "turkey",
    "uzbekistan": "uzbekistan",
    "usa": "united states",
    "united states": "united states",
    "netherlands": "netherlands",
}


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def temporada_objetivo(fecha=None):
    fecha = fecha or datetime.now()
    inicio = fecha.year if fecha.month >= 7 else fecha.year
    return f"{inicio}/{inicio + 1}"


def temporada_api_football(fecha=None):
    valor = os.getenv("QUINIHUB_PRO_DATA_SEASON")
    if valor:
        try:
            return int(valor)
        except ValueError:
            pass
    fecha = fecha or datetime.now()
    return fecha.year if fecha.month >= 6 else fecha.year - 1


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


def normalizar_api_nombre(texto):
    clave = normalizar(texto)
    return API_FOOTBALL_ALIAS.get(clave, clave)


def puntuacion_nombre(candidato, objetivo):
    candidato = normalizar_api_nombre(candidato)
    objetivo = normalizar_api_nombre(objetivo)
    if not candidato or not objetivo:
        return 0
    if candidato == objetivo:
        return 1000
    if candidato in objetivo or objetivo in candidato:
        return 700
    tokens_candidato = set(candidato.split())
    tokens_objetivo = set(objetivo.split())
    comunes = tokens_candidato & tokens_objetivo
    if not comunes:
        return 0
    cobertura = len(comunes) / max(len(tokens_objetivo), 1)
    return int(200 + cobertura * 400 + len(comunes) * 40)


def clave_partido(local, visitante):
    return f"{normalizar(local)}|{normalizar(visitante)}"


def url_es_api_football(url):
    proveedor = str(os.getenv("QUINIHUB_PRO_DATA_PROVIDER") or "").lower().replace("-", "_")
    if proveedor in {"api_football", "api_sports", "apisports"}:
        return True
    texto = str(url or "").lower()
    return any(fragmento in texto for fragmento in ("api-football", "api-sports", "football.api-sports.io"))


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
        "proveedores_directos_soportados": ["api_football"],
        "api_football_url_detectada": url_es_api_football(os.getenv("QUINIHUB_PRO_DATA_URL")),
        "url_configurada": bool(os.getenv("QUINIHUB_PRO_DATA_URL")),
        "token_configurado": bool(os.getenv("QUINIHUB_PRO_DATA_TOKEN")),
        "archivo_local_configurado": bool(os.getenv("QUINIHUB_PRO_DATA_FILE")),
        "formato": (
            "JSON normalizado o API-Football/API-SPORTS con fixtures, odds, injuries, "
            "fixtures/lineups y standings."
        ),
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


def ligas_api_football():
    valor = os.getenv("QUINIHUB_PRO_DATA_LEAGUES")
    if not valor:
        return API_FOOTBALL_LIGAS_DEFECTO
    ligas = {}
    for item in valor.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            liga_id, nombre = item.split(":", 1)
            ligas[liga_id.strip()] = nombre.strip() or liga_id.strip()
        else:
            ligas[item] = API_FOOTBALL_LIGAS_DEFECTO.get(item, item)
    return ligas or API_FOOTBALL_LIGAS_DEFECTO


def limite_jornadas_profesionales():
    try:
        return max(min(int(os.getenv("QUINIHUB_PRO_DATA_MAX_JORNADAS") or 2), 4), 1)
    except ValueError:
        return 2


def seleccionar_jornadas_objetivo(root=ROOT):
    data_dir = Path(root) / "data"
    jornadas_dir = data_dir / "jornadas"
    numeros = set()
    estado = cargar_json(data_dir / "estado_jornada_objetivo.json", {})
    pred = cargar_json(data_dir / "predicciones" / "ultima_prediccion.json", {})

    for valor in (estado.get("jornada_objetivo"), pred.get("jornada")):
        try:
            if valor:
                numeros.add(int(valor))
        except (TypeError, ValueError):
            pass

    existentes = []
    for path in jornadas_dir.glob("jornada_*.json"):
        data = cargar_json(path, {})
        try:
            existentes.append(int(data.get("jornada") or path.stem.split("_")[-1]))
        except (TypeError, ValueError):
            continue
    if existentes:
        numeros.add(max(existentes))

    seleccion = []
    for numero in sorted(numeros)[:limite_jornadas_profesionales()]:
        path = jornadas_dir / f"jornada_{numero}.json"
        data = cargar_json(path, {})
        if data.get("partidos"):
            seleccion.append(data)
    return seleccion


def api_football_get(base_url, token, endpoint, params=None, requester=None):
    if requests is None and requester is None:
        raise RuntimeError("requests no esta disponible para consultar API-Football")
    requester = requester or requests
    url = f"{str(base_url).rstrip('/')}/{str(endpoint).lstrip('/')}"
    respuesta = requester.get(
        url,
        headers={
            "User-Agent": "QuiniHub/1X2 datos-profesionales",
            "Accept": "application/json",
            "x-apisports-key": token,
        },
        params=params or {},
        timeout=30,
    )
    respuesta.raise_for_status()
    payload = respuesta.json()
    errores = payload.get("errors")
    if errores:
        raise RuntimeError(f"API-Football {endpoint}: {errores}")
    return payload.get("response") or []


def estado_cuenta_api_football(base_url, token, requester=None):
    """Consulta el endpoint /status de API-Football -barato y disponible
    incluso en el plan gratuito- para saber el estado real de la cuenta
    (plan, si esta activa, cuota de peticiones) en vez de tener que
    inferirlo de un 403 generico en un fixture concreto. Un 403 en
    /fixtures puede significar "token invalido" o "tu plan no cubre esta
    liga/temporada", y sin esto no se podia distinguir uno de otro.
    """
    try:
        payload = api_football_get(base_url, token, "status")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    payload = payload or {}
    suscripcion = payload.get("subscription") or {}
    peticiones = payload.get("requests") or {}
    return {
        "ok": True,
        "plan": suscripcion.get("plan"),
        "activa": suscripcion.get("active"),
        "fin_plan": suscripcion.get("end"),
        "peticiones_usadas": peticiones.get("current"),
        "peticiones_limite": peticiones.get("limit_day"),
    }


def fixture_nombres(fixture):
    equipos = fixture.get("teams") or {}
    home = (equipos.get("home") or {}).get("name") or ""
    away = (equipos.get("away") or {}).get("name") or ""
    return home, away


def puntuacion_fixture(fixture, partido):
    home, away = fixture_nombres(fixture)
    directo = puntuacion_nombre(home, partido.get("local")) + puntuacion_nombre(away, partido.get("visitante"))
    inverso = puntuacion_nombre(home, partido.get("visitante")) + puntuacion_nombre(away, partido.get("local"))
    return directo - 250 if directo >= inverso else inverso - 500


def buscar_fixture_api_football(base_url, token, partido, fixture_cache, requester=None):
    fecha = str(partido.get("fecha") or "").strip()
    if not fecha:
        return None
    candidatos = []
    for liga_id in ligas_api_football():
        cache_key = (fecha, liga_id)
        if cache_key not in fixture_cache:
            fixture_cache[cache_key] = api_football_get(
                base_url,
                token,
                "fixtures",
                {
                    "date": fecha,
                    "league": liga_id,
                    "season": temporada_api_football(),
                    "timezone": os.getenv("QUINIHUB_PRO_DATA_TIMEZONE") or "Europe/Madrid",
                },
                requester=requester,
            )
        candidatos.extend(fixture_cache[cache_key])
    if not candidatos:
        return None
    fixture = max(candidatos, key=lambda item: puntuacion_fixture(item, partido))
    return fixture if puntuacion_fixture(fixture, partido) >= 1100 else None


def cuota_valor_api_football(valor):
    texto = str((valor or {}).get("value") or "").strip().lower()
    cuota = (valor or {}).get("odd")
    if texto in {"home", "1", "local"}:
        return "1", cuota
    if texto in {"draw", "x", "empate"}:
        return "X", cuota
    if texto in {"away", "2", "visitante"}:
        return "2", cuota
    return None, None


def cuotas_api_football(base_url, token, fixture_id, requester=None):
    params = {"fixture": fixture_id}
    bookmaker = os.getenv("QUINIHUB_PRO_DATA_BOOKMAKER")
    if bookmaker:
        params["bookmaker"] = bookmaker
    response = api_football_get(base_url, token, "odds", params, requester=requester)
    for item in response:
        for casa in item.get("bookmakers") or []:
            for bet in casa.get("bets") or []:
                cuotas = {}
                for value in bet.get("values") or []:
                    signo, cuota = cuota_valor_api_football(value)
                    if signo:
                        cuotas[signo] = cuota
                if all(signo in cuotas for signo in ("1", "X", "2")):
                    cuotas.update({
                        "fuente": "API-Football",
                        "proveedor": casa.get("name"),
                        "mercado": bet.get("name") or "Match Winner",
                        "actualizado_en": ahora_iso(),
                    })
                    return cuotas
    return {}


def clasificar_baja_api_football(item):
    player = item.get("player") or {}
    texto = f"{player.get('type', '')} {player.get('reason', '')}".lower()
    if "suspend" in texto or "ban" in texto or "sanc" in texto:
        return "sanciones"
    if "doubt" in texto or "question" in texto:
        return "dudas"
    return "lesiones"


def bajas_api_football(base_url, token, fixture, requester=None):
    fixture_id = (fixture.get("fixture") or {}).get("id")
    home_id = ((fixture.get("teams") or {}).get("home") or {}).get("id")
    away_id = ((fixture.get("teams") or {}).get("away") or {}).get("id")
    salida = {"local": {"lesiones": [], "sanciones": [], "dudas": []}, "visitante": {"lesiones": [], "sanciones": [], "dudas": []}}
    response = api_football_get(base_url, token, "injuries", {"fixture": fixture_id}, requester=requester)
    for item in response:
        team_id = ((item.get("team") or {}).get("id"))
        lado = "local" if team_id == home_id else "visitante" if team_id == away_id else None
        if not lado:
            continue
        player = item.get("player") or {}
        tipo = clasificar_baja_api_football(item)
        salida[lado][tipo].append({
            "jugador": player.get("name"),
            "estado": player.get("reason") or player.get("type"),
            "impacto": 1.7 if tipo == "sanciones" else 0.9 if tipo == "dudas" else 1.8,
            "fuente": "API-Football",
            "actualizado_en": ahora_iso(),
        })
    return salida


def alineaciones_api_football(base_url, token, fixture, requester=None):
    fixture_id = (fixture.get("fixture") or {}).get("id")
    home_id = ((fixture.get("teams") or {}).get("home") or {}).get("id")
    away_id = ((fixture.get("teams") or {}).get("away") or {}).get("id")
    salida = {"local": {}, "visitante": {}}
    response = api_football_get(base_url, token, "fixtures/lineups", {"fixture": fixture_id}, requester=requester)
    for item in response:
        team_id = ((item.get("team") or {}).get("id"))
        lado = "local" if team_id == home_id else "visitante" if team_id == away_id else None
        if not lado:
            continue
        titulares = [
            ((registro.get("player") or {}).get("name") or "").strip()
            for registro in item.get("startXI") or []
        ]
        titulares = [nombre for nombre in titulares if nombre]
        salida[lado] = {
            "confirmada": bool(titulares),
            "confianza": 1.0 if titulares else 0.0,
            "titulares_probables": titulares[:11],
            "fuente": "API-Football",
            "actualizado_en": ahora_iso(),
        }
    return salida


def standings_api_football(base_url, token, fixture, standings_cache, requester=None):
    league = fixture.get("league") or {}
    liga_id = league.get("id")
    season = league.get("season") or temporada_api_football()
    if not liga_id:
        return {}
    cache_key = (liga_id, season)
    if cache_key not in standings_cache:
        rows = []
        response = api_football_get(
            base_url,
            token,
            "standings",
            {"league": liga_id, "season": season},
            requester=requester,
        )
        for item in response:
            for grupo in ((item.get("league") or {}).get("standings") or []):
                rows.extend(grupo)
        standings_cache[cache_key] = rows
    return {
        "temporada": f"{season}/{int(season) + 1}",
        "competicion": league.get("name"),
        "fuente": "API-Football",
        "local": standing_equipo(standings_cache[cache_key], fixture, "home"),
        "visitante": standing_equipo(standings_cache[cache_key], fixture, "away"),
        "actualizado_en": ahora_iso(),
    }


def standing_equipo(rows, fixture, lado_fixture):
    nombre = (((fixture.get("teams") or {}).get(lado_fixture) or {}).get("name") or "")
    mejor = None
    mejor_score = 0
    for row in rows or []:
        score = puntuacion_nombre(((row.get("team") or {}).get("name") or ""), nombre)
        if score > mejor_score:
            mejor = row
            mejor_score = score
    if not mejor or mejor_score < 700:
        return {}
    all_stats = mejor.get("all") or {}
    return {
        "posicion": mejor.get("rank"),
        "puntos": mejor.get("points"),
        "pj": all_stats.get("played"),
        "dg": mejor.get("goalsDiff"),
        "forma": mejor.get("form"),
        "fuente": "API-Football",
    }


def consultar_opcional(func, errores, etiqueta):
    try:
        return func()
    except Exception as exc:
        errores.append(f"{etiqueta}: {exc}")
        return {}


def leer_api_football_payload(base_url, token, root=ROOT, requester=None):
    if not token:
        raise RuntimeError("Falta QUINIHUB_PRO_DATA_TOKEN para API-Football.")
    fixture_cache = {}
    standings_cache = {}
    errores = []
    jornadas = {}
    fixtures_emparejados = 0

    for jornada_data in seleccionar_jornadas_objetivo(root):
        jornada = int(jornada_data.get("jornada") or 0)
        for partido in jornada_data.get("partidos", [])[:14]:
            fixture = consultar_opcional(
                lambda partido=partido: buscar_fixture_api_football(base_url, token, partido, fixture_cache, requester=requester),
                errores,
                f"fixtures {partido.get('local')} - {partido.get('visitante')}",
            )
            if not fixture:
                continue
            fixtures_emparejados += 1
            fixture_id = (fixture.get("fixture") or {}).get("id")
            home, away = fixture_nombres(fixture)
            league = fixture.get("league") or {}
            season_value = int(league.get("season") or temporada_api_football())
            fixture_info = fixture.get("fixture") or {}
            raw_partido = {
                "num": partido.get("num"),
                "jornada": jornada,
                "local": partido.get("local") or home,
                "visitante": partido.get("visitante") or away,
                "competicion": league.get("name"),
                "calendario": {
                    "fecha": str(fixture_info.get("date") or partido.get("fecha") or "")[:10],
                    "hora": str(fixture_info.get("date") or "")[11:16] or partido.get("hora"),
                    "temporada": f"{season_value}/{season_value + 1}",
                    "competicion": league.get("name"),
                    "jornada_liga": league.get("round"),
                    "sede": ((fixture_info.get("venue") or {}).get("name") or ""),
                    "fuente": "API-Football oficial",
                    "oficial": True,
                    "actualizado_en": ahora_iso(),
                },
                "cuotas": consultar_opcional(
                    lambda fixture_id=fixture_id: cuotas_api_football(base_url, token, fixture_id, requester=requester),
                    errores,
                    f"odds fixture {fixture_id}",
                ),
                "bajas": consultar_opcional(
                    lambda fixture=fixture: bajas_api_football(base_url, token, fixture, requester=requester),
                    errores,
                    f"injuries fixture {fixture_id}",
                ),
                "alineaciones": consultar_opcional(
                    lambda fixture=fixture: alineaciones_api_football(base_url, token, fixture, requester=requester),
                    errores,
                    f"lineups fixture {fixture_id}",
                ),
                "clasificacion": consultar_opcional(
                    lambda fixture=fixture: standings_api_football(base_url, token, fixture, standings_cache, requester=requester),
                    errores,
                    f"standings fixture {fixture_id}",
                ),
            }
            jornadas.setdefault(str(jornada), {"jornada": jornada, "partidos": []})
            jornadas[str(jornada)]["partidos"].append(raw_partido)

    return {
        "generado_en": ahora_iso(),
        "temporada_objetivo": temporada_objetivo(),
        "proveedores": {
            "api_football": {
                "base_url": base_url,
                "ligas": ligas_api_football(),
                "season": temporada_api_football(),
                "fixtures_emparejados": fixtures_emparejados,
                "errores": errores[:20],
                "estado_cuenta": estado_cuenta_api_football(base_url, token, requester=requester),
            }
        },
        "jornadas": jornadas,
    }


def leer_payload_externo():
    archivo = os.getenv("QUINIHUB_PRO_DATA_FILE")
    if archivo:
        return cargar_json(archivo, {})

    url = os.getenv("QUINIHUB_PRO_DATA_URL")
    if not url:
        return None
    if requests is None:
        raise RuntimeError("requests no esta disponible para leer QUINIHUB_PRO_DATA_URL")
    token = os.getenv("QUINIHUB_PRO_DATA_TOKEN")
    if url_es_api_football(url):
        if not token:
            return None
        return leer_api_football_payload(url, token)
    headers = {"User-Agent": "QuiniHub/1X2 datos-profesionales"}
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
