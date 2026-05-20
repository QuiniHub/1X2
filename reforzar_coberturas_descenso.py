from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

OLD = '''      if (visitanteVivo && top === "1") bonus += 16;
      if (localVivo && top === "2") bonus += 16;
      if (contieneDescensoVivoBoleto(localComp) || contieneDescensoVivoBoleto(visitanteComp)) bonus += 10;
      if ((probs?.["X"] || 0) >= 30) bonus += 6;
      if (margen < 18) bonus += 8;
      if (valores[0] < 55) bonus += 8;

      return Math.min(bonus, 44);
'''

NEW = '''      if (visitanteVivo && top === "1") bonus += 16;
      if (localVivo && top === "2") bonus += 16;
      if (visitanteVivo && contieneDescensoVivoBoleto(visitanteComp) && top === "1") bonus += 40;
      if (localVivo && contieneDescensoVivoBoleto(localComp) && top === "2") bonus += 40;
      if (contieneDescensoVivoBoleto(localComp) || contieneDescensoVivoBoleto(visitanteComp)) bonus += 10;
      if ((probs?.["X"] || 0) >= 30) bonus += 6;
      if (margen < 18) bonus += 8;
      if (valores[0] < 55) bonus += 8;

      return Math.min(bonus, 80);
'''


def main():
    html = INDEX.read_text(encoding="utf-8")
    if "contieneDescensoVivoBoleto(visitanteComp) && top === \"1\"" in html and "Math.min(bonus, 80)" in html:
        print("Refuerzo de coberturas por descenso ya aplicado.")
        return
    if OLD not in html:
        raise SystemExit("No encuentro el bloque de bonus competitivo original.")
    INDEX.write_text(html.replace(OLD, NEW, 1), encoding="utf-8")
    print("Refuerzo de coberturas por descenso aplicado.")


if __name__ == "__main__":
    main()
