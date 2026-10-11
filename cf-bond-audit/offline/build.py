import sys; sys.path.insert(0, "..")
"""Build per-geometry data: same-space classical energies, qubit Hamiltonian, VQE (UCCSD, pUCCD),
measurement groups and exact group variances. Writes ../data/geometries.json and ../circuits/*.qasm."""
import json, os, numpy as np, scipy.optimize as so
from qiskit import transpile, qasm2
from qiskit.quantum_info import Statevector, SparsePauliOp
from qiskit_nature.second_q.hamiltonians import ElectronicEnergy
from qiskit_nature.second_q.mappers import ParityMapper
from qiskit_nature.second_q.circuit.library import HartreeFock, UCCSD, PUCCD
import chem
from circjson import to_list
RS = [1.183, 1.283, 1.383, 1.583, 1.783, 1.983, 2.183, 2.483, 2.783, 3.083, 3.383]
NP = (2, 2)
mapper = ParityMapper(num_particles=NP)
BASIS = ['rz', 'sx', 'x', 'cx']

def qubit_ham(h1, h2, ecore):
    ee = ElectronicEnergy.from_raw_integrals(h1, h2)
    op = mapper.map(ee.second_q_op()).simplify(atol=1e-12)
    return (op + SparsePauliOp('I' * op.num_qubits, ecore)).simplify(atol=1e-12)

def sector_ground(H):

    return np.linalg.eigvalsh(H.to_matrix())[0]

def run_vqe(H, ansatz, x0):

    import scipy.linalg as sl
    Hm = H.to_matrix(); v0 = Statevector(HF_CIRCUIT).data
    eig = [np.linalg.eigh(o.to_matrix()) for o in ansatz.operators]
    ops = eig
    def state(x):
        v = v0.copy()
        for k, (lam, V) in enumerate(eig): v = V @ (np.exp(-1j * x[k] * lam) * (V.conj().T @ v))
        return v
    def f(x):
        v = state(x); return float(np.real(np.vdot(v, Hm @ v)))
    best = None
    starts = ([x0] if x0 is not None else []) + [np.zeros(len(ops))]
    for s0 in starts:
        r = so.minimize(f, s0, method='BFGS', options=dict(gtol=1e-8, maxiter=3000))
        if best is None or r.fun < best.fun: best = r
    return best

def bind(ansatz, x):

    return ansatz.assign_parameters({p: float(x[int(p.name[2:-1])]) for p in ansatz.parameters})

def groups_of(H):
    out = []
    for g in H.group_commuting(qubit_wise=True):
        basis = ['I'] * H.num_qubits
        for p in g.paulis:
            for q, ch in enumerate(p.to_label()):
                if ch != 'I': basis[q] = ch
        out.append(dict(basis=''.join(basis), paulis=[p.to_label() for p in g.paulis],
                        coeffs=[float(np.real(c)) for c in g.coeffs]))
    return out

def group_stats(state, grp):

    from qiskit import QuantumCircuit
    n = len(grp['basis']); qc = QuantumCircuit(n)
    for q, ch in enumerate(reversed(grp['basis'])):
        if ch == 'X': qc.h(q)
        elif ch == 'Y': qc.sdg(q); qc.h(q)
    probs = state.evolve(qc).probabilities()
    vals = np.zeros(2 ** n)
    for lab, c in zip(grp['paulis'], grp['coeffs']):
        mask = [n - 1 - i for i, ch in enumerate(lab) if ch != 'I']
        for b in range(2 ** n):
            par = sum((b >> q) & 1 for q in mask) % 2
            vals[b] += c * (-1 if par else 1)
    mean = float(probs @ vals); var = float(probs @ (vals - mean) ** 2)
    return mean, max(var, 0.0) ** 0.5

if __name__ == '__main__':
    os.makedirs('../data', exist_ok=True); os.makedirs('../circuits', exist_ok=True)
    hf = HartreeFock(4, NP, mapper)
    global HF_CIRCUIT
    HF_CIRCUIT = hf
    raw = {'uccsd': UCCSD(4, NP, mapper, initial_state=hf), 'puccd': PUCCD(4, NP, mapper, initial_state=hf)}
    ansatze = {}
    for k, a in raw.items():
        ta = transpile(a, basis_gates=BASIS, optimization_level=1, seed_transpiler=7)
        xr = np.random.default_rng(1).normal(0, 0.3, a.num_parameters)
        d = abs(Statevector(a.assign_parameters(xr)).equiv(Statevector(ta.assign_parameters(xr))))
        assert Statevector(a.assign_parameters(xr)).equiv(Statevector(ta.assign_parameters(xr))), k
        ansatze[k] = a
    x_prev = {k: None for k in ansatze}; dm = None; rows = []
    for r in RS:
        m, mf = chem.rhf(r, dm); dm = mf.make_rdm1()
        mo, w = chem.pick_active(m, mf); h1, h2, ec = chem.active_hamiltonian(mf, mo)
        cls = chem.same_space_methods(h1, h2, ec)
        H = qubit_ham(h1, h2, ec)
        e_qubit_min = sector_ground(H)
        grps = groups_of(H)
        row = dict(r=r, rhf_total=mf.e_tot, active_weights=[float(x) for x in w], **{k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in cls.items()},
                   qubit_ground=float(e_qubit_min), n_qubits=H.num_qubits, n_terms=len(H), groups=grps, ansatz={})
        for name, ans in ansatze.items():
            res = run_vqe(H, ans, x_prev[name]); x_prev[name] = res.x
            bound = bind(ans, res.x)
            st = Statevector(bound)
            t = transpile(bound, basis_gates=BASIS, optimization_level=1, seed_transpiler=7)
            assert abs(np.vdot(Statevector(t).data, st.data)) > 1 - 1e-9, 'transpiled circuit must prepare the same state'
            fname = f"{name}_r{int(round(r*1000))}.qasm"
            open(f'../circuits/{fname}', 'w').write(qasm2.dumps(t))
            json.dump(to_list(t), open(f'../circuits/{fname[:-5]}.json', 'w'))
            stats = [group_stats(st, g) for g in grps]
            row['ansatz'][name] = dict(e_vqe=float(res.fun), params=[float(x) for x in res.x], qasm=fname,
                cx=int(t.count_ops().get('cx', 0)), depth=int(t.depth()),
                group_mean=[s[0] for s in stats], group_std=[s[1] for s in stats])
            assert abs(sum(s[0] for s in stats) - res.fun) < 1e-8, 'group means must sum to the energy'
        rows.append(row)
        print(f"r={r:.3f} HF={cls['hf']:.6f} CCSD={cls['ccsd']} exact={cls['exact']:.6f} qubitmin={e_qubit_min:.6f} "
              f"uccsd_bias={1e3*(row['ansatz']['uccsd']['e_vqe']-cls['exact']):.4f}mHa (cx {row['ansatz']['uccsd']['cx']}) "
              f"puccd_bias={1e3*(row['ansatz']['puccd']['e_vqe']-cls['exact']):.4f}mHa (cx {row['ansatz']['puccd']['cx']}) groups={len(grps)} terms={len(H)}", flush=True)
    json.dump(dict(model=dict(molecule='CH3F', basis='STO-3G', reference='RHF', active_space='CAS(4e,4o)',
               active_labels=chem.LABELS, mapper='parity, two-qubit reduction', r_CH=chem.R_CH, angle_HCF=chem.A_HCF),
               geometries=rows), open('../data/geometries.json', 'w'), indent=1)
