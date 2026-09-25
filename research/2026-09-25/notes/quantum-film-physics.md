# Quantum film stock: physics note for *fixer*

2026-09-25.

**Tags:** **V** = source fetched and read; **M** = from memory, not fetched; **E** = our estimate or derivation. "calc" = exact computation on a 64×64 torus, filling ¼, Fermi-disc kernel (`calc/selwyn_dpp.py`).

**Bottom line.** Classical grain has structure factor S(k) = 1. Fermions drive S(k→0) to 0 (repulsive, hyperuniform grain); bosons or speckle drive it to 2 (clumped grain). Both can be sampled on qubits and checked exactly, and they break Selwyn's law in opposite directions.

## A. Classical yardstick

- **Boolean model.** Poisson germs of intensity λ carry discs, so coverage is 1 − exp(−λE[A]). λ is set per pixel from the grey level. Radii are constant or log-normal, and "clumping" comes from the Poisson placement itself [1 V]. Rendering is by Monte Carlo [2 V]. Constant radii fitted T-Max 3200; log-normal radii fitted Neopan 1600 [1 V].
- **Crystals.** Silver-halide crystals are 0.2–2.0 µm; dye clouds are 1–10 µm; T-GRAIN arrived in 1982 [3 V]. Regular grains are "often cubic or octahedral". Kodak's tabular patent claims crystals under 0.3 µm thick, at least 0.6 µm across, with aspect ratio above 8:1 [4 V].
- **Granularity.** Kodak quotes diffuse RMS granularity at net density 1.00, through a 48 µm aperture at 12×; T-MAX 100 scores 8 [5 V]. The figure is σ_D × 1000 [46 V].
- **Selwyn's law and NPS.** Selwyn granularity G = σ_D√A is independent of aperture only "approximately". The noise power spectrum at zero frequency, W(0), equals G². The NPS misses individual-grain phase structure [6 V]. Selwyn's law is equivalent to a finite, non-zero S(k→0) (E).
- **Latent image.**
  - Gurney and Mott (1938): photoelectrons reduce silver ions [7 V][8 V]. Ag₂ is a sub-latent image; Ag₄ is developable [7 V]. Development gain reaches billions [8 V].
  - Emulsions show 1–4-photon behaviour, and two photons per grain is the practical limit [7 V].
  - Plates reach "a few percent" quantum efficiency, against about 80% for CCDs [9 V].
  - So film already works as a quantum detector: Poisson photons, binary grains that need q hits, and a deterministic ~10⁹ amplifier. That is atlas-film's "fixed luck" picture (E).

**Discriminating statistics** (E calc, at equal density):

| Statistic | Poisson/Boolean | Fermionic DPP | Bosonic (permanental) |
|---|---|---|---|
| g at nearest neighbour | 1 | 0.57 | 1.43 |
| S at the smallest k | 1 | 0.036, proportional to k | 1.96, tending to 2 |
| σ√A relative to Poisson, window radius 4→16 sites | 1→1 | 0.48→0.27 | 1.33→1.39, tending to √2 |
| Count per tile | Poisson | Fixed; zero variance for a projection DPP [10 V] | Super-Poisson |

A single RMS reading at 48 µm mixes up density, grain size and correlation. Measure instead:
- g(r) of crystal centres, before development;
- the NPS and a Selwyn plot (σ√A over at least one decade of aperture), on developed flat fields at D ≈ 1.

## B. Candidate emulsions

### B1. Free-fermion determinantal point process (DPP)

