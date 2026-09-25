# Exact (no sampling) second-order statistics on an L x L torus for:
#  - Poisson (reference), Bernoulli lattice gas, projection DPP (2D Fermi sea),
#    and the alpha=1 permanental (boson/speckle Cox) process with the SAME kernel.
import numpy as np
L = 64; M = L*L; nu = 0.25; N = int(nu*M)
kx = np.fft.fftfreq(L)*2*np.pi
KX, KY = np.meshgrid(kx, kx, indexing='ij')
kmag = np.sqrt(KX**2+KY**2).ravel()
order = np.argsort(kmag, kind='stable')
occ = np.zeros(M); occ[order[:N]] = 1.0          # Fermi sea: N lowest |k| modes
occ2 = occ.reshape(L, L)
# kernel K(x) = (1/M) sum_q occ(q) e^{iqx}
K = np.fft.ifft2(occ2)                            # includes 1/M
rho = K[0,0].real
print(f"L={L}, M={M}, N={N}, density rho={rho:.4f}")
absK2 = np.abs(K)**2
# pair correlation on the lattice
g_F = 1 - absK2/rho**2; g_B = 1 + absK2/rho**2
for d in [(1,0),(1,1),(2,0),(3,0),(4,0)]:
    print(f"g at offset {d}: DPP {g_F[d]:.3f}   permanental {g_B[d]:.3f}")
# structure factor S(k) = 1 -/+ (1/rho) * FT(|K|^2)  (per particle)
T = np.fft.fft2(absK2).real/rho
S_F = 1 - T; S_B = 1 + T
kgrid = np.sqrt(KX**2+KY**2)
kF = np.sqrt(4*np.pi*nu)   # continuum estimate of Fermi wavevector
print(f"k_F (continuum est.) = {kF:.3f} rad/site;  2k_F = {2*kF:.3f}")
for kk in [1,2,4,8,16]:
    k = 2*np.pi*kk/L
    print(f"S(k={k:.3f}) : DPP {S_F[kk,0]:.3f}   permanental {S_B[kk,0]:.3f}   Poisson 1   Bernoulli {1-nu:.3f}")
# window number variance for discs of radius R (exact via autocorrelation of window indicator)
def win(R):
    x = np.arange(L); x = np.where(x > L//2, x-L, x)
    X, Y = np.meshgrid(x, x, indexing='ij')
    return (X**2+Y**2 <= R**2).astype(float)
print("\nSelwyn-type product G(R) = sqrt(Var N_W / |W|), normalised to Poisson (=sqrt(rho)):")
print("  R   |W|   Poisson  Bernoulli   DPP     permanental")
for R in [1,2,4,8,12,16,24]:
    W = win(R); A = W.sum()
    # sum_{x,y in W} f(x-y) = sum_d f(d) * (W autocorr)(d)
    Wac = np.fft.ifft2(np.abs(np.fft.fft2(W))**2).real
    S2 = (absK2*Wac).sum()
    EN = rho*A
    var_P = EN; var_Be = EN*(1-nu); var_F = EN - S2; var_B = EN + S2
    base = np.sqrt(var_P/A)
    print(f" {R:2d} {int(A):5d}   1.000    {np.sqrt(var_Be/A)/base:.3f}     {np.sqrt(max(var_F,0)/A)/base:.3f}   {np.sqrt(var_B/A)/base:.3f}")
# noise: global depolarisation after N-postselection ~ mix with uniform N-subset (hypergeometric) process
print("\nNoisy DPP (mixture weight p of ideal, 1-p of uniform N-subset) small-k S:")
for p in [1.0, 0.8, 0.5, 0.2, 0.0]:
    S_mix_uniform = 1 - nu   # approx for k != 0 (uniform N-subset ~ Bernoulli)
    print(f" p={p:.1f}: S(k=2pi/L) ~ {p*S_F[1,0] + (1-p)*S_mix_uniform:.3f}")
