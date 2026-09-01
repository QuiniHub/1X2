import json
import re
import unicodedata
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
TZ_COMPETICION = ZoneInfo("Europe/Madrid")
MARGEN_RESULTADO_FINAL = timedelta(minutes=105)

FUENTES_DIRECTO = [
    "https://www.quiniela15.com/resultados-quiniela",
    "https://dondeverlo.es/quiniela/directo/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "\ufffd" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|club|real|de|del|la|el|balompie|futbol)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = " ".join(texto.split()).strip()
    return texto.replace("ee uu", "eeuu")


PALABRAS_CIUDAD_AMBIGUAS = {"madrid", "barcelona"}


def es_equipo_liga_f(nombre_crudo):
    crudo = str(nombre_crudo or "")
    return bool(re.search(r"\(\s*f\s*\)", crudo, re.I)) or bool(re.search(r"femen[ií]", crudo, re.I))


def candidatos_equipo(nombre):
    n = normalizar(nombre)
    # Liga F: candidatos ESTRICTOS con marcador femenino obligatorio. Bug
    # real (01/09/2026, dinero de verdad): "Real Madrid (F)" degeneraba en
    # el candidato suelto "madrid" (normalizar quita "real" como particula
    # y "madrid" era la unica palabra que quedaba) y "At. Madrid (F)" igual
    # -asi que el fragmento del Sevilla 1-3 At. Madrid MASCULINO validaba a
    # los DOS equipos del derbi femenino y escribia ese 1-3 como
    # signo_oficial "2" del P14... cuando el resultado real fue 3-2 (signo
    # "1", el que Marc jugo). La web resto un acierto que si teniamos: J3
    # fue 10/14 con premio, no 9/14 sin el. Un equipo (F) solo puede
    # emparejar con texto que tambien lleve el marcador femenino pegado.
    if es_equipo_liga_f(nombre):
        nucleo = re.sub(r"\s*\bfemenin?[oa]?\b\s*$", "", re.sub(r"\s+f$", "", n)).strip()
        candidatos = {n}
        variantes = [nucleo] + [p for p in nucleo.split() if len(p) > 2]
        for v in variantes:
            if v:
                candidatos.add(f"{v} f")
                candidatos.add(f"{v} femenino")
        return {c for c in candidatos if c}
    partes = [p for p in n.split() if len(p) > 2]
    # "madrid"/"barcelona" identifican la CIUDAD, no el club -varios equipos
    # de Primera/Segunda la comparten (Real Madrid, Atletico de Madrid, Rayo
    # Vallecano de Madrid / FC Barcelona, RCD Espanyol de Barcelona). Si el
    # nombre tiene otra palabra mas especifica (atletico, rayo, espanyol...),
    # esa es la que debe identificar al equipo -la palabra de ciudad sola
    # solo se admite cuando es la UNICA palabra distintiva que queda tras
    # quitar particulas (ej. "Real Madrid CF" -> "madrid", "FC Barcelona" ->
    # "barcelona"). Bug real (26/08/2026): sin esto, un resultado real de
    # "RCD Espanyol de Barcelona vs Real Madrid CF" se escribia por error
    # sobre la casilla de calendario de "FC Barcelona vs Rayo Vallecano de
    # Madrid" (partido de otra jornada, ni jugado todavia).
    distintivas = [p for p in partes if p not in PALABRAS_CIUDAD_AMBIGUAS]
    candidatos = {n}
    candidatos.update(distintivas)
    if not distintivas:
        candidatos.update(p for p in partes if p in PALABRAS_CIUDAD_AMBIGUAS)
    alias = {
        "eeuu": ["ee uu", "estados unidos", "usa", "united states"],
        "estados unidos": ["eeuu", "ee uu", "usa", "united states"],
        "atletico madrid": ["at madrid", "atletico"],
        "athletic bilbao": ["athletic", "ath club"],
        "athletic": ["ath club"],
        "racing santander": ["r santander", "racing"],
        "real sociedad": ["r sociedad", "sociedad"],
        "rayo vallecano": ["rayo"],
        "real oviedo": ["r oviedo", "oviedo"],
        "deportivo alaves": ["alaves"],
        "sporting gijon": ["sporting"],
        "celtic glasgow": ["celtic"],
        "glasgow rangers": ["rangers"],
        "paises bajos": ["holanda"],
        "holanda": ["paises bajos"],
        "curazao": ["curacao", "curaçao"],
        "curacao": ["curazao", "curaçao"],
        "costa marfil": ["costa de marfil"],
    }
    for key, vals in alias.items():
        if key in n:
            candidatos.update(vals)
    return {c for c in candidatos if c}


def contiene_equipo(texto, equipo):
    base = normalizar(texto)
    if es_equipo_liga_f(equipo):
        # Palabra completa obligatoria: el candidato "madrid f" es substring
        # de "madrid final" (el texto masculino de quiniela15 esta lleno de
        # "final"), asi que el substring a secas reabria el mismo bug que
        # los candidatos estrictos intentan cerrar.
        return any(
            re.search(r"(?<![a-z0-9])" + re.escape(c) + r"(?![a-z0-9])", base)
            for c in candidatos_equipo(equipo)
        )
    return any(c in base for c in candidatos_equipo(equipo))


def descargar_fuentes():
    textos = []
    if requests is None or BeautifulSoup is None:
        print("No estan disponibles requests/BeautifulSoup; no se consultan fuentes directas.")
        return ""
    for url in FUENTES_DIRECTO:
        try:
            response = requests.get(url, headers=HEADERS, timeout=25)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            texto = " ".join(soup.get_text(" ").split())
            textos.append(texto)
            print(f"Fuente directa OK: {url}")
        except Exception as exc:
            print(f"No se pudo consultar {url}: {exc}")
    return "\n".join(textos)


def jornada_directo(texto):
    m = re.search(r"jornada\s+(\d{1,3})", texto, re.I)
    return int(m.group(1)) if m else None


def signo_valido(valor):
    return str(valor or "").strip().upper() in {"1", "X", "2"}


def signo_resultado(resultado):
    gl, gv = [int(x) for x in resultado.split("-")]
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def inicio_partido(partido):
    fecha_txt = str(partido.get("fecha") or "").strip()
    if not fecha_txt:
        return None
    try:
        fecha = datetime.fromisoformat(fecha_txt).date()
    except ValueError:
        return None

    hora_txt = str(partido.get("hora") or "").strip()
    if hora_txt in {"00:00", "0:00"}:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})$", hora_txt)
    if not m:
        return None
    hora = time(int(m.group(1)), int(m.group(2)))
    return datetime.combine(fecha, hora, TZ_COMPETICION)


