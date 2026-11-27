import json, re, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
HISTORIAL = DATA / "historial_quinielas.json"

HEADERS = {
    # Cliente automatizado identificado como tal (no se suplanta un navegador).
    "User-Agent": "quiniela-lae-bot/1.0 (cliente automatizado; python-requests)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Dias de margen entre la fecha de la jornada guardada y la del sorteo pedido.
MARGEN_DIAS_JORNADA = 4

_RE_COMBINACION = re.compile(r"(?<![0-9A-Za-z])([1X2]{14})(?![0-9A-Za-z])")


def fecha_de_jornada(registro):
    """Fecha real (date) de un registro de historial o de un jornada_N.json.

    Auditoria 26/11 (hallazgo 59): el campo 'fecha' es texto ('Domingo, 29 de
    noviembre de 2026') y se recortaba a 'Domingo,', que se enviaba tal cual
    como fecha_sorteo. Nunca se obtuvo un resultado.
    """
    import cronologia_jornadas

    if not isinstance(registro, dict):
        return None
    for clave in ("fecha", "fecha_real"):
        fecha = cronologia_jornadas.parsear_fecha(registro.get(clave))
        if fecha is not None:
            return fecha
    return cronologia_jornadas.fecha_real_jornada(registro)


def fecha_sorteo_lae(registro):
    """'AAAAMMDD' para la URL de LAE, o '' si no hay fecha reconocible."""
    fecha = fecha_de_jornada(registro)
    return fecha.strftime("%Y%m%d") if fecha else ""


def extraer_combinacion(texto):
    """14 signos 1/X/2 seguidos y AISLADOS (no un trozo de un numero largo).
    Una cadena sin ninguna X se descarta: es mucho mas probable que sea un
    identificador numerico de la pagina que una quiniela sin empates."""
    for m in _RE_COMBINACION.finditer(texto or ""):
        if "X" in m.group(1):
            return m.group(1)
    return None


def misma_fecha(fecha_a, fecha_b, margen=MARGEN_DIAS_JORNADA):
    if fecha_a is None or fecha_b is None:
        return False
    return abs((fecha_a - fecha_b).days) <= margen


def obtener_resultado_oficial_lae(fecha_sorteo_str):
    """
    Obtiene el resultado oficial de La Quiniela de LAE.
    fecha_sorteo_str: formato "aaaammdd" ej: "20260627"
    URL: https://www.loteriasyapuestas.es/f/loterias/resultados/quiniela.html?game_id=LAQU&fecha_sorteo=aaaammdd

    Devuelve dict con:
    - combinacion: string tipo "1X2X112X21XX12" (14 signos)
    - pleno15_local_goles: int
    - pleno15_visitante_goles: int
    - jornada: int
    - fecha: str
    """
    url = f"https://www.loteriasyapuestas.es/f/loterias/resultados/quiniela.html?game_id=LAQU&fecha_sorteo={fecha_sorteo_str}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"LAE error {r.status_code} para fecha {fecha_sorteo_str}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        texto = soup.get_text()

        # Buscar combinación ganadora (14 signos 1/X/2)
        combinacion = extraer_combinacion(texto)
        if not combinacion:
            return None

        # Buscar número de jornada
        jornada_m = re.search(r'[Jj]ornada\s*[Nº#]?\s*(\d+)', texto)
        jornada = int(jornada_m.group(1)) if jornada_m else None

        print(f"LAE: Jornada {jornada} - Combinación: {combinacion}")
        return {
            "combinacion": combinacion,
            "jornada": jornada,
            "fecha": fecha_sorteo_str,
            "fuente": "lae_oficial"
        }
    except Exception as e:
        print(f"LAE error: {e}")
        return None

def obtener_proxima_jornada_lae():
    """
    Obtiene los partidos de la próxima jornada desde el PDF de LAE.
    URL: https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Calendarios/Proximas_jornadas_deportivas.pdf
    """
    url = "https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Calendarios/Proximas_jornadas_deportivas.pdf"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            print(f"LAE PDF error: {r.status_code}")
            return None
        # Guardar el PDF para procesarlo después
        pdf_path = DATA / "quiniela_proximas_jornadas.pdf"
        with open(pdf_path, "wb") as f:
            f.write(r.content)
        print(f"LAE: PDF de próximas jornadas descargado ({len(r.content)} bytes)")
        return str(pdf_path)
    except Exception as e:
        print(f"LAE PDF error: {e}")
        return None

def descargar_historico_lae():
    """
    Descarga el histórico completo de La Quiniela en Excel.
    Contiene todas las jornadas desde el inicio hasta hoy.
    """
    url = "https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Calendarios/HistoricoQuiniela.xls"
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code == 200:
            xls_path = DATA / "historico_quiniela_lae.xls"
            with open(xls_path, "wb") as f:
                f.write(r.content)
            print(f"LAE: Histórico descargado ({len(r.content)} bytes)")
            return str(xls_path)
    except Exception as e:
        print(f"LAE histórico error: {e}")
    return None

def descargar_historico_lae_si_toca():
    """Descarga el histórico LAE solo si falta o tiene más de 7 días."""
    xls_path = DATA / "historico_quiniela_lae.xls"
    try:
        if xls_path.exists():
            edad = datetime.now(timezone.utc) - datetime.fromtimestamp(xls_path.stat().st_mtime, timezone.utc)
            if edad <= timedelta(days=7):
                print("LAE: histórico vigente; no se descarga de nuevo")
                return str(xls_path)
        return descargar_historico_lae()
    except Exception as e:
        print(f"LAE histórico semanal error: {e}")
        return None

def actualizar_resultado_oficial(jornada_num, combinacion, fecha=None):
    """
    Actualiza jornada_XX.json con el resultado oficial de LAE.
    combinacion: string de 14 signos "1X2X112X21XX12"
    fecha: date del sorteo; si se pasa, el fichero tiene que ser de esas fechas
           (el numero de jornada se repite cada temporada).
    """
    path = JORNADAS / f"jornada_{jornada_num}.json"
    if not path.exists():
        print(f"No existe jornada_{jornada_num}.json")
        return False

    data = json.load(open(path, encoding="utf-8"))
    partidos = data.get("partidos", [])

    if fecha is not None:
        import cronologia_jornadas

        inicio = cronologia_jornadas.fecha_real_jornada(data)
        fin = cronologia_jornadas.fecha_fin_jornada(data)
        if inicio is None or fin is None or not (
            inicio - timedelta(days=MARGEN_DIAS_JORNADA) <= fecha <= fin + timedelta(days=MARGEN_DIAS_JORNADA)
        ):
            print(f"jornada_{jornada_num}.json no es de la fecha {fecha}: no se toca")
            return False

    if len(combinacion) < 14:
        print(f"Combinación incompleta: {combinacion}")
        return False

    cambios = 0
    for p in partidos:
        num = p.get("num", 0)
        if 1 <= num <= 14:
            signo = combinacion[num - 1]
            if p.get("signo_oficial", "Pendiente") == "Pendiente":
                p["signo_oficial"] = signo
                p["fuente_resultado"] = "lae_oficial"
                cambios += 1

    if cambios:
        data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        if all(p.get("signo_oficial", "Pendiente") not in ("Pendiente", "")
               for p in partidos):
            data["estado"] = "cerrada"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Jornada {jornada_num}: {cambios} signos actualizados desde LAE oficial")

    return cambios > 0

def actualizar_historial_con_lae(jornada_num, combinacion, fecha=None):
    """
    Actualiza historial_quinielas.json con el resultado oficial de LAE.
    Con `fecha` se casa por jornada + fecha: el historial tiene varias
    temporadas y antes se paraba en la primera con ese numero.
    """
    try:
        hist = json.load(open(HISTORIAL, encoding="utf-8"))
    except Exception:
        return

    for j in hist.get("jornadas", []):
        if int(j.get("jornada", 0) or 0) == jornada_num:
            if fecha is not None and not misma_fecha(fecha_de_jornada(j), fecha):
                continue
            if j.get("resultado_oficial", "Pendiente") == "Pendiente":
                j["resultado_oficial"] = combinacion
                j["fuente_resultado"] = "lae_oficial"
                j["estado"] = "cerrada"
                with open(HISTORIAL, "w", encoding="utf-8") as f:
                    json.dump(hist, f, ensure_ascii=False, indent=2)
                print(f"Historial J{jornada_num} actualizado con resultado oficial LAE")
            break

def jornadas_a_consultar(hist, hoy=None):
    """Jornadas abiertas del historial cuya fecha ya ha llegado: lista de
    (numero, date). Sin fecha reconocible o con fecha futura no se consulta
    (antes se pedia 'fecha_sorteo=Domingo,' o se barrian 7 dias a ciegas)."""
    from datetime import date

    hoy = hoy or date.today()
    salida = []
    for j in (hist or {}).get("jornadas", []):
        if j.get("estado") not in ("abierta", "en_juego"):
            continue
        if j.get("resultado_oficial", "Pendiente") != "Pendiente":
            continue
        fecha = fecha_de_jornada(j)
        if fecha is None or fecha > hoy:
            continue
        try:
            salida.append((int(j.get("jornada") or 0), fecha))
        except (TypeError, ValueError):
            continue
    salida.sort(key=lambda par: par[1])  # por fecha real, no por numero
    return salida[-3:]


def actualizar_resultados_desde_lae(hoy=None):
    try:
        hist = json.load(open(HISTORIAL, encoding="utf-8"))
    except Exception as e:
        print(f"Error actualizando desde LAE: {e}")
        return 0
    aplicadas = 0
    for jornada_num, fecha in jornadas_a_consultar(hist, hoy):
        resultado = obtener_resultado_oficial_lae(fecha.strftime("%Y%m%d"))
        if not resultado or not resultado.get("combinacion"):
            continue
        if resultado.get("jornada") != jornada_num:
            # La pagina no confirma que sea ESTA jornada: no se aplica.
            print(f"LAE: la pagina del {fecha} dice jornada {resultado.get('jornada')}, se esperaba {jornada_num}; no se aplica")
            continue
        if actualizar_resultado_oficial(jornada_num, resultado["combinacion"], fecha=fecha):
            aplicadas += 1
        actualizar_historial_con_lae(jornada_num, resultado["combinacion"], fecha=fecha)
    return aplicadas


if __name__ == "__main__":
    print("=== Actualizando desde fuente oficial LAE ===")

    # Buscar jornadas abiertas y obtener sus resultados si ya se jugaron
    try:
        actualizar_resultados_desde_lae()
    except Exception as e:
        print(f"Error actualizando desde LAE: {e}")

    # Descargar PDF de próximas jornadas
    obtener_proxima_jornada_lae()

    # Descargar histórico completo solo una vez por semana
    descargar_historico_lae_si_toca()

    print("=== Completado ===")
