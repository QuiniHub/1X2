import json
import re
from pathlib import Path
from collections import Counter

DATA = Path('data')
JORNADAS = DATA / 'jornadas'
OUT = DATA / 'aprendizaje_ia.json'

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

def main():
    resumen = {'jornadas_revisadas':0, 'partidos_revisados':0, 'aciertos':0, 'fallos':0, 'fallos_por_tipo':Counter(), 'detalle':[]}
    for path in sorted(JORNADAS.glob('jornada_*.json')):
        data = cargar_json(path, {}); revisados_jornada = 0
        for p in data.get('partidos', []):
            real = signo_resultado(p.get('resultado'))
            pron = p.get('signo_nuestro') or p.get('signo_final') or p.get('pronostico_ia')
            if not real or not pron: continue
            ok = acierta(pron, real)
            resumen['partidos_revisados'] += 1; revisados_jornada += 1
            if ok: resumen['aciertos'] += 1
            else:
                resumen['fallos'] += 1
                if 'X' not in str(pron) and real == 'X': tipo = 'No cubrio empate'
                elif len(str(pron)) == 1: tipo = 'Fijo fallado'
                elif len(str(pron)) == 2: tipo = 'Doble insuficiente'
                else: tipo = 'Triple fallado'
                resumen['fallos_por_tipo'][tipo] += 1
            resumen['detalle'].append({'jornada': data.get('jornada') or path.stem, 'partido': f"{p.get('local','')} - {p.get('visitante','')}", 'pronostico': pron, 'resultado': p.get('resultado'), 'signo_real': real, 'acierto': ok})
        if revisados_jornada: resumen['jornadas_revisadas'] += 1
    total = max(resumen['partidos_revisados'], 1)
    salida = {'version':'1.0', 'precision': round(resumen['aciertos']/total*100, 2), 'jornadas_revisadas': resumen['jornadas_revisadas'], 'partidos_revisados': resumen['partidos_revisados'], 'aciertos': resumen['aciertos'], 'fallos': resumen['fallos'], 'fallos_por_tipo': dict(resumen['fallos_por_tipo']), 'detalle': resumen['detalle'][-250:], 'ajustes_recomendados':['Subir peso del empate si aumenta No cubrio empate.', 'Reducir fijos en partidos con margen probabilístico bajo.', 'Asignar triples a partidos con historial de sorpresa alta.']}
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Aprendizaje IA generado: {OUT}')

if __name__ == '__main__': main()
