import numpy as np
from pyscf import gto, scf, mcscf, ao2mo, cc, fci
NCAS, NELEC = 4, 4
LABELS = ['C 2s', 'C 2pz', 'F 2s', 'F 2pz']
R_CH, A_HCF = 1.087, 108.73

def geom(r):
    th = np.radians(A_HCF); hz, hr = R_CH*np.cos(th), R_CH*np.sin(th)
    H = [(hr*np.cos(p), hr*np.sin(p), hz) for p in np.radians([0, 120, 240])]
    return [['C', (0, 0, 0)], ['F', (0, 0, r)]] + [['H', h] for h in H]

def rhf(r, dm0=None):
    m = gto.M(atom=geom(r), basis='sto-3g', verbose=0)
    mf = scf.RHF(m); mf.conv_tol = 1e-11
    mf.kernel(dm0)
    return m, mf

def pick_active(m, mf):
    idx = m.search_ao_label(LABELS)
    S = m.intor('int1e_ovlp'); C = mf.mo_coeff
    proj = np.einsum('pi,pq,qi->i', C[idx], S[np.ix_(idx, idx)], C[idx])
    nocc = m.nelectron // 2
    occ = sorted(range(nocc), key=lambda i: -proj[i])[:2]
    vir = sorted(range(nocc, C.shape[1]), key=lambda i: -proj[i])[:2]
    act = sorted(occ) + sorted(vir)
    rest_occ = [i for i in range(nocc) if i not in act]
    rest_vir = [i for i in range(nocc, C.shape[1]) if i not in act]
    order = rest_occ + act + rest_vir
    return C[:, order], proj[act]

def active_hamiltonian(mf, mo):
    cas = mcscf.CASCI(mf, NCAS, NELEC)
    h1, ecore = cas.get_h1eff(mo)
    h2 = ao2mo.restore(1, cas.get_h2eff(mo), NCAS)
    return h1, h2, ecore

def same_space_methods(h1, h2, ecore):

    mol = gto.M(verbose=0); mol.nelectron = NELEC; mol.incore_anyway = True
    mf = scf.RHF(mol); mf.get_hcore = lambda *a: h1; mf.get_ovlp = lambda *a: np.eye(NCAS)
    mf._eri = ao2mo.restore(8, h2, NCAS); mf.energy_nuc = lambda *a: ecore
    dm0 = np.diag([2, 2, 0, 0]).astype(float)
    mf.conv_tol = 1e-12; mf.kernel(dm0)
    c = cc.CCSD(mf); c.conv_tol = 1e-10; c.max_cycle = 300; c.kernel()
    efci = fci.direct_spin1.kernel(h1, h2, NCAS, NELEC)[0] + ecore
    return dict(hf=mf.e_tot, ccsd=c.e_tot if c.converged else None, ccsd_converged=bool(c.converged), exact=efci)

if __name__ == '__main__':
    dm = None
    for r in [1.383, 1.783, 2.183, 2.783, 3.383]:
        m, mf = rhf(r, dm); dm = mf.make_rdm1()
        mo, w = pick_active(m, mf); h1, h2, ec = active_hamiltonian(mf, mo)
        cas = mcscf.CASCI(mf, NCAS, NELEC); ecas = cas.kernel(mo)[0]
        res = same_space_methods(h1, h2, ec)
        print(r, 'RHF', round(mf.e_tot, 6), 'CASCI', round(ecas, 6), {k: (round(v, 6) if isinstance(v, float) else v) for k, v in res.items()}, 'proj', np.round(w, 2))
