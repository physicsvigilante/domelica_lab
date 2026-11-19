#!/usr/bin/env python3
"""Independent curve, chain-rule, exact-state and conservation checker."""
import csv, json, math, os
from pathlib import Path
ROOT=Path.cwd()
CASES=('scalar_msl','scalar_explicit','direct_msl','direct_explicit','implicit_msl','implicit_explicit')
report={'schema':'domelica.omc-derivative-probe.v1','version':os.getenv('OMC_VERSION'),
        'image':os.getenv('OMC_IMAGE'),'cases':{},'comparisons':{}}
errors=[]

def curve(q):
    if q < 0: return 10-250*q, -250
    if q > .008: return -2250*(q-.008), -2250
    return 10-250*q-125000*q*q, -250-250000*q

def read(name):
    path=ROOT/f'probe_{name}_res.csv'
    if not path.is_file(): raise AssertionError(f'{name}: native CSV missing')
    fields={'time','q','qD','head','headD'}
    if not name.startswith('scalar'): fields|={'ratio','ratioD'}
    if name.startswith('implicit'): fields|={'tankA','tankB','waterVolume'}
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        missing=fields-set(reader.fieldnames or [])
        if missing: raise AssertionError(f'{name}: missing native columns {sorted(missing)}')
        rows=[{k:float(v) for k,v in row.items() if k in fields} for row in reader]
    if name.startswith('scalar'):
        for row in rows: row.update(ratio=1.,ratioD=0.)
    if len(rows)<401 or abs(rows[0]['time'])>1e-8 or abs(rows[-1]['time']-2)>1e-7:
        raise AssertionError(f'{name}: incomplete output; {len(rows)} samples, last {rows[-1]["time"] if rows else "none"}')
    if any(not math.isfinite(v) for row in rows for v in row.values()):
        raise AssertionError(f'{name}: nonfinite native result')
    if any(not 0<=b['time']-a['time']<=.005001 for a,b in zip(rows,rows[1:])):
        raise AssertionError(f'{name}: sampling grid incomplete')
    return rows

def verify(name,rows):
    value_error=derivative_error=exact_error=volume_error=implicit_qd_error=algebraic_chain_error=0.
    for row in rows:
        t,q,r=row['time'],row['q'],row['ratio']
        if r<=0.1: raise AssertionError(f'{name}: nonpositive speed at {t}')
        f,s=curve(q/r)
        expected_head=r*r*f
        if name.startswith('implicit'):
            # Differentiate the independent algebraic constraint H=3+250q+B-A.
            # Since A'=-q/0.25 and B'=q/0.25, solve the exact q' identity:
            expected_qd=(2*q/.25-2*r*row['ratioD']*f+s*q*row['ratioD'])/(r*s-250)
            implicit_qd_error=max(implicit_qd_error,abs(row['qD']-expected_qd))
        else: expected_qd=row['qD']
        expected_der=2*r*row['ratioD']*f+s*(r*expected_qd-q*row['ratioD'])
        algebraic_der=2*r*row['ratioD']*f+s*(r*row['qD']-q*row['ratioD'])
        algebraic_chain_error=max(algebraic_chain_error,abs(row['headD']-algebraic_der))
        value_error=max(value_error,abs(row['head']-expected_head))
        derivative_error=max(derivative_error,abs(row['headD']-expected_der))
        if name.startswith('direct'):
            q_expected=.0015+.0003*t+.00004*(1-math.cos(2*t))
            r_expected=.9+(.07/.3)*math.sin(.3*t)
            exact_error=max(exact_error,abs(q-q_expected),abs(r-r_expected))
        elif name.startswith('scalar'):
            exact_error=max(exact_error,abs(q-(.002+.0002*t)),abs(r-1))
        else:
            volume_error=max(volume_error,abs(row['waterVolume']-.35),
                abs(.25*(row['tankA']+row['tankB'])-.35))
            if abs(row['head']-(3+250*q+row['tankB']-row['tankA']))>=1e-5:
                raise AssertionError(f'{name}: implicit head balance wrong at {t}')
    # Finite differences from the recorded trajectory do not depend on
    # the compiler's exported derivative aliases or the analytical oracle.
    fd_head_error=fd_q_error=0.
    for i in range(1,len(rows)-1):
        dt=rows[i+1]['time']-rows[i-1]['time']
        if dt < 1e-9: continue
        h_fd=(rows[i+1]['head']-rows[i-1]['head'])/dt
        q_fd=(rows[i+1]['q']-rows[i-1]['q'])/dt
        fd_head_error=max(fd_head_error,abs(h_fd-rows[i]['headD']))
        fd_q_error=max(fd_q_error,abs(q_fd-rows[i]['qD']))
    d={'samples':len(rows),'maxValueErrorM':value_error,
       'maxHeadDerivativeErrorMPerS':derivative_error,
       'maxExactDirectStateError':exact_error,'maxVolumeErrorM3':volume_error,
       'maxImplicitFlowDerivativeErrorM3PerS2':implicit_qd_error,
       'maxChainErrorUsingExportedQDMPerS':algebraic_chain_error,
       'maxHeadDerivativeFiniteDifferenceErrorMPerS':fd_head_error,
       'maxFlowDerivativeFiniteDifferenceErrorM3PerS2':fd_q_error}
    fails=[]
    if value_error>=1e-6: fails.append('value curve')
    if derivative_error>=1e-5: fails.append('head derivative')
    if name.startswith(('direct','scalar')) and exact_error>=1e-6: fails.append('exact prescribed trajectory')
    if name.startswith('implicit') and volume_error>=1e-8: fails.append('volume conservation')
    if name.startswith('implicit') and implicit_qd_error>=1e-4: fails.append('implicit flow derivative')
    if fd_head_error>=1e-3: fails.append('head derivative versus finite difference')
    if fd_q_error>=1e-4: fails.append('flow derivative versus finite difference')
    d['passed']=not fails;d['failedCriteria']=fails
    return d

rows={}
for case in CASES:
    try:
        rows[case]=read(case)
        result=verify(case,rows[case]);report['cases'][case]=result
        print(('PASS' if result['passed'] else 'FAIL'),case,json.dumps(result),flush=True)
        if not result['passed']:errors.append(case+': '+','.join(result['failedCriteria']))
    except Exception as ex:
        report['cases'][case]={'passed':False,'error':str(ex)}
        errors.append(f'{case}: {ex}');print('FAIL',errors[-1],flush=True)
for a,b,label in [('scalar_msl','scalar_explicit','scalar'),('direct_msl','direct_explicit','direct'),('implicit_msl','implicit_explicit','implicit')]:
    if a not in rows or b not in rows:continue
    if len(rows[a])!=len(rows[b]):
        errors.append(label+': unequal native sample counts');continue
    delta={k:max(abs(x[k]-y[k]) for x,y in zip(rows[a],rows[b])) for k in ('time','q','ratio','head')}
    acceptable=delta['time']<1e-8 and delta['q']<1e-6 and delta['ratio']<1e-6 and delta['head']<1e-4
    report['comparisons'][label]={'maxAbs':delta,'passed':acceptable}
    print(('PASS' if acceptable else 'FAIL'),'MSL/explicit '+label,json.dumps(delta),flush=True)
    if not acceptable:errors.append(label+': MSL versus explicit trajectory divergence')
report['errors']=errors;report['passed']=not errors
(ROOT/'probe-report.json').write_text(json.dumps(report,indent=2)+'\n')
print('PROBE_FINAL',json.dumps({'passed':report['passed'],'errors':errors}),flush=True)
raise SystemExit(0 if report['passed'] else 1)
