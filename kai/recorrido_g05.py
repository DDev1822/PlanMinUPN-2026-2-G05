"""Controlador E1 → teoría S11 → aplicación S11 → S12 → entrega.

Reutiliza SQLite/Excel V1/V2 y ficha E1 sin reescribir sus aprobaciones.
Las extensiones V3 conservan los datos observados por corrida.
"""
from __future__ import annotations
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import quote
import zipfile

ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import registro_v2 as theory
import ficha_individual as e1
import ficha_individual_v2 as e1v2
import aplicacion_g05 as application
from src.missions.products import product_status, verified_product

REQUEST=ROOT/'.kai_solicitud_recorrido_g05.json'
DATA=ROOT/'.kai_local'


def e1_status(alias):
    return e1v2.sync(alias,DATA)


def application_view(info):
    """Guía privada para Kai; el contrato de las 26 observaciones permanece igual."""
    pending=info.get('pending')
    if not pending:return info
    fields,_,_=application.catalog(ROOT)
    field=next((f for f in fields if f['id']==pending['id']),None)
    if field is None:raise ValueError('La observación pendiente no pertenece al modelo G05 verificado')
    suffix=('?bloque='+quote(field['block']) if field['block'] else '')
    pending=dict(pending)
    pending['consulta_estudiantil']='docs/learning/RESULTADOS_G05.html'+suffix+'#campo-'+quote(field['id'])
    pending['dato_verificado']={'valor':field['expected'],'unidad':field['unit'],
                                'modelo':field['stage'],'procedencia':'PRODUCTO_G05_VALIDADO'}
    pending['tipo_actividad']='LECTURA_DE_DATO'
    return dict(info,pending=pending)


def decorate(info):
    info=copy.deepcopy(info)
    products=product_status(ROOT)
    app=application_view(application.progress(info['alumno'],ROOT,DATA))
    ficha=e1_status(info['alumno'])
    info['controller_version']=1
    info['productos_grupales']={k:{i:v for i,v in p.items() if i!='summary'} for k,p in products.items()}
    info['aplicacion_individual_v3']=app;info['ficha_e1']=ficha
    info['entregables_individuales']=dict(comprension=info['comprension_registrada'],ficha_e1=ficha['complete'],aplicacion_s11_s12=app['complete'])
    info['entrega_final_lista']=(info['comprension_registrada'] and ficha['complete'] and app['complete'] and
                               all(p['status']=='VALIDATED' for p in products.values()))
    actual=info['actividad_actual']
    if actual and actual.startswith('S11.0'):
        info['indicacion_visor']='Abre Métodos y teoría S11 en index.html#teoria. Los ejemplos de la guía no son resultados G05.'
    if actual and actual in {'S11.1','S11.2','S11.3','S11.4','S11.5','S11.6'}:
        if products['S11']['status']!='VALIDATED':
            info['objetivo_siguiente']='EJECUTAR_Y_VERIFICAR_S11_G05';info['actividad']=None
        else:
            info['actividad']['visor']=dict(url='index.html#s11',pantalla='S11 · Recursos académico',
                accion='Carga el visor S11. Cambia la propiedad, consulta un bloque y mira su valor, unidad, soporte y causa de faltante.',
                pregunta_desde_visor=info['actividad']['pregunta'])
    if info['etapas']['S11']=='S11_COMPRENSION_REGISTRADA' and not app['S11_complete']:
        info['objetivo_siguiente']='COMPLETAR_APLICACION_S11';info['actividad']=None
    if actual and actual.startswith('S12.'):
        if products['S12']['status']!='VALIDATED':
            if app['S11_complete']:info['objetivo_siguiente']='EJECUTAR_Y_VERIFICAR_S12_G05'
            info['actividad']=None
        elif info['actividad']:
            info['actividad']['visor']=dict(url='index.html#s12',pantalla='S12 · Reservas académico',
                accion='Carga S12. Consulta la clase candidata y el movimiento/OPEX asignados a un bloque; compara A y B en la tabla.',
                pregunta_desde_visor=info['actividad']['pregunta'])
    if info['comprension_registrada']:
        info['objetivo_siguiente']='ENTREGABLES_ACADEMICOS_LISTOS' if info['entrega_final_lista'] else (
            'COMPLETAR_APLICACION_S11' if not app['S11_complete'] else
            'COMPLETAR_APLICACION_S12' if not app['S12_complete'] else 'COMPLETAR_FICHA_E1' if not ficha['complete'] else 'VERIFICAR_PRODUCTOS_GRUPALES')
    if info['objetivo_siguiente'] in {'COMPLETAR_APLICACION_S11','COMPLETAR_APLICACION_S12'}:
        info['siguiente_observacion']=app.get('pending')
    return info


