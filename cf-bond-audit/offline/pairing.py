import sys; sys.path.insert(0, "..")
"""Paired-electron (seniority-zero, DOCI) certificate in the same CAS(4e,4o) model.
E_pair = lowest energy of ANY state built only from determinants with both electrons of each pair in the same
spatial orbital (6 determinants: choose 2 of 4 orbitals). pUCCD only reaches such states, so E_pUCCD >= E_pair >= E_exact.
E_pair - E_exact is therefore a lower bound on the error of every pUCCD circuit in these orbitals."""
import json, numpy as np
from pyscf import fci
from pyscf.fci import cistring
import chem, build

def pair_energy(h1, h2, ec, n=4, ne=(2, 2)):
    na = cistring.num_strings(n, ne[0]); nb = cistring.num_strings(n, ne[1])
    H = np.zeros((na * nb, na * nb))
    h2e = fci.direct_spin1.absorb_h1e(h1, h2, n, ne, 0.5)
    for k in range(na * nb):
        e = np.zeros(na * nb); e[k] = 1
        H[:, k] = fci.direct_spin1.contract_2e(h2e, e.reshape(na, nb), n, ne).ravel()
    H = (H + H.T) / 2
    e_full = np.linalg.eigvalsh(H)[0] + ec
    idx = [i * nb + i for i in range(na)]
    e_pair = np.linalg.eigvalsh(H[np.ix_(idx, idx)])[0] + ec
    return e_full, e_pair

if __name__ == '__main__':
    D = {round(g['r'], 3): g for g in json.load(open('../data/geometries.json'))['geometries']}
    dm = None; rows = []
    for r in build.RS:
        m, mf = chem.rhf(r, dm); dm = mf.make_rdm1()
        mo, w = chem.pick_active(m, mf); h1, h2, ec = chem.active_hamiltonian(mf, mo)
        e_full, e_pair = pair_energy(h1, h2, ec); g = D[round(r, 3)]
        assert abs(e_full - g['exact']) < 1e-8, 'full CI in the determinant basis must equal CASCI'
        ep = g['ansatz']['puccd']['e_vqe']
        assert g['exact'] - 1e-9 <= e_pair <= ep + 1e-9, (r, g['exact'], e_pair, ep)
        rows.append(dict(r=r, exact=g['exact'], e_pair=e_pair, e_puccd=ep,
                         pair_gap=e_pair - g['exact'], puccd_minus_pair=ep - e_pair))
        print(f"r={r:.3f}  E_pair-E_exact={1e3*(e_pair-g['exact']):7.3f} mHa   E_pUCCD-E_pair={1e3*(ep-e_pair):.2e} mHa", flush=True)
    json.dump(dict(note='seniority-zero (DOCI) energy in the same CAS(4e,4o) orbitals', rows=rows),
              open('../data/pairing.json', 'w'), indent=1)
