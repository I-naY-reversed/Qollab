# Repeater Run: entanglement from Toronto to Montreal

**Best of Quantum Unlocked, University of Toronto node, Qollab x IonQ Global Quantum Hackathon 2026**

- **Play it:** [qollab.xyz/u/hillel/repeater-run-entanglement-from](https://qollab.xyz/u/hillel/repeater-run-entanglement-from)
- **Code:** [github.com/I-naY-reversed/Qollab/tree/main/repeater-run](https://github.com/I-naY-reversed/Qollab/tree/main/repeater-run)
- **Demo video:** [Google Drive folder](https://drive.google.com/drive/folders/1bblDocKbWsfw6rfLd7BHZ63PDxwvBuo3)

## What it is
Repeater Run is a puzzle game about why a quantum internet needs repeaters. You try to get a secret key from Toronto to Montreal over 540 km of fibre. Over that distance about one photon in 60 billion makes it through, and you can't amplify a quantum signal, so sending pairs directly would take years.

The fix is to split the route into segments and join them with entanglement swapping. More segments means pairs arrive faster, but every swap adds noise, and once the error rate passes 11% there's no secret key. To get under that line you have to purify: spend two noisy pairs to keep one better one. The game is about finding the balance.

## How to play
Press Run with the built-in simulator selected. The route starts as 4 segments of 135 km. Press **Swap** at a station to join two links, or **Purify** on a link to trade two copies for one better one. You win when one link spans the whole route with an error rate (QBER) under 11%, and the score is your secret key rate in bits per second.

Try this first: swap at every station without purifying. The route connects, but QBER ends at 12.1%, so there's no key. Press Reset, purify each segment once, then swap. QBER drops to 8.7% and you get 0.20 bits per second. Then switch the starting fidelity to 0.90 and see how much more purifying it takes.

Keyboard: 1 to 4 pick the number of segments, F changes the starting fidelity, U undoes, R resets, K measures QBER, P pauses animations.

## How the quantum part works
Each link is a Werner state: the Bell state Φ+ with probability F, and noise otherwise. Every move also runs as a real 8-qubit Qiskit circuit (2000 shots), and Fig. 3 plots the measured fidelity next to the formula.

- **Swap:** a Bell measurement at the middle station joins two pairs. The corrections are applied as controlled gates, so the same circuit runs on Qollab's simulator and on IonQ-style hardware without mid-circuit measurement.
- **Purify:** the BBPSSW protocol. Both ends compare a parity check on a sacrificed pair and keep the other pair if the check passes.
- **Score:** secret key rate, (1 - 2h(QBER)) divided by the time per delivered pair, so a slow route doesn't win just because it uses fewer pairs.

Fig. 2 compares the best strategy at each segment count against the repeaterless (PLOB) bound. At 4 segments and F0 = 0.95, the best strategy beats it by about 9.6 times.

The circuits match the closed-form results exactly on a noiseless statevector (`offline/test_core.py`), and the formulas were checked against Bennett et al. 1996, Briegel et al. 1998 and Shor and Preskill 2000.

## Limitations
- Quantum memories are treated as perfect and classical messages as instant, so the rates are optimistic. Real repeaters lose fidelity while pairs wait.
- Station spacing is equal and the station names are made up.
- The protocol is classically simulable, so there's no claim of quantum advantage. The circuits are a portable encoding of the model.
- IonQ backends aren't supported in this version; use the built-in simulator.

## References
Briegel, Dür, Cirac and Zoller 1998, quantum repeaters (arXiv quant-ph/9803056). Bennett et al. 1996, BBPSSW purification (arXiv quant-ph/9511027). Deutsch et al. 1996, quantum privacy amplification (arXiv quant-ph/9604039). Pirandola, Laurenza, Ottaviani and Banchi 2017, PLOB bound (Nat. Commun. 8, 15043). Shor and Preskill 2000 (arXiv quant-ph/0003004).

## Team
Benjamin Kaganovitch and Yan Ivanov, University of Toronto.

## Disclosure
Built during the hackathon, Oct 9 to 11, 2026. We used Claude to help with the code and the write-up, and Google Gemini made the decorative art in `assets/`. Libraries: Qiskit (Apache 2.0), with KaTeX and Google Fonts loaded on the page.

MIT License. This effort is supported by Qollab & IonQ.