def deliver(alias,info):
    if not info['entrega_final_lista']:
        raise ValueError('Faltan comprensión, ficha E1, aplicación V3 o productos grupales verificados')
    if not info['ficha_e1']['excel_actualizado']:
        raise ValueError('El Excel V2 está abierto; ciérralo y vuelve a generar la entrega')
    folder=DATA/alias
    files=[Path(info['ficha_e1']['xlsx']),folder/'Progreso_Kai_G05_Teoria_V2.xlsx',Path(info['aplicacion_individual_v3']['xlsx'])]
    if not all(p.is_file() for p in files):raise ValueError('Falta un Excel individual; consulta su estado para regenerarlo')
    with closing(sqlite3.connect((folder/'teoria_v2.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        rows=db.execute("SELECT actividad,respuesta,criterio_observado FROM eventos_v2 WHERE estado='DEMOSTRADO' ORDER BY rowid").fetchall()
    report=f'# Evidencia individual G05 · {alias}\n\nOcho competencias E1 con respuestas del alumno; ficha V2 con 21 datos de fuente verificada, y 26 observaciones de aplicación S11/S12.\n\n'
    report+='Los archivos grupales se entregan separados. Generaciones: '+json.dumps({k:p.get('run_id') for k,p in info['productos_grupales'].items()})+'\n\n'
    report+='## Palabras registradas del alumno\n\n'
    for activity,response,criterion in rows:
        report+=f'### {activity}\n\n{response}\n\nCriterio observado por el tutor: {criterion}\n\n'
    report+='## Procedencia de los 21 datos de la ficha V2\n\nLos valores siguientes proceden del resumen verificado; ninguno se atribuye como respuesta del alumno. El ID de evidencia enlaza, cuando corresponde, la competencia E1 registrada por separado.\n\n'
    with closing(sqlite3.connect((folder/'ficha_individual_v2.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        fields=db.execute('SELECT field_id,origin,source_sha256,activity_id,evidence_event_id FROM campos_v2 ORDER BY field_id').fetchall()
    report+='| Campo | Procedencia | SHA fuente | Actividad | Evento E1 |\n|---|---|---|---|---|\n'
    for field,origin,sha,activity,event in fields:
        report+=f'| {field} | {origin} | `{sha}` | {activity or "—"} | `{event}` |\n' if event else f'| {field} | {origin} | `{sha}` | — | — |\n'
    report+='La valoración semántica corresponde al tutor. Este registro no acredita ensayo conversacional humano ni calificación oficial.\n'
    destination=Path(info['aplicacion_individual_v3']['xlsx']).parent
    md=destination/'Informe_Individual_G05_V2.md';md.write_text(report,encoding='utf-8')
    target=destination/'Entregable_Individual_G05_V2.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in [*files,md]:z.write(p,p.name)
    return str(target)


def process(request):
    if not isinstance(request,dict):raise ValueError('Se requiere una solicitud JSON')
    alias=request.get('alumno');theory.carpeta(alias)
    op=request.get('operacion')
    base=dict(route_id=theory.ROUTE_ID,route_version=theory.VERSION,alumno=alias)
    theory.DATA=DATA
    if op in {'estado_aplicacion','responder_aplicacion'}:
        current=theory.procesar(dict(base,operacion='estado'))
        return application_view(application.process(request,root=ROOT,data=DATA,comprehension=current))
    if op=='estado_ficha_e1':
        return e1_status(alias)
    if op=='responder_ficha_e1':
        raise ValueError('La ficha E1 V2 se completa con fuentes verificadas durante las actividades; no solicita copiar valores')
    if op=='entregar_individual':
        current=decorate(theory.procesar(dict(base,operacion='estado')))
        return dict(ok=True,zip=deliver(alias,current),entrega_final_lista=True)
    if op not in theory.CAMPOS:raise ValueError('Operación del recorrido desconocida')
    payload={k:v for k,v in request.items() if k not in {'controller_version'}}|base
    if op=='iniciar_etapa' and request.get('etapa')=='S12':
        state=decorate(theory.procesar(dict(base,operacion='estado')))
        if not state['aplicacion_individual_v3']['S11_complete']:
            raise ValueError('Primero verifica las 13 observaciones de aplicación S11')
        if state['productos_grupales']['S11']['status']!='VALIDATED' or state['productos_grupales']['S12']['status']!='VALIDATED':
            raise ValueError('S12 requiere S11 validado y una corrida S12 verificada')
        # Un inicio histórico sigue identificado con su base; la aplicación V3
        # acredita separadamente el vínculo actual con G05.
        payload['base']=state['base_s12'] or 'G05_S11_VALIDADO'
    return decorate(theory.procesar(payload))


def start_turn(alias=None):
    """Puerta breve para iniciar o retomar una tutoría, sin exponer el estado técnico."""
    group=theory.CONFIG['grupo'];project=theory.CONFIG['proyecto']
    if alias is None:
        return dict(ok=True,grupo=group,proyecto=project,accion='SOLICITAR_ALIAS',
                    pregunta_principal='¿Qué alias pseudónimo quieres usar para guardar tu progreso? '
                    'Usa 3 a 40 letras, números, guion o guion bajo; no necesito tu nombre legal ni correo.')
    theory.DATA=DATA
    theory.carpeta(alias)
    base=dict(route_id=theory.ROUTE_ID,route_version=theory.VERSION,alumno=alias)
    # E1 consulta solo el registro individual; los modelos se verifican cuando
    # una actividad S11/S12 o una entrega los necesita.
    state=theory.procesar(dict(base,operacion='estado'))
    new=state['eventos']==0 and state['etapas']['E1']=='E1_NO_INICIADA'
    if new:
        state=theory.procesar(dict(base,operacion='iniciar_etapa',etapa='E1'))
    e1_status(alias)
    if state['actividad_actual'] is None or not state['actividad_actual'].startswith('E1.'):
        state=process(dict(operacion='estado',alumno=alias))
    result=dict(ok=True,grupo=group,proyecto=project,alumno=alias,nuevo=new,
                eventos=state['eventos'],actividad_id=state['actividad_actual'],
                objetivo=state['objetivo_siguiente'])
    activity=state.get('actividad')
    if activity:
        checkpoint=state.get('checkpoint')
        question=(checkpoint.get('pregunta_pendiente') if checkpoint else None) or activity['pregunta']
        result.update(accion='ENSEÑAR_Y_PREGUNTAR',titulo=activity['titulo'],
                      explicacion=activity['explicacion'],pregunta_principal=question,
                      criterio=activity['criterio'],pista=activity['pista'])
        if activity['etapa']=='E1':
            result['contexto_verificado']=e1v2.context_for(activity['id'])
    else:
        result.update(accion=state['objetivo_siguiente'],
                      siguiente_observacion=state.get('siguiente_observacion'))
    return result


def main():
    if sys.argv[1:2]==['inicio'] and len(sys.argv)<=3:
        try:
            result=start_turn(sys.argv[2] if len(sys.argv)==3 else None)
            print(json.dumps(result,ensure_ascii=True,allow_nan=False));return 0
        except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as exc:
            print(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=True));return 1
    if sys.argv[1:]!=['procesar-pendiente']:
        print('Uso: python kai/recorrido_g05.py inicio [alias] | procesar-pendiente',file=sys.stderr);return 2
    try:
        request=json.loads(REQUEST.read_text(encoding='utf-8'));result=process(request)
        REQUEST.unlink();print(json.dumps(result,ensure_ascii=True,allow_nan=False));return 0
    except (ValueError,OSError,KeyError,TypeError,sqlite3.Error,zipfile.BadZipFile) as exc:
        print(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=True));return 1


if __name__=='__main__':raise SystemExit(main())
