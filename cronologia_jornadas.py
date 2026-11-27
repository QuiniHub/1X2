# -*- coding: utf-8 -*-
"""Cronologia comun de las jornadas de La Quiniela (modulo SIN efectos secundarios).

POR QUE EXISTE
--------------
La numeracion de La Quiniela se reinicia cada temporada a mediados de agosto.
En data/jornadas conviven J1-J27 de la 26/27 con J28-J76 de la 25/26, asi que
"la jornada mas alta" NO es la mas reciente y "jornada 24" no identifica una
jornada por si sola. Regla del proyecto: NUNCA ordenar, filtrar ni identificar
jornadas solo por numero. Este modulo es la unica fuente de verdad para:

  * convertir cualquier texto de fecha del repo en un date,
  * saber la fecha real y la temporada de un fichero jornada_N.json,
  * recorrer las jornadas en orden cronologico,
  * leer "lo que se dijo antes del cierre" (snapshot pre-cierre) comprobando
    que el snapshot es de la MISMA jornada real y no de otra temporada.

Solo lee de data/. No escribe nada, no accede a la red y no consulta el reloj
del sistema: quien necesite "hoy" lo pasa en el parametro opcional `hoy`.

API (estable)
-------------
parsear_fecha(texto, anio_por_defecto=None) -> date | None
    Acepta date/datetime, ISO 'YYYY-MM-DD[...]', 'dd/mm/yyyy', 'd/m/yyyy,',
    'dd-mm-yyyy', 'La Quiniela Domingo, 14 de diciembre de 2025',
    '13 de Mayo de 2026' y '13 de Mayo' (sin anio devuelve None salvo que se
    pase anio_por_defecto). Repara mojibake comun (UTF-8 leido como Latin-1
    y el caracter de reemplazo U+FFFD).

fecha_real_jornada(datos_jornada) -> date | None
    Fecha del primer partido: el MAS TEMPRANO con fecha valida (en J6, J26,
    J74 y J75 el partido num 1 no es el primero que se juega). Si ningun
    partido trae fecha, la fecha de la jornada (campo 'fecha').

fecha_fin_jornada(datos_jornada) -> date | None
    Fecha del ultimo partido con fecha valida (o la fecha de la jornada).

temporada_de_fecha(fecha, numero=None) -> 'YYYY_YYYY' | None
    Etiqueta de temporada. Sin numero el corte es el 12 de agosto. Con numero
    se desambigua julio/agosto: numero <= 15 es temporada que EMPIEZA ese
    anio; numero >= 40 es temporada que ACABA ese anio (J76 de 25/26 se jugo
    el 07-09/08/2026 y J1 de 26/27 el 15/08/2026).

clave_jornada(numero, fecha) -> (temporada, numero)
    Clave para indexar marcadores y diccionarios sin mezclar temporadas.

jornada_cerrada(datos_jornada) -> bool
    True si los partidos 1-14 tienen signo oficial valido (1/X/2).

indice_jornadas(dir_jornadas=None) -> list[dict]
    Un dict por fichero jornada_N.json con las claves
      numero (int), fecha (date|None), temporada (str|None),
      cerrada (bool: 14 signos oficiales validos), ruta (str),
    mas dos de ayuda: fecha_fin (date|None) y estado (str|None).
    Orden CRONOLOGICO (fecha, numero); las que no tienen fecha van al final
    ordenadas por numero (determinista).

jornadas_cronologicas(solo_cerradas=False, temporada=None, dir_jornadas=None)
    El indice anterior filtrado. `temporada` admite '2026_2027', '2026/2027',
    '2026-2027' o '2026/27'.

ultima_jornada_cerrada(hoy=None, temporada=None, dir_jornadas=None) -> dict | None
    La jornada cerrada mas reciente POR FECHA (si se pasa hoy, no posterior).

jornada_en_curso_o_proxima(hoy=None, temporada=None, dir_jornadas=None) -> dict | None
    La primera jornada no cerrada por FECHA. Con hoy: la primera no cerrada
    cuyo ultimo partido no es anterior a hoy - 3 dias (se saltan restos viejos
    sin cerrar). Sin hoy: la primera no cerrada posterior a la ultima cerrada.

cargar_jornada(numero, dir_jornadas=None) -> dict | None
    Lee data/jornadas/jornada_N.json (None si no existe o esta roto).

normalizar_equipo(nombre) -> str ; mismo_equipo(a, b) -> bool
    Comparacion tolerante de nombres ('B. Dortmund' ~ 'Borussia Dortmund').

misma_jornada(datos_a, datos_b) -> bool
    True si los partidos de ambos dicts (o listas de partidos) son los mismos
    equipos: al menos 7 partidos y la mitad coinciden. Sirve para detectar
    ficheros jornada_N de temporadas distintas.

snapshot_del_cierre(numero, dir_snapshots=None, dir_jornadas=None) -> dict | None
prediccion_del_cierre(numero, dir_snapshots=None, dir_jornadas=None) -> dict | None
    Snapshot data/backtesting/pre_cierre/jornada_N.json (y su campo
    'prediccion') SOLO si corresponde a la misma jornada real que
    data/jornadas/jornada_N.json: mismos equipos o, si no, primer_partido_utc
    a <= 2 dias de la fecha real. None si no existe, no se puede comprobar o
    es de otra temporada. OJO: data/predicciones/jornada_N.json se regenera
    despues del cierre y NO sirve como "lo que se dijo antes".
"""

