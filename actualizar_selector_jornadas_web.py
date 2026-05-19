import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
JORNADAS = ROOT / "data" / "jornadas"
INDEX = ROOT / "index.html"


def jornadas_disponibles():
    numeros = []
    for path in JORNADAS.glob("jornada_*.json"):
        match = re.search(r"(\d+)", path.stem)
        if match:
            numeros.append(int(match.group(1)))
    return sorted(numeros)


def main():
    jornadas = jornadas_disponibles()
    if not jornadas:
        print("No hay jornadas para actualizar el selector web.")
        return

    ultima = max(jornadas)
    html = INDEX.read_text(encoding="utf-8")
    original = html

    html = re.sub(
        r"for \(let j = 1; j <= \d+; j\+\+\) \{",
        f"for (let j = 1; j <= {ultima}; j++) {{",
        html,
        count=1,
    )
    html = re.sub(
        r"abrirQuinielaIA\(\d+\);",
        f"abrirQuinielaIA({ultima});",
        html,
        count=1,
    )
    html = html.replace(
        "<h2>Estado vivo para jornada 63</h2>",
        "<h2>Estado vivo de la jornada activa</h2>",
    )
    html = html.replace("pred.jornada || 63", "pred.jornada || \"-\"")
    html = html.replace("respuestaJornada(data.historial, 63)", "respuestaJornada(data.historial, Number(data.prediccion?.jornada || 0))")
    html = html.replace("si no puede cargar, abre por defecto la jornada 63", "si no puede cargar, abre por defecto la ultima jornada disponible")

    if html != original:
        INDEX.write_text(html, encoding="utf-8")
        print(f"Selector web actualizado hasta jornada {ultima}.")
    else:
        print(f"Selector web ya estaba actualizado hasta jornada {ultima}.")


if __name__ == "__main__":
    main()
