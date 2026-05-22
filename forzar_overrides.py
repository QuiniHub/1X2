import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MEM=ROOT/'data'/'memoria_ia'
CTX=MEM/'contexto_competitivo.json'
OVR=MEM/'objetivos_jornada_actual.json'

def load(p):
    return json.loads(p.read_text(encoding='utf-8'))

def save(p,x):
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def key(s):
    s=(s or '').lower()
    for a,b in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ü','u'),('ñ','n')]:
        s=s.replace(a,b)
    for t in [' real ',' club ',' fc ',' cf ',' cd ',' sd ',' ud ',' rc ',' de ',' del ',' la ',' el ']:
        s=s.replace(t,' ')
    return ''.join(c for c in s if c.isalnum())

def find(name,ovs):
    if name in ovs:
        return ovs[name]
    k=key(name)
    for n,o in ovs.items():
        if key(n)==k:
            return o
    return None

def obj(o):
    r={'objetivo':o.get('objetivo_principal','situacion_final'),'estado':o.get('estado','situacion_final'),'vivo':bool(o.get('vivo',False)),'terminal':bool(o.get('terminal',not o.get('vivo',False))),'override_oficial_jornada':True,'lectura':o.get('lectura','Objetivo oficial aplicado.')}
    for c in ['puntos_necesarios_para_asegurar','puntos_necesarios_para_entrar','puntos_necesarios_para_salvarse','depende_de_rivales']:
        if c in o:
            r[c]=o[c]
    return r

ctx=load(CTX)
ovs=load(OVR).get('equipos',{})
for liga in ['primera','segunda']:
    for e in ctx.get(liga,{}).get('equipos',[]):
        o=find(e.get('equipo'),ovs)
        if not o:
            continue
        r=obj(o)
        e['objetivos']=[r]
        e['objetivo_principal']=r
        e['objetivos_vivos']=[r] if r.get('vivo') else []
        e['motivacion_competitiva']=o.get('motivacion_competitiva','baja')
        e['motivacion']=e['motivacion_competitiva']
        e['situacion_competitiva']=o.get('situacion_competitiva',r.get('estado'))
        e['lectura_resumen']=r['lectura']
        e['override_oficial_jornada']=True
ctx['version']='1.4'
save(CTX,ctx)
print('ok')