def fecha_partido(partido):
    fecha_txt = str(partido.get("fecha") or "").strip()
    if not fecha_txt:
        return None
    try:
        return datetime.fromisoformat(fecha_txt).date()
    except ValueError:
        return None


def partido_ya_deberia_tener_resultado(partido):
    inicio = inicio_partido(partido)
    if not inicio:
        return False
    return inicio + MARGEN_RESULTADO_FINAL <= datetime.now(TZ_COMPETICION)


def partido_ya_empezo(partido):
    inicio = inicio_partido(partido)
    if not inicio:
        return False
    return inicio <= datetime.now(TZ_COMPETICION)


def resumen_temporal_jornada(data):
    partidos = list(data.get("partidos", []))
    pleno = data.get("pleno15") or {}
    if pleno:
        partidos.append(pleno)

    inicios = [inicio_partido(p) for p in partidos]
    inicios = [i for i in inicios if i]
    cerrados = sum(1 for p in data.get("partidos", []) if signo_valido(p.get("signo_oficial")))
    pendientes = sum(1 for p in data.get("partidos", []) if not signo_valido(p.get("signo_oficial")))
    vencidos = sum(1 for p in data.get("partidos", []) if not signo_valido(p.get("signo_oficial")) and partido_ya_deberia_tener_resultado(p))
    empezados = sum(1 for p in data.get("partidos", []) if partido_ya_empezo(p))
    return {
        "jornada": data.get("jornada"),
        "cerrados": cerrados,
        "pendientes": pendientes,
        "vencidos": vencidos,
        "empezados": empezados,
        "primer_inicio": min(inicios).isoformat() if inicios else "",
    }