- **Physics.** Measuring the occupations of a Slater determinant gives a projection DPP [11 V]. Fermionic processes are hyperuniform [12 V]. S ∝ |k| is hyperuniformity class II, with number variance growing as R^(d−1) ln R [13 V].
- **Kernel.** A Fermi-sea (ball) spectrum is the "most repulsive" stationary DPP, still softer than hard-core processes [14 V]. On a periodic pixel grid, stationary DPPs are diagonal in the 2D DFT [10 V], so the emulsion kernel is a Fermi disc of frequencies (E).
- **Circuit.** Bardenet, Fanuel and Feller [11 V] use Jordan–Wigner encoding, one qubit per site, X gates on N qubits, then a Givens network. They need O(Nr) gates, with depth O(N) on a line or O(r log N) all-to-all. Pfaffian point processes (a generalisation adding pairing) are covered too.
- **Gate counts.** On a nearest-neighbour line, (M−N)N Givens rotations in depth M−1 [15 V]. Depth drops to at most M/2, and plane-wave states need O(M) depth via the fermionic Fourier transform [16 V]. Each rotation costs about 2 CNOTs ([11]: 12 CNOTs for 6 rotations; E).
- **Hardware so far.** On 5-qubit IBM machines, total-variation distance was 0.27–0.40, against under 0.01 on a simulator. Wrong-size subsets appeared, and readout errors turned triplets into pairs [11 V]. Google ran 12-qubit Slater-determinant circuits with 78 two-qubit gates [17 V].
- **Noise signature (E calc).** Particle number leaks. A low-k floor appears, S(k_min) ≈ 0.036p + 0.75(1−p), where p is the ideal fraction. g at one site drifts back towards 1.
- **Classical authority.** Free fermions are classically simulable [18 V], and each configuration's probability is a determinant (E).

### B2. Permanental (bosonic) processes

- The α = 1 "boson/photon" process is a Cox process driven by |Z|², with Z complex Gaussian. It attracts where DPPs repel, and permanents are #P-complete [19 V]. Gaussian-boson-sampling point processes "form clusters"; the same paper gives a fast classical sampler [20 V].
- Qubits have no native bosonic modes, and encodings are costly (M). The practical route is the Cox construction: many shots from a Gaussian-amplitude state, which is speckle (B3) (E).

### B3. Porter–Thomas statistics and speckle

- **Random circuits.** Amplitudes are about Gaussian, so probabilities follow Porter–Thomas, N·e^(−Np), within about 10 cycles [21 V]. Anticoncentration needs Θ(log n) depth [22 V].
- **Optical speckle.** Fully developed speckle has exponential intensity and contrast 1. M incoherent patterns give 1/√M. The Wiener spectrum is δ plus the pupil autocorrelation [23 V].
- **Noise and XEB.** Google's cross-entropy benchmark (XEB) treats outputs as "similar … to laser speckles". For ρ = p|ψ⟩⟨ψ| + (1−p)I/D, the probability variance is p² times the Porter–Thomas value, measurable without knowing the gates ("speckle purity"). Linear XEB = D⟨p⟩ − 1 = p [24 V]. So contrast = p = F_XEB (E).
- **Emulsion design (E).** Plain random circuits give no spatial structure. Instead, entangle the low-order "pupil" qubits of the x *and* y registers (x alone gives a plaid), then apply a 2D QFT: this is true Fraunhofer speckle [23]. Each shot is one crystal centre, giving g(0) = 1 + p² and S(k) = 1 + p²T(k). A readout error on a high-order bit relocates a crystal (fog); on a low-order bit it only blurs.

### B4. Entangled lattice states

- **Graph and cluster states.** Every Pauli measurement on a stabilizer state is fixed or a fair coin [25 V]. Snapshots are white noise or rigid XOR constraints, with no tunable correlation length (E).
- **Toric code.** Prepared on hardware [26 V]; its Z-basis snapshots are random closed-loop nets (E).
- **Tunable correlation length ξ** needs non-stabilizer states. The 1D transverse-field Ising model (TFIM) has exact circuits: 6 gates for 4 spins [27 V]. 2D Rydberg arrays reached checkerboard ξ ≈ 11 sites on 12×12, with slower sweeps giving longer ξ [28 V].

### B5. Other processes

- **Rydberg blockade** natively encodes maximum-independent-set problems [29 V], making the array a quantum Poisson-disk sampler (E).
- **QuEra Aquila** is on Braket [30 V]: up to 256 atoms in 75×76 µm, at least 4 µm apart, evolution up to 4 µs. Readout error is 1% ground→Rydberg and 8% Rydberg→ground [31 V].
- **Quantum gas microscopes** image Pauli blocking of fermions site by site [32 V].

### Candidate summary

