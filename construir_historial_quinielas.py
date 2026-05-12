import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
JORNADAS_DIR = ROOT / "data" / "jornadas"
SALIDA = ROOT / "data" / "historial_quinielas.json"


def cargar_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def signo_valido(signo):
    return str(signo or "").strip().upper() in {"1", "X", "2"}


def nuestra_jugada(partido):
    signo = str(partido.get("signo_nuestro") or "").strip()
    return signo and "NO JUGADA" not in signo.upper()


def resumen_jornada(path):
    data = cargar_json(path)
    partidos = data.get("partidos", [])
    signos = []
    nuestros = []

    for partido in partidos:
        oficial = str(partido.get("signo_oficial") or "").strip().upper()
        nuestro = str(partido.get("signo_nuestro") or "").strip().upper()
        if signo_valido(oficial):
            signos.append(oficial)
        if nuestra_jugada(partido):
            nuestros.append(nuestro)

    pleno = data.get("pleno15") or {}
    pleno_oficial = str(pleno.get("signo_oficial") or pleno.get("resultado") or "").strip()
    pleno_nuestro = str(pleno.get("signo_nuestro") or "").strip()

    return {
        "jornada": int(data.get("jornada") or re.search(r"(\d+)", path.stem).group(1)),
        "fecha": data.get("fecha") or "",
        "fuente": data.get("fuente") or "",
        "resultado_oficial": "".join(signos) if len(signos) == 14 else "Pendiente",
        "pleno15_oficial": pleno_oficial if pleno_oficial and pleno_oficial.lower() != "pendiente" else "Pendiente",
        "nuestra_quiniela": " ".join(nuestros) if nuestros else "No validada",
        "pleno15_nuestro": pleno_nuestro if pleno_nuestro and "no jugada" not in pleno_nuestro.lower() else "No validada",
        "partidos_con_resultado": len(signos),
        "total_partidos": len(partidos),
        "validada": bool(nuestros),
        "estado": "cerrada" if len(signos) == 14 else "abierta",
    }


def main():
    jornadas = []
    for path in sorted(JORNADAS_DIR.glob("jornada_*.json"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
        jornadas.append(resumen_jornada(path))

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(
            {
                "version": "1.0",
                "total_jornadas": len(jornadas),
                "jornadas": jornadas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Historial Quiniela generado: {SALIDA} ({len(jornadas)} jornadas)")


if __name__ == "__main__":
    main()
