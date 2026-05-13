import json
import re
from pathlib import Path
from collections import Counter

DATA = Path('data')
OUT_ANALISIS = DATA / 'analisis_ia.json'
HISTORICO_QUINIELAS = Path('historico_quinielas.csv')
CALENDARIOS = {
    'primera': DATA / 'calendario_primera.json',
    'segunda': DATA / 'calendario_segunda.json',
}

def cargar_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))

def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def parse_resultado(resultado):
    m = re.match(r'^\s*(\d+)\s*-\s*(\d+)\s*$', str(resultado or ''))
    if not m:
        return None
    goles = int(m.group(1)), int(m.group(2))
    if max(goles) > 15:
        return None
    return goles

def asegurar(stats, equipo):
    if equipo not in stats:
        stats[equipo] = {
            'equipo': equipo, 'pj': 0, 'pts': 0, 'g': 0, 'e': 0, 'p': 0,
            'gf': 0, 'gc': 0, 'dg': 0,
            'local': {'pj': 0, 'pts': 0, 'g': 0, 'e': 0, 'p': 0, 'gf': 0, 'gc': 0},
            'visitante': {'pj': 0, 'pts': 0, 'g': 0, 'e': 0, 'p': 0, 'gf': 0, 'gc': 0},
            'ultimos': [], 'racha': {},
        }
    return stats[equipo]

def aplicar_resultado(stats, local, visitante, gl, gv):
    l = asegurar(stats, local); v = asegurar(stats, visitante)
    l['pj'] += 1; v['pj'] += 1
    l['gf'] += gl; l['gc'] += gv; v['gf'] += gv; v['gc'] += gl
    l['local']['pj'] += 1; v['visitante']['pj'] += 1
    l['local']['gf'] += gl; l['local']['gc'] += gv
    v['visitante']['gf'] += gv; v['visitante']['gc'] += gl
    if gl > gv:
        rl, rv = 'G', 'P'; l['pts'] += 3; l['g'] += 1; v['p'] += 1; l['local']['pts'] += 3; l['local']['g'] += 1; v['visitante']['p'] += 1
    elif gl < gv:
        rl, rv = 'P', 'G'; v['pts'] += 3; v['g'] += 1; l['p'] += 1; v['visitante']['pts'] += 3; v['visitante']['g'] += 1; l['local']['p'] += 1
    else:
        rl = rv = 'E'; l['pts'] += 1; v['pts'] += 1; l['e'] += 1; v['e'] += 1; l['local']['pts'] += 1; v['visitante']['pts'] += 1; l['local']['e'] += 1; v['visitante']['e'] += 1
    l['ultimos'].append({'r': rl, 'gf': gl, 'gc': gv, 'condicion': 'local'})
    v['ultimos'].append({'r': rv, 'gf': gv, 'gc': gl, 'condicion': 'visitante'})

def completar_stats(stats):
    for e in stats.values():
        e['dg'] = e['gf'] - e['gc']
        ult = e['ultimos']
        for n in [5, 10]:
            b = ult[-n:]
            e[f'forma_{n}'] = {
                'pj': len(b),
                'pts': sum(3 if x['r'] == 'G' else 1 if x['r'] == 'E' else 0 for x in b),
                'gf': sum(x['gf'] for x in b),
                'gc': sum(x['gc'] for x in b),
                'resultados': [x['r'] for x in b],
            }
        def racha(valor):
            total = 0
            for x in reversed(ult):
                if x['r'] == valor: total += 1
                else: break
            return total
        sin_ganar = 0; sin_perder = 0
        for x in reversed(ult):
            if x['r'] != 'G': sin_ganar += 1
            else: break
        for x in reversed(ult):
            if x['r'] != 'P': sin_perder += 1
            else: break
        e['racha'] = {'victorias': racha('G'), 'empates': racha('E'), 'derrotas': racha('P'), 'sin_ganar': sin_ganar, 'sin_perder': sin_perder}

def normalizar_probs(p):
    p = {k: max(float(p.get(k, 1.0)), 1.0) for k in ['1', 'X', '2']}
    total = sum(p.values())
    return {k: round(v / total * 100, 1) for k, v in p.items()}

def analizar_historico():
    if not HISTORICO_QUINIELAS.exists():
        return {'disponible': False, 'frecuencias': {'1': 45.0, 'X': 28.0, '2': 27.0}, 'lectura': 'Sin histórico suficiente; se usa patrón base.'}
    texto = HISTORICO_QUINIELAS.read_text(encoding='utf-8', errors='ignore').upper()
    signos = [s for s in re.findall(r'[12X]', texto) if s in ('1', 'X', '2')]
    if not signos:
        return {'disponible': False, 'frecuencias': {'1': 45.0, 'X': 28.0, '2': 27.0}, 'lectura': 'Sin signos detectados.'}
    c = Counter(signos); total = len(signos)
    return {'disponible': True, 'total_signos': total, 'frecuencias': {'1': round(c['1']/total*100,1), 'X': round(c['X']/total*100,1), '2': round(c['2']/total*100,1)}, 'lectura': 'Histórico incorporado como ajuste suave.'}

def score_equipo(e, condicion):
    pj = max(e['pj'], 1); f5 = e.get('forma_5', {}); cf = e.get(condicion, {}); cf_pj = max(cf.get('pj', 0), 1)
    return (e['pts']/pj)*26 + (f5.get('pts',0)/max(f5.get('pj',1),1))*24 + (e['dg']/pj)*12 + ((e['gf']-e['gc'])/pj)*8 + (cf.get('pts',0)/cf_pj)*18 + ((cf.get('gf',0)-cf.get('gc',0))/cf_pj)*7 + ((f5.get('gf',0)-f5.get('gc',0))/max(f5.get('pj',1),1))*5

