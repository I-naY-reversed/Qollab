# Repeater Run

Theme: Quantum Unlocked. Team: Benjamin Kaganovitch (captain), Yan Ivanov (University of Toronto node).

A game about quantum repeaters: join a 540 km Toronto-Montreal fibre route with entanglement swapping and purification, and deliver pairs good enough for a secret key.

## Run
- Built-in simulator (preselected), default settings. The page appears in a few seconds; each move runs one 8-qubit circuit.
- Swap at a station joins two links; Purify trades two copies of a link for one better one. The route is won when one link spans it with QBER below 11%.
- Try: swap everywhere without purifying (QBER 12.1%, no key). Then purify each segment once and swap (QBER 8.7%, 0.20 bits/s).
- Keys: 1 to 4 segments, F pair fidelity, M measured mode, U undo, R reset, K measure QBER.
- IonQ simulators: one circuit per run; later moves use the closed forms.

## How it works
- Links are Werner pairs, made exact by noise ancillas. Swaps use deferred measurement (no classical feedforward); purification is BBPSSW.
- Each move runs as a circuit and is compared with the closed forms (Eqs. 2 to 4 on the page). The key rate is compared with the repeaterless PLOB bound.
- Checks: `offline/test_core.py` (statevector to 1e-9, shots within binomial error).

## Limitations
- Perfect memories, free classical messages and equal spacing, so rates are optimistic. Asymptotic key rates.
- The protocol is Clifford operations on Pauli noise and is classically simulable; no advantage is claimed.

## Disclosure
- Built Oct 9 19:00 to Oct 11 19:00 ET. Nothing made before.
- AI: Claude was used to assist with the coding and the write-up; ChatGPT and DeepSeek reviewed it. Google Gemini generated the decorative art in `assets/` (`assets/ASSETS.md`).
- Libraries: Qiskit (Apache 2.0); KaTeX (MIT) from jsDelivr; STIX Two and IBM Plex fonts from Google Fonts.

## Links
Code: TBD · Video: TBD

MIT License; see repo root for license. This effort is supported by Qollab & IonQ.
