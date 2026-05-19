from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

FUNCIONES = r'''
    function competitivoPartidoLocal(partido) {
      return partido?.estrategia_local || partido?.contexto_competitivo_local || {};
    }

    function competitivoPartidoVisitante(partido) {
      return partido?.estrategia_visitante || partido?.contexto_competitivo_visitante || {};
    }

    function valorMotivacionEstrategia(comp) {
      const texto = `${comp?.motivacion_competitiva || comp?.motivacion || ""} ${comp?.situacion_competitiva || ""} ${comp?.objetivo_principal?.estado || ""} ${comp?.objetivo_principal?.objetivo || ""}`.toLowerCase();
      let valor = { baja: 0, media: 1, alta: 2, maxima: 3, maxima: 3 }[String(comp?.motivacion_competitiva || comp?.motivacion || "baja").toLowerCase()] ?? 0;
      if ((comp?.objetivos_vivos || []).length) valor += 1;
      if (comp?.objetivo_principal?.vivo === true) valor += 1;
      if (texto.includes("defiende") || texto.includes("aspira") || texto.includes("riesgo") || texto.includes("descenso") || texto.includes("playoff") || texto.includes("ascenso")) valor += 1;
      if (comp?.objetivo_principal?.terminal === true && !(comp?.objetivos_vivos || []).length) valor -= 2;
      if (texto.includes("asegurado") || texto.includes("campeon") || texto.includes("salvado matematicamente")) valor -= 1;
      return Math.max(0, Math.min(valor, 4));
    }

    function probabilidadesAjustadasEstrategia(partido) {
      const base = partido?.probabilidades || {};
      const p = {
        "1": Number(base["1"] || 0),
        "X": Number(base["X"] || 0),
        "2": Number(base["2"] || 0)
      };
      const local = competitivoPartidoLocal(partido);
      const visitante = competitivoPartidoVisitante(partido);
      const diferencia = valorMotivacionEstrategia(local) - valorMotivacionEstrategia(visitante);
      if (diferencia) {
        const ajuste = Math.max(Math.min(diferencia * 4, 10), -10);
        p["1"] += ajuste;
        p["2"] -= ajuste;
        if (valorMotivacionEstrategia(local) >= 2 || valorMotivacionEstrategia(visitante) >= 2) p["X"] += 2;
      }
      return normalizarProbabilidades(p);
    }

    function probTextoAjustadoEstrategia(partido) {
      const p = probabilidadesAjustadasEstrategia(partido);
      return `1=${p["1"]}%, X=${p["X"]}%, 2=${p["2"]}%`;
    }

    function rangoAjustadoEstrategia(partido) {
      const valores = Object.values(probabilidadesAjustadasEstrategia(partido)).map(Number).sort((a, b) => b - a);
      return valores.length ? valores[0] - valores[valores.length - 1] : 99;
    }

    function esTripleNaturalEstrategia(partido) {
      const p = probabilidadesAjustadasEstrategia(partido);
      return rangoAjustadoEstrategia(partido) <= 9 && Number(p["X"] || 0) >= 28;
    }

    function prioridadTripleEstrategia(partido) {
      const local = valorMotivacionEstrategia(competitivoPartidoLocal(partido));
      const visitante = valorMotivacionEstrategia(competitivoPartidoVisitante(partido));
      const desequilibrio = Math.abs(local - visitante);
      return riesgoPartidoEstrategia(partido)
        + (esTripleNaturalEstrategia(partido) ? 22 : -18)
        - desequilibrio * 7;
    }

    function resumenMotivacionEstrategia(partido) {
      const local = competitivoPartidoLocal(partido);
      const visitante = competitivoPartidoVisitante(partido);
      const vl = valorMotivacionEstrategia(local);
      const vv = valorMotivacionEstrategia(visitante);
      if (vl > vv) return `Ajuste competitivo: pesa mas la necesidad de ${partido.local}. ${local?.objetivo_principal?.lectura || local?.lectura_resumen || ""}`.trim();
      if (vv > vl) return `Ajuste competitivo: pesa mas la necesidad de ${partido.visitante}. ${visitante?.objetivo_principal?.lectura || visitante?.lectura_resumen || ""}`.trim();
      return "Ajuste competitivo: motivacion parecida o sin diferencia clara.";
    }
'''