import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_JORNADAS = RAIZ / "data" / "jornadas"
DIR_SNAPSHOTS = RAIZ / "data" / "backtesting" / "pre_cierre"

SIGNOS_VALIDOS = ("1", "X", "2")

# Corte de temporada cuando no hay numero de jornada para desambiguar.
MES_CORTE = 8
DIA_CORTE = 12
# Con numero: en julio/agosto un numero bajo es temporada nueva y uno alto es
# el final de la anterior (la 25/26 llego a J76 el 09/08/2026).
NUMERO_BAJO_MAX = 15
NUMERO_ALTO_MIN = 40
# Partidos con los mismos equipos para dar dos ficheros por la misma jornada.
UMBRAL_PARTIDOS_IGUALES = 7

_MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}
_DIAS_SEMANA = {
    "lunes", "martes", "miercoles", "mircoles", "jueves", "viernes",
    "sabado", "sbado", "domingo",
}

_RE_FICHERO = re.compile(r"^jornada_(\d+)\.json$")
_RE_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_RE_BARRAS = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{4}|\d{2}))?(?!\d)")
_RE_TEXTO = re.compile(r"(?<!\d)(\d{1,2})\s*(?:de\s+)?([a-z]{3,})\.?(?:\s*(?:del|de)?\s*(\d{4}))?")


# ---------------------------------------------------------------- texto

def reparar_mojibake(texto):
    """Devuelve el texto con el mojibake UTF-8/Latin-1 mas comun reparado."""
    if not isinstance(texto, str):
        return texto
    # chr(0xC3)/chr(0xC2): asi se ve un acento UTF-8 leido como Latin-1.
    if chr(0xC3) in texto or chr(0xC2) in texto:
        for codec in ("cp1252", "latin-1"):
            try:
                return texto.encode(codec).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
    return texto


def _sin_acentos(texto):
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _fecha_segura(anio, mes, dia):
    try:
        return date(int(anio), int(mes), int(dia))
    except (TypeError, ValueError):
        return None


def parsear_fecha(texto, anio_por_defecto=None):
    """Convierte cualquier fecha del repo en date. None si no se entiende."""
    if texto is None:
        return None
    if isinstance(texto, datetime):
        return texto.date()
    if isinstance(texto, date):
        return texto
    if not isinstance(texto, str):
        return None
    limpio = reparar_mojibake(texto).strip()
    if not limpio:
        return None

    m = _RE_ISO.search(limpio)
    if m:
        return _fecha_segura(m.group(1), m.group(2), m.group(3))

    plano = _sin_acentos(limpio).lower().replace(chr(0xFFFD), "")

    m = _RE_BARRAS.search(plano)
    if m:
        dia, mes, anio = m.group(1), m.group(2), m.group(3)
        if anio is None:
            anio = anio_por_defecto
        elif len(anio) == 2:
            anio = 2000 + int(anio)
        if anio is None:
            return None
        return _fecha_segura(anio, mes, dia)

    for m in _RE_TEXTO.finditer(plano):
        palabra = m.group(2)
        # 'martes' empieza como 'mar(zo)': un dia de la semana no es un mes.
        if palabra in _DIAS_SEMANA:
            continue
        mes = _MESES.get(palabra[:3])
        if mes is None:
            continue
        anio = m.group(3) or anio_por_defecto
        if anio is None:
            return None
        return _fecha_segura(anio, mes, m.group(1))
    return None


