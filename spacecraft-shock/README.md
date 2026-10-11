# Quantum Simulation of Pyroshock

Theme: Quantum Impact. Team: Benjamin Kaganovitch, Yan Ivanov (University of Toronto node).

The separation shock in a 12U CubeSat is simulated with the coupled-oscillator algorithm of Babbush et al. (2023), and 15 battery-mount and instrument-isolator designs are checked against component acceleration limits.

## Run
- Built-in simulator (preselected), default settings. The page appears in a few seconds and runs 8 circuits on 4 qubits (about 2.5 s natively).
- Pick the battery mount (B) and instrument isolator (1 to 5), or a cell of Fig. 2. Run circuits (R) measures the design at eight times; Left/Right step time; P plays.
- Unprotected, the battery exceeds 50 g at 0.60 ms and the instrument 20 g at 1.11 ms. Six of 15 designs pass.
- IonQ simulators: one 16-step circuit at the worst time (300 KB job limit).

## How it works
- Eight masses on a tree of springs (8 masses + 8 springs = 16 basis states, 4 qubits). Measurement probabilities are the energy fractions of each mass and spring; a component's acceleration follows from its mount spring's energy.
- Second-order product formula, 128 steps, built from uniformly controlled RX rotations: 96 CX per step, against 210 for a generic Pauli decomposition.
- Checked against the exact solution (`offline/test_core.py`): product-formula bias below 1.6 sigma of shot noise for every design.

## Limitations
- 1-D lumped model; masses, stiffnesses and allowables are assumed. Undamped, first 3.7 ms only.
- At 8 masses the classical solution is instant; all design conclusions come from it. No advantage is claimed at this size.

## Disclosure
- Built Oct 9 19:00 to Oct 11 19:00 ET. Nothing made before.
- AI: Claude was used to assist with the coding and the write-up; ChatGPT and DeepSeek reviewed it. No AI-generated images.
- Libraries: Qiskit (Apache 2.0), NumPy, SciPy (BSD); KaTeX (MIT) from jsDelivr.

## Links
Code: TBD · Video: TBD

MIT License; see repo root for license. This effort is supported by Qollab & IonQ.
