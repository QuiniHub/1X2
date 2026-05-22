from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

FUNCIONES = r'''

    function probabilidadSignoElige8Web(item) {
      const partido = item?.partido || item || {};
      const probs = partido.probabilidades || {};
      const signos = String(item?.signos || partido.signo_base || partido.signo_final || "")
        .replace(/[^1X2]/g, "")
        .split("");
      const candidatos = signos.length ? signos : ["1", "X", "2"];
      return candidatos.reduce((max, signo) => Math.max(max, Number(probs[signo] || 0)), 0);
    }

    function signoObjetivoElige8Web(item) {
      const partido = item?.partido || item || {};
      const probs = partido.probabilidades || {};
      const signos = String(item?.signos || partido.signo_base || partido.signo_final || "")
        .replace(/[^1X2]/g, "")
        .split("");
      const candidatos = signos.length ? signos : ["1", "X", "2"];
      return candidatos.sort((a, b) => Number(probs[b] || 0) - Number(probs[a] || 0))[0] || "";
    }

    function puntuacionElige8CobroWeb(item) {
      const partido = item?.partido || item || {};
      const signo = signoObjetivoElige8Web(item);
      const prob = probabilidadSignoElige8Web(item);
      const incertidumbre = Number(partido.incertidumbre || item?.riesgo || 0);
      const sorpresa = Number(partido.probabilidad_sorpresa || 0);
      let score = prob * 3 - incertidumbre * 0.08 - sorpresa * 0.12;

      if (signo === "X" && prob < 55) score -= 25;
      else if (signo === "X" && prob < 60) score -= 10;

      if (item?.tipo === "TRIPLE") score -= 8;
      if (partido.riesgo_necesidad_real) score -= 2;
      return score;
    }

    function candidatosElige8CobroWeb(detalle) {
      return [...detalle]
        .sort((a, b) => {
          const scoreA = puntuacionElige8CobroWeb(a);
          const scoreB = puntuacionElige8CobroWeb(b);
          if (scoreA !== scoreB) return scoreB - scoreA;
          return probabilidadSignoElige8Web(b) - probabilidadSignoElige8Web(a);
        })
        .slice(0, 8);
    }
'''

BLOQUE_ANTIGUO = r'''      const elige8Candidatos = [...detalle]
        .sort((a, b) => {
          const pesoA = a.tipo === "TRIPLE" ? 0 : a.tipo === "DOBLE" ? 1 : 2;
          const pesoB = b.tipo === "TRIPLE" ? 0 : b.tipo === "DOBLE" ? 1 : 2;
          if (pesoA !== pesoB) return pesoA - pesoB;
          return a.riesgo - b.riesgo;
        })
        .slice(0, 8);'''

BLOQUE_NUEVO = r'''      const elige8Candidatos = candidatosElige8CobroWeb(detalle);'''

LECTURA_ANTIGUA = "porque concentra la proteccion en los partidos cubiertos y en los fijos mas limpios."
LECTURA_NUEVA = "porque marca los 8 signos con mayor probabilidad real de cobro, no los partidos mas vistosos."


def main():
    html = INDEX.read_text(encoding="utf-8")
    original = html

    if "function candidatosElige8CobroWeb" not in html:
        html = html.replace("    function evaluarConfiguracionEstrategia(partidosBase, dobles, triples, elige8 = false) {", FUNCIONES + "\n    function evaluarConfiguracionEstrategia(partidosBase, dobles, triples, elige8 = false) {")

    if BLOQUE_ANTIGUO not in html:
        raise SystemExit("No encuentro el bloque antiguo de Elige 8 en index.html")
    html = html.replace(BLOQUE_ANTIGUO, BLOQUE_NUEVO)
    html = html.replace(LECTURA_ANTIGUA, LECTURA_NUEVA)

    if html != original:
        INDEX.write_text(html, encoding="utf-8")
        print("Elige 8 web corregido: ahora prioriza probabilidad de cobro.")
    else:
        print("Elige 8 web ya estaba corregido.")


if __name__ == "__main__":
    main()
