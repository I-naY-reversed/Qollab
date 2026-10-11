# Quantum Supersampling of a Black Hole

Theme: Quantum Playground. Team: Benjamin Kaganovitch, Yan Ivanov (University of Toronto node).

A Kerr-Newman black hole modelled on Sgr A* is rendered pass by pass at equal query budgets per pixel with Monte Carlo ray sampling, amplitude estimation and a hybrid of the two.

## Run
- Built-in simulator (preselected), default settings. The page appears in a few seconds and runs one pixel's circuits (5 qubits, 6 circuits).
- Space plays the 9 passes; arrows step; 1 to 3 switch black hole; Q switches method; E shows error maps; A shows where amplitude estimation wins; T shows the reference.
- Click a pixel (or Shift + arrows, Enter) to run its circuits. Measured hit rates follow sin^2((2k+1) theta).
- IonQ simulators: one 20-qubit circuit per run; Stop and Run to measure another pixel.

## How it works
- Each pixel is the mean of 1024 precomputed ray values (offline Kerr-Newman geodesic tracer, `offline/kn.py`).
- Amplitude encoding plus Grover iterations at k = 0, 1, 2, 4, ..., 128 and a maximum-likelihood fit (MLAE) give error ~1/N queries, against ~1/sqrt(N) for independent sampling.
- Hybrid: a 32-ray pilot flags high-variance pixels; those spend the remaining budget on MLAE.
- Results (3 seeds per preset): on high-variance pixels MLAE overtakes sampling between 1120 and 2176 queries; the hybrid lowers whole-image error at the last pass by 17 to 33%.

## Limitations
- Rays are precomputed, so the 1024 stored values can also be averaged exactly in 1024 classical reads. Query counts are compared, not run time; no speedup is claimed.
- Full-image passes sample the exact noiseless output distribution; the inspector runs real circuits. No hardware noise. Stratified classical sampling is not compared.
- Disk colour, tone map and bloom are artistic. The charge of Sgr A* is negligible; the charged preset is hypothetical.

## Disclosure
- Built Oct 9 19:00 to Oct 11 19:00 ET. Nothing made before.
- AI: Claude was used to assist with the coding and the write-up. No AI-generated images.
- Libraries: Qiskit (Apache 2.0), NumPy, SciPy, numba (BSD), Pillow (MIT-CMU); KaTeX (MIT) from jsDelivr.
- Image: Sgr A*, EHT Collaboration 2022, CC BY 4.0 via ESO (`data/eht_sgra.jpg`).

## Links
Code: TBD · Video: TBD

MIT License; see repo root for license. This effort is supported by Qollab & IonQ.
