# Why More Shots Stop Helping: a C-F Bond Measurement Audit

Theme: Quantum Impact. Team: Benjamin Kaganovitch, Yan Ivanov (University of Toronto node).

For a C-F bond being stretched (CH3F, a small model for PFAS bonds), this separates circuit error from measurement error and shows which failures more shots can and cannot fix.

## Run
- Built-in simulator (preselected), default settings. About 20 s natively: six energy measurements (UCCSD and pUCCD circuits at three bond lengths, 60,000 shots each, 6 qubits), a verdict and three plots.
- Settings: `shots_per_point`, `ansatz`, `strategy` (guarded, pilot, equal), `pilot_shots`, `seed`.
- IonQ backends are not supported (70 circuits per energy; IonQ allows one per run).

## Results
- pUCCD cannot reach chemical accuracy (1.6 mHa) at any bond length: the best paired-electron state (DOCI) is already 3.4 to 10.3 mHa above exact.
- UCCSD needs 4 to 17 million shots per energy with equal allocation.
- The common pilot-shot allocation stalls near 3 mHa at equilibrium because a group often looks zero-variance in the pilot; a guarded version does not.

## Limitations
- STO-3G, 4-electron 4-orbital active space; not comparable to experiment. Ideal simulator; VQE parameters optimized offline.
- Classical CCSD matches the exact answer here; this is a measurement audit, not a speedup.

## Disclosure
- Built Oct 9 19:00 to Oct 11 19:00 ET. Nothing made before.
- AI: Claude was used to assist with the coding and the write-up; ChatGPT reviewed the method. No AI-generated images.
- Libraries: Qiskit (Apache 2.0); offline: Qiskit Nature, PySCF (Apache 2.0), NumPy, SciPy, Matplotlib. Geometry from NIST CCCBDB.

## Links
Code: TBD · Video: TBD

MIT License; see repo root for license. This effort is supported by Qollab & IonQ.
