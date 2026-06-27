"""
Busca resultados de partidos pendientes en Google.
Para cada partido sin resultado en jornada_XX.json, construye una 
búsqueda automática y extrae el marcador del snippet de Google.
"""
import json
import re
import requests
import time
from datetime import datetime, timezone, timedelta, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
RESULTADOS_MUNDIAL = DATA / "mundial_2026_resultados.json"

TZ = ZoneInfo("Europe/Madrid")
MARGEN = timedelta(minutes=105)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

def partido_ya_terminado(fecha_txt, hora_txt):
    try:
        fecha = datetime.fromisoformat(str(fecha_txt)).date()
        m = re.match(r"^(\d{1,2}):(\d{2})$", str(hora_txt or ""))
        if not m:
            return fecha < datetime.now(TZ).date()
        hora = dt_time(int(m.group(1)), int(m.group(2)))
        inicio = datetime.combine(fecha, hora, TZ)
        return inicio + MARGEN <= datetime.now(TZ)
    except:
        return False

def extraer_marcador(texto):
    """Extrae patrón X-Y de un texto."""
    # Buscar patrón de marcador: número-número
    patrones = [
        r'\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b',
        r'\b(\d{1,2})\s+a\s+(\d{1,2})\b',
    ]
    for patron in patrones:
        m = re.search(patron, texto)
        if m:
            g1, g2 = int(m.group(1)), int(m.group(2))
            if g1 <= 20 and g2 <= 20:  # Sanity check
                return f"{g1}-{g2}"
    return None

def buscar_en_google(local, visitante):
    """
    Busca el resultado de un partido en Google.
    Extrae el marcador de los snippets de búsqueda.
    """
    query = f"{local} {visitante} resultado 2026"
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=es&gl=es"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        
        html = r.text
        
        # Buscar el marcador en el HTML de Google
        # Google muestra el resultado en un div especial
        # Buscar patrones cerca de los nombres de los equipos
        
        # Limpiar HTML básicamente
        texto_limpio = re.sub(r'<[^>]+>', ' ', html)
        texto_limpio = re.sub(r'\s+', ' ', texto_limpio)
        
        # Buscar el marcador cerca del nombre de los equipos
        # Buscar ventana de texto que contenga ambos equipos
        local_norm = local.lower().split()[0]  # Primera palabra del nombre
        vis_norm = visitante.lower().split()[0]
        
        # Encontrar posiciones donde aparecen los equipos
        pos_local = [m.start() for m in re.finditer(re.escape(local_norm), texto_limpio.lower())]
        pos_vis = [m.start() for m in re.finditer(re.escape(vis_norm), texto_limpio.lower())]
        
        if not pos_local or not pos_vis:
            return None
        
        # Buscar marcador en ventanas donde ambos equipos aparecen cerca
        for pl in pos_local[:5]:
            for pv in pos_vis[:5]:
                if abs(pl - pv) < 500:
                    inicio = max(0, min(pl, pv) - 50)
                    fin = min(len(texto_limpio), max(pl, pv) + 200)
                    fragmento = texto_limpio[inicio:fin]
                    
                    # Excluir fragmentos que parecen ser horarios o predicciones
                    if re.search(r'\b(hoy|mañana|pronóstico|cuándo|horario|canal|ver)\b', 
                                fragmento.lower()):
                        continue
                    
                    marcador = extraer_marcador(fragmento)
                    if marcador:
                        return marcador
        
        return None
        
    except Exception as e:
        print(f"  Error buscando {local} vs {visitante}: {e}")
        return None