Hardware inputs: IBM Heron r2 has 156 qubits on heavy-hex [33 V], with median two-qubit error about 2×10⁻³ and readout error 1.3–1.7% [34 V, secondary]. IBM Nighthawk has 120 qubits on a square lattice [35 V]. IQM Emerald has 54 square-lattice qubits at 99.5% median two-qubit fidelity [36 V]. Table entries are E unless tagged.

| Candidate | Signature | Exact check | Cost for 16 / 64 / 256 sites | Noise signature | Look |
|---|---|---|---|---|---|
| **Fermionic DPP (Givens)** | S ∝ k → 0; g(1) < 1; fixed N | Yes (determinants) | M qubits, N = M/4: ~96 / 1,536 / 24,576 CNOTs, depth ~2(M−1). Estimated fidelity 0.65 / 0.02 / not runnable | N leaks; low-k floor | Even, mottle-free grain that looks finer |
| **Speckle Cox (pupil + QFT)** | g(0) = 1 + p²; S = 1 + p²T | Yes (statevector or FFT) | log₂(pixels) qubits: 8 for 256 px (~60 CNOTs); 16 for 256×256 px (~350 CNOTs after routing) | Contrast = p; fog | Speckle-shaped clumps, like film exposed to laser light |
| Plain random circuit | Exponential pixel counts | Yes, up to ~30 qubits | 4 / 6 / 8 qubits, ~10 cycles [21] | Drifts to uniform | Salt-and-pepper with hot pixels |
| Graph state / toric code | Parity checks satisfied | Yes (stabilizer [25]) | M qubits, CZ depth 4: 24 / 112 / 480 CZs | Density of violated checks | XOR textures or loop nets (reticulation) |
| 1D TFIM | e^(−r/ξ), ξ tunable | Yes in 1D (free fermions) | O(n²) gates (M) | Shorter ξ | Streaky 1D domains |
| Rydberg (Aquila) | Blockade hole; ordering peaks | Small arrays only (M) | 16–256 atoms, one pulse | 8% missing grains; blockade violations | Poisson-disk voids or halftone domains |

Stitched fixed-N tiles stay hyperuniform at large scale but add seams at the tile period. A 156-qubit chip fits about 9 separate 16-qubit tiles per shot (E).

## C. Prior art

- **Quantum DPP sampling on hardware** has been done: [11 V] on 5 qubits; Thakkar et al. on ibmq_guadelupe [37 V]; Kazdaghli et al. on IBM up to 10 qubits [38 V]. Related samplers are in [39 V] and [40 V].
- **Clustering point processes** from Gaussian boson sampling: [20 V].
- **DPPs in images.** Launay, Desolneux and Galerne's determinantal pixel processes (DPixPs) drive shot-noise textures [41 V], and a projection DPixP gives minimum-variance shot noise [10 V]. *Classical "DPP grain" already exists.*
- **Random circuits as speckle**: Google's XEB and speckle purity [24 V].
- **Quantum textures**: Quantum Blur [42 V]; simulated skyrmion textures [43 V]; quantum halftoning [44 M].
- **Seeded, deterministic grain**: AV1 film grain uses a 16-bit LFSR [45 V].
- **Not found in our searches** (not proof of absence): "quantum film grain" or emulsions driven by quantum hardware; DPP blue-noise sampling in graphics venues; "quantum dithering" in graphics.
- **Defensible novelty**: hardware-sampled fermionic and bosonic emulsions, measured against Poisson grain with film-science statistics.

## D. Recommendation

1. **Fermionic "Pauli" stock.** A projection DPixP with a Fermi-disc kernel, run as 16-qubit Givens tiles (N = 4) on Heron, Nighthawk or Emerald. Larger reference tiles come from the exact classical sampler. Checks: fixed N, the low-k floor of S(k), total-variation distance and exact likelihood, and a falling Selwyn slope.
2. **Bosonic "speckle" stock.** A random pupil plus 2D QFT on 12–16 qubits, with one roll = S shots. Checks: exact probabilities, linear XEB and speckle purity (both give p), g(0) = 1 + p², and a Selwyn plateau at √(1+p²).

Both use the same kernel and give mirror-image spectra, S = 1 ∓ T(k), either side of atlas-film's Poisson baseline. They look different (even against clumped) and every prediction is closed-form and checkable.