# ---------------------------------------------------------------- jornada

def _partidos(datos):
    if isinstance(datos, list):
        return [p for p in datos if isinstance(p, dict)]
    if isinstance(datos, dict):
        ps = datos.get("partidos")
        if isinstance(ps, list):
            return [p for p in ps if isinstance(p, dict)]
    return []


def _fecha_cabecera(datos):
    if not isinstance(datos, dict):
        return None
    for clave in ("fecha", "fecha_jornada"):
        f = parsear_fecha(datos.get(clave))
        if f:
            return f
    return None


def _fechas_partidos(datos):
    """Fechas validas de los partidos, sin erratas lejanas a la cabecera."""
    cabecera = _fecha_cabecera(datos)
    anio = cabecera.year if cabecera else None
    fechas = []
    for p in _partidos(datos):
        f = parsear_fecha(p.get("fecha"), anio_por_defecto=anio)
        if f is None:
            continue
        if cabecera and abs((f - cabecera).days) > 10:
            continue
        fechas.append(f)
    return fechas, cabecera


def fecha_real_jornada(datos_jornada):
    """Fecha del primer partido (el mas temprano) o, si no hay, la de la jornada."""
    fechas, cabecera = _fechas_partidos(datos_jornada)
    if fechas:
        return min(fechas)
    return cabecera


def fecha_fin_jornada(datos_jornada):
    """Fecha del ultimo partido con fecha valida o, si no hay, la de la jornada."""
    fechas, cabecera = _fechas_partidos(datos_jornada)
    if fechas:
        return max(fechas)
    return cabecera


def temporada_de_fecha(fecha, numero=None):
    """Etiqueta 'YYYY_YYYY' de la temporada a la que pertenece una jornada."""
    f = parsear_fecha(fecha)
    if f is None:
        return None
    empieza_este_anio = (f.month, f.day) >= (MES_CORTE, DIA_CORTE)
    if numero is not None and f.month in (7, 8):
        try:
            n = int(numero)
        except (TypeError, ValueError):
            n = None
        if n is not None:
            if n <= NUMERO_BAJO_MAX:
                empieza_este_anio = True
            elif n >= NUMERO_ALTO_MIN:
                empieza_este_anio = False
    inicio = f.year if empieza_este_anio else f.year - 1
    return "%d_%d" % (inicio, inicio + 1)


def _normalizar_temporada(temporada):
    if temporada is None:
        return None
    texto = str(temporada)
    anios = re.findall(r"\d{4}", texto)
    if len(anios) >= 2:
        return "%s_%s" % (anios[0], anios[1])
    m = re.match(r"^\s*(\d{4})\D+(\d{2})\s*$", texto)
    if m:
        return "%s_%s%s" % (m.group(1), m.group(1)[:2], m.group(2))
    return texto


def clave_jornada(numero, fecha):
    """(temporada, numero): clave que no mezcla la J24 de dos temporadas."""
    return (temporada_de_fecha(fecha, numero), int(numero))


def _signo(valor):
    return str(valor).strip().upper() if valor is not None else ""