def explicar(local, visitante, el, ev, probs, signo, riesgo):
    f5l = el.get('forma_5', {}); f5v = ev.get('forma_5', {})
    partes = [
        f"Forma últimos 5: {local} {f5l.get('pts',0)} pts, GF {f5l.get('gf',0)}, GC {f5l.get('gc',0)}; {visitante} {f5v.get('pts',0)} pts, GF {f5v.get('gf',0)}, GC {f5v.get('gc',0)}.",
        f"Casa/fuera: {local} en casa {el['local'].get('pts',0)} pts en {el['local'].get('pj',0)} partidos; {visitante} fuera {ev['visitante'].get('pts',0)} pts en {ev['visitante'].get('pj',0)} partidos.",
        f"Balance global: {local} {el['pts']} pts, DG {el['dg']}; {visitante} {ev['pts']} pts, DG {ev['dg']}.",
    ]
    if el['racha']['sin_perder'] >= 3: partes.append(f"{local} llega con {el['racha']['sin_perder']} partidos sin perder.")
    if ev['racha']['sin_ganar'] >= 3: partes.append(f"{visitante} acumula {ev['racha']['sin_ganar']} partidos sin ganar.")
    if probs['X'] >= 31: partes.append('El empate tiene peso alto por equilibrio estadístico.')
    if riesgo == 'Alto': partes.append('Riesgo alto de sorpresa: conviene proteger con doble/triple.')
    elif riesgo == 'Medio': partes.append('Riesgo medio: candidato a doble si el presupuesto lo permite.')
    partes.append(f"Decisión IA: signo base {signo} por probabilidades 1={probs['1']}%, X={probs['X']}%, 2={probs['2']}%.")
    return ' '.join(partes)

def analizar_partido(stats, local, visitante, jornada):
    el = stats.get(local); ev = stats.get(visitante)
    if not el or not ev:
        return {'jornada': jornada, 'local': local, 'visitante': visitante, 'probabilidades': {'1':37.0,'X':31.0,'2':32.0}, 'recomendacion':'1X2', 'confianza':'Baja', 'riesgo_sorpresa':'Alto', 'explicacion':'Faltan datos completos; se recomienda protección.'}
    sl = score_equipo(el, 'local'); sv = score_equipo(ev, 'visitante'); diff = sl - sv
    p1 = 36 + max(min(diff, 28), -28); p2 = 30 + max(min(-diff, 26), -26); px = 100 - p1 - p2
    if abs(diff) < 8: px += 8
    if el['e']/max(el['pj'],1) > 0.30 or ev['e']/max(ev['pj'],1) > 0.30: px += 5
    probs = normalizar_probs({'1': p1, 'X': px, '2': p2})
    orden = sorted(probs.items(), key=lambda x: x[1], reverse=True); signo = orden[0][0]; margen = orden[0][1] - orden[1][1]
    confianza = 'Alta' if orden[0][1] >= 52 and margen >= 12 else 'Media' if orden[0][1] >= 43 else 'Baja'
    riesgo = 'Alto' if margen < 8 or probs['X'] >= 33 else 'Medio' if margen < 15 or probs['X'] >= 29 else 'Bajo'
    return {'jornada': jornada, 'local': local, 'visitante': visitante, 'probabilidades': probs, 'recomendacion': signo, 'confianza': confianza, 'riesgo_sorpresa': riesgo, 'score_local': round(sl,2), 'score_visitante': round(sv,2), 'explicacion': explicar(local, visitante, el, ev, probs, signo, riesgo)}

def construir_liga(calendario):
    stats = {}; proximos = []
    for jornada in calendario.get('jornadas', []):
        j = jornada.get('jornada')
        for p in jornada.get('partidos', []):
            local = p.get('local'); visitante = p.get('visitante')
            if not local or not visitante: continue
            res = parse_resultado(p.get('resultado'))
            if res: aplicar_resultado(stats, local, visitante, res[0], res[1])
            else: proximos.append({'jornada': j, 'local': local, 'visitante': visitante, 'fecha': p.get('fecha',''), 'hora': p.get('hora','')})
    completar_stats(stats)
    analisis = []
    for p in proximos[:100]:
        a = analizar_partido(stats, p['local'], p['visitante'], p['jornada']); a['fecha'] = p.get('fecha',''); a['hora'] = p.get('hora',''); analisis.append(a)
    equipos = sorted(stats.values(), key=lambda e: (e['pts'], e['dg'], e['gf']), reverse=True)
    return {'equipos': equipos, 'proximos_partidos': analisis, 'resumen': {'equipos_analizados': len(equipos), 'partidos_futuros_analizados': len(analisis)}}

def main():
    salida = {'version':'2.0', 'descripcion':'IA profunda: forma, casa/fuera, rachas, goles, equilibrio, riesgo de sorpresa e histórico.', 'historico_quinielas': analizar_historico(), 'ligas': {}}
    for liga, path in CALENDARIOS.items(): salida['ligas'][liga] = construir_liga(cargar_json(path, {}))
    guardar_json(OUT_ANALISIS, salida)
    print(f'Analisis IA profundo generado: {OUT_ANALISIS}')

if __name__ == '__main__': main()
