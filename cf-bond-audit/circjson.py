from qiskit import QuantumCircuit
def to_list(qc):
    return dict(n=qc.num_qubits, gates=[[i.operation.name, [qc.find_bit(q).index for q in i.qubits],
                 [float(p) for p in i.operation.params]] for i in qc.data])
def from_list(d):
    qc = QuantumCircuit(d['n'])
    for name, qs, ps in d['gates']:
        if name == 'rz': qc.rz(ps[0], qs[0])
        elif name == 'sx': qc.sx(qs[0])
        elif name == 'x': qc.x(qs[0])
        elif name == 'cx': qc.cx(qs[0], qs[1])
        else: raise ValueError(name)
    return qc
