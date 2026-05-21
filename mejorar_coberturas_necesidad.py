from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

APPLIED_MARKERS = (
    "Fijo condicionado: el analisis lo marca como peligroso",
    "No es un fijo tranquilo",
)

OLD_FIXED_TEXT = '      let lecturaTipo = "Se deja fijo porque el signo principal mantiene ventaja suficiente frente a las alternativas.";\n'

NEW_FIXED_TEXT = '''      let lecturaTipo = partido.riesgo_necesidad
        ? "Fijo condicionado: el analisis lo marca como peligroso; si hay mas presupuesto debe subir a doble o triple antes que un partido sin necesidad viva."
        : "Se deja fijo porque el signo principal mantiene ventaja suficiente frente a las alternativas.";
'''


def main():
    html = INDEX.read_text(encoding="utf-8")

    if any(marker in html for marker in APPLIED_MARKERS):
        print("Coberturas por necesidad competitiva ya estaban aplicadas.")
        return

    if OLD_FIXED_TEXT in html:
        INDEX.write_text(html.replace(OLD_FIXED_TEXT, NEW_FIXED_TEXT, 1), encoding="utf-8")
        print("Coberturas por necesidad competitiva reforzadas en el boleto IA.")
        return

    print("Coberturas por necesidad competitiva sin cambios: el bloque antiguo ya no existe.")


if __name__ == "__main__":
    main()
