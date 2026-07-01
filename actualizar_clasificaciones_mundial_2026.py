"""ELIMINADO: Mundial 2026 — script desactivado. Solo conserva exports para compatibilidad."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"

EQUIPO_A_GRUPO = {}


def normalizar_nombre(nombre):
    return nombre.lower().strip()


if __name__ == "__main__":
    print("Script Mundial 2026 desactivado — sin accion.")
