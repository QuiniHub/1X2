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
      if (partido.riesgo_necesidad_real || partido.riesgo_necesidad) score -= 2;
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

BLOQUE_ESTRATEGIA_ANTIGUO = r'''      const elige8Candidatos = [...detalle]
        .sort((a, b) => {
          const pesoA = a.tipo === "TRIPLE" ? 0 : a.tipo === "DOBLE" ? 1 : 2;
          const pesoB = b.tipo === "TRIPLE" ? 0 : b.tipo === "DOBLE" ? 1 : 2;
          if (pesoA !== pesoB) return pesoA - pesoB;
          return a.riesgo - b.riesgo;
        })
        .slice(0, 8);'''

BLOQUE_ESTRATEGIA_NUEVO = r'''      const elige8Candidatos = candidatosElige8CobroWeb(detalle);'''

BLOQUE_GENERAR_ANTIGUO = r'''      const elige8Set = new Set();
      if (activarElige8) {
        const triplesPrimero = partidos
          .filter(p => triplesSet.has(p.num))
          .sort((a, b) => a.incertidumbre - b.incertidumbre);
        const doblesDespues = partidos
          .filter(p => doblesSet.has(p.num))
          .sort((a, b) => a.incertidumbre - b.incertidumbre);
        const fijosSeguros = partidos
          .filter(p => !triplesSet.has(p.num) && !doblesSet.has(p.num))
          .sort((a, b) => a.incertidumbre - b.incertidumbre);

        [...triplesPrimero, ...doblesDespues, ...fijosSeguros]
          .slice(0, 8)
          .forEach(p => elige8Set.add(p.num));
      }'''

BLOQUE_GENERAR_NUEVO = r'''      const elige8Set = new Set();
      if (activarElige8) {
        candidatosElige8CobroWeb(partidos.map(p => ({
          partido: p,
          num: p.num,
          tipo: p.tipo_apuesta,
          signos: p.signo_final,
          riesgo: p.incertidumbre
        }))).forEach(item => elige8Set.add(item.num));
      }'''

LECTURA_ANTIGUA = "porque concentra la proteccion en los partidos cubiertos y en los fijos mas limpios."
LECTURA_NUEVA = "porque marca los 8 signos con mayor probabilidad real de cobro, no los partidos mas vistosos."


def main():
    html = INDEX.read_text(encoding="utf-8")
    original = html

    if "function candidatosElige8CobroWeb" not in html:
        marcador = "    function evaluarConfiguracionEstrategia(partidosBase, dobles, triples, elige8 = false) {"
        if marcador not in html:
            raise SystemExit("No encuentro donde insertar funciones de Elige 8")
        html = html.replace(marcador, FUNCIONES + "\n" + marcador)

    if BLOQUE_ESTRATEGIA_ANTIGUO in html:
        html = html.replace(BLOQUE_ESTRATEGIA_ANTIGUO, BLOQUE_ESTRATEGIA_NUEVO)

    if BLOQUE_GENERAR_ANTIGUO in html:
        html = html.replace(BLOQUE_GENERAR_ANTIGUO, BLOQUE_GENERAR_NUEVO)
    elif BLOQUE_GENERAR_NUEVO in html:
        pass
    else:
        raise SystemExit("No encuentro ni el bloque viejo ni el bloque nuevo de Elige 8 en generarBoletoIA")

    html = html.replace(LECTURA_ANTIGUA, LECTURA_NUEVA)

    if html != original:
        INDEX.write_text(html, encoding="utf-8")
        print("Elige 8 web corregido en Generar Quiniela.")
    else:
        print("Elige 8 web ya estaba corregido; no hay cambios.")


if __name__ == "__main__":
    main()
