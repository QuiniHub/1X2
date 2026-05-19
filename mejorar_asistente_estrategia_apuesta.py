from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

CALL = '''      const estrategiaApuesta = respuestaEstrategiaApuesta(q, data);
      if (estrategiaApuesta) return estrategiaApuesta;
'''

FUNCIONES = r'''
    function esPreguntaEstrategiaApuesta(q) {
      const hablaDeFormato = incluye(q, ["doble", "dobles", "triple", "triples", "elige8", "elige 8", "sencilla", "sencillo", "configuracion", "configurar", "presupuesto"]);
      const hablaDeBoleto = incluye(q, ["quiniela", "boleto", "apuesta", "jugar", "jugaria", "jornada", "mejor opcion", "mejor apuesta"]);
      const compara = incluye(q, ["mejor", "conviene", "recomiendas", "recomendarias", "o", "frente", "comparar", "valorar"]);
      return hablaDeFormato && hablaDeBoleto && compara;
    }

    function importeEstrategiaApuesta(dobles, triples, elige8) {
      const apuestas = Math.pow(2, dobles) * Math.pow(3, triples);
      const importeQuiniela = Math.max(apuestas * 0.75, 1.50);
      const importeElige8 = elige8 ? 0.50 : 0;
      return { apuestas, importeQuiniela, importeElige8, importeTotal: importeQuiniela + importeElige8 };
    }

    function eurosEstrategia(valor) {
      return Number(valor || 0).toFixed(2).replace(".", ",") + " EUR";
    }

    function signosOrdenadosEstrategia(partido) {
      const probs = partido?.probabilidades || {};
      return ["1", "X", "2"].map(signo => ({ signo, prob: Number(probs[signo] || 0) }))
        .sort((a, b) => b.prob - a.prob);
    }

    function signosCoberturaEstrategia(partido, tipo) {
      if (tipo === "TRIPLE") return "1X2";
      const orden = signosOrdenadosEstrategia(partido).map(x => x.signo);
      const elegidos = tipo === "DOBLE" ? orden.slice(0, 2) : orden.slice(0, 1);
      return ["1", "X", "2"].filter(s => elegidos.includes(s)).join("");
    }

    function probCubiertaEstrategia(partido, signos) {
      const probs = partido?.probabilidades || {};
      return signos.split("").reduce((total, signo) => total + Number(probs[signo] || 0), 0);
    }

    function riesgoPartidoEstrategia(partido) {
      const orden = signosOrdenadosEstrategia(partido);
      const margen = orden.length > 1 ? orden[0].prob - orden[1].prob : 0;
      const sorpresa = Number(partido?.probabilidad_sorpresa || 0);
      const x = Number(partido?.probabilidades?.X || 0);
      const incertidumbreBase = Number(partido?.incertidumbre || (100 - margen + x * 0.35));
      let extra = 0;
      if (margen <= 4) extra += 14;
      else if (margen <= 8) extra += 8;
      if (x >= 32) extra += 5;
      if (sorpresa >= 65) extra += 6;
      return incertidumbreBase + sorpresa * 0.25 + extra;
    }

    function esPeligrosoEstrategia(partido) {
      const orden = signosOrdenadosEstrategia(partido);
      const margen = orden.length > 1 ? orden[0].prob - orden[1].prob : 0;
      return riesgoPartidoEstrategia(partido) >= 128
        || Number(partido?.probabilidad_sorpresa || 0) >= 62
        || margen <= 6
        || Number(partido?.probabilidades?.X || 0) >= 32;
    }

    function nombrePartidoEstrategia(partido) {
      return `${partido.num}. ${partido.local} - ${partido.visitante}`;
    }

    function evaluarConfiguracionEstrategia(partidosBase, dobles, triples, elige8 = false) {
      const partidos = (partidosBase || []).filter(p => Number(p.num) <= 14);
      dobles = Math.max(0, Math.min(Number(dobles || 0), 14));
      triples = Math.max(0, Math.min(Number(triples || 0), 14));
      if (dobles + triples > 14) dobles = Math.max(0, 14 - triples);

      const ordenados = [...partidos].sort((a, b) => riesgoPartidoEstrategia(b) - riesgoPartidoEstrategia(a));
      const triplesSet = new Set(ordenados.slice(0, triples).map(p => Number(p.num)));
      const doblesSet = new Set(ordenados.filter(p => !triplesSet.has(Number(p.num))).slice(0, dobles).map(p => Number(p.num)));

      const detalle = partidos.map(p => {
        const num = Number(p.num);
        const tipo = triplesSet.has(num) ? "TRIPLE" : doblesSet.has(num) ? "DOBLE" : "FIJO";
        const signos = signosCoberturaEstrategia(p, tipo);
        const probCubierta = probCubiertaEstrategia(p, signos);
        const peligroso = esPeligrosoEstrategia(p);
        return { partido: p, num, tipo, signos, probCubierta, peligroso, riesgo: riesgoPartidoEstrategia(p) };
      });

      const coberturaMedia = detalle.length ? detalle.reduce((s, x) => s + x.probCubierta, 0) / detalle.length : 0;
      const fijosPeligrosos = detalle.filter(x => x.tipo === "FIJO" && x.peligroso);
      const trampasCubiertas = detalle.filter(x => x.tipo !== "FIJO" && x.peligroso);
      const coste = importeEstrategiaApuesta(dobles, triples, elige8);
      const elige8Candidatos = [...detalle]
        .sort((a, b) => {
          const pesoA = a.tipo === "TRIPLE" ? 0 : a.tipo === "DOBLE" ? 1 : 2;
          const pesoB = b.tipo === "TRIPLE" ? 0 : b.tipo === "DOBLE" ? 1 : 2;
          if (pesoA !== pesoB) return pesoA - pesoB;
          return a.riesgo - b.riesgo;
        })
        .slice(0, 8);

      const valor = coberturaMedia
        + trampasCubiertas.length * 2.8
        + triples * 1.1
        - fijosPeligrosos.length * 4.2
        - Math.log2(Math.max(coste.apuestas, 1)) * 1.8
        + (elige8 ? 0.8 : 0);

      return { dobles, triples, elige8, coste, detalle, coberturaMedia, fijosPeligrosos, trampasCubiertas, elige8Candidatos, valor };
    }

    function opcionesPedidasEstrategia(q) {
      const dobles = Array.from(q.matchAll(/(\d+)\s*dobl/g)).map(m => Number(m[1])).filter(Number.isFinite);
      const triples = Array.from(q.matchAll(/(\d+)\s*tripl/g)).map(m => Number(m[1])).filter(Number.isFinite);
      const opciones = [];
      const comparaSeparado = dobles.length && triples.length && (q.includes(" o ") || q.includes("frente") || q.includes("compar"));

      if (comparaSeparado) {
        dobles.forEach(d => opciones.push({ dobles: d, triples: 0, nombre: `${d} dobles` }));
        triples.forEach(t => opciones.push({ dobles: 0, triples: t, nombre: `${t} triples` }));
      } else if (dobles.length || triples.length) {
        opciones.push({ dobles: dobles[0] || 0, triples: triples[0] || 0, nombre: `${dobles[0] || 0} dobles + ${triples[0] || 0} triples` });
      }

      return opciones;
    }

    function opcionesGeneralesEstrategia() {
      return [
        { dobles: 0, triples: 0, nombre: "sencilla" },
        { dobles: 4, triples: 0, nombre: "4 dobles" },
        { dobles: 6, triples: 0, nombre: "6 dobles" },
        { dobles: 8, triples: 0, nombre: "8 dobles" },
        { dobles: 0, triples: 2, nombre: "2 triples" },
        { dobles: 0, triples: 3, nombre: "3 triples" },
        { dobles: 2, triples: 2, nombre: "2 dobles + 2 triples" },
        { dobles: 3, triples: 2, nombre: "3 dobles + 2 triples" },
        { dobles: 2, triples: 3, nombre: "2 dobles + 3 triples" },
        { dobles: 4, triples: 2, nombre: "4 dobles + 2 triples" }
      ];
    }

    function claveOpcionEstrategia(op) {
      return `${op.dobles || 0}-${op.triples || 0}-${op.elige8 ? 1 : 0}`;
    }

    function textoResumenEstrategia(ev) {
      const nombre = `${ev.dobles}D/${ev.triples}T${ev.elige8 ? " + Elige 8" : ""}`;
      return `- ${nombre}: ${ev.coste.apuestas} apuestas, ${eurosEstrategia(ev.coste.importeTotal)}, cobertura media ${ev.coberturaMedia.toFixed(1)}%, trampas cubiertas ${ev.trampasCubiertas.length}, fijos peligrosos ${ev.fijosPeligrosos.length}.`;
    }

    function respuestaEstrategiaApuesta(q, data) {
      if (!esPreguntaEstrategiaApuesta(q)) return "";
      const partidos = (data.prediccion?.partidos || []).filter(p => Number(p.num) <= 14);
      if (!partidos.length) return "No tengo una prediccion activa con 14 partidos para comparar dobles, triples y Elige 8.";

      const jornada = data.prediccion?.jornada || data.estadoVivo?.jornada_actual?.jornada || "-";
      const pedidas = opcionesPedidasEstrategia(q);
      const generales = opcionesGeneralesEstrategia();
      const quiereElige8 = incluye(q, ["elige8", "elige 8"]);
      const mapa = new Map();

      [...pedidas, ...generales].forEach(op => {
        mapa.set(claveOpcionEstrategia(op), { ...op, elige8: false });
        if (quiereElige8 || pedidas.length) mapa.set(claveOpcionEstrategia({ ...op, elige8: true }), { ...op, elige8: true });
      });

      const evaluadas = Array.from(mapa.values())
        .map(op => evaluarConfiguracionEstrategia(partidos, op.dobles, op.triples, op.elige8))
        .sort((a, b) => b.valor - a.valor);
      const evaluadasPedidas = pedidas.length
        ? pedidas.flatMap(op => [
            evaluarConfiguracionEstrategia(partidos, op.dobles, op.triples, false),
            evaluarConfiguracionEstrategia(partidos, op.dobles, op.triples, true)
          ]).sort((a, b) => b.valor - a.valor)
        : [];
      const mejor = evaluadas[0];
      const comparacion = (evaluadasPedidas.length ? evaluadasPedidas : evaluadas.slice(0, 6));
      const trampas = [...partidos].sort((a, b) => riesgoPartidoEstrategia(b) - riesgoPartidoEstrategia(a)).slice(0, 7);
      const triplesElegidos = mejor.detalle.filter(x => x.tipo === "TRIPLE").sort((a, b) => a.num - b.num);
      const doblesElegidos = mejor.detalle.filter(x => x.tipo === "DOBLE").sort((a, b) => a.num - b.num);
      const fijosPeligrosos = mejor.fijosPeligrosos.sort((a, b) => b.riesgo - a.riesgo).slice(0, 5);

      const mejorPedida = evaluadasPedidas[0];
      const decisionPedida = mejorPedida
        ? `Si me obligas a elegir solo entre lo que preguntas, me quedo con ${mejorPedida.dobles} dobles y ${mejorPedida.triples} triples${mejorPedida.elige8 ? " + Elige 8" : ""}.`
        : "";

      return [
        `Para la jornada ${jornada}, la lectura de sistema es: no trataria esta quiniela como sencilla. Hay varios partidos con riesgo alto y empates con peso.`,
        "",
        "Partidos que mas condicionan la estrategia:",
        ...trampas.map(p => `- ${nombrePartidoEstrategia(p)}: riesgo ${riesgoPartidoEstrategia(p).toFixed(1)}, probabilidades ${probTexto(p)}, sorpresa ${p.probabilidad_sorpresa ?? "-"}%.`),
        "",
        pedidas.length ? "Comparacion de las opciones que me planteas:" : "Ranking de opciones razonables:",
        ...comparacion.map(textoResumenEstrategia),
        "",
        decisionPedida,
        `Mi recomendacion global ahora mismo: ${mejor.dobles} dobles y ${mejor.triples} triples${mejor.elige8 ? " + Elige 8" : ""}. Coste: ${eurosEstrategia(mejor.coste.importeTotal)} (${mejor.coste.apuestas} apuestas).`,
        triplesElegidos.length ? `Triples prioritarios: ${triplesElegidos.map(x => `${nombrePartidoEstrategia(x.partido)} (${probTexto(x.partido)})`).join("; ")}.` : "Triples prioritarios: no abriria triples en esta configuracion.",
        doblesElegidos.length ? `Dobles prioritarios: ${doblesElegidos.map(x => `${nombrePartidoEstrategia(x.partido)} -> ${x.signos}`).join("; ")}.` : "Dobles prioritarios: no abriria dobles en esta configuracion.",
        "",
        mejor.elige8
          ? `Elige 8: lo activaria y marcaria ${mejor.elige8Candidatos.map(x => x.num).join(", ")}, porque concentra la proteccion en los partidos cubiertos y en los fijos mas limpios.`
          : `Elige 8: lo valoraria si vas a validar un boleto serio; por solo 0,50 EUR mas, mis candidatos serian ${evaluarConfiguracionEstrategia(partidos, mejor.dobles, mejor.triples, true).elige8Candidatos.map(x => x.num).join(", ")}.`,
        fijosPeligrosos.length ? `Ojo: aun quedarian fijos peligrosos en ${fijosPeligrosos.map(x => nombrePartidoEstrategia(x.partido)).join("; ")}.` : "Con esa configuracion no quedan fijos peligrosos fuertes segun la memoria actual.",
        "",
        "Conclusion practica: si quieres gastar menos, los triples concentran mejor el dinero en partidos locos; si quieres sobrevivir a mas desviaciones pequenas, los dobles reparten mejor la cobertura. Para esta jornada, no validaria sin cubrir al menos el bloque de partidos trampa."
      ].filter(Boolean).join("\n");
    }
'''


def patch(html):
    if "function respuestaEstrategiaApuesta" not in html:
        marcador_funciones = "    function respuestaDebatePartido(q, data) {"
        if marcador_funciones not in html:
            raise SystemExit("No encuentro donde insertar la estrategia de apuesta.")
        html = html.replace(marcador_funciones, FUNCIONES + "\n" + marcador_funciones, 1)

    if "const estrategiaApuesta = respuestaEstrategiaApuesta(q, data);" not in html:
        marcador_llamada = "      const aprendizajeErrores = respuestaAprendizajeErrores(q, data);\n      if (aprendizajeErrores) return aprendizajeErrores;\n"
        if marcador_llamada not in html:
            raise SystemExit("No encuentro donde activar la estrategia de apuesta.")
        html = html.replace(marcador_llamada, marcador_llamada + CALL, 1)
    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Asistente IA mejorado: compara dobles, triples, coste y Elige 8.")
    else:
        print("Asistente IA ya tenia estrategia de apuesta.")


if __name__ == "__main__":
    main()