def buscar_partidos_en_calendario(partido):
    encontrados = []
    for archivo in (DATA / "calendario_primera.json", DATA / "calendario_segunda.json"):
        data = cargar_json(archivo, {})
        for jornada in data.get("jornadas", []):
            for p_cal in jornada.get("partidos", []):
                if contiene_equipo(p_cal.get("local", ""), partido.get("local", "")) and contiene_equipo(p_cal.get("visitante", ""), partido.get("visitante", "")):
                    encontrados.append(p_cal)
    return encontrados


def partido_esta_programado_en_futuro(partido):
    ahora = datetime.now(TZ_COMPETICION)
    inicio = inicio_partido(partido)
    if inicio:
        return inicio + MARGEN_RESULTADO_FINAL > ahora

    fecha = fecha_partido(partido)
    if fecha and fecha >= ahora.date():
        return True

    for p_cal in buscar_partidos_en_calendario(partido):
        try:
            fecha = datetime.fromisoformat(str(p_cal.get("fecha", ""))).date()
        except ValueError:
            continue
        if fecha > ahora.date():
            return True
        if fecha == ahora.date():
            hora_txt = str(p_cal.get("hora") or "").strip()
            m = re.match(r"^(\d{1,2}):(\d{2})$", hora_txt)
            if not m:
                return True
            hora = time(int(m.group(1)), int(m.group(2)))
            cierre_minimo = datetime.combine(fecha, hora, TZ_COMPETICION) + MARGEN_RESULTADO_FINAL
            if cierre_minimo > ahora:
                return True
    return False


def buscar_resultado_final(texto, partido):
    local = partido.get("local", "")
    visitante = partido.get("visitante", "")
    patrones = [
        r"(?P<a>\d{1,2})\s*[-]\s*(?P<b>\d{1,2})",
        r"(?P<a>\d{1,2})\s+a\s+(?P<b>\d{1,2})",
    ]
    for patron in patrones:
        for match in re.finditer(patron, texto, re.I):
            fragmento = texto[max(0, match.start() - 180): min(len(texto), match.end() + 180)]
            if not (contiene_equipo(fragmento, local) and contiene_equipo(fragmento, visitante)):
                continue
            if re.search(r"\b(descanso|1t|2t|min\.?|minuto|en juego|pend)\b", fragmento, re.I):
                continue
            return f"{int(match.group('a'))}-{int(match.group('b'))}"
    return None


def jornada_activa_desde_archivos(jornada_detectada=None):
    if jornada_detectada:
        path = JORNADAS / f"jornada_{jornada_detectada}.json"
        if path.exists():
            return jornada_detectada

    candidatas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        numero = data.get("jornada")
        if not isinstance(numero, int):
            continue
        resumen = resumen_temporal_jornada(data)
        if resumen["pendientes"]:
            resumen["numero"] = numero
            candidatas.append(resumen)

    if not candidatas:
        return jornada_detectada

    en_juego = [c for c in candidatas if c["cerrados"] > 0 and c["pendientes"] > 0]
    if en_juego:
        return sorted(en_juego, key=lambda c: (c["numero"], c["cerrados"]), reverse=True)[0]["numero"]

    vencidas = [c for c in candidatas if c["vencidos"] > 0]
    if vencidas:
        return sorted(vencidas, key=lambda c: (c["numero"], c["vencidos"]), reverse=True)[0]["numero"]

    empezadas = [c for c in candidatas if c["empezados"] > 0]
    if empezadas:
        return sorted(empezadas, key=lambda c: (c["numero"], c["empezados"]), reverse=True)[0]["numero"]

    con_fecha = [c for c in candidatas if c["primer_inicio"]]
    if con_fecha:
        return sorted(con_fecha, key=lambda c: c["primer_inicio"])[0]["numero"]
    return max(c["numero"] for c in candidatas)


