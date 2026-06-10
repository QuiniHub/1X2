(function () {
  const CACHE = "?v=" + Date.now();
  const PRECIO_APUESTA_QUINIELA = 0.75;
  const PRECIO_ELIGE8_POR_APUESTA = 0.50;

  function euros(valor) {
    const n = Number(valor || 0);
    return n.toFixed(2).replace(".", ",") + " €";
  }

  function normalizarSignos(valor) {
    if (Array.isArray(valor)) return valor.map(String).slice(0, 14);
    const texto = String(valor || "").trim().toUpperCase();
    if (!texto || texto === "NO VALIDADA" || texto === "NO JUGADA") return [];
    const porEspacios = texto.split(/\s+/).filter(Boolean);
    if (porEspacios.length > 1) return porEspacios.slice(0, 14);
    if (/^[12X]{14}$/.test(texto)) return texto.split("");
    return [];
  }

  async function fetchJSON(url, fallback) {
    try {
      const res = await fetch(url + CACHE);
      if (!res.ok) throw new Error(url);
      return await res.json();
    } catch (e) {
      return fallback;
    }
  }

  function signoOficialDesdeItem(item) {
    const texto = String(item.resultado_oficial || item.resultado || "").trim().toUpperCase();
    if (["1", "X", "2"].includes(texto)) return texto;
    return "";
  }

  function apuestasDesdeSignos(signos) {
    return signos.reduce((total, signo) => {
      const limpios = String(signo || "").replace(/[^1X2]/g, "");
      return total * Math.max(limpios.length || 1, 1);
    }, 1);
  }

  function costeJugada(signos, elige8) {
    const apuestas = apuestasDesdeSignos(signos);
    const importeQuiniela = Math.max(apuestas * PRECIO_APUESTA_QUINIELA, 1.50);
    const importeElige8 = elige8 ? apuestas * PRECIO_ELIGE8_POR_APUESTA : 0;
    return { apuestas, importe: importeQuiniela + importeElige8 };
  }

  function costePrediccionActual(prediccion) {
    const coste = prediccion.coste || {};
    const config = prediccion.configuracion || {};
    const apuestas = Number(coste.apuestas || apuestasDesdeSignos(signosPrediccion(prediccion)) || 1);
    const importeQuiniela = Math.max(apuestas * PRECIO_APUESTA_QUINIELA, 1.50);
    const importeElige8Correcto = apuestas * PRECIO_ELIGE8_POR_APUESTA;
    const totalConElige8 = importeQuiniela + importeElige8Correcto;
    const totalSinElige8 = importeQuiniela;

    return {
      apuestas,
      importeQuiniela,
      importeElige8Correcto,
      totalActual: config.elige8 ? totalConElige8 : totalSinElige8,
      totalConElige8,
      elige8Activado: Boolean(config.elige8)
    };
  }

  function textoCostePrediccion(prediccion) {
    const coste = costePrediccionActual(prediccion);
    if (coste.elige8Activado) {
      return `Coste quiniela: ${euros(coste.importeQuiniela)} · Elige 8 (${coste.apuestas} apuestas x 0,50 €): ${euros(coste.importeElige8Correcto)} · Total: ${euros(coste.totalActual)}.`;
    }
    return `Coste quiniela: ${euros(coste.importeQuiniela)} · Si añades Elige 8 (${coste.apuestas} apuestas x 0,50 €): +${euros(coste.importeElige8Correcto)} · Total con Elige 8: ${euros(coste.totalConElige8)}.`;
  }

  function calcularMetricas(historial) {
    const jornadas = (historial.jornadas || []).filter(j => normalizarSignos(j.nuestra_quiniela || j.signos).length >= 14);
    const acumulado = {
      jornadas: 0,
      partidos: 0,
      aciertos: 0,
      coste: 0,
      porTipo: {
        FIJO: { total: 0, aciertos: 0 },
        DOBLE: { total: 0, aciertos: 0 },
        TRIPLE: { total: 0, aciertos: 0 }
      },
      evolucion: []
    };

    jornadas.forEach(jornada => {
      const signos = normalizarSignos(jornada.nuestra_quiniela || jornada.signos);
      const oficial = normalizarSignos(jornada.resultado_oficial || jornada.signos_oficiales);
      if (signos.length < 14 || oficial.length < 14) return;

      let aciertosJornada = 0;
      signos.slice(0, 14).forEach((jugado, idx) => {
        const real = oficial[idx] || signoOficialDesdeItem((jornada.partidos || [])[idx] || {});
        if (!["1", "X", "2"].includes(real)) return;
        const limpios = String(jugado || "").replace(/[^1X2]/g, "");
        const tipo = limpios.length >= 3 ? "TRIPLE" : limpios.length === 2 ? "DOBLE" : "FIJO";
        const acierto = limpios.includes(real);
        acumulado.partidos += 1;
        acumulado.porTipo[tipo].total += 1;
        if (acierto) {
          acumulado.aciertos += 1;
          acumulado.porTipo[tipo].aciertos += 1;
          aciertosJornada += 1;
        }
      });

      const coste = costeJugada(signos, Array.isArray(jornada.elige8) && jornada.elige8.length > 0);
      acumulado.coste += coste.importe;
      acumulado.jornadas += 1;
      acumulado.evolucion.push({ jornada: jornada.jornada, aciertos: aciertosJornada });
    });

    return acumulado;
  }

  function pct(aciertos, total) {
    if (!total) return "sin datos";
    return ((aciertos / total) * 100).toFixed(1).replace(".", ",") + "%";
  }

  function signosPrediccion(prediccion) {
    return (prediccion.partidos || [])
      .filter(p => Number(p.num) <= 14)
      .sort((a, b) => Number(a.num) - Number(b.num))
      .map(p => p.signo_final || p.signo_base || "?");
  }

  function razonesClave(prediccion) {
    const partidos = (prediccion.partidos || []).filter(p => Number(p.num) <= 14);
    return [...partidos]
      .sort((a, b) => Number(b.incertidumbre || b.probabilidad_sorpresa || 0) - Number(a.incertidumbre || a.probabilidad_sorpresa || 0))
      .slice(0, 3)
      .map(p => {
        const probs = p.probabilidades || {};
        const riesgo = p.probabilidad_sorpresa !== undefined ? `sorpresa ${p.probabilidad_sorpresa}%` : `incertidumbre ${Math.round(Number(p.incertidumbre || 0))}`;
        return `${p.num}. ${p.local} - ${p.visitante}: ${p.signo_final || p.signo_base || "?"} (${riesgo}; 1=${probs["1"] ?? "-"}%, X=${probs["X"] ?? "-"}%, 2=${probs["2"] ?? "-"}%).`;
      });
  }

  function renderMetricas(prediccion, metricas) {
    const signos = signosPrediccion(prediccion);
    const config = prediccion.configuracion || {};
    const porTipo = metricas.porTipo;
    const ultimas = metricas.evolucion.slice(-5).map(x => `J${x.jornada}: ${x.aciertos}/14`).join(" · ") || "sin histórico validado";
    const razones = razonesClave(prediccion);
    const precisionGlobal = pct(metricas.aciertos, metricas.partidos);
    const roiTecnico = metricas.jornadas ? `Coste simulado validado: ${euros(metricas.coste)}. Premios/ROI real: pendiente de integrar escrutinio oficial.` : "Sin coste histórico validado todavía.";
    const costeTexto = textoCostePrediccion(prediccion);

    return `
      <div class="boleto-resumen" id="resumen-rapido-metricas">
        <h3>Resumen rápido</h3>
        <p><strong>¿Qué jugar ahora?</strong><br>
          Jornada ${prediccion.jornada || "-"}: ${signos.join(" ") || "sin signos"}. ${config.dobles || 0} dobles · ${config.triples || 0} triples${config.elige8 ? " · Elige 8" : ""}. ${costeTexto}
        </p>
        <p><strong>¿Por qué lo recomienda?</strong><br>
          ${(razones.length ? razones : ["El modelo combina probabilidad, forma, casa/fuera, contexto competitivo y riesgo de sorpresa."]).join("<br>")}
        </p>
        <p><strong>¿Qué tal ha funcionado antes?</strong><br>
          Precisión global: ${precisionGlobal} (${metricas.aciertos}/${metricas.partidos} signos revisados). Fijos: ${pct(porTipo.FIJO.aciertos, porTipo.FIJO.total)} · Dobles: ${pct(porTipo.DOBLE.aciertos, porTipo.DOBLE.total)} · Triples: ${pct(porTipo.TRIPLE.aciertos, porTipo.TRIPLE.total)}.<br>
          Evolución reciente: ${ultimas}.<br>
          ${roiTecnico}
        </p>
      </div>
    `;
  }

  function activarMejoraXCercana() {
    if (window.__mejoraXCercanaActiva || typeof window.prioridadDobleAnalisis !== "function") return;
    window.__mejoraXCercanaActiva = true;
    const prioridadOriginal = window.prioridadDobleAnalisis;

    function ordenProbabilidades(probs) {
      return Object.entries(probs || {})
        .map(([signo, valor]) => [signo, Number(valor || 0)])
        .sort((a, b) => b[1] - a[1]);
    }

    function objetivoVivo(datos) {
      if (!datos) return false;
      const texto = JSON.stringify(datos).toLowerCase();
      return texto.includes("descenso") || texto.includes("permanencia") || texto.includes("playoff") || texto.includes("ascenso") || texto.includes("defiende") || texto.includes("aspira") || texto.includes("europa") || texto.includes("conference");
    }

    function mejoraXCercana(partido) {
      const orden = ordenProbabilidades(partido?.probabilidades || {});
      if (orden.length < 2) return 0;
      const [primero, segundo] = orden;
      const margen = primero[1] - segundo[1];
      const xCerca = segundo[0] === "X" && margen <= 12 && primero[1] < 58;
      const necesidad = Boolean(partido?.riesgo_necesidad || partido?.riesgo_necesidad_real) || objetivoVivo(partido?.contexto_competitivo_local) || objetivoVivo(partido?.contexto_competitivo_visitante);
      if (!xCerca || !necesidad) return 0;
      let bonus = 180;
      if (margen <= 8) bonus += 80;
      if (Number(partido?.probabilidad_sorpresa || 0) >= 60 || Number(partido?.incertidumbre || 0) >= 180) bonus += 60;
      return bonus;
    }

    window.prioridadDobleAnalisis = function prioridadDobleAnalisisConXCercana(partido) {
      return prioridadOriginal(partido) + mejoraXCercana(partido);
    };
  }

  function estabilizarElige8SobreBoletoBase() {
    if (window.__elige8EstableActiva || typeof window.evaluarConfiguracionEstrategia !== "function") return;
    window.__elige8EstableActiva = true;
    const evaluarOriginal = window.evaluarConfiguracionEstrategia;

    window.evaluarConfiguracionEstrategia = function evaluarConfiguracionEstrategiaElige8Estable(partidosBase, dobles, triples, elige8 = false) {
      const base = evaluarOriginal(partidosBase, dobles, triples, false);
      if (!elige8) return base;
      const conElige8 = evaluarOriginal(partidosBase, dobles, triples, true);
      return {
        ...base,
        elige8: true,
        coste: conElige8.coste,
        elige8Candidatos: conElige8.elige8Candidatos,
        valor: base.valor + 0.01,
        detalle: base.detalle,
        coberturaMedia: base.coberturaMedia,
        fijosPeligrosos: base.fijosPeligrosos,
        trampasCubiertas: base.trampasCubiertas
      };
    };
  }

  function programarEstabilidadElige8() {
    setTimeout(estabilizarElige8SobreBoletoBase, 200);
    setTimeout(estabilizarElige8SobreBoletoBase, 1200);
    setTimeout(estabilizarElige8SobreBoletoBase, 3000);
  }

  async function initResumenRapidoMetricas() {
    activarMejoraXCercana();
    estabilizarElige8SobreBoletoBase();
    const contenedor = document.getElementById("prediccion-resumen");
    if (!contenedor || document.getElementById("resumen-rapido-metricas")) return;

    const [prediccion, historial] = await Promise.all([
      fetchJSON("data/predicciones/ultima_prediccion.json", null),
      fetchJSON("data/historial_quinielas.json", { jornadas: [] })
    ]);

    if (!prediccion) return;
    const metricas = calcularMetricas(historial || { jornadas: [] });
    contenedor.insertAdjacentHTML("beforeend", renderMetricas(prediccion, metricas));
  }

  function programarResumenRapidoMetricas() {
    programarEstabilidadElige8();
    setTimeout(initResumenRapidoMetricas, 1200);
    setTimeout(initResumenRapidoMetricas, 3000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", programarResumenRapidoMetricas);
  } else {
    programarResumenRapidoMetricas();
  }
})();
