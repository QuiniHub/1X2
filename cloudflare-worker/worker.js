// Cloudflare Worker — QuiniHub IA Proxy
// Rutas: /api/groq, /api/gemini, /api/openrouter, /api/tavily, /api/football
//
// NOTA DE SEGURIDAD (auditoria externa 2026-08-03, hallazgo P0): antes, el
// header CORS era solo cosmetico -controla si el NAVEGADOR deja leer la
// respuesta a JS de otro origen, pero no impide que un script (curl, otro
// servidor) llame directamente a estas rutas y gaste la cuota real de
// Groq/Gemini/OpenRouter/Tavily sin pasar por la web. Este repo es publico,
// asi que cualquier "secreto compartido" escrito aqui seria visible para
// cualquiera que lea el codigo -no serviria de proteccion real, solo daria
// una falsa sensacion de seguridad. Lo que SI se puede hacer desde el propio
// codigo:
//   1. Verificar Origin/Referer de verdad (rechazar, no solo reflejar).
//   2. Fijar el modelo permitido en cada proveedor (evita que alguien pida
//      un modelo mas caro directamente al proxy).
//   3. Poner un limite de tamano al cuerpo de la peticion.
// Esto detiene el abuso automatizado/casual (la inmensa mayoria de trafico
// no deseado a un endpoint publico), pero NO a un atacante dirigido que
// falsifique headers. Para eso hace falta algo fuera de este archivo -
// Turnstile o una regla de Rate Limiting del propio panel de Cloudflare
// (Security > WAF > Rate limiting rules, sin tocar codigo, unos clics)-
// que Marc tendria que activar el mismo con acceso a su cuenta.

const ALLOWED_ORIGIN = "https://quinihub.github.io";
const MAX_BODY_BYTES = 200000; // 200 KB -de sobra para el contexto real del chat, bloquea payloads absurdos

const ESPN_LIGAS = {
  "esp.1":                  "La Liga",
  "esp.2":                  "Segunda División",
  "UEFA.CHAMPIONS":         "Champions League",
  "UEFA.EUROPA":            "Europa League",
  "UEFA.EUROPA.CONFERENCE": "Conference League",
  "eng.1":                  "Premier League",
  "ger.1":                  "Bundesliga",
  "ita.1":                  "Serie A",
  "fra.1":                  "Ligue 1",
  "por.1":                  "Primeira Liga",
  "ned.1":                  "Eredivisie",
  "FIFA.WORLD":             "Copa del Mundo",
  "swe.1":                  "Allsvenskan",
  "fin.1":                  "Veikkausliiga",
  "nor.1":                  "Eliteserien",
  "den.1":                  "Superliga Danesa",
};

const THESPORTSDB_LIGAS = {
  "La Liga":          "4335",
  "Segunda División": "4336",
  "Champions League": "4346",
  "Europa League":    "4347",
  "Premier League":   "4328",
  "Bundesliga":       "4331",
  "Serie A":          "4332",
  "Mundial 2026":     "600614",
  "Allsvenskan":      "4344",
  "Veikkausliiga":    "4430",
};

// Modelos realmente usados por index.html -cualquier otro valor que llegue
// en el body se sobreescribe con el primero de la lista, igual que ya se
// hacia con gemini/openrouter (evita pedir un modelo mas caro directamente
// al proxy sin pasar por la web).
// 18/08/2026: Groq retiro de golpe TODA la familia llama que teniamos aqui
// (llama-3.3-70b-versatile, llama-3.1-8b-instant, llama-4-scout/maverick) y
// el chat entero empezo a devolver 404 "The model does not exist". Verificado
// hoy contra el proxy: de los candidatos probados solo responden 200 los
// openai/gpt-oss-* y groq/compound. Ninguno acepta imagenes, asi que la
// vision queda cubierta por Gemini (ver mas abajo).
const MODELOS_GROQ_PERMITIDOS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"];

function origenValido(request) {
  const origin = request.headers.get("Origin") || "";
  const referer = request.headers.get("Referer") || "";
  if (origin) return origin === ALLOWED_ORIGIN;
  // Las peticiones GET simples (p.ej. /api/football desde <script> antiguo)
  // pueden no llevar Origin -en ese caso, exigir que el Referer empiece por
  // el origen permitido en su lugar.
  if (referer) return referer.startsWith(ALLOWED_ORIGIN + "/");
  return false;
}

