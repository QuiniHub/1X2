from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

MARKERS = (
    "function normalizarNombreEquipoCompleto",
    "function mejorCoincidenciaEquipo",
    "function buscarContextoCompetitivo",
    "function buscarAnalisisIA",
)


def main():
    texto = INDEX.read_text(encoding="utf-8")
    if all(marker in texto for marker in MARKERS):
        print("Emparejamiento robusto de equipos ya estaba aplicado en index.html")
        return
    print("Emparejamiento robusto de equipos sin cambios: no se encontro una estructura segura para modificar.")


if __name__ == "__main__":
    main()
