import sys; sys.path.insert(0, "..")
"""Checks for the offline model (run: python test_model.py). Each must pass before data are shipped."""
import json, numpy as np
import chem, build
from qiskit.quantum_info import Statevector
from circjson import from_list
from qiskit_nature.second_q.circuit.library import HartreeFock, UCCSD, PUCCD

def test_geometry(r=2.183):
    m, mf = chem.rhf(r)
    mo, w = chem.pick_active(m, mf); h1, h2, ec = chem.active_hamiltonian(mf, mo)
    cls = chem.same_space_methods(h1, h2, ec)
    from pyscf import mcscf
    e_casci = mcscf.CASCI(mf, 4, 4).kernel(mo)[0]
    assert abs(cls['exact'] - e_casci) < 1e-9, 'FCI on active integrals must equal CASCI'
    assert abs(cls['hf'] - mf.e_tot) < 1e-8, 'HF determinant in the active space must equal the full RHF energy'
    H = build.qubit_ham(h1, h2, ec)
    assert abs(build.sector_ground(H) - e_casci) < 1e-8, 'qubit Hamiltonian ground state must equal CASCI'
    print('model checks pass at r =', r)

def test_shipped():
    D = json.load(open('../data/geometries.json'))
    for g in D['geometries']:
        for n, a in g['ansatz'].items():
            st = Statevector(from_list(json.load(open('../circuits/' + a['qasm'].replace('.qasm', '.json')))))
            assert abs(sum(a['group_mean']) - a['e_vqe']) < 1e-8
            assert a['e_vqe'] >= g['exact'] - 1e-9, 'variational energy cannot be below exact'
            gs = [build.group_stats(st, grp)[0] for grp in g['groups']]
            assert abs(sum(gs) - a['e_vqe']) < 1e-8, 'shipped circuit must reproduce the VQE energy'
    print('shipped circuits reproduce VQE energies at', len(D['geometries']), 'geometries')

def test_active_space_gap():

    dm = None
    for r in build.RS:
        m, mf = chem.rhf(r, dm); dm = mf.make_rdm1()
        idx = m.search_ao_label(chem.LABELS); S = m.intor('int1e_ovlp'); C = mf.mo_coeff
        p = np.einsum('pi,pq,qi->i', C[idx], S[np.ix_(idx, idx)], C[idx]); n = m.nelectron // 2
        o = np.sort(p[:n])[::-1]; v = np.sort(p[n:])[::-1]
        assert o[1] > 0.85 and o[2] < 0.6 and v[1] > 1.0 and v[2] < 0.01, (r, o[:3], v[:3])
    print('active-space selection gap holds at all', len(build.RS), 'geometries')

def test_puccd_global(n_starts=40):

    from qiskit_nature.second_q.circuit.library import HartreeFock, PUCCD
    hf = HartreeFock(4, build.NP, build.mapper); build.HF_CIRCUIT = hf
    D = {g['r']: g for g in json.load(open('../data/geometries.json'))['geometries']}
    dm = None
    for r in build.RS[:3]:
        m, mf = chem.rhf(r, dm); dm = mf.make_rdm1()
        mo, w = chem.pick_active(m, mf); H = build.qubit_ham(*chem.active_hamiltonian(mf, mo))
        a = PUCCD(4, build.NP, build.mapper, initial_state=hf); rng = np.random.default_rng(0)
        best = min(build.run_vqe(H, a, rng.uniform(-np.pi, np.pi, 4)).fun for _ in range(n_starts))
        assert best >= D[r]['ansatz']['puccd']['e_vqe'] - 1e-8, r
    print('pUCCD optima match the best of', n_starts, 'random starts at', build.RS[:3])

if __name__ == '__main__':
    test_geometry(); test_geometry(1.383); test_shipped(); test_active_space_gap(); test_puccd_global()
