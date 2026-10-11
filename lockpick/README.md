# Lockpick

Theme: Quantum Playground. Team: Benjamin Kaganovitch, Yan Ivanov (University of Toronto node).

A qubit is in one of two known, non-orthogonal states. Choose a measurement and compare it, on the selected backend, with the Helstrom bound and the Ivanovic-Dieks-Peres (IDP) measurement.

## Run
- Built-in simulator (preselected), default settings. Each Measure runs one circuit (2 qubits, 4 for IDP), under a second.
- At beta = 0, Measure (Enter) gives P_corr = 0.50. Rotating the axis to 90 deg (drag in Fig. 1, or arrow keys) reaches the Helstrom bound, 0.933. Unambiguous (U) gives P_corr = P_? = 0.50, P_err = 0.
- Keys: 1 to 3 overlap, P a priori probability, O Helstrom axis.
- IonQ simulators: both states run side by side in one circuit; one measurement per run.

## How it works
- States RY(+-theta)|0>, overlap s = cos theta. Minimum-error: RY(-beta), then a computational-basis measurement.
- IDP: a three-outcome POVM via a Neumark dilation, one ancilla per state, no mid-circuit measurement.
- `offline/test_core.py` checks the circuits against Eqs. (2) to (4) for every preset.

## Limitations
- Pure states, known a priori probabilities, one copy, noiseless. IDP is optimal only for equal a priori probabilities.
- Classically simulable; no speedup is claimed.

## Disclosure
- Built Oct 11 2026, within the hackathon window. Nothing made before.
- AI: Claude was used to assist with the coding and the write-up. No AI-generated images.
- Libraries: Qiskit (Apache 2.0); KaTeX (MIT) from jsDelivr.

## Links
Code: TBD · Video: TBD

MIT License; see repo root for license. This effort is supported by Qollab & IonQ.
