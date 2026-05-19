import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CLASIFICACIONES = [
    DATA / "clasificaciones_oficiales.json",
    ROOT / "clasificaciones.json",
]
MEMORIAS = [
    DATA / "memoria_ia" / "aprendizaje_global.json",
    DATA / "temporadas" / "2025_2026" / "resumen_temporada.json",
]
LIGAS = ("primera", "segunda")


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(
        r"\b(cf|fc|rcd|rc|cd|ud|sd|sad|club|real|de|del|la|el|balompie|futbol)\b",
        " ",
        texto,
    )
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def cargar_clasificaciones():
    salida = {liga: {} for liga in LIGAS}
    for path in CLASIFICACIONES:
        data = cargar_json(path, {})
        for liga in LIGAS:
            for equipo in data.get(liga, []) or []:
                nombre = equipo.get("equipo")
                clave = normalizar(nombre)
                if not clave:
                    continue
                salida[liga][clave] = equipo
    return salida


def buscar_equipo(indice, nombre):
    clave = normalizar(nombre)
    if clave in indice:
        return indice[clave]
    piezas = set(clave.split())
    mejor = None
    mejor_score = 0
    for candidato, equipo in indice.items():
        score = len(piezas & set(candidato.split()))
        if clave and (clave in candidato or candidato in clave):
            score += 3
        if score > mejor_score:
            mejor = equipo
            mejor_score = score
    return mejor if mejor_score >= 1 else None


def copiar_dinamica(destino, fuente):
    cambios = 0
    for clave in ("posicion", "pj", "g", "e", "p", "gf", "gc", "dg", "pts"):
        if clave in fuente and destino.get(clave) != fuente.get(clave):
            destino[clave] = fuente.get(clave)
            cambios += 1
    if "puntos" in fuente:
        destino["pts"] = fuente.get("puntos")
    tendencias_fuente = fuente.get("tendencias") or {}
    tendencias_destino = destino.setdefault("tendencias", {})
    for clave in (
        "puntos_por_partido",
        "goles_favor_por_partido",
        "goles_contra_por_partido",
        "empates_pct",
        "forma_5_pts",
        "forma_10_pts",
    ):
        if clave in tendencias_fuente and tendencias_destino.get(clave) != tendencias_fuente.get(clave):
            tendencias_destino[clave] = tendencias_fuente.get(clave)
            cambios += 1
    if fuente.get("racha_actual") and destino.get("racha_actual") != fuente.get("racha_actual"):
        destino["racha_actual"] = fuente.get("racha_actual")
        cambios += 1
    return cambios


def sincronizar_memoria(path, clasificaciones):
    data = cargar_json(path, {})
    if not data:
        return 0, []
    cambios = 0
    faltantes = []
    for liga in LIGAS:
        equipos = ((data.get("ligas") or {}).get(liga) or {}).get("equipos", [])
        indice = clasificaciones.get(liga, {})
        for equipo in equipos:
            fuente = buscar_equipo(indice, equipo.get("equipo", ""))
            if not fuente:
                faltantes.append(f"{liga}:{equipo.get('equipo')}")
                continue
            cambios += copiar_dinamica(equipo, fuente)
    guardar_json(path, data)
    return cambios, faltantes


def main():
    clasificaciones = cargar_clasificaciones()
    cambios_totales = 0
    faltantes_totales = []
    for path in MEMORIAS:
        cambios, faltantes = sincronizar_memoria(path, clasificaciones)
        cambios_totales += cambios
        faltantes_totales.extend(faltantes)
    if faltantes_totales:
        print("Equipos sin sincronizar: " + ", ".join(sorted(set(faltantes_totales))))
    print(f"Dinamicas sincronizadas con memoria IA: {cambios_totales} cambios.")


if __name__ == "__main__":
    main()
