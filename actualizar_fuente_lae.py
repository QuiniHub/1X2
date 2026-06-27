import json, re, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
HISTORIAL = DATA / "historial_quinielas.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

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
        m = re.search(r'([1X2]{14})', texto)
        if not m:
            return None
        combinacion = m.group(1)

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

def actualizar_resultado_oficial(jornada_num, combinacion):
    """
    Actualiza jornada_XX.json con el resultado oficial de LAE.
    combinacion: string de 14 signos "1X2X112X21XX12"
    """
    path = JORNADAS / f"jornada_{jornada_num}.json"
    if not path.exists():
        print(f"No existe jornada_{jornada_num}.json")
        return False

    data = json.load(open(path, encoding="utf-8"))
    partidos = data.get("partidos", [])

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

def actualizar_historial_con_lae(jornada_num, combinacion):
    """
    Actualiza historial_quinielas.json con el resultado oficial de LAE.
    """
    try:
        hist = json.load(open(HISTORIAL, encoding="utf-8"))
    except:
        return

    for j in hist.get("jornadas", []):
        if int(j.get("jornada", 0)) == jornada_num:
            if j.get("resultado_oficial", "Pendiente") == "Pendiente":
                j["resultado_oficial"] = combinacion
                j["fuente_resultado"] = "lae_oficial"
                j["estado"] = "cerrada"
                with open(HISTORIAL, "w", encoding="utf-8") as f:
                    json.dump(hist, f, ensure_ascii=False, indent=2)
                print(f"Historial J{jornada_num} actualizado con resultado oficial LAE")
            break

if __name__ == "__main__":
    print("=== Actualizando desde fuente oficial LAE ===")

    # Buscar jornadas abiertas y obtener sus resultados si ya se jugaron
    try:
        hist = json.load(open(HISTORIAL, encoding="utf-8"))
        jornadas_abiertas = [
            j for j in hist.get("jornadas", [])
            if j.get("estado") in ("abierta", "en_juego") and
               j.get("resultado_oficial", "Pendiente") == "Pendiente"
        ]

        for j in jornadas_abiertas[-3:]:  # Solo las últimas 3 abiertas
            jornada_num = int(j.get("jornada", 0))
            fecha_str = str(j.get("fecha", "") or "").replace("-", "")[:8]
            resultado = None

            if not fecha_str or len(fecha_str) < 8:
                # Intentar con fecha de hoy y días anteriores
                from datetime import date
                for dias_atras in range(0, 7):
                    fecha = date.today() - timedelta(days=dias_atras)
                    fecha_str = fecha.strftime("%Y%m%d")
                    resultado = obtener_resultado_oficial_lae(fecha_str)
                    if resultado and resultado.get("jornada") == jornada_num:
                        break
            else:
                resultado = obtener_resultado_oficial_lae(fecha_str)

            if resultado and resultado.get("combinacion"):
                actualizar_resultado_oficial(jornada_num, resultado["combinacion"])
                actualizar_historial_con_lae(jornada_num, resultado["combinacion"])

    except Exception as e:
        print(f"Error actualizando desde LAE: {e}")

    # Descargar PDF de próximas jornadas
    obtener_proxima_jornada_lae()

    # Descargar histórico completo solo una vez por semana
    descargar_historico_lae_si_toca()

    print("=== Completado ===")
