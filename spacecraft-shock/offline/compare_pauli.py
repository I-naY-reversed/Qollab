import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import PauliEvolutionGate
from qiskit.quantum_info import SparsePauliOp
from qiskit.synthesis import SuzukiTrotter
from ss.core import *

dt = WINDOW / STEPS
for kiso in K_ISO_SWEEP:
    k = springs(kiso, K_BAT_SWEEP[1])
    op = SparsePauliOp.from_operator(hamiltonian(MASSES, k)).simplify()
    qc = QuantumCircuit(N_QUBITS)
    qc.append(PauliEvolutionGate(op, time=dt, synthesis=SuzukiTrotter(order=2, reps=1)), range(N_QUBITS))
    generic = transpile(qc, basis_gates=["rz", "sx", "x", "cx"], optimization_level=1).count_ops().get("cx", 0)
    sc = ShockCircuits(MASSES, k, dt)
    bond = sc.odd.count_ops().get("cx", 0) + sc.full.count_ops().get("cx", 0)
    print(f"k_iso = {kiso:.1e} N/m, k_bat = {K_BAT_SWEEP[1]:.1e} N/m: Pauli terms {len(op)}, CX per step generic {generic}, bond splitting {bond}")
