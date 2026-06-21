import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUTAS = [ROOT / "data"]


def main():
    errores = []
    total = 0
    for base in RUTAS:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            total += 1
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errores.append(f"{path.relative_to(ROOT)}: {exc}")

    print(f"VALIDACION_JSON: archivos revisados={total}, errores={len(errores)}")
    for error in errores:
        print(f"ERROR_JSON: {error}")
    if errores:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
