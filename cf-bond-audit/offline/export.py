import json, os
LIVE_R = [1.383, 2.183, 3.383]
D = json.load(open('../data/geometries.json')); A = json.load(open('../data/audit.json'))
os.makedirs('../data', exist_ok=True)
pts = []
for g in D['geometries']:
    if not any(abs(g['r'] - x) < 1e-9 for x in LIVE_R): continue
    cabs = [sum(abs(c) for lab, c in zip(grp['paulis'], grp['coeffs']) if set(lab) != {'I'}) for grp in g['groups']]
    pts.append(dict(r=g['r'], exact=g['exact'], groups=g['groups'], cabs=cabs,
        ansatz={n: dict(circuit=json.load(open('../circuits/' + a['qasm'].replace('.qasm', '.json'))),
                        bias=a['e_vqe'] - g['exact'], e_vqe=a['e_vqe'], cx=a['cx']) for n, a in g['ansatz'].items()}))
json.dump(dict(model=D['model'], points=pts), open('../project/data/live.json', 'w'))
curve = [dict(r=g['r'], exact=g['exact'], hf=g['hf'], ccsd=g['ccsd'], rhf_total=g['rhf_total'],
              ansatz={n: dict(e_vqe=a['e_vqe'], bias=a['e_vqe'] - g['exact'], cx=a['cx'], depth=a['depth'], params=a['params'])
                      for n, a in g['ansatz'].items()}) for g in D['geometries']]
json.dump(dict(model=D['model'], geometries=curve), open('../project/data/curve.json', 'w'), indent=1)
json.dump(A, open('../project/data/audit.json', 'w'))
for f in os.listdir('../data'): print(f, os.path.getsize('../project/data/' + f))