async function cuerpoDentroDelLimite(request) {
  const declarado = request.headers.get("Content-Length");
  if (declarado && Number(declarado) > MAX_BODY_BYTES) return false;
  return true;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const corsHeaders = {
      "Access-Control-Allow-Origin":  origin === ALLOWED_ORIGIN ? origin : ALLOWED_ORIGIN,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const url = new URL(request.url);
    const esEndpointDeIA = ["/api/groq", "/api/gemini", "/api/openrouter", "/api/tavily"].includes(url.pathname);

    if (esEndpointDeIA) {
      if (!origenValido(request)) {
        return new Response(JSON.stringify({ error: "Origen no permitido" }), {
          status: 403,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      if (!(await cuerpoDentroDelLimite(request))) {
        return new Response(JSON.stringify({ error: "Peticion demasiado grande" }), {
          status: 413,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
    }

    // ── /api/groq ────────────────────────────────────────────────────────────
    if (url.pathname === "/api/groq") {
      const body = await request.json().catch(() => ({}));
      if (!MODELOS_GROQ_PERMITIDOS.includes(body.model)) {
        body.model = MODELOS_GROQ_PERMITIDOS[0];
      }
      const upstream = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${env.GROQ_KEY}` },
        body:    JSON.stringify(body),
      });
      const res = new Response(upstream.body, upstream);
      Object.entries(corsHeaders).forEach(([k, v]) => res.headers.set(k, v));
      return res;
    }

    // ── /api/gemini ──────────────────────────────────────────────────────────
    if (url.pathname === "/api/gemini") {
      const body = await request.json().catch(() => ({}));
      // gemini-2.0-flash retirado (18/08/2026): la propia API respondia
      // 404 indicando gemini-3.6-flash como reemplazo. Es ademas el unico
      // camino que queda para leer imagenes de boletos, porque Groq ya no
      // ofrece ningun modelo con vision para esta cuenta.
      body.model = "gemini-3.6-flash";
      const upstream = await fetch("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${env.GEMINI_KEY}` },
        body:    JSON.stringify(body),
      });
      const res = new Response(upstream.body, upstream);
      Object.entries(corsHeaders).forEach(([k, v]) => res.headers.set(k, v));
      return res;
    }

    // ── /api/openrouter ──────────────────────────────────────────────────────
    if (url.pathname === "/api/openrouter") {
      const body = await request.json().catch(() => ({}));
      // mistralai/mistral-7b-instruct:free fue retirado del catalogo de
      // OpenRouter (404 "No endpoints found", detectado 2026-07-18).
      // OJO (18/08/2026): esta variante ":free" tambien dejo de existir.
      // OpenRouter responde 404 "This model is unavailable for free" y
      // apunta al slug de pago (sin sufijo), que NO se activa aqui a
      // proposito: cambiarlo supondria empezar a pagar por cada llamada.
      // Este es el TERCER fallback (solo entra si Groq y Gemini fallan),
      // asi que se deja documentado y pendiente de decision en vez de
      // asumir el coste por defecto.
      body.model = "meta-llama/llama-3.3-70b-instruct:free";
      const upstream = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${env.OPENROUTER_KEY}` },
        body:    JSON.stringify(body),
      });
      const res = new Response(upstream.body, upstream);
      Object.entries(corsHeaders).forEach(([k, v]) => res.headers.set(k, v));
      return res;
    }

    // ── /api/tavily ──────────────────────────────────────────────────────────
    if (url.pathname === "/api/tavily") {
      const body = await request.json().catch(() => ({}));
      body.api_key = env.TAVILY_KEY;
      const upstream = await fetch("https://api.tavily.com/search", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(body),
      });
      const res = new Response(upstream.body, upstream);
      Object.entries(corsHeaders).forEach(([k, v]) => res.headers.set(k, v));
      return res;
    }

    // ── /api/football ────────────────────────────────────────────────────────
    // GET /api/football?ligas=esp.1,UEFA.CHAMPIONS&dias=3
    // GET /api/football?ligas=all&dias=1   → todas las ligas
    if (url.pathname === "/api/football") {
      const ligasParam = url.searchParams.get("ligas") || "esp.1,UEFA.CHAMPIONS,UEFA.EUROPA,eng.1";
      const dias       = Math.min(parseInt(url.searchParams.get("dias") || "2"), 7);
      const ligas      = ligasParam === "all" ? Object.keys(ESPN_LIGAS) : ligasParam.split(",");

      const hoy    = new Date();
      const fechas = [];
      for (let i = dias; i >= 0; i--) {
        const d = new Date(hoy);
        d.setDate(d.getDate() - i);
        fechas.push(d.toISOString().slice(0, 10).replace(/-/g, ""));
      }

      const partidos = [];
      const enJuego  = [];

      await Promise.all(ligas.map(async (liga) => {
        const nombreLiga = ESPN_LIGAS[liga] || liga;
        await Promise.all(fechas.map(async (fecha) => {
          try {
            const r = await fetch(
              `https://site.api.espn.com/apis/site/v2/sports/soccer/${liga}/scoreboard?dates=${fecha}`,
              { headers: { "User-Agent": "QuiniHub/1X2" } }
            );
            if (!r.ok) return;
            const data = await r.json();
            for (const ev of (data.events || [])) {
              for (const comp of (ev.competitions || [])) {
                const statusName = comp?.status?.type?.name || "";
                const terminado  = ["STATUS_FINAL","STATUS_FULL_TIME","STATUS_EXTRA_TIME","STATUS_PENALTIES"].includes(statusName);
                const vivo       = ["STATUS_IN_PROGRESS","STATUS_HALFTIME"].includes(statusName);
                const comps      = comp.competitors || [];
                const home       = comps.find(c => c.homeAway === "home") || comps[0];
                const away       = comps.find(c => c.homeAway === "away") || comps[1];
                if (!home || !away) continue;
                const local     = home?.team?.displayName || "";
                const visitante = away?.team?.displayName || "";
                const sh        = home?.score;
                const sa        = away?.score;
                const fechaP    = (ev.date || "").slice(0, 10);
                const obj = { liga: nombreLiga, local, visitante, fecha: fechaP };
                if ((terminado || vivo) && sh != null && sa != null) {
                  obj.resultado = `${sh}-${sa}`;
                  obj.ganador   = parseInt(sh) > parseInt(sa) ? local : parseInt(sa) > parseInt(sh) ? visitante : "Empate";
                }
                if (vivo) {
                  obj.en_juego = true;
                  obj.minuto   = comp?.status?.displayClock || "";
                  enJuego.push(obj);
                } else if (terminado && obj.resultado) {
                  partidos.push(obj);
                }
              }
            }
          } catch (_) {}
        }));
      }));

      // Completar con TheSportsDB para cualquier liga que ESPN no devolvió
      const ligasConDatos = new Set(partidos.map(p => p.liga));
      const theSportsDBLigasFaltantes = Object.entries(THESPORTSDB_LIGAS)
        .filter(([nombre]) => !ligasConDatos.has(nombre));

      await Promise.all(theSportsDBLigasFaltantes.map(async ([nombre, id]) => {
        try {
          const r = await fetch(`https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php?id=${id}`);
          if (!r.ok) return;
          const data = await r.json();
          for (const e of (data.events || [])) {
            const status = e.strStatus || "";
            const terminado = ["Match Finished","FT","AOT","AP","finished"].includes(status);
            if (!terminado) continue;
            const hg = e.intHomeScore, ag = e.intAwayScore;
            if (hg == null || ag == null) continue;
            partidos.push({
              liga:       nombre,
              local:      e.strHomeTeam || "",
              visitante:  e.strAwayTeam || "",
              resultado:  `${hg}-${ag}`,
              ganador:    parseInt(hg) > parseInt(ag) ? e.strHomeTeam : parseInt(ag) > parseInt(hg) ? e.strAwayTeam : "Empate",
              fecha:      e.dateEvent || "",
            });
          }
        } catch (_) {}
      }));

      const respData = {
        actualizado_en: new Date().toISOString(),
        en_juego:       enJuego,
        resultados:     partidos.slice(-200),
      };

      return new Response(JSON.stringify(respData), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response("Not found", { status: 404, headers: corsHeaders });
  },
};