def buscar_en_flashscore(local, visitante):
    """
    Busca resultado en Flashscore como fuente secundaria.
    """
    query = f"{local} {visitante} flashscore"
    url_busqueda = f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=es"
    
    try:
        r = requests.get(url_busqueda, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        
        # Buscar URL de Flashscore en los resultados
        urls_flashscore = re.findall(
            r'https://www\.flashscore\.es/partido/futbol/[^\s"&<>]+', 
            r.text
        )
        
        if not urls_flashscore:
            return None
        
        # Intentar con la primera URL encontrada
        url_partido = urls_flashscore[0]
        time.sleep(1)
        
        r2 = requests.get(url_partido, headers=HEADERS, timeout=15)
        if r2.status_code != 200:
            return None
        
        # El resultado está en el og:title
        m = re.search(r'og:title[^>]*content="([^"]+)"', r2.text)
        if not m:
            m = re.search(r'<title>([^<]+)</title>', r2.text)
        if m:
            titulo = m.group(1)
            marcador = re.search(r'(\d{1,2})-(\d{1,2})', titulo)
            if marcador:
                return f"{marcador.group(1)}-{marcador.group(2)}"
        
        return None
        
    except Exception as e:
        print(f"  Error Flashscore {local} vs {visitante}: {e}")
        return None

def actualizar_resultados_pendientes():
    """
    Busca y actualiza resultados de todos los partidos pendientes 
    en todas las jornadas activas.
    """
    # Cargar resultados del mundial existentes
    try:
        with open(RESULTADOS_MUNDIAL, encoding="utf-8") as f:
            data_mundial = json.load(f)
    except:
        data_mundial = {"resultados": []}
    
    indice_mundial = {
        (r.get("local","").lower(), r.get("visitante","").lower()): r
        for r in data_mundial.get("resultados", [])
    }
    
    cambios_totales = 0
    
    # Procesar cada jornada
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = json.load(open(path, encoding="utf-8"))
        partidos = data.get("partidos", [])
        cambios_jornada = 0
        
        for p in partidos:
            # Solo procesar si está pendiente
            resultado_actual = p.get("resultado", "Pendiente")
            if resultado_actual != "Pendiente" and re.match(r"^\d+-\d+$", str(resultado_actual)):
                continue
            
            # Solo si ya debería haber terminado
            if not partido_ya_terminado(p.get("fecha"), p.get("hora")):
                continue
            
            local = p.get("local", "")
            visitante = p.get("visitante", "")
            
            if not local or not visitante:
                continue
            
            # Saltar partidos con nombres de grupos (aún no resueltos)
            if "grupo" in local.lower() or "grupo" in visitante.lower():
                continue
            
            print(f"  Buscando: {local} vs {visitante}...")
            
            # Intentar primero en Google
            resultado = buscar_en_google(local, visitante)
            fuente = "google"
            
            # Si no encuentra, intentar en Flashscore
            if not resultado:
                time.sleep(1)
                resultado = buscar_en_flashscore(local, visitante)
                fuente = "flashscore"
            
            if resultado:
                print(f"  ✅ {local} vs {visitante}: {resultado} (via {fuente})")
                
                # Actualizar en jornada
                p["resultado"] = resultado
                p["signo_oficial"] = (
                    "1" if int(resultado.split("-")[0]) > int(resultado.split("-")[1])
                    else "X" if resultado.split("-")[0] == resultado.split("-")[1]
                    else "2"
                )
                p["fuente_resultado"] = fuente
                p["actualizado_en"] = datetime.now(timezone.utc).isoformat()
                cambios_jornada += 1
                cambios_totales += 1
                
                # También actualizar en mundial_2026_resultados.json si es partido del mundial
                clave = (local.lower(), visitante.lower())
                indice_mundial[clave] = {
                    "local": local,
                    "visitante": visitante,
                    "resultado": resultado,
                    "fuente": fuente,
                    "confianza": "confirmado",
                    "actualizado_en": datetime.now(timezone.utc).isoformat()
                }
            else:
                print(f"  ⚠️  {local} vs {visitante}: sin resultado")
            
            time.sleep(2)  # Pausa entre búsquedas para no saturar
        
        # Guardar jornada si hubo cambios
        if cambios_jornada:
            todos_con_resultado = all(
                re.match(r"^\d+-\d+$", str(p.get("resultado","")))
                for p in partidos
            )
            data["estado"] = "cerrada" if todos_con_resultado else "en_juego"
            data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  Jornada {data.get('jornada')}: {cambios_jornada} resultados actualizados")
    
    # Guardar mundial actualizado
    if cambios_totales:
        data_mundial["resultados"] = list(indice_mundial.values())
        data_mundial["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        with open(RESULTADOS_MUNDIAL, "w", encoding="utf-8") as f:
            json.dump(data_mundial, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Total: {cambios_totales} resultados actualizados")
    return cambios_totales

if __name__ == "__main__":
    actualizar_resultados_pendientes()
