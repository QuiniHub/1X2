import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ARCHIVOS = [
    ROOT / "clasificaciones.json",
    ROOT / "data" / "clasificaciones_oficiales.json",
]

CORRECCION = {
    "partido": "CD Leganes 0-0 SD Huesca",
    "fecha": "2026-05-18",
    "competicion": "LALIGA HYPERMOTION",
    "temporada": "2025-2026",
}

INICIO_CORRECCION = datetime(2026, 5, 18, tzinfo=timezone.utc)
FIN_CORRECCION = datetime(2026, 7, 1, tzinfo=timezone.utc)


def cargar_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def buscar(tabla, nombre):
    objetivo = normalizar(nombre)
    for equipo in tabla:
        if normalizar(equipo.get("equipo")) == objetivo:
            return equipo
    return None


def correccion_activa():
    ahora = datetime.now(timezone.utc)
    return INICIO_CORRECCION <= ahora <= FIN_CORRECCION


def sumar_empate_si_falta(equipo, pj_objetivo=40):
    if not equipo or int(equipo.get("pj", 0)) >= pj_objetivo:
        return False
    equipo["pj"] = int(equipo.get("pj", 0)) + 1
    equipo["e"] = int(equipo.get("e", 0)) + 1
    equipo["puntos"] = int(equipo.get("puntos", equipo.get("pts", 0))) + 1
    equipo["pts"] = equipo["puntos"]
    equipo["dg"] = int(equipo.get("dg", int(equipo.get("gf", 0)) - int(equipo.get("gc", 0))))
    return True


def reordenar(tabla):
    tabla.sort(key=lambda e: (-int(e.get("puntos", e.get("pts", 0))), -int(e.get("dg", 0)), -int(e.get("gf", 0)), normalizar(e.get("equipo"))))
    for posicion, equipo in enumerate(tabla, start=1):
        equipo["posicion"] = posicion
        equipo["pts"] = int(equipo.get("puntos", equipo.get("pts", 0)))
    return tabla


def corregir_archivo(path):
    data = cargar_json(path)
    segunda = data.get("segunda", [])
    if len(segunda) != 22:
        return False

    leganes = buscar(segunda, "CD Leganes")
    huesca = buscar(segunda, "SD Huesca")
    cambio = False
    cambio = sumar_empate_si_falta(leganes) or cambio
    cambio = sumar_empate_si_falta(huesca) or cambio

    if not cambio:
        return False

    data["segunda"] = reordenar(segunda)
    data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
    fuentes = data.get("fuentes", {}) if isinstance(data.get("fuentes"), dict) else {}
    fuentes["correccion_leganes_huesca"] = CORRECCION
    data["fuentes"] = fuentes
    guardar_json(path, data)
    return True


def main():
    if not correccion_activa():
        print("Correccion Segunda desactivada fuera del cierre 2025-2026.")
        return

    cambios = [str(path) for path in ARCHIVOS if corregir_archivo(path)]
    if cambios:
        print("Correccion Segunda aplicada: Leganes 0-0 Huesca en " + ", ".join(cambios))
    else:
        print("Correccion Segunda no necesaria: Leganes y Huesca ya estaban al dia.")


if __name__ == "__main__":
    main()
