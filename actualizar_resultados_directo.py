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


def candidatos_equipo(nombre):
    n = normalizar(nombre)
    partes = [p for p in n.split() if len(p) > 2]
    candidatos = {n}
    candidatos.update(partes)
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

    # Sin hora fiable no se acepta scraping de resultados el mismo dia ni en el futuro.
    # Evita cerrar partidos con marcadores encontrados en paginas agregadas pero no
    # vinculados a un partido ya finalizado.
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


def sincronizar_calendario_liga(partidos):
    cambios = 0
    for archivo in (DATA / "calendario_primera.json", DATA / "calendario_segunda.json"):
        data = cargar_json(archivo, {})
        if not data:
            continue
        for jornada in data.get("jornadas", []):
            for p_cal in jornada.get("partidos", []):
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
