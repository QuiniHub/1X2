import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
HISTORIAL = DATA / "historial_quinielas.json"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"

VALORES_SIN_JUGADA = {
    "",
    "NO VALIDADA",
    "NO JUGADA",
    "PENDIENTE",
    "PENDIENTE OFICIAL",
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def numero_jornada_desde_path(path):
    match = re.search(r"jornada_(\d+)", Path(path).stem)
    return int(match.group(1)) if match else 0


def jornadas_cargadas(jornadas_dir=JORNADAS):
    jornadas_dir = Path(jornadas_dir)
    numeros = set()
    for path in jornadas_dir.glob("jornada_*.json"):
        data = cargar_json(path, {})
        numero = data.get("jornada") if isinstance(data, dict) else None
        if not isinstance(numero, int):
            numero = numero_jornada_desde_path(path)
        if numero:
            numeros.add(numero)
    return sorted(numeros)


def normalizar_signos(valor):
    if isinstance(valor, list):
        return [str(signo).strip().upper() for signo in valor if str(signo).strip()][:14]

    texto = str(valor or "").strip().upper()
    if texto in VALORES_SIN_JUGADA:
        return []

    partes = texto.split()
    if len(partes) > 1:
        signos = []
        for parte in partes:
            limpio = "".join(signo for signo in parte if signo in "1X2")
            if limpio:
                signos.append(limpio)
        return signos[:14]

    limpio = "".join(signo for signo in texto if signo in "1X2")
    if len(limpio) == 14:
        return list(limpio)
    return []


def tiene_jugada_nuestra(item):
    if not isinstance(item, dict):
        return False
    if item.get("validada") is True:
        return True
    signos = normalizar_signos(
        item.get("nuestra_quiniela")
        or item.get("signos")
        or item.get("pronostico")
    )
    return len(signos) >= 14


def jornadas_con_memoria(historial_path=HISTORIAL, quinielas_path=QUINIELAS_JUGADAS):
    numeros = set()

    historial = cargar_json(historial_path, {"jornadas": []})
    for item in historial.get("jornadas", []) if isinstance(historial, dict) else []:
        if tiene_jugada_nuestra(item):
            try:
                numeros.add(int(item.get("jornada")))
            except (TypeError, ValueError):
                pass

    jugadas_data = cargar_json(quinielas_path, {"jugadas": []})
    if isinstance(jugadas_data, list):
        jugadas = jugadas_data
    elif isinstance(jugadas_data, dict):
        jugadas = jugadas_data.get("jugadas", [])
    else:
        jugadas = []

    for item in jugadas:
        if tiene_jugada_nuestra(item):
            try:
                numeros.add(int(item.get("jornada")))
            except (TypeError, ValueError):
                pass

    return sorted(numeros)


def ultima_jornada_aprendida(historial_path=HISTORIAL, quinielas_path=QUINIELAS_JUGADAS):
    aprendidas = jornadas_con_memoria(historial_path, quinielas_path)
    return max(aprendidas) if aprendidas else 0


def jornada_objetivo_prediccion(
    jornadas_dir=JORNADAS,
    historial_path=HISTORIAL,
    quinielas_path=QUINIELAS_JUGADAS,
):
    ultima_aprendida = ultima_jornada_aprendida(historial_path, quinielas_path)
    cargadas = jornadas_cargadas(jornadas_dir)
    if ultima_aprendida:
        siguientes_cargadas = [j for j in cargadas if j > ultima_aprendida]
        if siguientes_cargadas:
            return min(siguientes_cargadas)
        return ultima_aprendida + 1

    return max(cargadas) if cargadas else 0


def resumen_jornada_objetivo(
    jornadas_dir=JORNADAS,
    historial_path=HISTORIAL,
    quinielas_path=QUINIELAS_JUGADAS,
):
    cargadas = jornadas_cargadas(jornadas_dir)
    ultima_aprendida = ultima_jornada_aprendida(historial_path, quinielas_path)
    objetivo = jornada_objetivo_prediccion(jornadas_dir, historial_path, quinielas_path)
    max_cargada = max(cargadas) if cargadas else 0
    futuras_cargadas = [j for j in cargadas if objetivo and j > objetivo]
    cargadas_set = set(cargadas)
    primera_pendiente = (ultima_aprendida + 1) if ultima_aprendida else objetivo
    faltantes_intermedias = [
        j
        for j in range(primera_pendiente, max_cargada + 1)
        if primera_pendiente and j not in cargadas_set
    ]

    return {
        "ultima_jornada_aprendida": ultima_aprendida,
        "jornada_objetivo": objetivo,
        "jornada_objetivo_cargada": objetivo in cargadas_set,
        "ultima_jornada_cargada": max_cargada,
        "jornadas_cargadas": cargadas,
        "jornadas_futuras_cargadas": futuras_cargadas,
        "jornadas_intermedias_faltantes": faltantes_intermedias,
    }
