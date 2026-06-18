import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SALIDA = ROOT / "data" / "ultimo_workflow_ok.json"


def main():
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({
        "status": "success",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "workflow": "Actualizar Quiniela IA Pro Completo",
        "mensaje": "Si este archivo se actualiza y queda comiteado por github-actions, el flujo completo llego al final sin errores."
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(SALIDA)


if __name__ == "__main__":
    main()