def jornada_cerrada(datos_jornada):
    """True si hay 14 signos oficiales validos (1/X/2) en los partidos 1-14."""
    por_num = {}
    for i, p in enumerate(_partidos(datos_jornada)):
        try:
            num = int(p.get("num", i + 1))
        except (TypeError, ValueError):
            num = i + 1
        por_num.setdefault(num, p)
    return all(
        n in por_num and _signo(por_num[n].get("signo_oficial")) in SIGNOS_VALIDOS
        for n in range(1, 15)
    )


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def cargar_jornada(numero, dir_jornadas=None):
    """Lee jornada_N.json; None si no existe o no es un JSON valido."""
    base = Path(dir_jornadas) if dir_jornadas else DIR_JORNADAS
    datos = _leer_json(base / ("jornada_%d.json" % int(numero)))
    return datos if isinstance(datos, dict) else None


def indice_jornadas(dir_jornadas=None):
    """Indice de todas las jornadas en orden cronologico (sin fecha, al final)."""
    base = Path(dir_jornadas) if dir_jornadas else DIR_JORNADAS
    filas = []
    if not base.is_dir():
        return filas
    for ruta in base.iterdir():
        m = _RE_FICHERO.match(ruta.name)
        if not m:
            continue
        datos = _leer_json(ruta)
        if not isinstance(datos, dict):
            continue
        numero = int(m.group(1))
        fecha = fecha_real_jornada(datos)
        estado = datos.get("estado")
        filas.append({
            "numero": numero,
            "fecha": fecha,
            "temporada": temporada_de_fecha(fecha, numero) if fecha else None,
            "cerrada": jornada_cerrada(datos),
            "ruta": str(ruta),
            "fecha_fin": fecha_fin_jornada(datos),
            "estado": estado if isinstance(estado, str) else None,
        })
    filas.sort(key=lambda j: (j["fecha"] is None, j["fecha"] or date.min, j["numero"]))
    return filas


def jornadas_cronologicas(solo_cerradas=False, temporada=None, dir_jornadas=None):
    """Jornadas en orden cronologico, opcionalmente solo cerradas o de una temporada."""
    temporada = _normalizar_temporada(temporada)
    salida = []
    for j in indice_jornadas(dir_jornadas):
        if solo_cerradas and not j["cerrada"]:
            continue
        if temporada is not None and j["temporada"] != temporada:
            continue
        salida.append(j)
    return salida


def ultima_jornada_cerrada(hoy=None, temporada=None, dir_jornadas=None):
    """La jornada cerrada mas reciente por FECHA real (no por numero)."""
    hoy = parsear_fecha(hoy)
    candidatas = [
        j for j in jornadas_cronologicas(True, temporada, dir_jornadas)
        if j["fecha"] is not None and (hoy is None or j["fecha"] <= hoy)
    ]
    return candidatas[-1] if candidatas else None


def jornada_en_curso_o_proxima(hoy=None, temporada=None, dir_jornadas=None):
    """La primera jornada no cerrada por FECHA real (en curso o proxima)."""
    hoy = parsear_fecha(hoy)
    todas = jornadas_cronologicas(False, temporada, dir_jornadas)
    abiertas = [j for j in todas if not j["cerrada"] and j["fecha"] is not None]
    if hoy is not None:
        limite = hoy - timedelta(days=3)
        for j in abiertas:
            if (j["fecha_fin"] or j["fecha"]) >= limite:
                return j
        return None
    cerradas = [j for j in todas if j["cerrada"] and j["fecha"] is not None]
    if cerradas:
        ultima = cerradas[-1]["fecha"]
        abiertas = [j for j in abiertas if j["fecha"] > ultima]
    return abiertas[0] if abiertas else None


# ---------------------------------------------------------------- equipos

# Siglas que no distinguen a un club. No se quitan 'real' ni 'atletico':
# distinguen al Real Madrid del Atletico de Madrid.
_PALABRAS_VACIAS = {
    "cf", "fc", "cd", "ud", "sd", "rcd", "rc", "ca", "sad", "ad", "cp", "sc",
    "ac", "as", "afc", "club", "de", "del", "la", "el", "los", "las", "futbol",
    # Marcas de equipo femenino: '(F)', 'W', 'Women'.
    "f", "w", "women", "femenino",
}


def normalizar_equipo(nombre):
    """Nombre de equipo en minusculas, sin acentos, puntuacion ni siglas vacias."""
    if not isinstance(nombre, str):
        return ""
    plano = _sin_acentos(reparar_mojibake(nombre)).lower()
    plano = re.sub(r"[^a-z0-9]+", " ", plano)
    return " ".join(t for t in plano.split() if t not in _PALABRAS_VACIAS)