**Caveats.** At these sizes both are classically simulable, so "measurably quantum" means the samples verifiably come from coherent interference, not a quantum advantage. Rydberg arrays look the most photographic but lack an exact check at 256 atoms; keep them as a stretch goal.

## References

1. Newson, Delon, Galerne (2017), "A Stochastic Film Grain Model for Resolution-Independent Rendering", Computer Graphics Forum. https://hal.science/hal-01520260 **V**
2. Newson, Faraj, Delon, Galerne (2017), "Realistic Film Grain Rendering", IPOL 7. https://www.ipol.im/pub/art/2017/192/ **V**
3. Vitale (2009), film-grain essay quoting Kodak publications (title truncated in PDF). https://cool.culturalheritage.org/videopreservation/library/film_grain_resolution_and_perception_v24.pdf **V**
4. Kofron et al., US4439520A, "Sensitized high aspect ratio silver halide emulsions and photographic elements" (1984). https://patents.google.com/patent/US4439520A/en **V**
5. Kodak Alaris (2016), "KODAK PROFESSIONAL T-MAX 100 Film". https://business.kodakmoments.com/sites/default/files/files/resources/f4016_TMax_100.pdf **V**
6. Stephenson, Saunders (2007), "Simulating Film Grain using the Noise-Power Spectrum". https://eprints.bournemouth.ac.uk/10547/1/grain.pdf **V**
7. Leubner (1999), "Review of Latent Image Formation Mechanisms in Silver Halides", IS&T PICS (cites Gurney & Mott 1938). https://www.imaging.org/common/uploaded%20files/pdfs/Papers/1999/PICS-0-42/977.pdf **V**
8. Wikipedia, "Latent image". https://en.wikipedia.org/wiki/Latent_image **V**
9. Starlink, "The 2-D CCD Data Reduction Cookbook", §4. https://starlink.eao.hawaii.edu/docs/sc5.htx/sc5se4.html **V**
10. Desolneux (2022), "Determinantal Point Processes and applications in imaging" (slides). https://www.i2m.univ-amu.fr/seminaires_signal_apprentissage/Conf/Dec2022/slides/Talk-Marseille-ProcessusPonctuels-2022.pdf **V**
11. Bardenet, Fanuel, Feller (2024), "On sampling determinantal and Pfaffian point processes on a quantum computer", J. Phys. A. https://arxiv.org/abs/2305.15851 **V**
12. Torquato, Scardicchio, Zachary (2008), "Point processes in arbitrary dimension from fermionic gases, random matrix theory, and number theory". https://arxiv.org/abs/0809.0449 **V**
13. Torquato group, "Hyperuniformity". https://torquato.princeton.edu/research/hyperuniformity/ **V**
14. Lavancier, Møller, Rubak, "Determinantal point process models and statistical inference : Extended version". https://arxiv.org/abs/1205.4818 **V**
15. Jiang et al. (2018), "Quantum algorithms to simulate many-body physics of correlated fermions". https://arxiv.org/abs/1711.05395 **V**
16. Kivlichan et al. (2018), "Quantum Simulation of Electronic Structure with Linear Depth and Connectivity". https://arxiv.org/abs/1711.04789 **V**
17. Arute et al. (2020), "Hartree-Fock on a superconducting qubit quantum computer". https://arxiv.org/abs/2004.04174 **V**
18. Terhal, DiVincenzo (2002), "Classical simulation of noninteracting-fermion quantum circuits". https://arxiv.org/abs/quant-ph/0108010 **V**
19. McCullagh, Møller (2005 report), "The permanent process" (Adv. Appl. Prob. 2006, **M**). http://www.stat.uchicago.edu/~pmcc/reports/permanent.pdf **V**
20. Jahangiri et al. (2020), "Point Processes with Gaussian Boson Sampling". https://arxiv.org/abs/1906.11972 **V**
21. Boixo et al., "Characterizing Quantum Supremacy in Near-Term Devices" (Nature Physics 2018, **M**). https://arxiv.org/abs/1608.00263 **V**
22. Dalzell, Hunter-Jones, Brandão (2022), "Random quantum circuits anti-concentrate in log depth". https://arxiv.org/abs/2011.12277 **V**
23. Goodman (1976), "Some fundamental properties of speckle", JOSA. http://materias.df.uba.ar/l5a2021c1/files/2021/05/goodman1976.pdf **V**
24. Google AI Quantum and collaborators (2019), "Supplementary information for Quantum supremacy using a programmable superconducting processor". https://arxiv.org/abs/1910.11333 **V**
25. Aaronson, Gottesman, "Improved Simulation of Stabilizer Circuits". https://arxiv.org/abs/quant-ph/0406196 **V**
26. Satzinger et al. (2021), "Realizing topologically ordered states on a quantum processor". https://arxiv.org/abs/2104.01180 **V**
27. Verstraete, Cirac, Latorre, "Quantum circuits for strongly correlated quantum systems". https://arxiv.org/abs/0804.1888 **V**
28. Ebadi et al. (2021), "Quantum Phases of Matter on a 256-Atom Programmable Quantum Simulator". https://arxiv.org/abs/2012.12281 **V**
29. Ebadi et al. (2022), "Quantum Optimization of Maximum Independent Set using Rydberg Atom Arrays". https://arxiv.org/abs/2202.09372 **V**
30. AWS, "Amazon Braket supported regions and devices". https://docs.aws.amazon.com/braket/latest/developerguide/braket-devices.html **V**
31. Wurtz et al. (2023), "Aquila: QuEra's 256-qubit neutral-atom quantum computer". https://arxiv.org/abs/2306.11727 **V**
32. Omran et al. (2015), "Microscopic Observation of Pauli Blocking in Degenerate Fermionic Lattice Gases". https://arxiv.org/abs/1510.04599 **V**
33. IBM Quantum docs, "Processor types". https://quantum.cloud.ibm.com/docs/en/guides/processor-types **V**
34. PostQuantum, "IBM Launches Heron R3 (ibm_pittsburgh)". https://postquantum.com/industry-news/ibm-heron-r3-pittsburgh/ **V**
35. IBM Newsroom (2025-11-12), Nighthawk announcement. https://newsroom.ibm.com/2025-11-12-ibm-delivers-new-quantum-processors,-software,-and-algorithm-breakthroughs-on-path-to-advantage-and-fault-tolerance **V**
36. AWS blog (2025-07-21), IQM Emerald launch. https://aws.amazon.com/blogs/quantum-computing/amazon-braket-launches-new-54-qubit-superconducting-quantum-processor-from-iqm/ **V**
37. Thakkar et al. (2024), "Improved Financial Forecasting via Quantum Machine Learning". https://arxiv.org/html/2306.12965v2 **V**
38. Kazdaghli et al., "Improved clinical data imputation via classical and quantum determinantal point processes". https://arxiv.org/abs/2303.17893 **V**
39. Kerenidis, Prakash (2022), "Quantum machine learning with subspace states". https://arxiv.org/abs/2202.00054 **V**
40. Fanuel, Bardenet (2025), "Bypassing orthogonalization in the quantum DPP sampler". https://arxiv.org/abs/2503.05906 **V**
41. Launay, Desolneux, Galerne (2021), "Determinantal point processes for image processing", SIAM J. Imaging Sci. https://sgsia21.karlin.mff.cuni.cz/abstracts/Galerne.pdf **V**
42. Wootton (2020), "Procedural generation using quantum computation". https://arxiv.org/abs/2007.11510 **V**
43. Biswas (2025), "Quantum Random Synthetic Skyrmion Texture Generation, a Qiskit Simulation". https://arxiv.org/abs/2509.18947 **V**
44. Oktorianti et al. (2014), "Implementation of Quantum Image Halftoning Algorithm". https://www.neliti.com/publications/171396/implementation-of-quantum-image-halftoning-algorithm **M**
45. Norkin, Birkbeck (2018), "Film Grain Synthesis for AV1 Video Codec". https://norkin.org/pdf/DCC_2018_AV1_film_grain.pdf **V**
46. Wikipedia, "Film grain". https://en.wikipedia.org/wiki/Film_grain **V**
