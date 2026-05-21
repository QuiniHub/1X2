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

INTERMEDIO = '''      if (visitanteVivo && top === "1") bonus += 16;
      if (localVivo && top === "2") bonus += 16;
      if (visitanteVivo && contieneDescensoVivoBoleto(visitanteComp) && top === "1") bonus += 40;
      if (localVivo && contieneDescensoVivoBoleto(localComp) && top === "2") bonus += 40;
      if (contieneDescensoVivoBoleto(localComp) || contieneDescensoVivoBoleto(visitanteComp)) bonus += 10;
      if ((probs?.["X"] || 0) >= 30) bonus += 6;
      if (margen < 18) bonus += 8;
      if (valores[0] < 55) bonus += 8;

      return Math.min(bonus, 80);
'''

NEW = '''      if (visitanteVivo && top === "1") bonus += 16;
      if (localVivo && top === "2") bonus += 16;
      if (visitanteVivo && contieneDescensoVivoBoleto(visitanteComp) && top === "1") bonus += 70;
      if (localVivo && contieneDescensoVivoBoleto(localComp) && top === "2") bonus += 70;
      if (contieneDescensoVivoBoleto(localComp) || contieneDescensoVivoBoleto(visitanteComp)) bonus += 10;
      if ((probs?.["X"] || 0) >= 30) bonus += 6;
      if (margen < 18) bonus += 8;
      if (valores[0] < 55) bonus += 8;

      return Math.min(bonus, 110);
'''


def main():
    html = INDEX.read_text(encoding="utf-8")
    if "bonus += 70" in html and "Math.min(bonus, 110)" in html:
        print("Refuerzo alto de coberturas por descenso ya aplicado.")
        return
    if INTERMEDIO in html:
        html = html.replace(INTERMEDIO, NEW, 1)
        INDEX.write_text(html, encoding="utf-8")
        print("Refuerzo alto de coberturas por descenso aplicado.")
        return
    if OLD in html:
        html = html.replace(OLD, NEW, 1)
        INDEX.write_text(html, encoding="utf-8")
        print("Refuerzo alto de coberturas por descenso aplicado.")
        return
    print("Refuerzo alto de coberturas por descenso sin cambios: la logica nueva ya sustituyo el bloque antiguo.")


if __name__ == "__main__":
    main()