def actualizar_jornada_quiniela(texto):
    numero = jornada_activa_desde_archivos(jornada_directo(texto))
    if not numero:
        print("No se detecto jornada activa.")
        return 0, []

    path = JORNADAS / f"jornada_{numero}.json"
    data = cargar_json(path, {})
    if not data:
        print(f"No existe {path}")
        return 0, []

    cambios = 0
    actualizados = []
    for partido in data.get("partidos", []):
        if partido_esta_programado_en_futuro(partido):
            continue
        anterior = partido.get("resultado")
        resultado = buscar_resultado_final(texto, partido)
        if not resultado:
            continue
        signo = signo_resultado(resultado)
        if anterior != resultado or partido.get("signo_oficial") != signo:
            partido["resultado"] = resultado
            partido["signo_oficial"] = signo
            partido["actualizado_en"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            cambios += 1
        actualizados.append(partido)

    pleno = data.get("pleno15") or {}
    if pleno:
        resultado = None if partido_esta_programado_en_futuro(pleno) else buscar_resultado_final(texto, pleno)
        if resultado and pleno.get("resultado") != resultado:
            pleno["resultado"] = resultado
            pleno["signo_oficial"] = resultado
            pleno["actualizado_en"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            cambios += 1

    if cambios:
        data["estado"] = "cerrada" if all(str(p.get("signo_oficial", "")).upper() in ("1", "X", "2") for p in data.get("partidos", [])) else "en_juego"
        guardar_json(path, data)
    print(f"Jornada quiniela {numero}: {cambios} cambios.")
    return cambios, actualizados


def _fecha_calendario_es_futura(p_cal):
    fecha_txt = str(p_cal.get("fecha") or "").strip()[:10]
    if not fecha_txt:
        return False
    try:
        return datetime.fromisoformat(fecha_txt).date() > datetime.now(TZ_COMPETICION).date()
    except ValueError:
        return False


def sincronizar_calendario_liga(partidos):
    # Bug real (26/08/2026): "FC Barcelona - Rayo Vallecano de Madrid"
    # (Jornada 3, 2026-08-30, aun sin jugar) quedo marcado "Jugado" con el
    # resultado real de OTRO partido de la Jornada 2 ya cerrada (RCD
    # Espanyol de Barcelona 1-2 Real Madrid CF) -contiene_equipo() emparejo
    # por la palabra de ciudad compartida ("barcelona"/"madrid", ya
    # corregido arriba en candidatos_equipo). Guardia adicional aqui, igual
    # que en actualizar_calendario() (actualizar_ligas_football_data.py):
    # nunca marcar "Jugado" una casilla del calendario cuya fecha todavia no
    # ha llegado, sea cual sea la causa del emparejamiento erroneo.
    cambios = 0
    for archivo in (DATA / "calendario_primera.json", DATA / "calendario_segunda.json"):
        data = cargar_json(archivo, {})
        if not data:
            continue
        for jornada in data.get("jornadas", []):
            for p_cal in jornada.get("partidos", []):
                if _fecha_calendario_es_futura(p_cal):
                    continue
                for p_q in partidos:
                    resultado = p_q.get("resultado")
                    if not resultado or resultado == "Pendiente":
                        continue
                    if contiene_equipo(p_cal.get("local", ""), p_q.get("local", "")) and contiene_equipo(p_cal.get("visitante", ""), p_q.get("visitante", "")):
                        if p_cal.get("resultado") != resultado:
                            p_cal["resultado"] = resultado
                            p_cal["estado"] = "Jugado"
                            p_cal["actualizado_en"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                            cambios += 1
        guardar_json(archivo, data)
    print(f"Calendarios sincronizados desde quiniela: {cambios} cambios.")
    return cambios


def main():
    texto = descargar_fuentes()
    if not texto:
        print("Sin texto de fuentes directas.")
        return
    cambios, partidos = actualizar_jornada_quiniela(texto)
    if partidos:
        cambios += sincronizar_calendario_liga(partidos)
    print(f"Actualizacion directa finalizada: {cambios} cambios.")


if __name__ == "__main__":
    main()