def _tokens_compatibles(a, b):
    # Abreviaturas: 'b' ~ 'borussia', 'man' ~ 'manchester', 'at' ~ 'atletico'.
    corto, largo = (a, b) if len(a) <= len(b) else (b, a)
    return largo.startswith(corto)


def mismo_equipo(nombre_a, nombre_b):
    """True si dos nombres son el mismo club ('B. Dortmund' ~ 'Borussia Dortmund')."""
    a, b = normalizar_equipo(nombre_a), normalizar_equipo(nombre_b)
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = a.split(), b.split()
    corto, largo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    usados = set()
    hay_token_largo = False
    for t in corto:
        for i, u in enumerate(largo):
            if i not in usados and _tokens_compatibles(t, u):
                usados.add(i)
                if min(len(t), len(u)) >= 3:
                    hay_token_largo = True
                break
        else:
            return False
    # Una inicial sola ('B.') no basta: hace falta al menos una palabra real.
    return hay_token_largo


def _pares(datos):
    pares = []
    for p in _partidos(datos)[:14]:
        local, visitante = p.get("local"), p.get("visitante")
        if (isinstance(local, str) and isinstance(visitante, str)
                and local.strip() and visitante.strip()):
            pares.append((local, visitante))
    return pares


def coincidencia_equipos(datos_a, datos_b):
    """(coinciden, comparables) entre los 14 primeros partidos de A y de B."""
    pa, pb = _pares(datos_a), _pares(datos_b)
    if not pa or not pb:
        return 0, 0
    libres = list(pb)
    coinciden = 0
    for la, va in pa:
        for i, (lb, vb) in enumerate(libres):
            if mismo_equipo(la, lb) and mismo_equipo(va, vb):
                coinciden += 1
                del libres[i]
                break
    return coinciden, min(len(pa), len(pb))


def misma_jornada(datos_a, datos_b):
    """True si ambos describen los mismos partidos (al menos 7 y la mitad)."""
    # Medido en el repo: dos jornadas reales distintas nunca comparten 3 o mas
    # partidos, y un snapshot de su propia jornada comparte 9 o mas salvo que
    # la fuente cambie todos los nombres (J22 femenina: 5/14, la salva la fecha).
    coinciden, comparables = coincidencia_equipos(datos_a, datos_b)
    return coinciden >= UMBRAL_PARTIDOS_IGUALES and coinciden * 2 >= comparables


# ---------------------------------------------------------------- snapshot

def snapshot_del_cierre(numero, dir_snapshots=None, dir_jornadas=None):
    """Snapshot pre-cierre de jornada_N solo si es de la misma jornada real."""
    numero = int(numero)
    base = Path(dir_snapshots) if dir_snapshots else DIR_SNAPSHOTS
    snap = _leer_json(base / ("jornada_%d.json" % numero))
    if not isinstance(snap, dict):
        return None
    pred = snap.get("prediccion")
    if not isinstance(pred, dict):
        return None
    for origen in (snap, pred):
        declarada = origen.get("jornada")
        if declarada is not None:
            try:
                if int(declarada) != numero:
                    return None
            except (TypeError, ValueError):
                return None
    jornada = cargar_jornada(numero, dir_jornadas)
    if jornada is None:
        return None

    if misma_jornada(pred, jornada):
        return snap
    # Sin equipos comparables (o la LAE cambio partidos): manda la fecha.
    primer = parsear_fecha(snap.get("primer_partido_utc"))
    real = fecha_real_jornada(jornada)
    if primer is not None and real is not None and abs((primer - real).days) <= 2:
        return snap
    return None


def prediccion_del_cierre(numero, dir_snapshots=None, dir_jornadas=None):
    """Campo 'prediccion' del snapshot pre-cierre (lo que se dijo ANTES del cierre)."""
    snap = snapshot_del_cierre(numero, dir_snapshots, dir_jornadas)
    return snap.get("prediccion") if snap else None
