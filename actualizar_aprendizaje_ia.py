import json
import re
from pathlib import Path
from collections import Counter

DATA = Path('data')
JORNADAS = DATA / 'jornadas'
OUT = DATA / 'aprendizaje_ia.json'
QUINIELAS_JUGADAS = DATA / 'quinielas_jugadas.json'
HISTORIAL_QUINIELAS = DATA / 'historial_quinielas.json'

def cargar_json(path, default=None):
    if default is None: default = {}
    if not path.exists(): return default
    return json.loads(path.read_text(encoding='utf-8'))

def signo_resultado(resultado):
    m = re.match(r'^\s*(\d+)\s*-\s*(\d+)\s*$', str(resultado or ''))
    if not m: return None
    gl, gv = int(m.group(1)), int(m.group(2))
    if gl > gv: return '1'
    if gl == gv: return 'X'
    return '2'

def acierta(pron, real):
    return real in str(pron or '')

def pronostico_valido(valor):
    texto = str(valor or '').strip().upper()
    if not texto or texto in {'NO JUGADA', 'NO VALIDADA', 'PENDIENTE'}:
        return False
    return any(signo in texto for signo in ('1', 'X', '2'))

def extraer_signos_jugada(valor):
    if isinstance(valor, list):
        return [str(s).strip().upper() for s in valor if str(s).strip()]
    texto = str(valor or '').strip().upper()
    if not texto or texto in {'NO VALIDADA', 'NO JUGADA', 'PENDIENTE'}:
        return []
    partes = [p for p in texto.split() if p]
    if len(partes) > 1:
        return partes
    if re.fullmatch(r'[12X]{14}', texto):
        return list(texto)
    return []

def normalizar_jugada(jugada, origen):
    jornada = jugada.get('jornada')
    jornada_num = int(jornada) if str(jornada or '').isdigit() else None
    signos = extraer_signos_jugada(jugada.get('signos') or jugada.get('nuestra_quiniela'))
    if jornada_num and len(signos) >= 14:
        return jornada_num, {
            'signos': signos[:14],
            'pleno15': str(jugada.get('pleno15') or jugada.get('pleno15_nuestro') or '').strip(),
            'elige8': [int(x) for x in jugada.get('elige8', []) if str(x).isdigit()],
            'origen': jugada.get('origen') or origen,
        }
    return None, None

def cargar_jugadas_validadas():
    jugadas = {}
    memoria = cargar_json(QUINIELAS_JUGADAS, {'jugadas': []})
    historial = cargar_json(HISTORIAL_QUINIELAS, {'jornadas': []})
    for jugada in memoria.get('jugadas', []):
        jornada, normalizada = normalizar_jugada(jugada, 'data/quinielas_jugadas.json')
        if normalizada:
            jugadas[jornada] = normalizada
    for jugada in historial.get('jornadas', []):
        jornada, normalizada = normalizar_jugada(jugada, 'data/historial_quinielas.json')
        if normalizada and jornada not in jugadas:
            jugadas[jornada] = normalizada
    return jugadas

def clasificar_fallo(pron, real):
    texto = str(pron)
    if 'X' not in texto and real == 'X':
        return 'No cubrio empate'
    if len(texto) == 1:
        return 'Fijo fallado'
    if len(texto) == 2:
        return 'Doble insuficiente'
    return 'Triple fallado'

def numero_jornada(path):
    m = re.search(r'(\d+)', path.stem)
    return int(m.group(1)) if m else 0

def main():
    resumen = {'jornadas_revisadas':0, 'partidos_revisados':0, 'aciertos':0, 'fallos':0, 'fallos_por_tipo':Counter(), 'detalle':[]}
    jugadas = cargar_jugadas_validadas()
    fuentes_jugadas = Counter(jugada.get('origen') or 'desconocido' for jugada in jugadas.values())
    for path in sorted(JORNADAS.glob('jornada_*.json'), key=numero_jornada):
        data = cargar_json(path, {}); revisados_jornada = 0
        jornada_num = data.get('jornada')
        jugada = jugadas.get(jornada_num)
        for idx, p in enumerate(data.get('partidos', [])):
            real = signo_resultado(p.get('resultado'))
            pron = None
            if jugada and idx < len(jugada['signos']):
                pron = jugada['signos'][idx]
            else:
                pron = p.get('signo_nuestro') or p.get('signo_final') or p.get('pronostico_ia')
            if not real or not pronostico_valido(pron): continue
            ok = acierta(pron, real)
            resumen['partidos_revisados'] += 1; revisados_jornada += 1
            if ok: resumen['aciertos'] += 1
            else:
                resumen['fallos'] += 1
                resumen['fallos_por_tipo'][clasificar_fallo(pron, real)] += 1
            resumen['detalle'].append({'jornada': jornada_num or path.stem, 'partido': f"{p.get('local','')} - {p.get('visitante','')}", 'pronostico': pron, 'resultado': p.get('resultado'), 'signo_real': real, 'acierto': ok, 'origen': jugada.get('origen') if jugada else 'partido'})
        if revisados_jornada: resumen['jornadas_revisadas'] += 1
    total = max(resumen['partidos_revisados'], 1)
    salida = {'version':'1.0', 'precision': round(resumen['aciertos']/total*100, 2), 'jornadas_revisadas': resumen['jornadas_revisadas'], 'partidos_revisados': resumen['partidos_revisados'], 'aciertos': resumen['aciertos'], 'fallos': resumen['fallos'], 'fallos_por_tipo': dict(resumen['fallos_por_tipo']), 'detalle': resumen['detalle'][-250:], 'ajustes_recomendados':['Subir peso del empate si aumenta No cubrio empate.', 'Reducir fijos en partidos con margen probabilístico bajo.', 'Asignar triples a partidos con historial de sorpresa alta.']}
    salida['fuentes_jugadas'] = dict(fuentes_jugadas)
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Aprendizaje IA generado: {OUT}')

if __name__ == '__main__': main()