def patch(html):
    if "function competitivoPartidoLocal" not in html:
        marcador = "    function evaluarConfiguracionEstrategia(partidosBase, dobles, triples, elige8 = false) {"
        if marcador not in html:
            raise SystemExit("No encuentro evaluarConfiguracionEstrategia.")
        html = html.replace(marcador, FUNCIONES + "\n" + marcador, 1)

    html = html.replace(
        '      const probs = partido?.probabilidades || {};\n      return ["1", "X", "2"].map(signo => ({ signo, prob: Number(probs[signo] || 0) }))',
        '      const probs = probabilidadesAjustadasEstrategia(partido);\n      return ["1", "X", "2"].map(signo => ({ signo, prob: Number(probs[signo] || 0) }))',
        1,
    )
    html = html.replace(
        '      const x = Number(partido?.probabilidades?.X || 0);',
        '      const probsAjustadas = probabilidadesAjustadasEstrategia(partido);\n      const x = Number(probsAjustadas?.X || 0);',
        1,
    )
    html = html.replace(
        '      const ordenados = [...partidos].sort((a, b) => riesgoPartidoEstrategia(b) - riesgoPartidoEstrategia(a));\n      const triplesSet = new Set(ordenados.slice(0, triples).map(p => Number(p.num)));',
        '      const ordenados = [...partidos].sort((a, b) => riesgoPartidoEstrategia(b) - riesgoPartidoEstrategia(a));\n      const ordenadosTriple = [...partidos].sort((a, b) => prioridadTripleEstrategia(b) - prioridadTripleEstrategia(a));\n      const triplesSet = new Set(ordenadosTriple.slice(0, triples).map(p => Number(p.num)));',
        1,
    )
    html = html.replace(
        '      const partidos = (data.prediccion?.partidos || []).filter(p => Number(p.num) <= 14);',
        '      const partidos = (data.prediccion?.partidos || [])\n        .filter(p => Number(p.num) <= 14)\n        .map(p => ({\n          ...p,\n          estrategia_local: datosEquipoCompetitivo(data, p.local)?.competitivo || {},\n          estrategia_visitante: datosEquipoCompetitivo(data, p.visitante)?.competitivo || {}\n        }));',
        1,
    )
    html = html.replace(
        '        ...trampas.map(p => `- ${nombrePartidoEstrategia(p)}: riesgo ${riesgoPartidoEstrategia(p).toFixed(1)}, probabilidades ${probTexto(p)}, sorpresa ${p.probabilidad_sorpresa ?? "-"}%.`),',
        '        ...trampas.map(p => `- ${nombrePartidoEstrategia(p)}: riesgo ${riesgoPartidoEstrategia(p).toFixed(1)}, probabilidades base ${probTexto(p)}, ajustadas ${probTextoAjustadoEstrategia(p)}, sorpresa ${p.probabilidad_sorpresa ?? "-"}%. ${resumenMotivacionEstrategia(p)}`),',
        1,
    )
    html = html.replace(
        '        triplesElegidos.length ? `Triples prioritarios: ${triplesElegidos.map(x => `${nombrePartidoEstrategia(x.partido)} (${probTexto(x.partido)})`).join("; ")}.` : "Triples prioritarios: no abriria triples en esta configuracion.",',
        '        triplesElegidos.length ? `Triples prioritarios: ${triplesElegidos.map(x => `${nombrePartidoEstrategia(x.partido)} (ajustadas ${probTextoAjustadoEstrategia(x.partido)})`).join("; ")}.` : "Triples prioritarios: no abriria triples en esta configuracion.",',
        1,
    )
    html = html.replace(
        '      const necesitaPuntuar = String(datosObjecion?.competitivo?.objetivo_principal?.objetivo || "").includes("descenso")\n        || String(datosObjecion?.competitivo?.situacion_competitiva || "").includes("descenso")\n        || String(datosObjecion?.competitivo?.objetivo_principal?.estado || "").includes("riesgo");',
        '      const textoNecesidad = `${datosObjecion?.competitivo?.objetivo_principal?.objetivo || ""} ${datosObjecion?.competitivo?.objetivo_principal?.estado || ""} ${datosObjecion?.competitivo?.situacion_competitiva || ""}`.toLowerCase();\n      const necesitaPuntuar = datosObjecion?.competitivo?.objetivo_principal?.vivo === true\n        || textoNecesidad.includes("descenso")\n        || textoNecesidad.includes("riesgo")\n        || textoNecesidad.includes("defiende")\n        || textoNecesidad.includes("aspira")\n        || textoNecesidad.includes("playoff")\n        || textoNecesidad.includes("ascenso");',
        1,
    )
    html = html.replace(
        '      if (necesitaPuntuar && !esVisitante && signoBase === "2") {\n        return "Yo mantendria el 2 como lectura base, pero si ese equipo necesita puntuar, el primer doble logico seria X2.";\n      }',
        '      if (necesitaPuntuar && !esVisitante && signoBase === "2") {\n        return "Aqui no trataria el 2 visitante como fijo limpio: si el local necesita puntuar, el primer doble logico pasa a ser 1X.";\n      }',
        1,
    )
    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Estrategia ajustada por motivacion competitiva y necesidad real de puntuar.")
    else:
        print("Estrategia por motivacion ya estaba ajustada.")


if __name__ == "__main__":
    main()
