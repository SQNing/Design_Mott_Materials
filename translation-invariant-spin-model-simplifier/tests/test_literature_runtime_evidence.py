import ast
import sys
import csv
import hashlib
import inspect
import json
import math
import re
from copy import deepcopy
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation import literature_reproduction_audit
from validation import literature_runtime_evidence
from validation.literature_reproduction_audit import build_literature_reproduction_audit
from validation.literature_reproduction_audit import (
    write_audit_csv,
    write_audit_markdown,
    write_remaining_strict_reproduction_gaps_markdown,
)
from validation.literature_spin_model_benchmarks import LITERATURE_STANDARD_RESULTS
from validation import literature_spin_model_benchmarks
from validation.literature_runtime_evidence import (
    RuntimeEvidenceError,
    collect_runtime_evidence,
    parse_cri3_ferromagnetic_order,
    parse_yang_yang_xxx_ground_state_energy,
)


CR_I3_SOURCE_TEXT = """
In the chromium trihalides, Cr3+ ions are arranged in a honeycomb network.
Our magnetization and heat capacity measurements reveal long range
ferromagnetic order develops below TC = 61 K and evidence for strong
magnetic anisotropy developing upon cooling below TC.
"""

YANG_YANG_SOURCE_TEXT = """
Delta = -1,
f(Delta, 0) =-,' -ln2;                                      (31c)
Delta < -1,
"""

HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT = """
Phase diagram of S = 1/2 XXZ chain with NNN interaction
Shunsaku Hirata and Kiyohide Nomura
arXiv:cond-mat/9909290v1 [cond-mat.stat-mech] 20 Sep 1999

One of the simplest models is the spin-1/2 XXZ chain with
next-nearest-neighbor interaction, described by the Hamiltonian
H = J sum_i (h_i,i+1 + alpha h_i,i+2),
h_i,j = S_i^x S_j^x + S_i^y S_j^y + Delta S_i^z S_j^z. (1)
In the following, we set NN coupling J > 0.

The ground state properties are known for several cases. When alpha = 0,
it is integrable by the Bethe ansatz. For Delta < -1, the system becomes
the ferromagnetic phase, while for Delta > 1, it becomes the Neel phase.
In the case of XY-type anisotropy (-1 <= Delta <= 1), quantum fluctuation
destroys the long range order even at zero temperature. The ground state
is characterized by a gapless excitation and algebraic decay of spin
correlations (spin fluid phase).
"""

OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT = """
Physics Letters A 169 (1992) 433-437
Fluid-dimer critical point in S=1/2 antiferromagnetic Heisenberg chain
with next nearest neighbor interactions
Kiyomi Okamoto and Kiyohide Nomura
Received 20 April 1992; revised manuscript received 27 July 1992;
accepted for publication 5 August 1992

We numerically investigate the critical value alpha_c of the fluid-dimer
transition in the ground state of the S=1/2 antiferromagnetic Heisenberg
chain with next nearest neighbor interactions,
H = J sum_j (S_j dot S_j+1 + alpha S_j dot S_j+2)
with J > 0 and alpha > 0. With the help of conformal field theory,
we can estimate alpha_c = 0.2411 +/- 0.0001.

We assume the periodic boundary condition S_N+j = S_j, and N is the
number of spins which is assumed to be even. When alpha=0 the ground
state is the spin fluid state, characterized by gapless excitation and
power decay of the spin correlation. At alpha=1/2 the ground state is
the dimer state, characterized by the excitation gap and exponential
decay of the spin correlation.

The critical value alpha_c will be determined by
alpha_c = lim_(N -> infinity) alpha_c(N),                         (19)
where alpha_c(N) is obtained from
G_st(N, alpha_c(N)) = G_ss(N, alpha_c(N)).                       (20)
We have numerically calculated the singlet-triplet gap G_st(N,alpha)
and the singlet-singlet gap G_ss(N,alpha) for the finite systems
N=8, 10, ..., 24 by the use of TITPACK ver. 2. The crossing points of
G_st and G_ss are almost independent of N. In both cases the crossing
occurs for 0.24 < alpha < 0.25.

The alternating-epsilon algorithm gives
alpha_c = 0.24112218.                                            (24)
Shanks' transformation yields
alpha_c = 0.24117290.                                            (25)
The least-squares fitting versus 1/N^2 yields
alpha_c = 0.241155 +/- 0.000003.                                 (30)
Thus we can safely conclude that
alpha_c = 0.2411 +/- 0.0001.                                    (31)

In conclusion, we have determined the critical value
alpha_c = 0.2411 +/- 0.0001 from the numerical data of the finite-size
systems with the help of conformal field theory.
PHYSICS LETTERS A 12 October 1992
"""

OKAMOTO_NOMURA_J1_J2_IA_OCR_SOURCE_TEXT = """
Physics Letters A 169 (1992) 433-437
Fluid-dimer critical point in S=} antiferromagnetic Heisenberg chain
with next nearest neighbor interactions
Kiyomi Okamoto and Kiyohide Nomura
Received 20 April 1992; revised manuscript received 27 July 1992;
accepted for publication 5 August 1992

We numerically investigate the critical value a, of the fluid-dimer
transition in the ground state of the S=} antiferromagnetic Heisenberg
chain with next nearest neighbor interactions,
H=J> (S;-S;4,+a5S;-S;.2) with J>0 and a>0.
With the help of the conformal field theory, we can estimate
a,=0.2411+0.0001.

Our Hamiltonian in this paper is expressed as N H=J sum
(S_j dot S_j+1 + a S_j dot S_j+2), J>0, a>0, (1)
where we assume the periodic boundary condition S_N+j=S_j, and N is
the number of spins which is assumed to be even.

The critical value a, will be determined by a,=lim a,.(N), (19)
where a,.(N) is obtained from G_st(N,a,.(N))=G_ss(N,a,.(N)). (20)
We have numerically calculated the singlet-triplet gap and the
singlet-singlet gap for the finite systems N=8, 10, ..., 24 by the use
of TITPACK ver. 2. The crossing points of G_st and G_ss are almost
independent of N. In both cases the crossing occurs for 0.24<a<0.25.

The alternating-e algorithm gives a,=0.24112218. (24)
Shanks' transformation yields a,=0.24117290. (25)
The least-squares fitting yields a,=0.241155+0.000003. (30)
Thus we can safely conclude that a,=0.2411+0.0001. (31)
In conclusion, we have determined the critical value a,=0.2411+0.0001
from the numerical data of the finite size systems with the help of
conformal field theory.
PHYSICS LETTERS A 12 October 1992
"""

KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT = """
Bond-order wave phase, spin solitons and thermodynamics of a frustrated linear
spin-1/2 Heisenberg antiferromagnet
Manoranjan Kumar, S. Ramasesha and Z. G. Soos
arXiv:1006.5052v1 [cond-mat.str-el] 25 Jun 2010

The linear spin-1/2 Heisenberg antiferromagnet with exchanges J1, J2 between
first and second neighbors has a bond-order wave phase that starts at the
fluid-dimer transition at J2/J1 = 0.2411 and is particularly simple at
J2/J1 = 1/2. Exact solutions are presented up to N = 28 spins with either
periodic or open boundary conditions.

The spin chain has antiferromagnetic exchange between first and second
neighbors,
H(x) = J sum_n [(1-x) s_n dot s_(n+1) + x s_n dot s_(n+2)]. (1)
We set the total exchange J = 1. Second-neighbor exchange J2 = xJ frustrates
the nearest-neighbor exchange J1 = (1-x)J.
Okamoto and Nomura located the transition at
x_c = x_1/(1-x_1) = 0.2411, or x_1 = 0.1943 in our notation, where a magnetic
gap E_m opens.
"""

SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT = """
Definitive Evidence for Order-by-Quantum-Disorder in Er2Ti2O7
Lucile Savary, Kate A. Ross, Bruce D. Gaulin, Jacob P. C. Ruff,
and Leon Balents
arXiv:1204.1320v1 [cond-mat.str-el] 5 Apr 2012

We project the Hamiltonian to that of effective S = 1/2 quantum spins
describing the magnetic doublet of each rare earth ion on the pyrochlore
lattice. Nearest-neighbor exchange dominates, for which the Hamiltonian is
H = sum_<ij> [Jzz S_i^z S_j^z
              - Jpm (S_i^+ S_j^- + S_i^- S_j^+)
              + Jpmpm (gamma_ij S_i^+ S_j^+
                       + gamma_ij^* S_i^- S_j^-)
              + Jzpm (S_i^z (zeta_ij S_j^+
                             + zeta_ij^* S_j^-) + i <-> j)]. (6)
In units of 10^-2 meV, the fitted Er2Ti2O7 parameters are
Jpmpm = 4.2 +/- 0.5, Jpm = 6.5 +/- 0.75,
Jzz = -2.5 +/- 1.8, and Jzpm = -0.88 +/- 1.5. (7)

The U(1)-degenerate states of Er2Ti2O7 are its classical ground states.
Only zero-point quantum fluctuations can break the degeneracy of a clean
crystal at low temperature. We indeed find that zero-point fluctuations
break the U(1) degeneracy, and that the six equivalent values
alpha = n pi/3 (n = 0, 1, ..., 5) are the minima of the zero-point energy.
These are exactly the psi2 states. Comparison with the measured Bragg-peak
intensities gives strong evidence for the correctness of the psi2 ground
state and the Hamiltonian parameters.
"""

RICHTER_STAR_LATTICE_SOURCE_TEXT = """
PHYSICAL REVIEW B 70, 174454 (2004)
Absence of magnetic order for the spin-half Heisenberg antiferromagnet
on the star lattice
J. Richter, J. Schulenburg, A. Honecker, and D. Schmalfuss
DOI: 10.1103/PhysRevB.70.174454

We study the ground-state properties of the spin-half Heisenberg
antiferromagnet on the two-dimensional star lattice. We find evidence
for a quantum paramagnetic ground state. Its quantum ground state is
most likely dimerized with a gap to all excitations.

The geometric unit cell of the star lattice contains six sites and the
underlying Bravais lattice is a triangular one. For this lattice we consider
the spin-half HAFM in a magnetic field h,
H = J sum_<ij> S_i dot S_j - h S^z. (1)
The star lattice carries topologically inequivalent nearest-neighbor bonds
J_D (dimer bonds) and J_T (triangular bonds). For the uniform lattice these
bonds are of equal strength J_D = J_T = J.

All these features support the conclusion that the quantum ground state
of the HAFM on the star lattice is dominated by local singlet pairing.
This dimerized ground state represents a so-called explicit valence-bond
crystal state, which respects the lattice symmetry. The quantum paramagnetic
ground state appears in the spin-1/2 star lattice even in the uniform case
J_D = J_T.
"""

RICHTER_SQUARE_KAGOME_SOURCE_TEXT = """
The spin-half Heisenberg antiferromagnet on the square-kagome lattice:
Ground state and low-lying excitations
J. Richter, J. Schulenburg, P. Tomczak, and D. Schmalfuss
arXiv:cond-mat/0411673v1 [cond-mat.str-el] 26 Nov 2004

We discuss the ground state and the low-lying excitations of the spin-half
Heisenberg antiferromagnet on the two-dimensional square-kagome lattice.
The quantum ground state of the spin-half system is a quantum paramagnet
likely with a finite spin gap and with a large number of non-magnetic
excitations within this gap.

The geometric unit cell of the square-kagome lattice contains six sites and
the underlying Bravais lattice is a square one. For this lattice we consider
the spin-half HAFM in a magnetic field h,
H = J sum_<ij> S_i dot S_j - h S^z. (1)
The square-kagome lattice carries topologically inequivalent nearest-neighbor
bonds J_S (square bonds) and J_T (triangular bonds). For the uniform lattice
these bonds are of equal strength J_S = J_T = J and we set J = 1.

We find evidence for a spin-liquid like ground state with a small gap of
about J/20 and a considerable number of low-lying singlets within this spin
gap. Contrary to the star lattice case we do not see here a tendency towards
forming a valence bond crystal ground state. A jump follows from independent
localized magnon states in the square-kagome lattice. These localized magnons
live on the squares and produce a macroscopic jump to saturation.
"""

WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT = """
Evidence for biquadratic exchange in the quasi-two-dimensional
antiferromagnet FePS3
A. R. Wildes, M. E. Zhitomirsky, T. Ziman, D. Lancon, and H. C. Walker
arXiv:2005.12031v1 [cond-mat.mtrl-sci] 25 May 2020

FePS3 is a van der Waals compound with a honeycomb lattice that is a good
example of a two-dimensional antiferromagnet with Ising-like anisotropy.
The Fe2+ ions form a slightly distorted honeycomb lattice in the ab planes.
The compound is antiferromagnetic, ordering below its Neel temperature of
approximately 120 K with a propagation vector k_M = (0, 1, 1/2). The
high-spin (S = 2) Fe2+ ions are aligned parallel to the c* direction,
normal to the ab planes, forming ferromagnetic zig-zag chains parallel to
the a axis. The chains are antiferromagnetically coupled along the b and c
axes. The paramagnetic susceptibility is highly anisotropic and the compound
appears to be a good example of an Ising-like antiferromagnet.

The Hamiltonian initially used to model the spin waves for FePS3 was
H = -sum_<ij> J_ij S_i dot S_j - Delta sum_i (S_i^z)^2. (1)
The large single-ion anisotropy dominates the spin-wave gap and explains
the Ising-like behaviour.
"""

DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT = """
Spin-liquid behavior in J_eff = 1/2 triangular lattice compound Ba3IrTi2O9
Tusharkanti Dey, A. V. Mahajan, P. Khuntia, M. Baenitz,
B. Koteswararao, and F. C. Chou
PHYSICAL REVIEW B 86, 140405(R) (2012)
DOI: 10.1103/PhysRevB.86.140405

Ba3IrTi2O9 crystallizes in a hexagonal structure consisting of a layered
triangular arrangement of Ir4+ (J_eff = 1/2). Magnetic susceptibility and
heat capacity data show no magnetic ordering down to 0.35 K in spite of a
strong magnetic coupling evidenced by a Curie-Weiss temperature
theta_CW approximately -130 K. The magnetic heat capacity follows a power
law at low temperature. Our measurements suggest that Ba3IrTi2O9 is a 5d,
Ir-based J_eff = 1/2 quantum spin liquid on a two-dimensional triangular
lattice.

Ir4+ spins form an edge-shared triangular lattice in the ab plane. Site
sharing with nonmagnetic Ti4+ depletes the triangular planes. Nevertheless,
geometrical frustration continues to exist in the depleted triangular
lattice, and no long-range ordering anomaly is found from 0.35 to 295 K.

Conclusions. We have presented a potentially new spin liquid system
Ba3IrTi2O9, based on
a triangular lattice of Ir4+ ions. Magnetic correlations and frustrations
are maintained with the absence of magnetic ordering down to 0.35 K despite
the high Curie-Weiss scale. Ba3IrTi2O9 is possibly an example of a
J_eff = 1/2 quantum spin liquid system.
"""

GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT = """
Simplex Crystal Ground State and Magnetization Plateaus in the Spin-1/2
Heisenberg Model on the Ruby Lattice
Pratyay Ghosh and Frederic Mila
arXiv:2512.14173v1 [cond-mat.str-el] 16 Dec 2025

The spin-1/2 Heisenberg Hamiltonian on this lattice is given by
H = sum_<ij>_k J_k S_i dot S_j, (1)
where S_i are S = 1/2 operators and <ij>_k denotes a bond of type
k in {h, t, d}. The regime of primary interest is the isotropic limit
J_h = J_t = J_d.

One can also construct such localized-magnon states on the ruby lattice.
One starts by building single-magnon eigenstates immediately below h_s.
On certain geometries, like our ruby lattice, the magnon can become
strictly localized within a region R. Consider a magnon wavefunction
|Phi> proportional to sum_(i in R) c_i S_i^- |FP>. (4)
Destructive interference between these processes localizes the magnon when
the following necessary and sufficient condition holds:
sum_(i in R) J_ij c_i = 0, for all j in R-bar. (5)
On the ruby lattice, this condition is satisfied when the magnon is
confined to a J_h hexagon with an alternating sign structure of c_i.

Following this, one can construct an exact product state of single-magnon
states placed on every hexagonal plaquette, yielding m/m_s = 2/3. This
state becomes energetically favorable to the fully polarized state at
h = 4. Its energy, however, is higher than the iPEPS energy. The state
just below saturation and the m/m_s = 2/3 plateau obtained from iPEPS
does not appear to correspond to a localized-magnon state.

We focus on the isotropic point, J_t = J_h = J_d, where localized-magnon
eigenstates can occur. None of the observed plateau states can be
interpreted as strongly localized magnon states.
"""

BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT = """
Noncoplanar and Counterrotating Incommensurate Magnetic Order Stabilized by
Kitaev Interactions in gamma-Li2IrO3
A. Biffin, R. D. Johnson, I. Kimchi, R. Morris, A. Bombardi,
J. G. Analytis, A. Vishwanath, and R. Coldea
PRL 113, 197201 (2014)
DOI: 10.1103/PhysRevLett.113.197201

Materials that realize Kitaev spin models with bond-dependent anisotropic
interactions have long been searched for. Here, we explore the magnetism of
gamma-Li2IrO3, which has the topology of a three-dimensional Kitaev lattice
of interconnected Ir honeycombs. Using magnetic resonant x-ray diffraction,
we find a complex, yet highly symmetric incommensurate magnetic structure
with noncoplanar and counterrotating Ir moments. We propose a minimal
Kitaev-Heisenberg Hamiltonian that naturally accounts for all key features
of the observed magnetic structure. Our results provide strong evidence that
gamma-Li2IrO3 realizes a spin Hamiltonian with dominant Kitaev interactions.

At low temperatures new magnetic Bragg peaks appeared at satellite positions
with an incommensurate propagation vector q = (0.57(1), 0, 0). The satellite
peaks were as sharp as structural peaks in all three reciprocal-space
directions, indicating coherent three-dimensional magnetic ordering.

Kitaev interactions can stabilize the counterrotating moments with a
propagation vector q along a. Therefore, we construct the following
Kitaev-Heisenberg Hamiltonian as a minimal model:
H = sum_c-bonds [K_c S_i^eta S_j^eta + J_c S_i dot S_j
                 + I_cc S_i^c S_j^c]
  + sum_d-bonds [K_d S_i^eta S_j^eta + J_d S_i dot S_j]
  + sum_second-neighbors J_2 S_i dot S_j. (1)
We take K_c = -15, K_d = -12, J_c = 5, J_d = 2.5,
I_cc = -4.5, and J_2 = -0.9 meV.
The Hamiltonian was analyzed in Fourier space using the Luttinger-Tisza
approximation. This gave the lowest-energy mode identical to the coplanar
projection of the magnetic structure, and mode mixing exactly reproduces
the observed noncoplanar structure.

To summarize, through MRXD measurements on gamma-Li2IrO3 single crystals,
we have observed an incommensurate, noncoplanar magnetic structure with
counterrotating moments. A Kitaev-Heisenberg Hamiltonian can fully explain
the observed complex magnetic structure, providing strong evidence that
gamma-Li2IrO3 is an experimental realization of 3D Kitaev physics.
"""

TAYLOR_ISING_SOURCE_TEXT = """
The two-point correlation function is
<s_i s_i+l> = (1 / Z_N) sum_(s_i) (s_i s_i+l) exp(-H beta). (5)
It is found in this situation to be equal to tanh^l(J beta).
"""

PFEUTY_TFIM_SOURCE_TEXT = """
The One-Dimensional Ising Model with a Transverse Field
The one-dimensional Ising model with a transverse field is solved exactly by
transforming the set of Pauli operators to a new set of Fermi operators.
Defining h = J / (2 Gamma), the normal modes obey
Lambda_k^2 = 1 + h^2 + 2 h cos(k). (2.10)
For h = 1, Lambda_pi = 0. (2.12)
We get a system of noninteracting fermions of energy Gamma Lambda_k.
For h = 1 (Gamma = J/2) the gap in the excitation spectrum disappears.
The k'=0 mode energy drops to zero and rises again when Gamma is not J/2.
"""

DZIARMAGA_TFIM_SOURCE_TEXT = """
Dynamics of quantum phase transition: exact solution in quantum Ising model
Jacek Dziarmaga
arXiv:cond-mat/0509490v3 [cond-mat.other] 23 Nov 2005

The 1-dimensional quantum Ising model is exactly solvable. It is defined by
the Hamiltonian
H = -J sum_(n=1)^N (g sigma_n^x + sigma_n^z sigma_(n+1)^z). (1)
Quantum phase transition takes place at the critical value g = 1 of external
magnetic field.

After Jordan-Wigner transformation, sigma_n^x = 1 - 2 c_n^dagger c_n, (6)
and sigma_n^z is expressed using the fermionic string in Eq. (7).
Diagonalization is completed by the Bogoliubov transformation (14), provided
that the Bogoliubov modes are eigenstates of the stationary
Bogoliubov-de Gennes equations (15). There are two eigenstates for each k with
eigenenergies epsilon = +/- epsilon_k, where
epsilon_k = 2J sqrt([g - cos(ka)]^2 + sin^2(ka)). (16)
"""

LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT = """
Two Soluble Models of an Antiferromagnetic Chain
The first model is the XY model. Sx and Sy are represented by the usual Pauli
spin matrices. The Hamiltonian is
H_gamma = sum_i [(1 + gamma) Sx_i Sx_(i+1)
                 + (1 - gamma) Sy_i Sy_(i+1)]. (2.1)
The ground-state energy is E0 = -(1/2) sum_k Lambda_k. (2.20)
In the limit N tends to infinity the sum can be replaced by the integral
E0/N = -(1/(2 pi)) integral_-pi^pi
       [1 - (1 - gamma^2) sin^2(k)]^(1/2) dk. (2.21)
E0/N = -1/pi, isotropic case, gamma = 0. (2.22a)
"""

COLLURA_CALABRESE_ESSLER_XX_SOURCE_TEXT = """
Quantum quench within the gapless phase of the spin-1/2 Heisenberg XXZ spin
chain
Mario Collura, Pasquale Calabrese, and Fabian H. L. Essler
DOI: 10.1103/PhysRevB.92.125131

We consider the one-dimensional spin-1/2 XXZ chain with Hamiltonian
H(Delta) = J sum_(j=1)^L [
S_j^x S_(j+1)^x + S_j^y S_(j+1)^y + Delta S_j^z S_(j+1)^z]. (1)
Here S_j^alpha are spin operators, and throughout this paper we set J = 1.
We prepare the system in the ground state of the XX model (Delta_0 = 0).
Our best estimate of the ground-state energy density is
E0 = -0.318 309 81. This differs from the exact value of
E_XX = -1/pi by 7 x 10^-8.
"""

PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT = """
Phase transition and phase diagram of the J1-J2 Heisenberg model on a simple
cubic lattice
We consider a classical Heisenberg model with the Hamiltonian
H = sum_<ij> J1 S_i.S_j + sum_<<ij>> J2 S_i.S_j. (1)
The first and second sums run over nearest-neighbor and next-nearest-neighbor
pairs, respectively. All interactions are antiferromagnetic and the energy is
measured in units of J1.
For 0 < J2 < 0.25 J1, the classical ground state is the antiferromagnetic
structure. For 0.25 J1 < J2 the classical ground state has an infinite
degeneracy. The three collinear configurations (one line up, one line down)
are particular ground-state configurations in this range.
The dashed line in the phase diagram indicates the critical value
J2/J1 = 0.25.
"""

SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT = """
EXACT GROUND STATE OF A QUANTUM MECHANICAL ANTIFERROMAGNET
We consider a two dimensional lattice where each dashed line represents a
bond with strength 2 alpha and each nearest-neighbor bond has strength unity.
The Hamiltonian is
H = sum_<ij> h_ij + 2 alpha sum_<lm> h_lm - h sum_i S_i^z. (1)
We first observe that the state
|psi> = product_<lm> [l,m] (3)
is an eigenstate of the Hamiltonian Eq. (1) with eigenvalue E0/N given in
Eq. (4). We use the notation [l,m] for a singlet combination of the spins
l and m. The identity S_i dot (S_l + S_m) [l,m] = 0 shows that the first
term annihilates |psi>. We further show that E0 saturates a lower bound to
the ground-state energy for suitable values of the parameters and hence
|psi> is the rigorous ground state.
"""

FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT = """
The planar pyrochlore: a Valence Bond Crystal.
Exact diagonalizations of the spin-1/2 Heisenberg model on the checkerboard
lattice have been performed.
The checker-board lattice is built out of corner-sharing four-spin squares
and is the two-dimensional analog of the pyrochlore lattice.
The first-neighbor classical Heisenberg model on such lattices can be
rewritten as the sum of the square of the total spin of corner-sharing units:
H = J sum_(i,j bonds) S_i.S_j
  = (J/2) sum_(alpha units) S_alpha^2 + constant. (1.1)
Thus a classical ground state is obtained whenever S_alpha = 0 for all alpha.
"""

SYOZI_KAGOME_ISING_SOURCE_TEXT = """
Statistics of Kagome Lattice
After the work of Onsager, who solved exactly the problem of Ising model for
the plane square lattice, the honeycomb and triangular lattices were treated.
The kagome lattice consists exclusively of equivalent lattice points and
equivalent bonds. The number of nearest neighbors of a lattice point is four.
Let us start from a decorated honeycomb lattice. By summing first over the
spin variables at its vertices, we arrive at the partition function of the
kagome lattice by a star-triangle transformation, with interaction parameter
K. The same decorated lattice maps to an ordinary honeycomb lattice with
interaction parameter H.
In the ferromagnetic case, the specific heat becomes logarithmically infinite
at the temperature
exp(4 K) = 3 + 2 sqrt(3),
corresponding to cosh(2 H) = 2 for the honeycomb lattice.
But in the antiferromagnetic case there is no phase change.
"""

KANO_NAYA_KAGOME_ISING_SOURCE_TEXT = """
Progress of Theoretical Physics, Vol. 10, No. 2, August 1953, pages 158-172
Antiferromagnetism. The Kagome Ising Net
Kenzi KANO and Shigeo NAYA
(Received May 28, 1953)

We can solve exactly the eigenvalue problem of the kagome Ising net with
z = 4. The transition temperature lies a little below that of the square
lattice.

The transition temperature is defined by zeta = 1 in (28). We must treat the
limiting case of the interaction energy tending to infinity. Therefore the
equation determining the transition temperature gives
e^(4 L_c) = 3 + 2 sqrt(3). (32)

Put -J for the interaction energy of an equal pair and J for that of an
unequal pair, where J > 0 in the ferromagnetic case and J < 0 in the
antiferromagnetic case.

In the antiferromagnetic case the kagome lattice does not fit an
antiferromagnetic arrangement, is disordered at all temperatures, and
possesses a finite zero point entropy. There are free spins of N/3, already
showing an extensive ground-state multiplicity.

The energy per atom is obtained from the partition function with
L = J/(k T). (38)

Comparing (44) with (46), we get the exact value of the zero point entropy:
S_k(0)/R = 1/(24 pi^2) integral_0^(2 pi) integral_0^(2 pi)
log[21 - 4(cos(omega_1) + cos(omega_2)
             + cos(omega_1 + omega_2))] d omega_1 d omega_2. (47)
= 0.50183.
"""

KANO_NAYA_KAGOME_ISING_OCR_SOURCE_TEXT = """
Progress of Theoretical Physics, Vol. 10, No.2, August 1953
Antiferromagnetism. The Kagome Ising Net
Kenzi KANO* and Shigeo NAYA**
We can solve exactly the eigenvalue problem of the kagome Ising net with
z.=4.
In the case of anti ferromagnetism, especially, the kagome lattice which
does not fit to antiferromag;"etic arrangement is disorderd at all
temperature and possesses a finite zero point entropy.
The equation determining the transition temperature is obtained in the
limiting case. Thus we obtain e4Lc =3 +2 V3. (32)
where, j> 0 in ferromagnetic case, J < 0 in antiferromagnetic case.
There are the free spins of N/3 which belong to one kagome sublattice.
The energy per atom is given by the formula L=J/kT. (38)
5,,(0) / R=~J2"'J2"'log[21-4(COS WI + cos w2+
cos (Wl+ ( 2) )]dWldw2 (47) .~~ 0.50183.
"""

ISING_1925_LINEAR_CHAIN_SOURCE_TEXT = """
Ernst Ising
Contribution to the Theory of Ferromagnetism
1925
2. The simple linear chain.
We calculate the middle moment J of a linear magnet consisting of n elements.
Each of these n elements should be able to take only two positions in which
its moment points in the ordered direction of the chain. We distinguish the
two possible directions by the designations positive and negative.
If similar poles of neighboring elements interact on (2s + delta) positions,
then such an arrangement has the inner energy
(2s + delta) epsilon, where epsilon > 0.
Their total energy in an outer magnetic field is given in Eq. (3').
Here k is the Boltzmann constant and T is the absolute temperature. To
calculate the middle moment, using Eqs. (2), (2'), (3') and (4), we form the
partition function Z and sum over the positive and negative elements.
For a very large number n one finds the moment function in Eq. (8).
This function disappears for H = 0; thus we find no appearances of hysteresis
and no spontaneous magnetization.
At H = 0 the probabilities as a function of the moment M could have two
maxima or a single maximum at M = 0. A simple calculation shows that the
probabilities only have a simple maximum.
"""

HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT = """
The Statistics of Honeycomb and Triangular Lattice. I
Kodi Husimi and Itiro Syozi
Progress of Theoretical Physics, Volume 5, Issue 2, March 1950, Pages 177-186
https://doi.org/10.1143/ptp/5.2.177
Summary
We applied the matrix method in crystal statistics to the honeycomb lattice
and the exact solution has been obtained. From this, by the so called dual
transformation we can get the partition function for the triangular net.
The Curie point occurs at ch 2H = 2 in the honeycomb lattice and at
exp(4H) = 3 in the triangular net. These coincide with the results obtained
by the dual and star-triangle transformations. The specific heat becomes
logarithmically infinite but the energy itself remains continuous at this
temperature. In the antiferromagnetic case, the honeycomb lattice behaves
similar to the former case but the triangular net exhibits no phase change.
"""

CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT = """
J. Phys. A: Math. Gen. 17 (1984) 2687-2696. Printed in Great Britain
The Majumdar-Ghosh chain. Twofold ground state and elementary excitations
W J Caspers, K M Emmett and W Magnus
DOI 10.1088/0305-4470/17/13/020
Received 9 April 1984
Abstract. Recently it was proved that the Majumdar-Ghosh chain with the
Hamiltonian
H = 4 sum_{j=1}^{2N} S_j dot S_{j+1}
  + 2 sum_{j=1}^{2N} S_j dot S_{j+2},
S_{i+2N} = S_i, S_i = 1/2. (1)
has at least two ground states, in which the spins are arranged in
nearest-neighbour singlet pairs. In this work it is shown that these two
states are the only ground states.
The MG chain is a linear system of spins 1/2 with an isotropic interaction
between nearest and next-nearest neighbours, and the interaction constant
for next-nearest neighbours is one-half of that for nearest neighbours.
It was suggested that the system has at least two ground states, the
singlet-pair states (SPS). The two SPS are asymptotically orthogonal and are
connected by a translation over one elementary distance.
In section 2 it is proved that the two SPS are the only ground states for
the system with periodic boundary conditions, the closed MG chain. For the
open chain there is only one ground state.
As was proved in this section, all ground states of the Hamiltonian (1) may
be expressed in terms of two independent parameters. In this way we have
completed the proof that the two SPS are the only ground states for a system
with periodic boundary conditions.
"""

CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_OCR_SOURCE_TEXT = """
The Majumdar-Ghosh chain. Twofold ground state and elementary excitations
W J Caspers, K M Emmett and W Magnus
Journal of Physics A: Mathematical and General, Volume 17, Number 13
Citation W J Caspers et al 1984 J. Phys. A: Math. Gen. 17 2687
DOI 10.1088/0305-4470/17/13/020
Abstract
Recently it was proved that the Majumdar-Ghosh chain with the Hamiltonian
H=4 Sigma j=1 2N S j.S j+1+2 Sigma j=1 2N S j.S j+2,
S i+2N identical to S i, S i=1/2, has at least two ground states, in which
the spins are arranged in nearest-neighbour singlet pairs. In this work it
is shown that these two states are the only ground states.
J. Phys. A: Math. Gen. 17 (1984) 2687-2696. Printed in Great Britain
The MG chain is a linear system of spins f with an isotropic interaction
between nearest and next-nearest neighbours, and the interaction constant
for next-nearest neighbours is f of that for nearest neighbours.
The two singlet-pair states (SPS) are connected by a translation over one
elementary distance.
In 8 2 it is proved that the two SPS are the only ground states for the
system with periodic boundary conditions, the closed MG chain. For the open
chain there is only one ground state.
In this way we have completed the proof that the two SPS are the only ground
states. This is for a system with periodic boundary conditions.
"""

CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SCAN_TEXT = """
J. Phys. A: Math. Gen. 17 (1984) 2687-2696. Printed in Great Britain
The Majumdar-Ghosh chain. Twofold ground state and elementary excitations
W J Caspersi, K M Emmett? and W MagnusS
Received 9 April 1984
Abstract. Recently it was proved that the Majumdar-Ghosh chain with the
Hamiltonian has at least two ground states, in which the spins are arranged
in nearest-neighbour singlet pairs. In this work it is shown that these two
states are the only ground states.
This work is about the ground states and elementary excitations of the linear
spin system introduced by Majumdar and Ghosh (1969a, b) (MG). The MG chain is,
in our restricted definition, a linear system of spins f with an isotropic
interaction (exchange) between nearest and next-nearest neighbours, and the
interaction constant for next- nearest neighbours is f of that for nearest
neighbours.
It was suggested already in Majumdar and Ghosh (1969b) that the system has at
least two ground states, the singlet-pair states (SPS), in which the spins are
arranged in nearest-neighbour singlet pairs. The two SPS are asymptotically
orthogonal and are connected by a translation over one elementary distance.
In 8 2 it is proved that the two SPS are the only ground states for the system
with periodic boundary conditions, the closed MG chain. For the open chain
there is only one ground state.
0305-44701841132687 + 10$02.25 0 1984 The Institute of Physics 2687
In this way we have completed the proof that the two SPS are the only ground
states and have given a relation between these two states and the set
constructed in this section. This is for a system with periodic boundary
conditions.
"""

LAPILLI_SQUARE_CLOCK_SOURCE_TEXT = """
PHYSICAL REVIEW LETTERS PRL 96, 140603 (2006)
Universality Away from Critical Points in Two-Dimensional Phase Transitions
Cintia M. Lapilli, Peter Pfeifer, and Carlos Wexler
DOI: 10.1103/PhysRevLett.96.140603
The p-state clock model in two dimensions is a system of discrete rotors
with a quasiliquid phase in a region T1 < T < T2 for p > 4.
The model Hamiltonian is
H = -J0 sum_<i,j> cos(theta_i - theta_j), theta_i = 2 pi n_i / p. (1)
The high-temperature transition, T2, is obtained from the fixed point of
the magnetization cumulant. The low-temperature transition, T1, is obtained
from the temperature derivative of the magnetization and its cumulant.
Figure 1 is the phase diagram of the p-state clock model. For p > 4, a
quasiliquid phase appears, and the transitions at T1 and T2 are both
second order. The plotted data include p = 5.
The correlation function goes to a nonzero constant at large distance for
T < T1 (long-range ordered phase), decays as a power law for
T1 < T < T2 (quasi-long-range ordered quasiliquid phase), and decays
exponentially for T > T2 (disordered phase).
"""

TASAKI_LSM_SOURCE_TEXT = """
By using the local twist version of the theorem, it was proved that a
one-dimensional spin system with a half-odd-integer S has gapless excitations
in the infinite volume limit provided that the ground state is unique.
"""

ONSAGER_SQUARE_ISING_SOURCE_TEXT = """
The two-way infinite crystal has an order-disorder transition at a
temperature T = Tc given by the condition
sinh(2 J/kTc) sinh(2 J'/kTc) = 1.
"""

DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT = """
The exchange coupling along the rungs J' is much larger than J along the
chains, J' >> J. The energy in this limit is approximately
Egs = -3/4 J' N, where N is the number of rungs and -3/4 J' the energy of
each rung singlet. An isolated rung-triplet has an energy J' above the rung
singlet.
"""

KITAEV_EXACT_SOLUTION_SOURCE_TEXT = """
The model has two phases (denoted by A and B). The exact solution is obtained
by a reduction to free real fermions. In phase B the fermions are gapless.
In the symmetric case (Jx = Jy = Jz) the zeros of the spectrum are given by
q = plus or minus q star.
"""

KITAEV_TRIANGLE_SOURCE_TEXT = """
The equation has solutions if and only if |Jx|, |Jy|, |Jz| satisfy the
triangle inequalities:
|Jx| <= |Jy| + |Jz|, |Jy| <= |Jx| + |Jz|, |Jz| <= |Jx| + |Jy|. (33)
The region defined by inequalities (33) is phase B; this phase is gapless.
In the symmetric case (Jx = Jy = Jz) the zeros of the spectrum are given by
q = plus or minus q star.
"""

KITAEV_FIELD_GAP_SOURCE_TEXT = """
The simplest time-reversal-breaking perturbation is the external magnetic
field V = -sum_j (hx sigma_j^x + hy sigma_j^y + hz sigma_j^z). (45)
It does open a spectral gap, and for simplicity Jx = Jy = Jz = J.
The first time-reversal-breaking contribution is the third-order effective
Hamiltonian. Its next-nearest-neighbor coefficient obeys
kappa proportional to hx hy hz / J^2. (48)
The important mass parameter is
Delta = 6 sqrt(3) kappa proportional to hx hy hz / J^2, (50)
which determines the energy gap. Near the two conic points,
epsilon(q) = plus or minus sqrt(3 J^2 |delta q|^2 + Delta^2). (51)
The spectral Chern number is nu = sgn Delta = plus or minus 1. (55)
Vortices behave as non-Abelian anyons for any odd value of nu.
"""

KITAEV_TORIC_CODE_SOURCE_TEXT = """
I start with a class of stabilizer quantum codes associated with lattices on
the torus and other 2-D surfaces. The ground state of this Hamiltonian
coincides with the protected space of the code. It is 4^g-fold degenerate,
where g is the genus of the surface.
"""

WHITE_HUSE_HALDANE_SOURCE_TEXT = """
The excitation energy of the first excited state, a state with one magnon
with momentum q = pi, is the Haldane gap, which we find to be
Delta = 0.41050(2).
"""

SANDVIK_SQUARE_QMC_SOURCE_TEXT = """
The ground-state parameters of the two-dimensional S=1/2 antiferromagnetic
Heisenberg model are calculated using quantum Monte Carlo. The extrapolated
ground-state energy per spin is E = -0.669437(5).
"""

JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT = """
PHYSICAL REVIEW B 83, 155120 (2011)
High-precision determination of low-energy effective parameters for a
two-dimensional Heisenberg quantum antiferromagnet
F.-J. Jiang and U.-J. Wiese
DOI: 10.1103/PhysRevB.83.155120

The two-dimensional (2D) spin-1/2 Heisenberg antiferromagnet with exchange
coupling J is investigated on a periodic square lattice of spacing a at very
small temperatures using the loop-cluster algorithm.

The spin-1/2 Heisenberg model considered in this study is defined by the
Hamilton operator
H = sum_x J [S_x dot S_(x+1hat) + S_x dot S_(x+2hat)]. (1)
Here 1hat and 2hat refer to the two spatial unit vectors. Further, J in
Eq. (1) is the antiferromagnetic exchange coupling.

For a fixed box size L, we vary beta until the average squares of the spatial
and temporal winding numbers are the same. The spin wave velocity then
results as c = L/beta. Using this method, we obtain c = 1.6586(3) J a.

Using c = 1.6586(3) J a and performing a combined fit of the Monte Carlo data
for the staggered and uniform susceptibilities in the cubical regime, we
arrive at M_s = 0.307 43(1)/a^2 and rho_s = 0.180 81(11) J with
chi^2/d.o.f. approximately 1.
"""

BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT = """
PREPRINT
Ising Universality in Three Dimensions: A Monte Carlo Study
Henk W. J. Blöte, Erik Luijten and Jouke R. Heringa
September 4, 1995
To appear in Journal of Physics A: Mathematical and General
cond-mat/9509016

We investigate three Ising models on the simple cubic lattice by means of
Monte Carlo methods and finite-size scaling. These models are the spin-1/2
Ising model with nearest-neighbor interactions, a spin-1/2 model with
nearest-neighbor and third-neighbor interactions, and a spin-1 model with
nearest-neighbor interactions. The critical point of the nearest-neighbor
spin-1/2 model is K_c = 0.2216546(10).

We quote some preliminary results for the Hamiltonian
H/(k_B T) = -K_nn sum_<nn> s_i s_j
            -K_3n sum_[3n] s_i s_j. (1)
Here <nn> indicates a sum over nearest-neighbor pairs and [3n] over
third-neighbor pairs. The spins s_i can assume the values +1 and -1.

Thus, we selected the spin-1/2 Ising model with K_3n/K_nn = 0
(the nearest-neighbor model) as model 1.
Table 1: model 1, K_3n/K_nn = 0, spin-1/2 model with nn couplings.

Table 16: Results of a data analysis assuming universality for the three
investigated Ising models. All system sizes L >= 5 were included, and the
table lists the critical points for model 1, model 2, and model 3:
K_c  0.2216546(5)  0.1280039(4)  0.3934220(7).
We conclude that the fits presented in Table 16 are the most accurate
results.
"""

DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT = """
Nature of the Spin Liquid Ground State of the S = 1/2 Heisenberg Model on the
Kagome Lattice
Stefan Depenbrock, Ian P. McCulloch, and Ulrich Schollwöck
arXiv:1205.4858v2 [cond-mat.str-el] 14 Aug 2012

We perform a density-matrix renormalization group (DMRG) study of the S = 1/2
Heisenberg antiferromagnet on the kagome lattice to identify the conjectured
spin liquid ground state. Exploiting SU(2) spin symmetry, which allows us to
keep up to 16,000 DMRG states, we consider cylinders with circumferences up
to 17 lattice spacings and find a spin liquid ground state with an estimated
per site energy of -0.4386(5), a spin gap of 0.13(1), and very short-range
correlations.

The Heisenberg antiferromagnet on the kagome lattice (KAFM) is described by
the S = 1/2 model
H = sum_<i,j> S_i dot S_j. (1)
Here <i,j> are nearest neighbors, so the nearest-neighbor exchange coefficient
is the unit of energy.

Energies for cylinders of fixed circumference c and length L are extrapolated
in the truncation error. Bulk energies per site are extracted by a subtraction
technique and extrapolated to L -> infinity. At 16,000 states, DMRG is highly
accurate; negligible changes in energy for substantially larger c support that
the thermodynamic-limit energy is found, which we place at -0.4386(5).

On the issue of a spin (triplet) gap, SU(2) DMRG computes the S = 1 state
directly. We find the spin gap to remain finite also for cylinders of large
circumference c. The SU(2)-invariant results evolve smoothly with c, allowing
a tentative extrapolation to a spin gap Delta E = 0.13(1) in the
thermodynamic limit.
"""

SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT = """
Striped phase in a quantum XY-model with ring exchange
A. W. Sandvik, S. Daul, R. R. P. Singh, and D. J. Scalapino
arXiv:cond-mat/0205270v2 [cond-mat.str-el] 2 Dec 2002

We present quantum Monte Carlo results for a square-lattice S = 1/2 XY-model
with a standard nearest-neighbor coupling J and a four-spin ring exchange
term K. Increasing K/J, the ground-state spin stiffness vanishes at a critical
point at which a spin gap opens and a striped bond-plaquette order emerges.
At still higher K/J this phase becomes unstable and the system develops a
staggered magnetization.

Defining the bond and plaquette exchange operators
B_ij = S_i^+ S_j^- + S_i^- S_j^+
     = 2(S_i^x S_j^x + S_i^y S_j^y), (1)
P_ijkl = S_i^+ S_j^- S_k^+ S_l^-
       + S_i^- S_j^+ S_k^- S_l^+, (2)
the Hamiltonian is
H = -J sum_<ij> B_ij - K sum_<ijkl> P_ijkl. (3)
Here <ij> denotes nearest-neighbor sites and <ijkl> the corners of a
plaquette. For K = 0 this is the standard quantum XY-model.

The central result is that the competing J and K interactions give rise to a
third phase at K/J approximately 10: a striped bond-plaquette phase where
the bond and plaquette expectation values alternate with period 2. In the
thermodynamic limit the striped state should be analogous to the fourfold
degenerate columnar spin-Peierls state.

Finite-size scaling at K/J = 8.5 shows that the stripe order survives in the
thermodynamic limit: the squared plaquette-stripe order parameter extrapolates
to a non-zero value as L tends to infinity, while staggered correlations are
short ranged.

In summary, the spin-1/2 XY-model with ring exchange exhibits superfluid,
striped, and staggered ground-state orderings as the ring term is increased.
There is an absence of a spin liquid phase.
"""

CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT = """
On the Origin of Zigzag Magnetic Order in Iridium Oxide Na2IrO3
Jiri Chaloupka, George Jackeli, and Giniyat Khaliullin
arXiv:1209.5100v1 [cond-mat.str-el] 23 Sep 2012

We explore the phase diagram of spin-orbit Mott insulators on a honeycomb
lattice, within the Kitaev-Heisenberg model extended to its full parameter
space. Zigzag-type magnetic order is found to occupy a large part of the phase
diagram of the model, and its physical origin is explained as due to
interorbital t2g-eg hopping. Magnetic susceptibility and spin wave spectra are
calculated and compared to the experimental data, obtaining thereby the spin
coupling constants in Na2IrO3 and Li2IrO3.

The nearest-neighbor interaction between isospin one-half Kramers doublets of
Ir4+ ions is
H_ij^(gamma) = 2 K S_i^gamma S_j^gamma + J S_i dot S_j. (1)
Here gamma = x, y, z labels the three distinct types of nearest-neighbor bonds
of a honeycomb lattice of Ir ions in Na2IrO3. The bond-dependent Ising coupling
is the Kitaev model, and the second term stands for the Heisenberg exchange.

We introduce the energy scale A and angle phi via K = A sin phi and
J = A cos phi. We let the phase angle phi vary from 0 to 2 pi, uncovering
additional phases of the model, including its zigzag ordered state.

In its full parameter space, the Kitaev-Heisenberg model accommodates
6 different phases. In addition to the previously discussed Neel-AF,
stripy-AF, and spin-liquid states, we observe three more states: an AF
Kitaev spin-liquid, a ferromagnetic phase, and a zigzag-AF phase.
Figure 1: Phase diagram of the Kitaev-Heisenberg model containing
2 spin-liquid and 4 spin-ordered phases.

We show that the zigzag order is a natural ground state of the
Kitaev-Heisenberg model in a previously overlooked parameter range. The
calculated spin-wave spectra and magnetic susceptibility agree with
experiments, lending strong support to the Kitaev-Heisenberg model as a
dominant interaction in Na2IrO3 and related oxides.

The fit for Na2IrO3 gives J = -4.01 meV and K = 10.45 meV and locates Na2IrO3
near phi = 111 +/- 2 degrees in the model phase diagram. To conclude, we have
clarified the origin of zigzag magnetic order in Na2IrO3 in terms of the
nearest-neighbor Kitaev-Heisenberg model for localized Ir moments. The model
well agrees with the low-energy magnon and high-temperature magnetic
susceptibility data.
"""

CAPRIOTTI_TRIANGULAR_ENERGY_SOURCE_TEXT = """
We have studied the Heisenberg model on the triangular lattice using quantum
Monte Carlo techniques (up to 144 sites) and exact diagonalization (up to 36
sites). Our best estimate is that in the thermodynamic limit the ground state
energy per site is e0 = -0.5458 +/- 0.0001 in units of the exchange coupling.
"""

CHECKERBOARD_PLAQUETTE_SOURCE_TEXT = """
Exact diagonalizations of the spin-1/2 Heisenberg model on the checkerboard
lattice have been performed. This antiferromagnet does not break SU(2)
symmetry and displays long-range order in four-spin S=0 plaquettes.
The Heisenberg quantum model on a checkerboard lattice is a valence bond
crystal.
"""

SPIN_PEIERLS_GAP_SOURCE_TEXT = """
We develop a theory of the spin-Peierls transition in spin-1/2 Heisenberg
chains. The calculation treats the response of a one-dimensional Heisenberg
chain with nearest-neighbor interactions to a small static lattice distortion.
The energy gap at zero temperature scales as the lattice distortion to the
power 2/3.
"""

BPCB_FIELD_LL_SOURCE_TEXT = """
The two-leg spin-ladder material (Hpip)2CuBr4 is described by a Heisenberg
ladder Hamiltonian. For weakly coupled ladders the spin Luttinger liquid is
induced from a gapped quantum-disordered phase by an applied magnetic field.
The magnetocaloric-effect measurements demonstrate spin Luttinger-liquid
behavior between the critical fields Bc and Bs.
"""

HASENBUSCH_XY_BKT_SOURCE_TEXT = """
We study the classical XY model on the square lattice with coupling J=1,
where beta is the inverse temperature. The transition estimate is
beta_KT = 1.1199(1) = 1/0.89294(8) for the XY model.
"""

AZURITE_PLATEAU_SOURCE_TEXT = """
We present a specific-heat and inelastic-neutron-scattering study in magnetic
fields up into the 1/3 magnetization plateau phase of the diamond-chain
compound azurite Cu3(CO3)2(OH)2. We establish that the magnetization plateau
is a dimer-monomer state.
"""

BA3COSB2O9_PLATEAU_SOURCE_TEXT = """
We report magnetization and specific-heat measurements on Ba3CoSb2O9 and
provide evidence that a spin-1/2 Heisenberg antiferromagnet on a regular
triangular lattice is realized. The entire magnetization curve including the
one-third quantum magnetization plateau is in excellent quantitative
agreement with theoretical calculations.
"""

KAGOME_ONE_THIRD_PLATEAU_SOURCE_TEXT = """
We study the quantum spin-1/2 kagome Heisenberg antiferromagnet in an applied
magnetic field. A grand canonical density matrix renormalization group analysis
gives the bulk magnetization curve. Without ambiguity, one finds plateau
structures at fractions M/Msat = 0, 1/9, 1/3, 5/9 and 7/9.
"""

CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT = """
Quantum theory of an antiferromagnet on a triangular lattice in a magnetic field
A V Chubukov and D I Golosov
J. Phys.: Condens. Matter 3 (1991) 69-82

In the last few years there has been renewed interest in the possibility for
the disordered ground state to occur in S = 1/2 two-dimensional
antiferromagnets on a triangular lattice.

2. Isotropic case
We start with an isotropic Heisenberg antiferromagnetic on a triangular lattice:
H = J sum_<ij> S_i dot S_j - 2 mu H sum_i S_i^z. (4)
We explore a traditional spin wave approach, based on the 1/S expansion.

In the intermediate region, h_1 < h < h_2, the collinear configuration is
stable. The absence of broken continuous symmetry then implies that all the
excitations have a finite gap.

The magnetization remains constant inside the collinear phase. Classically,
the magnetization equals one third of the saturation value at h = 1. We
calculated the first quantum correction to the magnetization and ascertained
that it equals zero, so the magnetization retains its classical value also in
the quantum case.

Figure 3. The anticipated behaviour of longitudinal magnetization in a 2D
Heisenberg AFM on a triangular lattice. The plateau on the magnetization curve
results from the stabilization of the collinear phase in the finite region of
magnetic fields due to zero-point motion.

6. Summary
We have found that spin reorientations at T = 0 in the external magnetic field
in quasi-2D antiferromagnets on a triangular lattice may occur via an
intermediate collinear phase with the constant longitudinal magnetization equal
to one third of the saturation value. For quasi-2D Heisenberg and XY
antiferromagnets this mode of reorientation is singled out by quantum
fluctuations.
"""

CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SCAN_TEXT = """
Quantum theory of an antiferromagneton a triangular
lattice in a magnetic field
A V Chubukov and D I Golosov
1. Phys.: Condens. Matter3(1991)69-82.

the disordered ground state to occur in S = 1/2 two dimensional (ZD)
antiferromagnets onatriangular lattice

2. Isotropic case
We start with an isotropic Heisenberg antiferromagnetic on a triangular lattice:
X = J x S , S , + A- 2 p H x S f . (4)
we will explore a traditional spin wave approach, based on the 1/S expansion.

In the intermediate region, h , < h < h,, the collinear configuration is stable.
The absence of broken continuous symmetry then implies that all the excitations
have a finite gap.

The magnetization, M , , remains constant inside the collinear phase.
Classically, M , equals one third of the saturation value at h = 1. We calculated
the first quantum correction to M , and ascertained that it equals zero, that is
the magnetization retains its classical value, pS/3, also in the quantum case.

Figure 2. The anticipated behaviour of AFMR fre- Figure 3. The anticipated
behaviour of longi-
quencies versus magnetic field in 2D Heisenberg tudinal magnetization in 2D
Heisenberg AFM on a
AFM on a triangular lattice. The broken lines triangular lattice. The plateau
on the magnet-
denote the branches which would be gapless in the ization curve results from the
stabilization of the
classical treatment. collinear phase in the finite region of magnetic fields due
to zero-point motion.

6. Summary
We have found that spin reorientations at T = 0 in the external magnetic field
in quasi-2D antiferromagnets on a triangular lattice may occur via an
intermediate collinear phase with the constant longitudinal magnetization equal
to one third of the saturation value. For quasi-2D Heisenberg and XY
antiferromagnets this mode of reorientation is singled out by quantum
fluctuations.
"""

KAGEYAMA_SHASTRY_SUTHERLAND_SOURCE_TEXT = """
Magnetic susceptibility, Cu NQR, and high-field magnetization have been measured
in polycrystalline SrCu2(BO3)2 having a two-dimensional orthogonal network of Cu
dimers. Furthermore, in the magnetization, two plateaus corresponding to 1/4 and
1/8 of the full Cu moment were first observed for two-dimensional quantum spin
systems.
"""

CACU2O3_SPIN_LADDER_SOURCE_TEXT = """
We report studies of the spin-1/2 quasi-one-dimensional antiferromagnet
CaCu2O3. Its structure is similar to that of the prototype two-leg spin-ladder
compound SrCu2O3. The Cu-O-Cu bond angle in the ladder rungs is 123 degrees, so
the magnetic interaction along the rung is weaker. The structure consists of an
array of ladderlike structures with quasi-1D copper-oxide chains.
"""

BA2CUGEO7_DM_SPIRAL_SOURCE_TEXT = """
We report an observation in the Dzyaloshinskii-Moriya spiral antiferromagnet
Ba2CuGe2O7. Bulk magnetic measurements and neutron-diffraction experiments
establish an incommensurate spin spiral. The incommensurate magnetic phase is a
result of Dzyaloshinskii-Moriya interactions rather than competing exchange.
"""

HO2TI2O7_SPIN_ICE_SOURCE_TEXT = """
The pyrochlore material Ho2Ti2O7 has been suggested to show spin ice behavior.
We present neutron scattering and specific heat results that establish
unambiguously that Ho2Ti2O7 exhibits spin ice correlations at low temperature.
Diffuse magnetic neutron scattering is quite well described by a nearest
neighbor spin ice model and very accurately described by a dipolar spin ice
model.
"""

JAROSITE_Q0_ORDER_SOURCE_TEXT = """
The spin wave excitations of the S=5/2 kagome lattice antiferromagnet
KFe3(OH)6(SO4)2 have been measured using high-resolution inelastic neutron
scattering. The ground-state spin configuration has every triangle oriented
120 degrees relative to each other. The magnetic unit cell is the same as the
chemical unit cell. The antisymmetric Dzyaloshinskii-Moriya interaction is the
primary source of anisotropy and explains the low-temperature spin structure.
"""

MAPLE_LEAF_ORDER_SOURCE_TEXT = """
We investigate the ground state of the two-dimensional spin-half Heisenberg
antiferromagnet on the maple-leaf lattice. We use the coupled cluster method to
high orders of approximation and exact diagonalization of finite-sized lattices
to discuss ground-state magnetic long-range order. Our results indicate that
the pure maple-leaf (J'/J=1) Heisenberg antiferromagnet is magnetically ordered.
"""

ALPHA_RUCL3_SOURCE_TEXT = """
The honeycomb trihalide alpha-RuCl3 displays zigzag order below TN. Table IV
gives the complete magnetic interactions for alpha-RuCl3, including the Kitaev
coupling Kn and off-diagonal coupling Gamma_n. Off-diagonal couplings
Gamma_1 approximately -K_1 dominate the nearest-neighbor magnetic interactions.
"""

BETA_LI2IRO3_SOURCE_TEXT = """
The iridate beta-Li2IrO3 is a hyperhoneycomb Kitaev-lattice material. A combined
study using neutron powder diffraction and magnetic resonant x-ray diffraction
solves the complete magnetic structure. We find a complex, incommensurate
magnetic order with non-coplanar and counter-rotating Ir moments.
"""

CS2CUCL4_SPIRAL_SOURCE_TEXT = """
The magnetic excitations of the quasi-2D spin-1/2 frustrated Heisenberg
antiferromagnet Cs2CuCl4 are explored throughout the 2D Brillouin zone using
high-resolution time-of-flight inelastic neutron scattering. Upon cooling below
TN magnetic order in an incommensurate spiral forms due to the 2D frustrated
couplings.
"""

SQUARE_DIMERIZED_TRANSITION_SOURCE_TEXT = """
The S=1/2 two-dimensional quantum Heisenberg antiferromagnet on the anisotropic
dimerized square lattice is investigated by quantum Monte Carlo. Finite-size
scaling determines the ground-state phase diagram. The quantum phase transition
is between the spin-gapped dimer phase and the antiferromagnetic Neel
long-range-ordered phase.
"""

SQUARE_JQ_TRANSITION_SOURCE_TEXT = """
Using ground-state projector quantum Monte Carlo simulations, nonfrustrating
four-spin interactions destroy the Neel order of the two-dimensional S=1/2
Heisenberg antiferromagnet and drive it into a valence-bond solid (VBS) phase.
Spin and dimer correlations are consistent with a single continuous transition.
"""

TRIANGULAR_CLASSICAL_120_SOURCE_TEXT = """
We consider Heisenberg spin-1/2 antiferromagnets with nearest-neighbor pairs
on a two-dimensional triangular lattice. The classical ground state of the
triangular-lattice antiferromagnet has three sublattices, A, B, and C, with
spins on each sublattice at an angle of 2 pi/3 to those on the other two
sublattices. Translation by a nearest-neighbor vector is accompanied by a
spin-space rotation by angle 2 pi/3.
"""

FECL3_HELIX_SOURCE_TEXT = """
Neutron-diffraction measurements on anhydrous FeCl3 show that near-neighbor
moments in the c-axis direction are oppositely oriented. The satellite
displacement gives r = (b1 + 4 b2)/15, parallel to the [1450] direction,
with a wavelength of 15 lattice spacings. The modulation is of the helical
type: moments rotate by 2 pi/15 in successive planes along [1450]. Threefold
domain symmetry gives the equivalent [4,1,5,0] in-plane propagation domain.
"""

MATERIAL_CANDIDATE_SOURCE_TEXTS = {
    "parse_haydeeite_ferromagnetic_exchange": """Haydeeite is an S=1/2 kagome ferromagnet. Inelastic neutron scattering spin-wave excitations are described by a Heisenberg Hamiltonian with ferromagnetic nearest-neighbor exchange J1=-38 K and antiferromagnetic Jd=+11 K across kagome hexagons.""",
    "parse_na4ir3o8_hyperkagome_spin_liquid": """Na4Ir3O8 forms an antiferromagnetically coupled S=1/2 geometrically frustrated hyperkagome lattice. Magnetization and magnetic specific heat show absence of long-range order down to 2 K and strongly suggest its ground state is a three-dimensional spin liquid.""",
    "parse_ybmggao4_qsl_candidate": """YbMgGaO4 is a spin-1/2 triangular antiferromagnet with an ideal two-dimensional isotropic triangular lattice. No spin freezing down to 60 mK, power-law heat capacity and nonzero low-temperature susceptibility suggest it is a promising gapless QSL candidate.""",
    "parse_barlowite_interlayer_coupling": """Barlowite Cu4(OH)6FBr contains perfect kagome layers, but copper ions between the kagome layers mediate strong interkagome couplings and lead to an ordered ground state.""",
    "parse_substituted_barlowite_two_parameter_model": """For interlayer-substituted barlowite, isoelectronic substitution with nonmagnetic ions significantly reduces the interkagome exchange coupling. The material is described by a simple two-parameter Heisenberg Hamiltonian with J1 kagome and J2 interlayer exchange.""",
    "parse_pr2zr2o7_quantum_spin_ice": """In Pr2Zr2O7 elastic neutron scattering shows spin-ice correlations, while more than 90% of neutron scattering is inelastic. This is experimental evidence for quantum dynamics of magnetic monopolar quasiparticles in a new class of exchange spin ice.""",
}

DIRECT_SOURCE_CLAIM_TEXTS = {
    "parse_herbertsmithite_qsl_candidate": """We performed thermodynamic and neutron scattering measurements on the S=1/2 kagome lattice antiferromagnet ZnCu3(OH)6Cl2, known as herbertsmithite. No magnetic order is observed down to 50 mK. Inelastic neutron scattering reveals low-energy spin excitations with no observable gap. These results suggest that an unusual spin liquid state is realized in this kagome lattice system.""",
    "parse_kapellasite_competing_exchanges": """Kapellasite, Cu3Zn(OH)6Cl2, is a spin-1/2 kagome antiferromagnet. Its Heisenberg Hamiltonian possesses competing exchange interactions. The susceptibility fit gives a ferromagnetic nearest-neighbor interaction J1=-15.0 K in competition with the antiferromagnetic across-hexagon interaction Jd=12.7 K.""",
    "parse_li2cuo2_frustrated_chain": """Li2CuO2 consists of simple edge-sharing Cu-O chains. The nearest-neighbor interaction J1 is ferromagnetic, while the next-nearest-neighbor interaction J2 has a considerable antiferromagnetic contribution. Both J1 and J2 are required to describe the magnetic properties of Li2CuO2.""",
    "parse_u1_pyrochlore_spin_liquid": """We study the S=1/2 Heisenberg antiferromagnet on the pyrochlore lattice in the limit of strong easy-axis exchange anisotropy. The models enter the U(1) spin liquid phase, a fractionalized spin liquid with an emergent U(1) gauge structure. This state is stable to all zero-temperature perturbations and exists over a finite extent of the phase diagram.""",
    "parse_herbertsmithite_dm_relevance": """We determine the Dzyaloshinsky-Moriya interaction, the dominant magnetic anisotropy term in the spin-1/2 kagome compound ZnCu3(OH)6Cl2. Electron spin resonance gives the main component |Dz|=15(1) K perpendicular to the kagome planes. This perturbation can drastically affect the low-temperature properties and may stabilize long-range order.""",
    "parse_kagome_chiral_spin_liquid_phase": """We study a spin-1/2 model on the Kagome lattice with nearest-neighbour Heisenberg exchange and the scalar spin chirality Si dot (Sj cross Sk). The scalar spin chirality breaks time-reversal symmetry. We find an extended chiral spin liquid phase around the pure three-spin term, stable almost up to the Heisenberg point.""",
    "parse_kagome_dm_critical_ratio": """The S=1/2 kagome antiferromagnet undergoes a quantum phase transition as the Dzyaloshinskii-Moriya coupling increases. For D<Dc it is moment-free, while for D>Dc it develops antiferromagnetic long-range order. Exact diagonalization and finite-size scaling give the quantum critical point Dc approximately 0.1 J.""",
    "parse_breathing_kagome_trimerization": """We numerically study the spin-1/2 breathing kagome Heisenberg antiferromagnet using DMRG and exact diagonalization. Upward and downward triangles have different coupling strengths. In the strong breathing anisotropy limit the model is the trimerized kagome model and we find a transition out of the robust kagome spin liquid.""",
    "parse_ca10cr7o28_qsl_exchange": """The compound Ca10Cr7O28 realizes strong ferromagnetic and weaker antiferromagnetic isotropic interactions on a bilayer breathing-kagome lattice. Experimentally and theoretically, neutron scattering and muon measurements show coherent spin dynamics and the complete absence of static magnetism, all features expected of a quantum spin liquid.""",
    "parse_hyperkagome_heisenberg_qsl": """Na4Ir3O8 has spin-1/2 local moments on a three-dimensional hyperkagome lattice. Exact diagonalization and Gutzwiller projected variational wave functions identify a quantum spin liquid with spinon Fermi surfaces as a favorable candidate for the ground state of the nearest-neighbor Heisenberg model.""",
    "parse_beta_li2iro3_hyperhoneycomb_kitaev": """Beta-Li2IrO3 crystallizes in a hyperhoneycomb structure and is a spin-orbital Mott insulator with Jeff=1/2 moments. Bond-dependent ferromagnetic interactions are an essential ingredient of the Kitaev model, placing this hyperhoneycomb material close to a Kitaev spin liquid.""",
    "parse_triangular_ring_exchange_spin_liquid": """We study a triangular-lattice spin-1/2 model with antiferromagnetic Heisenberg and ring exchanges using variational wave functions. In a range of ring-exchange coupling, destroying antiferromagnetic order produces a spin-liquid region whose best state is a Gutzwiller-projected Fermi sea.""",
    "parse_triangular_xxz_supersolid": """Quantum Monte Carlo determines the phase diagram of hard-core bosons on the triangular lattice with nearest-neighbor repulsion. At intermediate fillings 1/3<rho<2/3, we find an extended supersolid phase even at half filling, with simultaneous superfluid and solid order.""",
    "parse_volborthite_distorted_kagome": """Volborthite Cu3V2O7(OH)2.2H2O contains S=1/2 copper ions in two-dimensional kagome-like layers. Its monoclinic symmetry makes the triangles isosceles rather than equilateral, producing a unique modified and distorted kagome lattice.""",
    "parse_nips3_zigzag_order": """Neutron diffraction determines the magnetic structure of quasi-two-dimensional antiferromagnet NiPS3. The transition-metal atoms form a honeycomb lattice. NiPS3 adopts a k=[010] antiferromagnetic structure, which is identical to zigzag magnetic order on the honeycomb lattice.""",
    "parse_kitaev_gamma_phase_content": """For Jeff=1/2 honeycomb iridates, the nearest-neighbor Hamiltonian contains bond-dependent off-diagonal Gamma exchange in addition to Heisenberg and Kitaev terms. Classical analysis and exact diagonalization find new noncollinear 120-degree and incommensurate spiral phases, together with extended regions of zigzag and stripy order.""",
    "parse_ggg_short_range_order": """Powder neutron scattering measurements on gadolinium gallium garnet Gd3Ga5O12 reveal short-range magnetic order from 0.14 to 5 K. No long-range magnetic order is found in zero field down to 25 mK, and the low-temperature phase is a mixture of a spin-liquid state and rigid impurity-nucleated pieces rather than an ordinary spin glass.""",
    "parse_honeycomb_j1j2_nonmagnetic_candidate": """SU(2) DMRG studies the spin-1/2 J1-J2 Heisenberg model on a honeycomb lattice. Neel order vanishes at J2/J1 approximately 0.22; for 0.22<J2/J1<0.25 both spin and dimer orders vanish in the thermodynamic limit, consistent with a possible spin liquid phase.""",
    "parse_honeycomb_j1j2_intermediate_nonmagnetic": """SU(2) DMRG studies the spin-1/2 J1-J2 Heisenberg model on a honeycomb lattice. Neel order vanishes at J2/J1 approximately 0.22; for 0.22<J2/J1<0.25 both spin and dimer orders vanish in the thermodynamic limit, consistent with a possible spin liquid phase.""",
    "parse_kagome_j1j2_phase_set": """An SU(2)-symmetric DMRG study of the spin-1/2 J1-J2 Heisenberg model on the kagome lattice finds sqrt(3) x sqrt(3) magnetic order for ferromagnetic J2, an extended spin-liquid region around J2=0, and q=0 magnetic order for antiferromagnetic J2.""",
    "parse_triangular_j1j2_phase_set": """DMRG studies the S=1/2 J1-J2 Heisenberg model on the triangular lattice. For 0.06 <= J2/J1 <= 0.17 it finds a spin liquid, bordered by a 120-degree Neel ordered state at small J2 and a two-sublattice collinear stripe state at larger J2.""",
    "parse_triangular_j1j2_spin_liquid_window": """DMRG studies the spin-1/2 Heisenberg model on the triangular lattice with antiferromagnetic J1 and J2. It finds 120-degree magnetic order for J2 <= 0.07 J1, stripe antiferromagnetic order for J2 >= 0.15 J1, and identifies a spin-liquid region between these phases.""",
    "parse_spin1_haldane_large_d_transition": """Numerical exact diagonalization studies the one-dimensional S=1 XXZ chain with uniaxial single-ion anisotropy D. Its phase diagram contains both the Haldane phase and large-D phase, separated by a Gaussian transition.""",
    "parse_bcc_large_j2_collinear_order": """The spin-S J1-J2 Heisenberg model on the body-centered cubic lattice has ferromagnetic J1<0 and antiferromagnetic J2>0. For J2 greater than the classical transition 2|J1|/3, the ground state is a collinear antiferromagnetic state with Q=(pi,pi,pi).""",
    "parse_kagome_topological_entanglement_z2": """A DMRG study of the S=1/2 Heisenberg antiferromagnet on the kagome lattice finds finite topological entanglement consistent with gamma=log_2(2), ruling out nontopological spin liquids and providing strong evidence for a gapped topological Z2 spin liquid.""",
}

DIRECT_SOURCE_CLAIM_REMOVALS = {
    "parse_herbertsmithite_qsl_candidate": ("ZnCu3(OH)6Cl2", "No magnetic order", "50 mK", "spin liquid state"),
    "parse_kapellasite_competing_exchanges": ("Kapellasite", "Heisenberg Hamiltonian", "ferromagnetic", "antiferromagnetic"),
    "parse_li2cuo2_frustrated_chain": ("Li2CuO2", "edge-sharing Cu-O chains", "ferromagnetic", "antiferromagnetic"),
    "parse_u1_pyrochlore_spin_liquid": ("S=1/2", "pyrochlore lattice", "U(1) spin liquid phase", "stable"),
    "parse_herbertsmithite_dm_relevance": ("ZnCu3(OH)6Cl2", "Dzyaloshinsky-Moriya", "dominant magnetic anisotropy", "15(1) K"),
    "parse_kagome_chiral_spin_liquid_phase": ("Kagome lattice", "scalar spin chirality", "time-reversal symmetry", "extended chiral spin liquid phase"),
    "parse_kagome_dm_critical_ratio": ("S=1/2 kagome", "Dzyaloshinskii-Moriya", "moment-free", "0.1 J"),
    "parse_breathing_kagome_trimerization": ("spin-1/2", "breathing kagome", "different coupling strengths", "trimerized kagome"),
    "parse_ca10cr7o28_qsl_exchange": ("Ca10Cr7O28", "ferromagnetic", "antiferromagnetic", "quantum spin liquid"),
    "parse_hyperkagome_heisenberg_qsl": ("Na4Ir3O8", "hyperkagome lattice", "Gutzwiller", "quantum spin liquid"),
    "parse_beta_li2iro3_hyperhoneycomb_kitaev": ("Beta-Li2IrO3", "hyperhoneycomb", "Bond-dependent ferromagnetic", "essential ingredient"),
    "parse_triangular_ring_exchange_spin_liquid": ("triangular-lattice", "spin-1/2", "ring exchanges", "spin-liquid region"),
    "parse_triangular_xxz_supersolid": ("hard-core bosons", "triangular lattice", "1/3<rho<2/3", "extended supersolid phase"),
    "parse_volborthite_distorted_kagome": ("Volborthite", "S=1/2", "monoclinic symmetry", "distorted kagome"),
    "parse_nips3_zigzag_order": ("NiPS3", "Neutron diffraction", "honeycomb lattice", "zigzag magnetic order"),
    "parse_kitaev_gamma_phase_content": ("Jeff=1/2", "off-diagonal Gamma", "incommensurate spiral", "zigzag"),
    "parse_ggg_short_range_order": ("Gd3Ga5O12", "neutron scattering", "short-range magnetic order", "No long-range magnetic order"),
    "parse_honeycomb_j1j2_nonmagnetic_candidate": ("spin-1/2", "J1-J2", "0.22<J2/J1<0.25", "both spin and dimer orders vanish"),
    "parse_honeycomb_j1j2_intermediate_nonmagnetic": ("spin-1/2", "J1-J2", "0.22<J2/J1<0.25", "both spin and dimer orders vanish"),
    "parse_kagome_j1j2_phase_set": ("spin-1/2", "J1-J2", "sqrt(3) x sqrt(3)", "spin-liquid", "q=0"),
    "parse_triangular_j1j2_phase_set": ("S=1/2", "J1-J2", "0.06 <= J2/J1 <= 0.17", "120-degree", "collinear stripe"),
    "parse_triangular_j1j2_spin_liquid_window": ("spin-1/2", "triangular lattice", "0.07 J1", "0.15 J1", "spin-liquid region"),
    "parse_spin1_haldane_large_d_transition": ("S=1", "single-ion anisotropy", "Haldane phase", "large-D phase", "Gaussian transition"),
    "parse_bcc_large_j2_collinear_order": ("J1-J2", "body-centered cubic", "J1<0", "J2>0", "collinear antiferromagnetic"),
    "parse_kagome_topological_entanglement_z2": ("S=1/2", "kagome lattice", "DMRG", "topological entanglement", "Z2 spin liquid"),
}

AKLT_PROJECTOR_SOURCE_TEXT = """
The neighboring pair implies that the total spin of each such pair cannot be 2.
We choose our Hamiltonian to be a sum of projection operators onto spin 2
for each neighboring pair, H = sum_i P_2(S_i + S_i+1).
Clearly, the ground-state energy is zero.
"""

DIAMOND_LOCALIZED_MAGNON_SOURCE_TEXT = """
For the diamond chain the magnons may be localized on the vertical bonds.
The explicit expressions for the localized one-magnon state having the
smallest possible region of localization read |1lm> proportional to
(|s-1, s> - |s, s-1>) |s, ..., s>.
The independent localized magnon states are the lowest-energy states in the
corresponding sectors of Sz = Ns - 1, ..., Ns - nmax.
"""

SAWTOOTH_LOCALIZED_MAGNON_SOURCE_TEXT = """
For the sawtooth chain the localized magnons may be trapped in a valley between
two neighboring triangles. The explicit expressions for the localized
one-magnon state having the smallest possible region of localization read
|1lm> proportional to (|s-1, s, s> - 2|s, s-1, s> + |s, s, s-1>) |s, ..., s>.
The independent localized magnon states are the lowest-energy states in the
corresponding sectors of Sz = Ns - 1, ..., Ns - nmax.
"""

DAGOTTO_RICE_TWO_LEG_GAP_SOURCE_TEXT = """
J (> 0) is the antiferromagnetic exchange coupling that provides the energy
scale in the problem. There is evidence that 2-leg ladders have a finite
spin-gap, i.e. a finite energy is needed to create a S=1 excitation. The
exchange coupling along the rungs of a 2-leg ladder is denoted by J'.
"""

HALDANE_SHASTRY_SOURCE_TEXT = """
In this Letter I construct the exact Jastrow-product ground-state wave
function of the S=1/2 one-dimensional (1D) isotropic Heisenberg
antiferromagnet with an exchange coupling falling off as the inverse square
of the distance between sites.
"""

BAXTER_EIGHT_VERTEX_SOURCE_TEXT = """
Eight-Vertex Model in Lattice Statistics. The solution of the zero-field
"eight-vertex" model is presented. This model includes the square lattice
Ising, dimer, ice, and KDP models as special cases.
"""

BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT = """
Eight-Vertex Model in Lattice Statistics
R. J. Baxter
The solution of the zero-field "eight-vertex" model is presented. This model
includes the square lattice Ising, dimer, ice, P, and KDP models as special
cases. The free energy has a branch-point singularity at a phase transition,
with a continuously variable exponent.
Suppose the model is unchanged by reversal of all arrows; in ferroelectric
terminology this implies that there are no electric fields.
We have succeeded in solving this model for arbitrary values of a, b, c, and d.
The restrictions are equivalent to a > 0, b > 0, d > 0, and c > a+b+d. This
set of values is called the principal domain.
Inside the principal domain f is an analytic function of a, b, c, and d. Thus
a phase transition can occur only when the weights cross a boundary of the
principal domain, corresponding to a, b, d, or c-a-b-d becoming zero.
If c-a-b-d has a simple zero at some value Tc, f can be written as the sum of
an analytic and a singular function of temperature.
"""

LIEB_SQUARE_ICE_SOURCE_TEXT = """
The statement of the problem in two dimensions is to find the number of ways
of drawing arrows on the bonds of a square planar net so that precisely two
arrows point into each vertex. If N is the number of molecules and W^N is the
number of arrangements, then S = Nk ln W. Our exact result is W = (4/3)^(3/2).
"""

YANG_GAUDIN_SOURCE_TEXT = """
Some Exact Results for the Many-Body Problem in One Dimension with Repulsive
Delta-Function Interaction. The repulsive delta interaction problem in one
dimension for N particles is reduced through Bethe's hypothesis. The
ground-state problem of spin-1/2 fermions is reduced to a generalized Fredholm
equation.
"""

LIEB_LINIGER_SOURCE_TEXT = """
Exact Analysis of an Interacting Bose Gas. A gas of one-dimensional Bose
particles interacting via a repulsive delta-function potential has been solved
exactly. All the eigenfunctions can be found explicitly and the energies are
given by a transcendental equation. For impenetrable bosons in one dimension,
the energy spectrum is identical with the spectrum of a noninteracting Fermi gas.
"""

PAULING_SPIN_ICE_SOURCE_TEXT = """
Spin ice materials are the magnetic analogue of water ice. Pauling estimated
the degeneracy to be approximately (3/2)^(N/2), which leads to a measurable
zero point entropy S0 approximately (R/2) ln(3/2). The two-in two-out ice
rule describes the disordered spin-ice ground state.
"""

BKT_UNIVERSAL_JUMP_SOURCE_TEXT = """
Universal Jump in the Superfluid Density of Two-Dimensional Superfluids.
The two-dimensional XY model predicts a universal jump. Predictions for the
spin-wave stiffness in two-dimensional magnetic systems follow from XY
magnetism and superfluidity. Taking over the analysis gives
lim K_i(T)/(k_B T) = 2/pi as T approaches T_BKT from below.
"""

KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT = """
Bifurcation at the c = 3/2 Takhtajan-Babujian point to the c = 1 critical
lines
Atsuhiro Kitazawa and Kiyohide Nomura

We study the S = 1 quantum spin chains with bilinear, biquadratic, plus bond
alternation in the vicinity of the S = 1 Takhtajan-Babujian model.
We study the following S = 1 spin model in the vicinity of the TB point
(theta = -pi/4, delta = 0),
H = sum_j [1-delta(-1)^j] [
    cos(theta) S_j dot S_j+1
    + sin(theta) (S_j dot S_j+1)^2
].
Affleck and Haldane argued for the instability of the integrable
Takhtajan-Babujian (TB) model.
At the TB point (theta = -pi/4, delta = 0), the critical properties of the
system are described by the k = 2 SU(2) Wess-Zumino-Witten model. This has
been confirmed by Bethe ansatz.
"""

KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_LAYOUT_TEXT = """
Bifurcation at the c = 3/2 Takhtajan-Babujian point
to the c = 1 critical lines
Atsuhiro Kitazawa and Kiyohide Nomura

We study the S = 1 quantum spin chains with bilinear,    havior, that is,
biquadratic, plus bond alternation in the vicinity of the S =    To see this
behavior, we study the following S = 1 spin
1 Takhtajan-Babujian model.
model in the vicinity of the TB point (theta = -pi/4, delta = 0),
    N X
    1-delta(-1)^j cos(theta) S_j dot S_j+1
    + sin(theta) (S_j dot S_j+1)^2.
model) at the Takhtajan-Babujian point to c = 1    H =

They argued the instability of the integrable    In this paper, we study
Takhtajan-Babujian (TB) model which is described by

At the TB point (theta = -pi/4, delta = 0), the critical prop-
right-column current algebra text
erties of the system are described by the k = 2 SU(2)
right-column operator-product text
Wess-Zumino-Witten model. This has been confirmed
right-column correlator text
by Bethe ansatz.
"""

ULS_SU3_SOURCE_TEXT = """
Model for a multicomponent quantum system. Place exactly one object to a site
and let the operator P_jk permute whatever objects occupy neighboring sites;
the Hamiltonian is the sum of P_j,j+1. Equation (41) is invariant under the
total SU(3) group. We now
return to consider a spin-1 representation for our system, writing the SU(3)
generators in terms of the three spin operators and six tensor operators. The
one-dimensional problem is solved by Bethe's ansatz.
"""

SQUARE_COMPASS_SOURCE_TEXT = """
The general anisotropic compass model, as given for D = 2 in Eq. (1), has
general couplings J x and J y and is given in D dimensions by Eq. (4) without
field: H90 = - sum_(r,gamma) J_gamma tau_r^gamma tau_(r+e_gamma)^gamma. (82)
Exact symmetries of the square lattice 90 degree compass model are
O^(gamma) = product_(r in P_gamma) exp(i pi T_r^gamma). (84)
Here P_gamma is any line in the two-dimensional model orthogonal to the
external e_gamma axis. The operators of Eq. (84) commute with the general
Hamiltonian of Eq. (82), [O^(gamma), H] = 0.
"""

AKLT_ANGLE_SOURCE_TEXT = """
For the spin-1 chain, the total spin of each neighboring pair cannot be 2.
Thus, we choose our Hamiltonian to be a sum of projection operators onto
spin 2 for each neighboring pair. The general bilinear-biquadratic
Hamiltonian is H = sum_i [S_i.S_(i+1) - beta (S_i.S_(i+1))^2].
"""

YANG_SPONTANEOUS_MAGNETIZATION_SOURCE_TEXT = """
The Spontaneous Magnetization of a Two-Dimensional Ising Model
The spontaneous magnetization of a two-dimensional Ising model is calculated
exactly. Below the critical temperature the largest eigenvalue is doubly
degenerate. VI. FINAL RESULTS. The spontaneous magnetization I is obtained
from (95) and (80) as I = [1 - sinh(2H)^(-4)]^(1/8). (96)
"""

SQUARE_POTTS_SOURCE_TEXT = """
The critical point of the ferromagnetic Potts model is known for the square,
triangular, and honeycomb lattices. Define
x_n = (exp(K_n) - 1) / sqrt(q). (4.4)
For the square lattice the critical condition is x_1 x_2 = 1. (5.1b)
The expression (5.1b) for the critical point of the Potts model on the square
lattice follows from duality, which determines the transition at the self-dual
point x_1 x_2 = 1.
In two dimensions the transition is continuous for q <= 4 and first order
for q > 4.
"""

WANNIER_TRIANGULAR_ISING_SOURCE_TEXT = """
Antiferromagnetism. The Triangular Ising Net
The triangular net with antiferromagnetic interaction is a non-fitting lattice.
The entropy at absolute zero is finite. Thus we get for the zero-point entropy
S(0)/R = (2/pi) integral_0^(pi/3) ln(2 cos(omega)) d omega. (37a)
By elementary considerations we obtain the alternate expression and the power
series in omega, printed as S(0)/R = 0.338314. (37c)
"""

GAREL_MAILLARD_VILLAIN_SOURCE_TEXT = """
J. Phys. A: Math. Gen. 16 (1983) 2257-2265
Study of a two-dimensional fully frustrated model
T Garel and J M Maillard

Abstract. We consider a fully frustrated Ising model on a square lattice,
depending on four parameters. The partition function is shown to be equivalent
to the two-parameter ferromagnetic Onsager partition function. This result can
be checked in the particular case of the one-parameter Villain model. In
particular, the residual entropy of the Villain model is linked to the free
energy of the Onsager model at criticality.

The model is defined in figure 1, and its reduced Hamiltonian reads
-beta H = sum_(ij) {K}_ij sigma_i sigma_j. (1)
In equation (1), (ij) denotes nearest-neighbour pairing, sigma_i = +/- 1,
and the reduced coupling constants {K}_ij may take the values
K1, -K2, K3, -K4. The isotropic case
K1 = K2 = K3 = K4 corresponds to Villain's model.
Figure 1. The four-parameter fully frustrated model. Double lines denote
negative coupling constants (-K2 or -K4).

3. Application to the Villain model
Let us consider the Villain (1977) model where K_i = K, as an example.
The angular integrals of the two partition functions are the same for any
temperature. This allows us to link the residual entropy S_V of the Villain
model with the Onsager free energy at criticality F_c:
S_V = (1/2)(-beta_c F_c - (1/2) ln 2) = G / pi,
where G is Catalan's constant and beta_c = T_c^(-1).
"""

GAREL_MAILLARD_VILLAIN_SCAN_OCR_SOURCE_TEXT = """
J. Phys. A: Math. Gen. 16 (1983) 2257-2265.
Study of a two-dimensional fully frustrated model
T Garel and J M Maillard

Abstract. We consider a fully frustrated Ising model on a square lattice,
depending on four parameters. The partition function is shown to be equivalent
to the two-parameter (ferromagnetic) Onsager partition function. This result
can be checked in the particular case of the (one-parameter) Villain model.
In particular, the residual entropy of the Villain model is linked to the free
energy of the Onsager model at criticality.

The model is defined in figure 1, and its reduced Hamiltonian reads
-&P = -H/keT = 1 {K}ij pi pj, (1)
In equation ( l ) , ( i j ) denotes nearest-neighbour pairing, pi = i l , and
the reduced coupling constants { K } i j may take the values
K1, *K2, K3, *K4. The isotropic case
(K1= K 2= K 3 = K4) corresponds to Villain's model.
Figure 1. The four-parameter fully frustrated model. Double lines denote
negative coupling constants (-K2 or -K4).

3. Application to the Villain model
Let us consider the Villain (1977) model where K i = K, as an example.
This shows that the angular integrals of the two partition functions are the
same for any temperature. This allows us to link the residual entropy Sv of
the Villain model with the Onsager free energy at criticality Fc:
Sv = f (-pcFc- f in 2 ) = G / T
where G is Catalan's constant and pc= T i 1.
"""

BAROUCH_MCCOY_XY_SOURCE_TEXT = """
Statistical Mechanics of the XY Model. II. Spin-Correlation Functions
The Hamiltonian is H = J sum_j [(1+gamma) Sx_j Sx_(j+1)
+ (1-gamma) Sy_j Sy_(j+1)] - h sum_j Sz_j, with J positive.
At h=0 the rotational symmetry in the XY plane holds if gamma=0. (1.2)
At T=0, if |h| < J, the ground-state energy is not an analytic function of
gamma at gamma=0. The magnetization fails to be an analytic function of h at
|h|=J for any gamma. There are qualitative differences between h<1, h=1,
and h>1 when the field is measured in units of J.
"""

BERGMAN_DIAMOND_SOURCE_TEXT = """
Order by disorder and spiral spin liquid in frustrated diamond lattice
antiferromagnets. The parent Hamiltonian has nearest-neighbor J1 and
second-neighbor antiferromagnetic exchange J2 on the diamond lattice.
Exact ground states can be obtained for arbitrary J2/J1. For
0 <= J2/J1 <= 1/8 the ground state is the Neel phase. For larger J2 the
Neel phase is supplanted by degenerate coplanar spin spirals whose wavevectors
lie on a two-dimensional spiral surface.
Transforming to momentum space gives two bands
epsilon_pm(q) = 4 J2 [Lambda(q)^2 - 1] +/- 2 J1 Lambda(q). (5)
The lower-band minimum is at q=0 for J2/J1 < 1/8 and on a two-dimensional
surface for larger J2/J1.
"""

MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT = """
PHYSICAL REVIEW B 81, 214419 (2010)
Spiral order by disorder and lattice nematic order in a frustrated Heisenberg
antiferromagnet on the honeycomb lattice
A. Mulder, R. Ganesh, L. Capriotti, and A. Paramekanti
arXiv:1004.1119v2

We study a frustrated J1-J2 Heisenberg model on the two-dimensional honeycomb
lattice. The classical J1-J2 Heisenberg model exhibits Neel order for
J2 < J1/6. For J2 > J1/6, it has a family of degenerate incommensurate spin
spiral ground states where the spiral wave vector can point in any direction.

The Hamiltonian for this model is
H = J1 sum_<ij> S_i dot S_j + J2 sum_<<ij>> S_i dot S_j. (1)
Here <ij> denotes nearest-neighbor pairs, <<ij>> denotes next-neighbor pairs,
and we set J1, J2 > 0.

To calculate the classical ground state energy we assume coplanar spiral order
and parameterize the spins on the two sublattices as
S1(r) = S[cos(Q dot r) zhat + sin(Q dot r) xhat], (2)
S2(r) = -S[cos(Q dot r + phi) zhat + sin(Q dot r + phi) xhat]. (3)
The classical ground state energy per spin is
E_cl/N = -(J1 S^2/2)[cos(phi) + cos(phi-Q_b)
                     + cos(phi-Q_a-Q_b)]
         + J2 S^2[cos(Q_a) + cos(Q_b) + cos(Q_a+Q_b)]. (4)

For J2/J1 > 1/6, the minimum energy solutions correspond to Q* satisfying
cos(Q*_a) + cos(Q*_b) + cos(Q*_a+Q*_b)
    = (1/2)[(J1/(2 J2))^2 - 3]. (5)
The phase phi* is determined completely by
sin(phi*) = (2 J2/J1)[sin(Q*_b) + sin(Q*_a+Q*_b)], (6)
cos(phi*) = (2 J2/J1)[1 + cos(Q*_b) + cos(Q*_a+Q*_b)]. (7)
The classically degenerate solutions to Eq. (5) form a closed contour around
Q=(0,0) for 1/6 < J2/J1 < 1/2. For J2/J1 > 1/2, they form closed contours
around (Q_a,Q_b) = +/-(2 pi/3, 2 pi/3).
"""

BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT = """
Degenerate manifolds, helimagnets, and multi-Q chiral phases in the classical
Heisenberg antiferromagnet on the face-centered-cubic lattice
Peter Balla, Yasir Iqbal, and Karlo Penc
arXiv:2007.00376v3 [cond-mat.str-el] 24 Nov 2020

We present a detailed study of the ground state phase diagram of the classical
frustrated Heisenberg model on the face-centered-cubic lattice. By considering
exchange interactions up till third nearest neighbors, we find commensurate,
helimagnetic, as well as noncollinear multi-Q orders.

II. THE MODEL AND THE LUTTINGER-TISZA METHOD
The Hamiltonian of the classical isotropic Heisenberg model
H = J1 sum_<i,j>1 S_i dot S_j
  + J2 sum_<i,j>2 S_i dot S_j
  + J3 sum_<i,j>3 S_i dot S_j. (1)
It describes three dimensional unit vectors |S_i| = 1 at the sites R_i of the
fcc lattice, interacting with first (J1), second (J2), and third neighbor (J3)
interactions. The summation indices <i,j>delta with delta = 1, 2, 3 refer to
the delta-th neighbor pairs.

Table I. The corresponding energy per site epsilon(Q) is given in the third
column. The fourth column gives the stability region of the commensurate
phases, i.e. exchange parameter regions where the Hessian is positive
definite. The last column gives the conventional names of the commensurate
antiferromagnetic phases.
X (1, 0, 0)  -2J1 + 3J2 - 4J3  J2 < 4J3 < 2J1 - 2J2  Type I
L (1/2, 1/2, 1/2)  -3J2  J1 - 2J2 < 2J3 < J1 + J2  Type II
W (1, 1/2, 0)  -2J1 + J2 + 4J3  8J3 < 2J2 < J1 - 2J3  Type III

The three kinds of antiferromagnetic orders have ordering vectors X(1,0,0),
L(1/2,1/2,1/2), and W(1,1/2,0), which are already present in the J1-J2
models.

Figure 3. X (1, 0, 0) is the Type-I antiferromagnet, L (1/2, 1/2, 1/2) is
the Type-II antiferromagnet, and W (1, 1/2, 0) is the Type-III
antiferromagnet.

VIII. CONCLUSIONS
We presented a detailed study of the ground state phase diagram of the
classical isotropic J1-J2-J3 Heisenberg model on the face-centered-cubic
lattice. We found and analyzed in detail the commensurate Type I, II and III
structures.
"""

BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_TWO_COLUMN_TEXT = (
    BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
        "II. THE MODEL AND THE LUTTINGER-TISZA METHOD",
        "R_i of the fcc lattice, interacting with first (J1), second (J2), "
        "and third neighbor (J3) interactions. The summation indices "
        "<i,j>delta with δ = 1, 2, 3 refer to the δ'th neighbor pairs. "
        "[right-column text precedes the left-column Hamiltonian]\n\n"
        "II. THE MODEL AND THE LUTTINGER-TISZA METHOD",
    )
    .replace(
        "It describes three dimensional unit vectors |S_i| = 1 at the sites R_i of the\n"
        "fcc lattice, interacting with first (J1), second (J2), and third neighbor (J3)\n"
        "interactions. The summation indices <i,j>delta with delta = 1, 2, 3 refer to\n"
        "the delta-th neighbor pairs.",
        "It describes three dimensional unit vectors |S_i| = 1 at the sites. "
        "N Q in M_GS [the page then enters Table I].",
    )
    .replace(
        "The three kinds of antiferromagnetic orders have ordering vectors X(1,0,0),\n"
        "L(1/2,1/2,1/2), and W(1,1/2,0), which are already present in the J1-J2\n"
        "models.",
        "The three kinds of antiferromagnetic or- [phase-diagram labels] ders: "
        "with ordering vectors X(1,0,0), L(1/2,1/2,1/2), and W(1,1/2,0), "
        "which are already present in -2 (b) J1>0 the J1-J2 models.",
    )
)

HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT = """
POWER-LAW SPIN CORRELATIONS IN PYROCHLORE ANTIFERROMAGNETS
C. L. Henley
arXiv:cond-mat/0407005v1 [cond-mat.stat-mech] 1 Jul 2004

The ground state ensemble of the highly frustrated pyrochlore-lattice
antiferromagnet can be mapped to a coarse-grained polarization field satisfying
a zero-divergence condition. The actual spin correlations decay with separation
like a dipole-dipole interaction (1/|R|^3). A lattice version gives an
approximate formula for spin correlations, in particular the pinch-point
(pseudo-dipolar) singularities at reciprocal lattice vectors.

A. Pyrochlore lattice and Hamiltonian
The pyrochlore lattice consists of corner-sharing tetrahedra. The spin
Hamiltonian, having only nearest-neighbor antiferromagnetic exchange, can be
cast as a sum of squares:
H_spin = J_spin sum_<ij> s_i dot s_j + const
       = (J_spin/2) sum_alpha L_alpha^2. (1.2)
The total spin of four sites in a tetrahedron is
L_alpha = sum_(i in alpha) s_i. (1.3)
From (1.4) it is evident that any state with
L_alpha = 0 (1.5)
is a classical ground state; these are massively degenerate.

The other two situations correspond to isotropic Heisenberg models in the
large-S semiclassical regime. The third situation is the low-T limit of the
classical Heisenberg model, and the notion of polarization extends to the
Heisenberg spin case.

D. Generalization to Heisenberg spins
In the case of isotropic n = 3 component spins, we can reiterate all the
coarse-graining arguments in terms of the Heisenberg spin components. The
polarization field becomes a tensor and the divergence condition becomes three
equations, one for each spin-space component.

The structure factor, namely the neutron diffraction intensity modulo
polarization factors, has pseudo-dipolar singularities
<|t(K_200+q)|^2> proportional to
q_perp^2 / (q_parallel^2 + q_perp^2). (2.10)
Here K_200 = [2pi/a](2,0,0) is a reciprocal lattice vector; q_parallel is
parallel and q_perp is perpendicular to the radial direction.

Several pyrochlore systems show the same characteristic diffuse scattering
features: there is a pinch-point singularity of form (2.10) at K_200 and also
K_111 reciprocal lattice vectors.

IV. DISCUSSION
In summary, a polarization can be defined in pyrochlore antiferromagnets which,
in a ground state, exactly satisfies a divergence condition. The correlations
have a pseudo-dipolar form which, since this is a pure power law, implies an
infinite correlation length.
"""

HENLEY_PYROCHLORE_COULOMB_PHASE_TWO_COLUMN_TEXT = (
    HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
        "(pseudo-dipolar) singularities",
        "(pseudodipolar) singularities",
    )
    .replace(
        "The pyrochlore lattice consists of corner-sharing tetrahedra. The spin\n"
        "Hamiltonian, having only nearest-neighbor antiferromagnetic exchange, can be\n"
        "cast as a sum of squares:\n"
        "H_spin = J_spin sum_<ij> s_i dot s_j + const\n"
        "       = (J_spin/2) sum_alpha L_alpha^2. (1.2)",
        "The pyrochlore lattice consists of corner-sharing tetrahedra arranged in "
        "cubic (fcc) symmetry. Its key property is that the sites are the bond "
        "midpoints of a diamond lattice. [The two columns then interleave the "
        "remainder of the lattice review and the temperature-regime discussion.] "
        "The spin Hamiltonian, having only nearest-neighbor constant. At "
        "temperatures T much less than E_J, it is reasonable to antiferromagnetic "
        "exchange, can be cast as a sum of approximate the spin ensemble by a "
        "subset of the groundsquares: state ensemble. X Jspin X 2 Hspin = Jspin "
        "si dot sj + const = Lalpha, (1.2)",
    )
    .replace(
        "The total spin of four sites in a tetrahedron is\n"
        "L_alpha = sum_(i in alpha) s_i. (1.3)\n"
        "From (1.4) it is evident that any state with\n"
        "L_alpha = 0 (1.5)\n"
        "is a classical ground state; these are massively degenerate.",
        "The total spin of four sites in a tetrahedron is breaks the ground-state "
        "degeneracy, favoring collinear states. Lalpha = si (1.3) effective "
        "Hamiltonian, with coupling constant i in alpha. From (1.4) it is evident "
        "that any state with Finer treatment of the spin-wave fluctuations "
        "produces Lalpha = 0. (1.5) an even smaller energy scale for selection "
        "among the discrete states. It is a classical ground state; these are "
        "massively degeneranharmonic terms in the Holstein-Primakoff expansion, "
        "ate.",
    )
)

ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT = """
Cu2IrO3: A New Magnetically Frustrated Honeycomb Iridate
Mykola Abramchuk, Cigdem Ozsoy-Keskinbora, Jason W. Krizan, Kenneth R. Metz,
David C. Bell, and Fazel Tafti
Cite This: J. Am. Chem. Soc. 2017, 139, 15371-15376
DOI: 10.1021/jacs.7b06911

ABSTRACT: We present the first copper iridium binary metal oxide with the
chemical formula Cu2IrO3. The material is synthesized from the parent compound
Na2IrO3 by a topotactic reaction where sodium is exchanged with copper under
mild conditions. Cu2IrO3 has the same monoclinic space group (C2/c) as Na2IrO3
with a layered honeycomb structure.

Figure 1. Structural and chemical relations between CuFeO2, Na2IrO3, and
Cu2IrO3. The structure of Cu2IrO3 consists of edge-sharing (Ir2/3Cu1/3)O6
octahedra in honeycomb layers, similar to Na2IrO3, and copper dumbbells between
the layers, similar to CuFeO2. Sodium atoms are replaced by copper atoms both
between the layers and within the honeycomb layers.

Structural refinement shows that Cu2IrO3 crystallizes in the C2/c space group
with honeycomb layers of edge-sharing (Ir2/3Cu1/3)O6 octahedra similar to
Na2IrO3, but these layers are linked by the CuO2 dumbbells as in CuFeO2.

CONCLUSIONS
The resulting material, Cu2IrO3, is the first copper iridium binary metal oxide
and a new member of A2IrO3 honeycomb iridates. Structurally, Cu2IrO3 has
honeycomb layers in a C2/c unit cell similar to Na2IrO3.
"""

ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_TWO_COLUMN_TEXT = (
    ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
        "Structural refinement shows that Cu2IrO3 crystallizes in the C2/c "
        "space group\nwith honeycomb layers of edge-sharing "
        "(Ir2/3Cu1/3)O6 octahedra",
        "Structural refinement shows that diffraction pattern after 3 weeks "
        "at ambient conditions. Cu2IrO3 crystallizes in the C2/c space group "
        "with honeycomb X-ray Diffraction. Powder X-ray diffraction (PXRD) "
        "was layers of edge-sharing (Ir2/3Cu1/3)O6 octahedra",
    ).replace(
        "The resulting material, Cu2IrO3, is the first copper iridium binary "
        "metal oxide\nand a new member of A2IrO3 honeycomb iridates.",
        "We demonstrate that it is possible to completely substitute all "
        "sodium atoms in Na2IrO3 with copper atoms through a the frustration "
        "index is a rough measure of magnetic topotactic reaction under mild "
        "conditions. The resulting frustration in Na2IrO3 material, Cu2IrO3, "
        "is the first copper iridium binary metal between the exchange scales "
        "oxide and a new member of A2IrO3 honeycomb iridates.",
    )
)

ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT = """
EUROPHYSICS LETTERS
15 April 2005
Europhys. Lett., 70 (2), pp. 237-243 (2005)
DOI: 10.1209/epl/i2004-10484-x

Quantum helimagnetism of the frustrated spin-1/2 chain LiCuVO4
M. Enderle, C. Mukherjee, B. Fak, R. K. Kremer, J.-M. Broto, H. Rosner,
S.-L. Drechsler, J. Richter, J. Malek, A. Prokofiev, W. Assmus, S. Pujol,
J.-L. Raggazzoni, H. Rakoto, M. Rheinstadter and H. M. Ronnow

Abstract. Inelastic neutron scattering, susceptibility, and high-field
magnetization identify LiCuVO4 as a nearest-neighbour ferromagnetic,
next-nearest-neighbour frustrated, quasi-one-dimensional helimagnet, which is
largely influenced by quantum fluctuations.

LiCuVO4 crystallizes in the space group Imma, with edge-shared CuO2 chains
running along b as illustrated in fig. 1. The magnetic structure is helical
with propagation vector (0 0.532 0).

All data were taken in the ordered phase below TN = 2.1 K, verified by the
presence of a magnetic Bragg peak.

The full data set is only compatible with ferromagnetic nearest-neighbour
intrachain interaction J1, and antiferromagnetic next-nearest-neighbour
interaction J2.

The experimentally observed incommensurability translates into a pitch angle
of 83.6 +/- 0.6 degrees.

To summarize, our results demonstrate that LiCuVO4 can be described coherently
with a frustrated FMnn-AFnnn chain model supplemented with a small
ferromagnetic frustrating interchain interaction.
"""

ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_LAYOUT_TEXT = (
    ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
        "quasi-one-dimensional helimagnet",
        "quasi-one- dimensional helimagnet",
    )
    .replace(
        "edge-shared CuO2 chains\nrunning along b",
        "edge-shared CuO2 chains run- ning along b",
    )
    .replace("intrachain interaction J1, and", "intrachain interaction J1 , and")
)

BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT = """
J. Phys. C: Solid State Physics, 13 (1980) L881-885
DOI: 10.1088/0022-3719/13/31/002

Theory of helical magnetic structures and phase transitions in MnSi and FeGe
Per Bak and M. H. Jensen

Abstract. The long-period helical magnetic structures in MnSi and FeGe are
shown to be consequences of a ferromagnetic Dzyaloshinskii instability.

There have been reported several neutron diffraction experiments showing a
helical magnetic structure in MnSi. The wavevector is found to be in the
(111) direction, and it is rather small (0.036 A^-1), indicating a very long
period (175 A).

The b term, which is linear in the gradient, destabilises the ferromagnetic
structure. Physically this term may be caused by relativistic interactions
between the spins of the form Si x Sj.

The potential is minimised by
k = |b| / (B1 + B2/3). (6)
The smallness of k follows from the smallness of b compared to B1 + B2/3.

The spin structure can be expressed in terms of the real vectors:
S(r) = alpha_k cos(k dot r) - beta_k sin(k dot r). (7)
This indeed describes left-handed or right-handed spirals with a long period.

In conclusion, we have demonstrated that the helical magnetic structures in
MnSi and FeGe are caused by a ferromagnetic Dzyaloshinskii instability.
"""

BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_IOP_SCAN_TEXT = (
    BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
        "DOI: 10.1088/0022-3719/13/31/002",
        "(http://iopscience.iop.org/0022-3719/13/31/002)",
    )
    .replace("Per Bak and M. H. Jensen", "Per Bak and M Hsgh Jensen")
    .replace(
        "(111) direction, and it is rather small (0.036 A^-1), indicating a "
        "very long\nperiod (175 A)",
        "(1 11) direction, and it is rather small (-0.036 A-'), indicating "
        "a very long\nperiod ( - 175 A)",
    )
    .replace(
        "relativistic interactions",
        "rela-\ntivistic interactions",
    )
    .replace(
        "The potential is minimised by\n"
        "k = |b| / (B1 + B2/3). (6)\n"
        "The smallness of k follows from the smallness of b compared to "
        "B1 + B2/3.",
        "The potential (3) is now given by F = ...\n"
        "which is minimised by\n"
        "+\n"
        "k = Ibl/(B, SB,). (6)\n"
        "The smallness of k follows from the smallness of b compared to "
        "B , + +B2.",
    )
    .replace(
        "The spin structure can be expressed in terms of the real vectors:\n"
        "S(r) = alpha_k cos(k dot r) - beta_k sin(k dot r). (7)\n"
        "This indeed describes left-handed or right-handed spirals with a "
        "long period.",
        "The spin structure can be expressed in terms of the real vectors "
        "in the following way:\n"
        ".\n"
        "S(r) = a, cos(k r) - Bk sin(k. r ) (7)\n"
        "which indeed describes left-handed or right-handed spirals with a "
        "long period.",
    )
)

SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT = """
SCIENCE 336 (2012) 198-201
DOI: 10.1126/science.1214143

Observation of Skyrmions in a Multiferroic Material
S. Seki, X. Z. Yu, S. Ishiwata, and Y. Tokura

A magnetic skyrmion is a topologically stable particle-like object that
appears as a vortex-like spin texture at the nanometer scale in a
chiral-lattice magnet. Here, we report the experimental discovery of
magnetoelectric skyrmions in an insulating chiral-lattice magnet Cu2OSeO3
through Lorentz transmission electron microscopy and magnetic susceptibility
measurements.

The crystal structure of Cu2OSeO3 is characterized by the same space group
(cubic and chiral) P213 as the B20 alloys. Under zero magnetic field we
observed stripe patterns corresponding to a proper screw-spin order with a
modulation period of approximately 50 nm.

With H approximately 800 Oe applied normal to the sample plane, the formation
of a triangular lattice of skyrmions is observed both for the (110) and (111)
planes. Every skyrmion in the SkX state has a uniform spin chirality.

In both cases, proper screw-spin texture appears for zero magnetic field,
whereas a skyrmion lattice with identical spin chirality is formed for
H = 800 Oe.

Based on these real-space observations, Fig. 2B shows the H-T phase diagram
for thin-film Cu2OSeO3 determined through the measurement of skyrmion density.
Skyrmions disappear for H > 1800 Oe, which implies transition into the
collinear ferrimagnetic spin state.

Considering the reported dimension dependence for the stability of the SkX
state in B20 alloys, we conclude that the observed A phase represents the SkX
state in the bulk form of Cu2OSeO3.

Cu2OSeO3 can be regarded as an insulating analog of B20 alloys, given the
similarity in the crystal symmetry and a magnetic phase diagram characterized
by the narrow A phase (SkX state) region. In insulators, the skyrmion can be
accompanied by electric polarization.
"""

SEKI_CU2OSEO3_SKYRMION_LATTICE_SCIENCE_LAYOUT_TEXT = (
    SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
        "formation\nof a triangular lattice",
        "formation of a trian-\ngular lattice",
    )
    .replace(
        "determined through the measurement of skyrmion density",
        "determined through the measure-\nment of skyrmion density",
    )
    .replace(
        "reported dimension dependence",
        "reported dimen-\nsion dependence",
    )
    .replace(
        "we conclude that the observed A phase",
        "we conclude that the ob-\nserved A phase",
    )
)

WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT = """
SCIENCE 284 (1999) 133-135
DOI: 10.1126/science.284.5411.133

Quantum Phase Interference and Parity Effects in Magnetic Molecular Clusters
W. Wernsdorfer and R. Sessoli

An experimental method based on the Landau-Zener model was developed to
measure very small tunnel splittings in molecular clusters of eight iron
atoms, which at low temperature behave like a nanomagnet with a spin ground
state of S = 10. The observed oscillations of the tunnel splittings as a
function of the magnetic field applied along the hard anisotropy axis are due
to topological quantum interference of two tunnel paths of opposite windings.
Transitions with n even or odd revealed a parity effect analogous to the
suppression of tunneling predicted for half-integer spins.

The octanuclear iron(III) oxo-hydroxo cluster is Fe8. Fe8 has a spin ground
state of S = 10 and an Ising-type magneto-crystalline anisotropy, which
generates an energy barrier for reversal of the magnetization of about 25 K
for Fe8.

For Fe8, however, the relaxation time becomes temperature independent below
360 mK, showing that a pure tunneling mechanism between the only populated
M = +/-10 states is responsible for the relaxation of the magnetization.

Fig. 1. Magnetic hysteresis curves for a crystal of molecular Fe8 clusters at
several temperatures. Resonant tunneling is evidenced by six equally
separated steps. Below 0.4 K, the hysteresis loops are temperature
independent, demonstrating the pure quantum regime.

Our measurements were made with an array of micro-SQUIDs with a very high
sensitivity, allowing us to study single Fe8 crystals. Measurements of
magnetic hysteresis curves reveal the quantum regime. Resonant tunneling is
evidenced by six equally separated steps of Delta Hz = 0.22 T, which, at
T < 360 mK, correspond to tunnel transitions.

To apply the Landau-Zener formula, we swept the applied field at a constant
rate over one of the resonance transitions and measured the fraction of
molecules that reversed their spin. This procedure yields the tunneling rate
P and thus the tunnel splitting. We found good agreement for sweeping rates
between 0.5 and 0.001 T/s.

For small angles the tunneling rate oscillates with a period between minima of
0.41 T. The corresponding tunnel splittings oscillate with almost the same
period of 0.41 T. Comparing quantum transitions with n even or odd revealed a
parity effect analogous to the suppression of tunneling predicted for
half-integer spins.

Our measurement technique directly measures very small tunnel splittings. We
have found a very clear oscillation in the tunnel splittings, which is direct
evidence of the role of the topological spin phase in the spin dynamics of
these molecules. We have also observed an Aharonov-Bohm type of oscillation
in a magnetic system.
"""

WERNSDORFER_SESSOLI_FE8_SCIENCE_WEBPRINT_LAYOUT_TEXT = (
    WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
        "SCIENCE 284 (1999) 133-135\n"
        "DOI: 10.1126/science.284.5411.133\n",
        "",
    )
    .replace(
        "measure very small tunnel splittings",
        "measure very small"
        + (" " * 100)
        + "Alert me when:\n"
        + (" " * 108)
        + "new articles cite this article\n"
        + "tunnel splittings",
    )
    .replace("Delta Hz = 0.22 T", "H z 0.22 T")
    + "\nVolume 284, Number 5411, Issue of 2 Apr 1999, pp. 133-135.\n"
)

KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT = """
Letter
Published: 15 February 2018

A spin-orbital-entangled quantum liquid on a honeycomb lattice
K. Kitagawa, T. Takayama, Y. Matsumoto, A. Kato, R. Takano,
Y. Kishimoto, S. Bette, R. Dinnebier, G. Jackeli, and H. Takagi

Nature volume 554, pages 341-345 (2018)
DOI: https://doi.org/10.1038/nature25482

Abstract
The quantum spin liquid is a long-sought exotic state of matter, in which
interacting spins remain quantum-disordered without spontaneous symmetry
breaking. Here we report a quantum-liquid state of pseudospin-1/2 moments in
the 5d-electron honeycomb compound H3LiIr2O6.

This iridate does not display magnetic ordering down to 0.05 kelvin, despite
an interaction energy of about 100 kelvin. We observe signatures of low-energy
fermionic excitations that originate from a small number of spin defects in
the nuclear-magnetic-resonance relaxation and the specific heat. We therefore
conclude that H3LiIr2O6 is a quantum spin liquid. This result opens the door to
finding exotic quasiparticles in a strongly spin-orbit-coupled 5d-electron
transition-metal oxide.

Figure 2: Evidence from NMR spectroscopy of a spin-liquid ground state in
H3LiIr2O6 down to 1.0 K.
Figure 3: The Knight shift and relaxation rate for H3LiIr2O6 reveal the
intrinsic static susceptibility and spin dynamics.
Figure 4: Low-lying excitations are captured by the specific heat.
"""

RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT = """
Letter
Published: 27 May 1999

Zero-point entropy in 'spin ice'
A. P. Ramirez, A. Hayashi, R. J. Cava, R. Siddharthan, and B. S. Shastry

Nature volume 399, pages 333-335 (1999)
DOI: https://doi.org/10.1038/20619

Abstract
Common water ice (ice I_h) is an unusual solid. Pauling showed that the
presence of two inequivalent O-H bond lengths leads to a macroscopic
degeneracy of possible ground states, such that the system has finite entropy
as the temperature tends towards zero.

An analogous system in which this degeneracy can be studied is a magnet with
the pyrochlore structure--termed 'spin ice'--where spin orientation plays a
similar role to that of the hydrogen position in ice I_h.

Here we present specific-heat data for one such system, Dy2Ti2O7, from which
we infer a total spin entropy of 0.67 R ln 2. This is similar to the value,
0.71 R ln 2, determined for ice I_h, so confirming the validity of the
correspondence. We also find, through application of a magnetic field,
restoration of much of the ground-state entropy and new transitions involving
transverse spin degrees of freedom.

Figure 2: Specific heat and entropy of the spin-ice compound Dy2Ti2O7 showing
agreement with Pauling's prediction for the entropy of water ice I_h,
R (ln 2 - (1/2) ln (3/2)).
"""

CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT = """
Journal of Physics: Condensed Matter
Table of contents for issue 1, volume 7, Journal of Physics: Condensed Matter

69
Crystallographic, magnetic and electronic structures of a new layered
ferromagnetic compound Cr₂Ge₂Te₆
V Carteaux, D Brunet, G Ouvrard and G Andre

Cr₂Ge₂Te₆ is a new layered material belonging to the lamellar ternary
M₂X₂Te₆ chalcogenides family (where M is a 3⁺ oxidation state metal and X₂ a
silicon or a germanium pair). The crystal symmetry is rhombohedral, of space
group R3, with the following hexagonal cell parameters: a=b=0.68275(4) nm,
c=2.05619(9) nm, V=0.830 1(1) nm³ and Z=3.

The crystal structure of Cr₂Ge₂Te₆ was solved using both X-ray single-crystal
diffraction and neutron powder diffraction data. The magnetic structure and
properties of Cr₂Ge₂Te₆ have been determined by neutron powder diffraction
and susceptibility and magnetization measurements. Below 61 K, Cr₂Ge₂Te₆ is
ferromagnetic with spins aligned along the c axis of the cell
(mu (Cr³⁺)=2.80(4)_(mu B) at 5 K). The thermal evolution of the magnetic
moments below T_(c) is given.

https://doi.org/10.1088/0953-8984/7/1/008
"""

CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT = """
Journal of Physics and Chemistry of Solids
Volume 19, Issues 1-2, April 1961, Pages 29-34

Neutron diffraction investigation of antiferromagnetism in CrCl3
J. W. Cable, M. K. Wilkinson, E. O. Wollan
https://doi.org/10.1016/0022-3697(61)90053-1

Abstract
Neutron diffraction observations have been made on powder and single crystal
samples of anhydrous CrCl3 at temperatures from 298 to 4.2 K. This hexagonal
layer-type crystal undergoes a transition at 16.8 K to an antiferromagnetic
state in which the magnetic moments within each hexagonal layer of metal ions
are aligned parallel but adjacent layers of moments are oppositely directed.

The axis of spontaneous sublattice magnetization is closely perpendicular to
the c-axis. Observations of the (003) antiferromagnetic reflection in an
external magnetic field show that the antiferromagnetism can be destroyed with
fields of only a few kilo-oersteds, and lead to the conclusion that a net
magnetization can be produced with very small magnetic fields.
"""

RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT = """
PHYSICAL REVIEW B 82, 100408(R) (2010)

Magnetoelectric MnPS3 as a candidate for ferrotoroidicity
E. Ressouche, M. Loire, V. Simonet, R. Ballou, A. Stunault, and A. Wildes
Received 27 August 2010; published 16 September 2010
DOI: 10.1103/PhysRevB.82.100408

We have revisited the magnetic structure of manganese phosphorus trisulfide
MnPS3 using neutron diffraction and polarimetry. MnPS3 undergoes a transition
toward a collinear antiferromagnetic order at 78 K.

MnPS3 is a lamellar compound, crystallizing in the monoclinic space group
C2/m. The transition-metal ions Mn2+ with spin 5/2, responsible for the
magnetic properties, form a honeycomb lattice in the (a,b) plane. The
transition occurring at 78 K is toward an antiferromagnetic collinear phase.

A MnPS3 crystal has been studied by neutron diffraction at the Institut
Laue-Langevin. The crystal and magnetic structures were first checked on the
four-circle diffractometer D15. Spherical-neutron-polarimetry experiments were
performed on the hot neutron beam diffractometer D3 using CRYOPAD.

In a first step, the magnetic structure was refined from the integrated
intensities collected on D15 at 10 K. Below TN, the antiferromagnetic phase is
characterized by a zero propagation vector. The four magnetic atoms on the 4g
Wyckoff site have their magnetic moment coupled following a +−+− sequence,
i.e., each Mn2+ is antiferromagnetically coupled with its nearest neighbors in
the (a,b) plane and the coupling between adjacent planes is ferromagnetic.

This magnetic structure description was further submitted to the stringent
test of CRYOPAD. The polarization matrices measured for a set of (0,k,l)
reflections at 2 K were refined. The resulting 99 observations were fitted
using the magnetic structure described before.

Figure 2. Antiferromagnetic structure on the honeycomb lattice of Mn2+.
"""

FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT = """
SHORT NOTES
Journal of the Physical Society of Japan

Collapsing Behavior of the Ferrimagnetic Ground State of the S = 1/2
Heisenberg Antiferromagnet on the Lieb Lattice due to Frustration
Rito Furuchi, Hiroki Nakano, and Toru Sakai
arXiv:2409.16715v1 [cond-mat.str-el] 25 Sep 2024

We study the S = 1/2 Heisenberg antiferromagnet on the Lieb lattice
accompanied by additional interactions that create frustration. The system
exhibits a ferrimagnetic ground state in the absence of frustration.

The antiferromagnet on the Lieb lattice exhibits ferrimagnetism, which is
explained in the Marshall-Lieb-Mattis (MLM) theorem. If an additional
interaction that creates frustration is switched on to the Lieb lattice
antiferromagnet, the MLM theorem no longer holds.

Let us explain the model Hamiltonian treated in this study. It is expressed
as
H = sum_<i in D,j in U> J S_i dot S_j
  + sum_<i in U,j in U> J' S_i dot S_j.                         (1)
Here S_i denotes the S = 1/2 spin operator at site i. The number of spins is
denoted by N. The interaction bonds of the first term form the Lieb lattice.

The spin sites of the Lieb lattice are divided into two sublattices denoted
by U and D. The numbers of sites in the primitive unit cell in sublattice U
and D are 2 and 1, respectively. This difference in the number of sites leads
to the occurrence of a ferrimagnetic ground state. The second term of Eq. (1)
denotes additional antiferromagnetic interactions.

We consider J and J' positive and use the interaction ratio eta = J'/J. The
ferrimagnetic ground state appears for eta = 0, corresponding to the Lieb
lattice antiferromagnet.

The saturation magnetization, namely the maximum of M, is M_sat = N/2.
Note that the ferrimagnetic ground states of N = 30, 36, and 42 correspond
to M_spo = 5, 6, and 7, respectively.
"""

HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT = """
Spin Order by Quantum Frustration in Triangular Lattice Mott Insulator
NaCrO2: A Neutron Scattering Study
D. Hsieh, D. Qian, R. F. Berger, Chang Liu, B. Ueland, P. Schiffer,
Q. Huang, R. J. Cava, J. W. Lynn, and M. Z. Hasan

We report high resolution neutron scattering measurements on the triangular
lattice Mott insulator Nax CrO2 (x=1), which exhibits an unusually broad
fluctuating crossover regime extending far below the onset of spin freezing
(Tc approximately 41 K). Below some crossover temperature
(T approximately 0.75 Tc), a small incommensuration develops which helps
resolve the spin frustration and drives three-dimensional magnetic order
supporting coherent spin wave modes. This incommensuration-assisted
dimensional crossover suggests that inter-layer frustration stabilizes the
rare 2D correlated phase above 0.75 Tc. No magnetic long-range order is
observed down to 1.5 K (xi_c less than 16 A).

The classical ground state of the nearest-neighbor triangular-lattice
antiferromagnet is the 120-degree spin structure. If such layers are
rhombohedrally stacked, cancellation of inter-layer Weiss fields leads to a
classical decoupling of spin layers. The ACrO2 Mott insulators, in which Cr3+
(S = 3/2) ions form a rhombohedrally stacked triangular lattice, are good
candidates for this system.

A 15 g powder sample of NaCrO2 was prepared. Magnetic neutron scattering was
performed at the NIST Center for Neutron Research.

For T greater than 40 K spin correlations are purely 2D (N = 1). Weak
inter-plane correlations develop at 40 K (N = 2), and N saturates to 4 from
30 K down to 1.5 K. Comparison of the 1.5 K data to the expected lineshape in
the limit N approaching infinity shows that xi_c is indeed short-range.

The development of weak c-axis correlations between 40 K and 30 K is
accompanied by a change in q from (0, 4 pi/3a, 0) to an incommensurate value.
The ordering wave vector at 40 K points to a 120-degree arrangement and is
consistent with the purely 2D nature of spin correlations. The slight
incommensuration at 30 K represents a departure from 120-degree order which
resolves the inter-layer frustration and explains the onset of inter-layer
correlations.

To conclude, the neutron scattering measurements reveal a rare 2D
antiferromagnetic phase in NaCrO2 with strong spin fluctuations over an
extended temperature range. Low-temperature c-axis correlations together
with a weak incommensurate modulation identify inter-layer frustration as the
mechanism stabilizing this unusual 2D phase.
"""

YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT = """
The tensor renormalization group study of the general spin-S Blume-Capel model
Li-Ping Yang and Zhi-Yuan Xie
arXiv:1204.5027v2 [cond-mat.stat-mech] 21 Oct 2015

We focus on the special situation of D = 2J of the general spin-S Blume-Capel
model on the square lattice. In the absence of the magnetic field, the
visualization parameter characterizing the intrinsic degeneracy of the
different phases clearly demonstrates the phase transition process.

The Hamiltonian of the Blume-Capel model with general spin-S is
H = -J sum_<i,j> S_i S_j + D sum_i S_i^2 - h sum_i S_i^z. (1)
The spin variable S takes 2S + 1 values: (-S, -S+1, ..., S-1, S).
J is the coupling constant, D is the strength of the single-ion anisotropy,
and h is the magnetic field. The sum of the first term runs over all nearest
neighbors. Firstly, we consider the case of h = 0.

For the Hamiltonian of any bond linking two sites i and j,
H_ij = -J S_i S_j + D(S_i^2 + S_j^2)/q. (2)
Here, q is the coordination number depending on the lattice structure. This
formula can be rewritten as
H_ij = J(S_i - S_j)^2/2 + (D/q - J/2)(S_i^2 + S_j^2). (3)

For ferromagnetic coupling (J > 0), when D > qJ/2, the configuration of the
ground state is S_i = S_j = 0 for the integer spin cases. When D < qJ/2, the
configuration of the ground state is S_i = S_j = max(S) for any spin-S case.
At the special situation D = qJ/2, the ground state is S_i = S_j with
(2S + 1)-fold degeneracy.

Without loss of generality, we focus on the square lattice. Then q = 4 and
D = 2J is the special parameter. The phase boundaries of the square lattice
end at (T/J, D/J) = (0, 2), and the critical temperature is T_c = 0 for the
general spin cases when h = 0.

In the case of S = 1, there are three optional values: +/-1 and 0 for each
spin variable.

[1] M. Blume, Phys. Rev. 141, 517 (1966); H. W. Capel,
    Physica 32, 966 (1966).
"""

MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT = """
CaMn2Sb2: a fully frustrated classical magnetic system
I. I. Mazin
arXiv:1309.3744v1 [cond-mat.str-el] 15 Sep 2013

We show by means of density functional calculations that CaMn2Sb2 is very
close to a mean-field critical point known for the classical Heisenberg model
on the honeycomb lattice. Three entirely different long-range ordered
magnetic phases become degenerate at this point: the Neel phase and two
different spiral phases.

CaMn2Sb2 is an interesting implementation of a nearly classical spin system
on a honeycomb lattice. Such systems have been attracting the attention of
researchers since the seminal paper of Rastelli et al. from 1979 [1]. The
basic model involves the nearest-neighbor interaction J1 and the
second-neighbor interaction J2.

In the classical limit, the ground state of this J1-J2 model, for
antiferromagnetic J1 and J2, is the Neel phase where all nearest-neighbor
bonds are fully antiferromagnetic if J2/J1 < 1/6. For
1/6 < J2/J1 < 1/2, there are two degenerate solutions corresponding to two
different spiral phases. At J2/J1 > 1/2 the ground state is the stripe phase
with alternating ferromagnetic pairs.

Both critical points J2/J1 = 1/2 and J2/J1 = 1/6 are triple points. If there
is an additional parameter, for instance the third-neighbor exchange J3,
three phases meet at these points. Whenever a third parameter is added, be
it the third-neighbor exchange J3, uniaxial anisotropy, or biquadratic
coupling K, complex phase diagrams arise with the four phases described
above and additional phases such as zigzag antiferromagnetism.

We calculated the total energies of 10 different magnetic configurations and
mapped the results onto the Heisenberg model that includes first-, second-,
and third-nearest neighbors inside the MnSb layers (J1, J2, and J3).

Figure 5. Phase diagram of the classical J1-J2-J3 Heisenberg model. The phase
boundaries include y = (6x-1)/4, y = (2x+1)/4, y = 0, and x = 1/2 [1].

In the classical phase diagram of an antiferromagnetic J1, J2 two-dimensional
honeycomb layer there are five planar phases: the Neel (N) phase, where all
nearest neighbors order antiferromagnetically; the "stripy" (S) phase, where
all bonds along one direction are ferromagnetic and double stripes order
antiferromagnetically; and two spiral phases (A and B). Adding J3 creates a
complicated phase diagram with a new "zigzag" phase emerging at large J3, as
shown in Figure 5.

[1] E. Rastelli, A. Tassi, and L. Reatto, Physica B 97, 1 (1979).
[2] J. B. Fouet, P. Sindzingre, and C. Lhuillier,
    European Physical Journal B 20, 241 (2001).
"""

STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT = """
Competing Ordering Modes in the Distorted Quantum Kagome Material
Clinoatacamite Cu2Cl(OH)3
L. Stodter, C. Kastner, H. O. Jeschke, and collaborators
arXiv:2601.21024v2 [cond-mat.str-el] 19 Jun 2026

We have studied the magnetic properties of clinoatacamite Cu2Cl(OH)3. As we
reveal using density-functional theory, clinoatacamite belongs to the class of
distorted kagome antiferromagnets with the kagome plane being embedded into a
low-symmetry crystal structure.

Employing density-functional theory (DFT), we demonstrate that clinoatacamite
can be understood as a non-uniform kagome antiferromagnet with weak
ferromagnetic (FM) couplings to the interlayer Cu sites, leading to a weak
network of kagome planes and interlayer sites.

The Cu(2) and Cu(3) sites form a slightly distorted kagome motif. Cu(1) sites
are interlayer sites. There are three inequivalent NN Cu-Cu exchange paths
(J4-J6) within the kagome layers and three inequivalent NN Cu-Cu exchange
paths (J1-J3) between kagome and interlayer sites.

The exchange strengths were derived by means of DFT and GGA+U. At U = 7.19 eV,
the mean-field Curie-Weiss temperature agrees with the experimental value
Theta_CW = -165(1) K with J1 = -6.8 K, J2 = -14.5 K, J3 = -30.3 K,
J4 = 120.1 K, J5 = 211.6 K and J6 = 367.7 K.

The dominant exchange couplings, J4 = 120.1 K, J5 = 211.6 K and J6 = 367.7 K,
form the non-uniform AFM kagome layers. The couplings J1 = -6.8 K,
J2 = -14.5 K and J3 = -30.3 K are FM. These couplings between kagome sites and
interlayer sites |Ji| <= 0.082 J6 lead to a weak ferromagnetic network between
kagome and interlayer sites.

Our findings further rule out the scenario of clinoatacamite as valence bond
solid from Ref. [21].

[21] S.-H. Lee, H. Kikuchi, Y. Qiu, B. Lake, Q. Huang, K. Habicht, and
K. Kiefer, Quantum-spin-liquid states in the two-dimensional kagome
antiferromagnets ZnxCu4-x(OD)6Cl2, Nat. Mater. 6, 853 (2007).
"""

ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT = """
Magnetic Properties of the Spin-1/2 Deformed Kagome Antiferromagnet Edwardsite
Hajime Ishikawa, Yoshihiko Okamoto, and Zenji Hiroi
arXiv:1305.2477v1 [cond-mat.mtrl-sci] 11 May 2013

We prepared a powder sample of edwardsite
Cd2Cu3(SO4)2(OH)6*4H2O, which is a new candidate compound for the spin-1/2
kagome antiferromagnet, and studied its magnetic properties by magnetic
susceptibility and heat capacity measurements. Edwardsite has a deformed
kagome lattice with an average antiferromagnetic interaction of 51 K between
nearby spins and shows an antiferromagnetic order accompanied by a small
ferromagnetic moment below 4.3 K. The weak ferromagnetism is likely due to
spin canting caused by sizable Dzyaloshinsky-Moriya interactions.

The spin-1/2 antiferromagnet on a kagome lattice consists of a
two-dimensional network of corner-sharing triangles.

In edwardsite, Cu2+ ions are aligned in a kagome geometry. The kagome layers
are well separated from each other by a thick nonmagnetic block layer. The
distance between kagome layers is 10.0 A, suggesting that the interplanar
coupling is relatively small in edwardsite.

Cu2+ ions occupy four crystallographic sites, and the Cu-Cu distance in the
kagome lattice varies within 5%. We prepared a pure sample of
Cd2Cu3(SO4)2(OH)6*4H2O and studied its physical properties.

The Curie-Weiss fit yields theta_W = -66.2(3) K. To obtain a more reliable J,
we fit the magnetic susceptibility data between 150 and 300 K to a
calculation for the spin-1/2 KAFM using the high-temperature-series
expansion. This fit gives J/k_B = 51.1(1) K and a Lande g-factor of
g = 2.195(1).

The heat capacity at zero magnetic field shows a broad but distinct peak at
T_N = 4.3 K. Since magnetic interactions in edwardsite are definitely
antiferromagnetic, this magnetic phase transition must be due to a canted
antiferromagnetic order.

Cu2+ ions occupy four different crystallographic sites on the kagome plane,
giving six nonequivalent Cu-Cu bonds with different magnetic couplings. All
the magnetic interactions in edwardsite must be antiferromagnetic because
the Cu-O(H)-Cu angles are between 109 degrees and 116 degrees. The six
antiferromagnetic couplings are classified into two groups: two stronger
ones with J and four weaker ones with J'. The kagome lattice approximately
consists of J-J'-J' isosceles triangles.

In summary, edwardsite is a spin-1/2 deformed KAFM with an average
J/k_B = 51.1 K and exhibits an antiferromagnetic order below T_N = 4.3 K.
The magnetic structure is suggested to be a canted 120-degree order with a
q = 0 propagation vector, preferred by a strong DM interaction and the
deformation of the kagome lattice.
"""

NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT = """
npj Quantum Materials | (2026) 11:42
https://doi.org/10.1038/s41535-026-00868-6
Magnetic excitations of the Kitaev model candidate RuBr3
Kazuhiro Nawa, Yoshinori Imai, Maiko Kofu, Richard Mole, Hideyuki Fujihara,
Takumi Hiraoka, Ryo Murasaki, Pharit Piyawongwatthana, Daisuke Okuyama,
Hirotada Gotou, Kenya Ohgushi, and Taku J. Sato

We performed powder inelastic neutron scattering on RuBr3 with a layered
honeycomb structure, which is isostructural to the low-temperature structure
of alpha-RuCl3. Strongly dispersive magnetic modes were observed near the
centre of the antiferromagnetic zone below T_N. With increasing temperature,
the spectral weight remains near the centre of the antiferromagnetic zone just
above T_N, whereas it shifts to the Gamma point at 3T_N. Strong dispersion
indicates that antiferromagnetic interactions that stabilise the zigzag
antiferromagnetic order, namely, nearest-neighbour symmetric off-diagonal or
third-neighbour isotropic magnetic interactions, are comparable to or even
stronger than ferromagnetic Kitaev interactions, and drive the ground state of
RuBr3 away from the ideal ferromagnetic Kitaev spin liquid state.

The Weiss temperature estimated from the Curie-Weiss fit is -58 K. RuBr3
exhibits a zigzag antiferromagnetic order below 34 K. The size of the magnetic
moments is 0.74(12) mu_B, and the tilting angle from the honeycomb plane is
64(12) degrees.

The inelastic neutron scattering spectrum of RuBr3 reveals strongly dispersive
magnetic excitations centred at the antiferromagnetic zone centre. The
occurrence of zigzag antiferromagnetic order below 34 K was confirmed by
neutron diffraction experiments. Peaks were observed at 0.60 and 1.55
inverse Angstrom. The dispersive magnetic excitations range from 1.5 to
15 meV. The spectrum shows an energy gap of 1.5 meV at 10 K, which becomes
almost zero above 25 K.

We could not conclude that the weak excitations are induced by the Kitaev
interactions since their wavevector and energy dependences are not clear in
the powder inelastic scattering spectra. Linear spin wave theory should
provide a rough estimate for magnetic interactions, although the linear spin
wave approximations would not perfectly apply to the pseudospin-1/2 system.

We looked for parameters J1, K, Gamma, Gamma', J2, and J3. Since it is not
possible to estimate several exchange parameters simultaneously, we present
two extreme combinations with the dominant Gamma or J3 term. The parameters
are phenomenologically adjusted so that the simulated spectrum can reproduce
specific dispersive and dispersionless features.

The former J1-K-Gamma-Gamma' model includes a large Gamma term with zero J2
and J3: J1 = -1.8, K = -7.2, Gamma = 10.5, Gamma' = -2.5 meV. The latter
J1-K-J2-J3 model includes a large J3 term with zero Gamma: J1 = 1.5,
K = -8.1, J2 = 0.8, J3 = 5.8, Gamma' = -0.16 meV. Interplane interactions
of Jp = 0.15 meV were included in both models.

In summary, magnetic excitations of a new polymorph of RuBr3 were investigated
via powder inelastic neutron scattering experiments. Strong antiferromagnetic
interactions coexist with sizable ferromagnetic Kitaev interactions. The
majority of magnetic excitations were reproduced by linear spin wave theory
based on the J1-K-Gamma-Gamma' model with a large Gamma term and the
J1-K-J2-J3 model with a large J3 term. Br substitution should tune the ground
state of RuBr3 away from the ideal ferromagnetic Kitaev spin liquid state.

The Hamiltonian contains nearest-neighbour anisotropic interactions, including
the Kitaev term K, Heisenberg term J1, and non-diagonal components Gamma and
Gamma'. We also introduced J2, J3 and Jp for next-nearest-neighbour,
third-nearest-neighbour, and interplane interactions. The classical ground
state was estimated by the Luttinger-Tisza method. The zigzag
antiferromagnetic order was confirmed to be the classical ground state for the
given parameters discussed in the main text.

Received: 3 October 2025; Accepted: 21 February 2026.
Imai, Y. et al. Zigzag magnetic order in the Kitaev spin-liquid candidate
material RuBr3 with a honeycomb lattice. Phys. Rev. B 105, L041112 (2022).
"""

BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT = """
Vesignieite: a S = 1/2 kagome antiferromagnet with dominant third-neighbor
exchange
D. Boldrin, B. Fak, E. Canevet, J. Ollivier, H. C. Walker, P. Manuel,
D. Khalyavin, and A. S. Wills
arXiv:1806.03074v1 [cond-mat.str-el] 8 Jun 2018

We show using neutron scattering measurements that deuterated vesignieite
BaCu3 V2 O8 (OD)2, a fully stoichiometric S = 1/2 kagome magnet with <1%
lattice distortion, orders magnetically at T_N = 9 K into a multi-k coplanar
variant of the predicted triple-k octahedral structure. We find this structure
is stabilized by a dominant antiferromagnetic 3rd-neighbor exchange J3 with
minor 1st- or 2nd-neighbour exchange. The spin-wave spectrum is well described
by a J3-only model including a tiny symmetric exchange anisotropy.

The mineral vesignieite BaCu3 V2 O8 (OH)2 is a fully stoichiometric yet
distorted S = 1/2 kagome lattice, although this distortion is significantly
less than 1% in terms of bond distances. Vesignieite consists of nearly perfect
Cu2+ kagome layers. Small satellite Bragg peaks suggest the trigonal P3_121
space group, where the tiny scalene distortion of the triangles corresponds to
less than 1% difference in the three Cu-Cu bond lengths. The lowering of the
kagome symmetry is due to a cooperative Jahn-Teller distortion and leads to
the formation of two distinct Cu2+ sites.

Magnetic susceptibility measurements show theta_W = -75 K and predominant
antiferromagnetic interactions. Attempts to estimate the strength and
anisotropy of the exchange interactions based on nearest-neighbor exchange J1
only are bound to fail, as vesignieite has a dominant J3 exchange. Our sample
shows a clear antiferromagnetic phase transition at T_N = 9 K.

Neutron diffraction peaks observed at Q values of 0.64, 1.08, and 1.65
inverse Angstrom can be indexed by a propagation vector of k = (1/2, 0, 0),
which corresponds to the M point of the Brillouin zone of the kagome lattice.
The magnetic structure of vesignieite is related to the octahedral state,
which is favored by a large antiferromagnetic J3 > 0 interaction. The
octahedral state is energetically degenerate with a number of coplanar states
such as the hexagonal structure.

The data were modeled using semi-classical spin-wave theory assuming the
hexagonal magnetic structure and the spin Hamiltonian
H = sum_ij Jij [Six Sjx + Siy Sjy + (1 + delta) Siz Sjz]
    + Dij dot (Si cross Sj).
The flat mode at E = 4 meV fixes the main exchange integrals to
J3 - Jd approximately 2.0, whereas the width and lack of dispersion impose
|Jd| < 0.2, |J1| < 0.1, and |J2| << 0.1. The best fit using an isotropic
version of the Hamiltonian, delta = 0 and Dij = 0, was obtained with
J3 = 1.9 and Jd = -0.1 meV.

Competing nearest-neighbor superexchange paths can cancel in vesignieite,
leading to the negligible J1 and dominant J3 exchange energies we observe.
The hexagonal structure minimizes the J3-only antiferromagnetic Heisenberg
Hamiltonian on the kagome lattice along with a full continuum of magnetic
orders including octahedral and related coplanar and collinear orders.

In conclusion, neutron scattering data show that vesignieite orders
magnetically at T_N = 9 K in a hexagonal multi-k structure with dominant
antiferromagnetic third-neighbor interactions, J3 > 0. First- and
second-neighbor interactions are weak compared to third-neighbor interactions.
For a Heisenberg Hamiltonian, a dominating J3 stabilizes a continuum of
energetically equivalent magnetic structures. A weak symmetric exchange
anisotropy of delta/J3 = -0.006 stabilizes the coplanar hexagonal magnetic
structure from this manifold.

Y. Okamoto, H. Yoshida, and Z. Hiroi, Vesignieite BaCu3 V2 O8 (OH)2 as a
candidate spin-1/2 kagome antiferromagnet, J. Phys. Soc. Japan 78, 033701
(2009).
"""

SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT = """
VOLUME 73, NUMBER 18 PHYSICAL REVIEW LETTERS 31 OCTOBER 1994

Investigation of the Field Induced Antiferromagnetic Phase Transition in the
Frustrated Magnet: Gadolinium Gallium Garnet
P. Schiffer, A. P. Ramirez, D. A. Huse, and A. J. Valentino
(Received 20 May 1994)

The geometrically frustrated magnet gadolinium gallium garnet (GGG) has a
unique low temperature (<0.38 K) antiferromagnetic phase which exists only in
finite fields (H approximately 1 T). We have measured the specific heat and
magnetic susceptibility of GGG to obtain the first accurate map of the low
temperature phase diagram. A ground state magnetic structure in this field
regime has been determined by simulations including both the exchange and
dipole interactions.

One such material is Gd3Ga5O12 (gadolinium gallium garnet or GGG), in which
the magnetic Gd ions are on two interpenetrating corner-sharing triangular
sublattices within the garnet structure, and the exchanges are almost purely
antiferromagnetic with theta_W approximately -2 K. The availability of high
quality GGG samples makes it a model system for the study of frustrated
magnets.

Because of the high degree of frustration, long-range antiferromagnetic order
is suppressed in GGG to T much less than |theta_W| and appears to be completely
suppressed in low magnetic fields. An antiferromagnetic ordering transition
appears as the external magnetic field is increased to approximately 1 T.

The magnetic Gd ions in GGG are on two equivalent sublattices of corner
sharing equilateral triangles. The Gd spins (S = 7/2) are isotropic, although
there is a small single ion anisotropy in the gadolinium garnets of less than
0.04 K. This isotropy leads to the high degree of frustration in GGG which
prevents ordering at low fields. The nearest neighbor dipole energy is
approximately 0.7 K and the nearest neighbor exchange energy is 1.5 K.
Further neighbor exchanges are known to be an order of magnitude or more
smaller.

The antiferromagnetic phase in GGG exists when the Zeeman energies associated
with the external field are of the same order as the antiferromagnetic
exchange energy. A field of that magnitude alleviates the local geometric
frustration but does not force the magnetization to saturate.

To further understand magnetic ordering in GGG, we have studied a simple
model consisting of classical Heisenberg spins at each Gd site coupled with
nearest-neighbor isotropic antiferromagnetic exchange interactions and dipolar
interactions to the third nearest neighbor. The nearest-neighbor exchange is
assumed to be twice the strength of the nearest-neighbor dipolar interactions.
We examined ground states as a function of field and finite-temperature
behavior in Monte Carlo simulations.

In conclusion, this model magnetic system has a unique combination of strong
geometric frustration and dipolar interactions.
"""

QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT = """
PHYSICAL REVIEW B 87, 174421 (2013)

Juxtaposition of spin freezing and long range order in a series of
geometrically frustrated antiferromagnetic gadolinium garnets
J. A. Quilliam, S. Meng, H. A. Craig, L. R. Corruccini, G. Balakrishnan,
O. A. Petrenko, A. Gomez, S. W. Kycia, M. J. P. Gingras, and J. B. Kycia
arXiv:1006.2969v2 [cond-mat.dis-nn] 5 Apr 2013
DOI: 10.1103/PhysRevB.87.174421

Specific heat measurements in zero magnetic field are presented on a
homologous series of geometrically frustrated, antiferromagnetic, Heisenberg
garnet systems. Measurements of Gd3Ga5O12 show no ordering features. In
contrast, samples of Gd3Te2Li3O12 and Gd3Al5O12 exhibit clear ordering
transitions at 243 mK and 175 mK respectively. A thorough structural
characterization using X-ray diffraction is performed on all samples.

Magnetic systems on a lattice of corner-sharing simplexes, such as triangles
or tetrahedra, coupled via a nearest-neighbor antiferromagnetic Heisenberg
exchange Hamiltonian H0 are highly frustrated. We investigate frustrated
garnet materials described by a three-dimensional network of corner-sharing
triangles. Gd3Te2Li3O12 is abbreviated GTLG.

The cubic unit cell of the Gd3A2B3O12 garnet structure has Gd positions which
form two interpenetrating networks of corner-sharing triangles, known as
hyperkagome lattices. With largely isotropic S = 7/2 Gd3+ moments, these
materials are fair representations of classical Heisenberg antiferromagnets.
Because the nearest-neighbor exchange scale J1 is approximately 0.1 to 0.14 K,
the dipolar interaction becomes very important. All of the Gd garnet
materials studied are highly frustrated.

III. HAMILTONIANS

They are likely to be described primarily by a Hamiltonian consisting of a
nearest-neighbor exchange interaction
H_Ex = sum_<i,j> J1 S_i dot S_j                                      (1)
and the dipolar interaction
H_D = D sum_<i,j> r_nn^3/r_ij^3
      [S_i dot S_j - 3(S_i dot rhat_ij)(S_j dot rhat_ij)].            (2)
Further-neighbor interactions may be important, but for GTLG they have not
yet been determined.

High-temperature susceptibility gives the Curie-Weiss temperature and
primarily represents nearest-neighbor exchange. This gives J1 = 126 mK for
GTLG. The dipolar interaction is nearly identical between GGG and GTLG at
D = 45 mK. The ratio D/J1 progresses from GAG (0.34) to GTLG (0.36) and then
GGG (0.42).

In stark contrast to GGG, GTLG displays a very sharp phase transition at
243 mK. The transition is clearly first order. With a Curie-Weiss temperature
theta_CW approximately -2.7 K in GTLG, this ordering temperature gives a
frustration index f = |theta_CW|/T_C = 11.

Below the transition there are gapped spin-wave excitations, as expected from
long-range order with a strong dipolar interaction. A linear fit gives a gap
Delta approximately 0.62 K, which is expected to come primarily from the
anisotropic dipole-dipole interaction H_D. The sharp transition and
exponential drop in specific heat provide strong evidence of long-range order.

The GTLG sample is cubic with space group Ia-3d (230). In conclusion, GTLG
shows a clear ordering transition, demonstrating that the response of a
highly frustrated magnet to weak random disorder can be highly nontrivial.
"""

ROSS_PYROCHLORE_EXCHANGE_SOURCE_TEXT = """
Quantum Excitations in Quantum Spin Ice
We rewrite the zero-field nearest-neighbor pyrochlore Hamiltonian in terms of
spins quantized along each local C3 axis:
H = sum_<ij> {Jzz Sz_i Sz_j - Jpm (S+_i S-_j + S-_i S+_j)
+ Jpmpm (gamma_ij S+_i S+_j + gamma*_ij S-_i S-_j)
+ Jzpm [Sz_i (zeta_ij S+_j + zeta*_ij S-_j) + i <-> j]}. (4)
Here Jzz, Jpm, Jpmpm, and Jzpm are expressed in terms of the four independent
global exchange constants J1, J2, J3, and J4.
"""

KANE_MELE_HUBBARD_SOURCE_TEXT = """
We investigate the Hubbard model on the honeycomb lattice with intrinsic
spin-orbit interactions. At half filling, consider the spin-orbit term in the
strong-coupling limit U -> infinity with t and lambda fixed. The second-order
spin Hamiltonian is
H = |J2| (-Sx_i Sx_j - Sy_i Sy_j + Sz_i Sz_j), (31)
with exchange coupling J2 = 4 lambda^2 / U. The XY term favors ferromagnetic
order and the Z term favors antiparallel alignment of the spins.
"""

YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT = """
Quantum Excitations in Quantum Spin Ice
For Yb2Ti2O7, high-field time-of-flight inelastic neutron scattering measured
spin-wave dispersions throughout the Brillouin zone. The spectrum is extremely
well fit by spin-wave theory, and through this fit we unambiguously extract all
the microscopic exchange parameters in the spin Hamiltonian. Symmetry allows
four independent exchange constants J1, J2, J3, and J4. Rewriting the zero-field
nearest-neighbor pyrochlore Hamiltonian in terms of spins quantized along each
local C3 axis gives
H = sum_<ij> {Jzz Sz_i Sz_j - Jpm (S+_i S-_j + S-_i S+_j)
+ Jpmpm (gamma_ij S+_i S+_j + gamma*_ij S-_i S-_j)
+ Jzpm [Sz_i (zeta_ij S+_j + zeta*_ij S-_j) + i <-> j]}. (4)
Here Jzz, Jpm, Jpmpm, and Jzpm are expressed in terms of the four independent
global exchange constants J1, J2, J3, and J4.
From the fits in Eq. (3), we find in meV:
Jzz = 0.17 +/- 0.04; Jpm = 0.05 +/- 0.01;
Jpmpm = 0.05 +/- 0.01; Jzpm = -0.14 +/- 0.01. (5)
"""

HARRIS_SPIN_ICE_TETRAHEDRON_SOURCE_TEXT = """
We consider a ferromagnetic pyrochlore with Ising anisotropy directed along the
<111>-type directions, which connect a spin with the center of its tetrahedron.
The ground state of such a single tetrahedron is characterized by two spins in
and two spins out. This two-in, two-out condition is identical to the ice rule.
"""

KHARKOV_SQUARE_J1_J3_SOURCE_TEXT = """
The field n_mu is the staggered magnetization. In the spin spiral phase,
n(r) = e1 cos(Q r) + e2 sin(Q r), where Q is the pitch of the spiral.
We consider the antiferromagnetic J1-J3 Heisenberg model on the square lattice.
The Hamiltonian is H = J1 sum_<ij> Si.Sj + J3 sum_<<<ij>>> Si.Sj, (34)
where the sums denote first- and third-nearest-neighbor interactions.
In the classical limit, the spin-spiral to Neel Lifshitz point is located at
J3/J1 = 1/4.
"""

LIU_SQUARE_J1_J2_J3_SOURCE_TEXT = """
Using the finite projected entangled pair state (PEPS) method, we investigate
the global phase diagram of the spin-1/2 square-lattice J1-J2-J3
antiferromagnetic Heisenberg model. The ground-state phase diagram contains the
Neel AFM, gapless quantum spin liquid, valence-bond solid (VBS), stripe AFM,
and incommensurate spiral phases. Quantum fluctuations stabilize paramagnetic
states. We find two successive gapless quantum spin liquid (QSL) and VBS phases
lying between the Neel and stripe phases.
"""

GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT = """
Plaquette Ordered Phase and Quantum Phase Diagram in the Spin-1/2 J1-J2 Square
Heisenberg Model. We study the spin-1/2 Heisenberg model on the square lattice
with first- and second-neighbor antiferromagnetic interactions J1 and J2. We use
the density matrix renormalization group approach with explicit SU(2) symmetry.
With increasing J2, we find a Neel phase and a plaquette valence-bond (PVB)
phase with a finite spin gap. The growing PVB textures are consistent with
long-range PVB order in the two-dimensional limit.
"""

MOESSNER_PYROCHLORE_FLAT_BAND_SOURCE_TEXT = """
We study the low-temperature behavior of the classical Heisenberg
antiferromagnet with nearest-neighbor interactions on the pyrochlore lattice.
The Hamiltonian can be written
H = J sum_<i,j> S_i.S_j = (J/2) sum_a |L_a|^2 - (J/2) N q, (1)
where L_a is the total spin in tetrahedral unit a. A configuration is a ground
state provided L_a = 0 for each unit separately. For a generic ground state,
three quarters of the harmonic modes have finite frequencies and the remaining
one quarter have zero frequency.
"""

RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT = """
We use the coupled cluster method to high orders of approximation to calculate
the spin-1/2 J1-J2 model on the square lattice. We obtain transition points from
the Neel and collinear antiferromagnetic phases to the magnetically disordered
quantum paramagnetic phase of J2c1 = 0.454 J1 and J2c2 = 0.588 J1.
"""

GARDNER_TB2TI2O7_SOURCE_TEXT = """
Neutron scattering, muon spin relaxation, and dc susceptibility studies have
been carried out on polycrystalline Tb2Ti2O7, a pyrochlore antiferromagnet.
Tb2Ti2O7 remains paramagnetic down to 0.07 K rather than ordering into a
conventional Neel or spin-glass-like state, despite short-range
antiferromagnetic correlations. The smooth monotonic muon spin relaxation down
to 70 mK establishes that it remains paramagnetic with persistent spin
dynamics. This leaves it a cooperative paramagnet at low temperatures.
"""

RAMIREZ_SCGO_SOURCE_TEXT = """
The interactions in SrCr8Ga4O19 are highly frustrated. The Cr sites form
corner-sharing triangles of the kagome lattice and dominate the
quasi-two-dimensional magnetic behavior. The Curie-Weiss temperature is 515 K,
yet no conventional ordering anomaly is seen until 3.5 K. The low-temperature
anomaly is a spin-glass-type freezing transition rather than conventional
long-range magnetic order.
"""

SOURCE_SHA256 = "9ad3044b7528d53fd0aa3616eb2ab8190b196b3f46f9f0711e53d10be24815e0"
MISSING = object()
REQUIRED_RUNTIME_SOURCE_IDS = {
    "arxiv_1210a896b82f8e645da1",
    "doi_122dc1b374767a010cb0",
    "doi_5ac1fc0c40596b19c09f",
    "doi_f31ef7e012b01a5ac71d",
    "doi_f900791f74b4918a9a3e",
    "doi_ebcdccab3f81a5059936",
    "doi_696bd9749ec01fc72d99",
    "doi_735636355d51385c61be",
    "doi_33fcf4c762fb137794a6",
    "doi_31d77765ea903f1adaa9",
    "doi_607b6dc8e2ebace9ef53",
    "doi_d3dec73b0de1021b7f2a",
    "doi_b5e49ab59ee164e8232f",
    "doi_3c3be4c66f0054c73f1d",
    "doi_cb3265e8744878673955",
    "doi_648ea4bc439b5b7a10c2",
    "doi_f915390aad8ba95157bf",
    "doi_5c4f75ee56f57b91e3e4",
    "doi_2817c61413e96673d2ef",
    "doi_2e773eb6fd2e35377402",
    "arxiv_6d8189949f34733eb8b4",
    "doi_94d0604c7e864a5e1f8f",
    "doi_7f88cea74a31c9249c7c",
    "doi_f605e466ceaab98b53c2",
    "arxiv_22ae1487c7957c762836",
    "doi_ae5fae7f5deae7bdf7e5",
    "doi_9bc03c9b602db2e07251",
    "doi_7f5b5aacbb36eeb82b59",
    "doi_ed7a65b8814519a190b1",
    "doi_bbb9a260b243a8c2d482",
    "doi_d9030016946221a0420c",
    "doi_30de47257cfae45dcfca",
    "doi_1d4ba213888164ea4467",
    "doi_642f8a747bfe6282382d",
    "doi_3e2040dc6e9848bd1404",
    "doi_4ad6882c76431fdc6aa1",
    "doi_c0cf5cc8dcbcb862c362",
    "doi_5b656dfc4b6b9ffc48f2",
    "arxiv_63ac2dc486b14b933a79",
    "doi_0e5fc23af85ddd55e5bc",
    "doi_c7592568c4ee5f8fd07c",
}


def _require_runtime_cache():
    missing = sorted(
        source_id
        for source_id in REQUIRED_RUNTIME_SOURCE_IDS
        if not (literature_runtime_evidence.DEFAULT_CACHE_ROOT / source_id).is_dir()
    )
    if missing:
        pytest.skip(
            "provision source-cache directories before runtime integration: "
            + ", ".join(missing)
        )


def _runtime_source_parse_record(*, matched=True):
    return {
        "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
        "evidence_mode": "local_source_parse",
        "source_id": "doi_f31ef7e012b01a5ac71d",
        "source_sha256": SOURCE_SHA256,
        "registry_selector": {
            "path": ["standard_result"],
            "fields": ["ferromagnetic_order"],
        },
        "source_operand": {"ferromagnetic_order": True},
        "registry_operand": {"ferromagnetic_order": True},
        "comparison": {"kind": "exact_field_map", "matched": matched},
    }


def _extraction_trace():
    return {
        "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
        "parser": "parse_cri3_ferromagnetic_order",
        "coordinate_space": "whitespace_normalized_extracted_text",
        "source_sha256": SOURCE_SHA256,
        "matched_anchors": [
            "honeycomb network",
            "long range ferromagnetic order develops below TC = 61 K",
        ],
        "text_spans": [[48, 65], [117, 174]],
    }


def test_cri3_parser_extracts_ferromagnetic_order_from_source_text():
    parsed, trace = parse_cri3_ferromagnetic_order(CR_I3_SOURCE_TEXT)

    assert parsed == {"ferromagnetic_order": True}
    assert trace["parser"] == "parse_cri3_ferromagnetic_order"
    assert trace["matched_anchors"] == [
        "honeycomb network",
        "long range ferromagnetic order develops below TC = 61 K",
    ]
    assert len(trace["text_spans"]) == 2


@pytest.mark.parametrize(
    "source_text",
    [
        CR_I3_SOURCE_TEXT.replace("honeycomb network", "layered network"),
        CR_I3_SOURCE_TEXT.replace("ferromagnetic order develops", "magnetic response develops"),
        CR_I3_SOURCE_TEXT.replace("61 K", "unknown temperature"),
    ],
)
def test_cri3_parser_fails_closed_when_source_claim_is_incomplete(source_text):
    with pytest.raises(RuntimeEvidenceError, match="CrI3 source claim"):
        parse_cri3_ferromagnetic_order(source_text)


def test_yang_yang_parser_normalizes_hashed_pdf_fraction_glyphs():
    parsed, trace = parse_yang_yang_xxx_ground_state_energy(
        YANG_YANG_SOURCE_TEXT
    )

    assert parsed["energy_per_site"] == pytest.approx(0.25 - 0.6931471805599453)
    assert trace["parser"] == "parse_yang_yang_xxx_ground_state_energy"
    assert trace["equation"] == "31c"
    assert trace["normalization"] == "yang_yang_1966_fraction_glyph_one_quarter"


@pytest.mark.parametrize(
    "source_text",
    [
        YANG_YANG_SOURCE_TEXT.replace("(31c)", "(31d)"),
        YANG_YANG_SOURCE_TEXT.replace("ln2", "ln3"),
        YANG_YANG_SOURCE_TEXT.replace("-,'", "unknown"),
    ],
)
def test_yang_yang_parser_fails_closed_without_complete_equation(source_text):
    with pytest.raises(RuntimeEvidenceError, match=r"Yang-Yang Eq. \(31c\)"):
        parse_yang_yang_xxx_ground_state_energy(source_text)


def test_hirata_nomura_parser_extracts_exact_xxz_phase_boundaries():
    parsed, trace = (
        literature_runtime_evidence.parse_hirata_nomura_xxz_phase_boundaries(
            HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT
        )
    )

    assert parsed == {
        "ferromagnetic_boundary_delta": -1.0,
        "neel_boundary_delta": 1.0,
        "gapless_interval": [-1.0, 1.0],
    }
    assert trace["parser"] == (
        "parse_hirata_nomura_xxz_phase_boundaries"
    )
    assert trace["source_model"] == (
        "H=J sum_i(h_i,i+1+alpha h_i,i+2), "
        "h_ij=SxSx+SySy+Delta SzSz, J>0"
    )
    assert trace["exact_submodel"] == (
        "alpha=0 nearest-neighbor spin-1/2 XXZ chain"
    )
    assert trace["registered_convention_mapping"] == (
        "source Delta equals registry Delta; no sign or scale conversion"
    )
    assert trace["corrected_source_identity"] == (
        "arXiv:cond-mat/9909290v1"
    )
    assert trace["superseded_registered_doi"] == (
        "10.1103/PhysRev.150.321"
    )
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "Phase diagram of S = 1/2 XXZ chain with NNN interaction",
            "Phase diagram of a classical Ising ladder",
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "Kiyohide Nomura", "Kiyohide Example"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "cond-mat/9909290v1", "cond-mat/9900000v1"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "spin-1/2 XXZ chain", "spin-1 XXZ chain"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "h_i,j = S_i^x S_j^x + S_i^y S_j^y + Delta S_i^z S_j^z",
            "h_i,j = S_i^z S_j^z",
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "NN coupling J > 0", "NN coupling J < 0"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "When alpha = 0", "When alpha = 0.2"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "integrable by the Bethe ansatz",
            "estimated by classical mean-field theory",
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "For Delta < -1", "For Delta < -2"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "for Delta > 1", "for Delta > 2"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "(-1 <= Delta <= 1)", "(-0.5 <= Delta <= 0.5)"
        ),
        HIRATA_NOMURA_XXZ_PHASE_SOURCE_TEXT.replace(
            "characterized by a gapless excitation",
            "characterized by a finite excitation gap",
        ),
    ],
)
def test_hirata_nomura_xxz_parser_fails_closed_without_full_phase_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Hirata-Nomura exact XXZ submodel",
    ):
        literature_runtime_evidence.parse_hirata_nomura_xxz_phase_boundaries(
            source_text
        )


@pytest.mark.parametrize(
    "source_text",
    [
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT,
        OKAMOTO_NOMURA_J1_J2_IA_OCR_SOURCE_TEXT,
    ],
)
def test_okamoto_nomura_j1_j2_parsers_extract_both_registered_ratio_fields(
    source_text,
):
    parsed, trace = (
        literature_runtime_evidence.parse_okamoto_nomura_j1_j2_critical_point(
            source_text
        )
    )
    approximate, approximate_trace = (
        literature_runtime_evidence.parse_okamoto_nomura_j1_j2_bkt_reference(
            source_text
        )
    )

    assert parsed == {"critical_j2_over_j1": pytest.approx(0.2411)}
    assert approximate == {
        "critical_j2_over_j1_approx": pytest.approx(0.2411)
    }
    assert trace["reported_uncertainty"] == pytest.approx(0.0001)
    assert trace["finite_sizes"] == list(range(8, 25, 2))
    assert trace["source_ratio_mapping"] == "alpha=J2/J1"
    assert trace["matched_anchors"] == [
        "identified Okamoto-Nomura Physics Letters A 169 paper",
        "periodic antiferromagnetic spin-half NN-plus-NNN Hamiltonian",
        "singlet-triplet/singlet-singlet crossing for N=8,10,...,24",
        "alternating-epsilon, Shanks, and 1/N^2 extrapolations",
        "alpha_c=0.2411+/-0.0001 conclusion",
    ]
    assert trace["text_spans"] == approximate_trace["text_spans"]
    assert all(start < end for start, end in trace["text_spans"])


@pytest.mark.parametrize(
    "source_text",
    [
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "Physics Letters A 169 (1992) 433-437",
            "Physics Letters A 168 (1992) 433-437",
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "Fluid-dimer critical point in S=1/2 antiferromagnetic "
            "Heisenberg chain",
            "Fluid-dimer critical point in a classical Ising chain",
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "Kiyohide Nomura", "Kiyohide Example"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "with J > 0 and alpha > 0",
            "with J < 0 and alpha > 0",
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "periodic boundary condition", "open boundary condition"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "singlet-triplet gap", "singlet-quintet gap"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "singlet-singlet gap", "triplet-triplet gap"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "N=8, 10, ..., 24", "N=8, 10, ..., 20"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "0.24 < alpha < 0.25", "0.34 < alpha < 0.35"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "alpha_c = 0.24112218", "alpha_c = 0.34112218"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "alpha_c = 0.24117290", "alpha_c = 0.34117290"
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "alpha_c = 0.241155 +/- 0.000003",
            "alpha_c = 0.341155 +/- 0.000003",
        ),
        OKAMOTO_NOMURA_J1_J2_SOURCE_TEXT.replace(
            "alpha_c = 0.2411 +/- 0.0001",
            "alpha_c = 0.3411 +/- 0.0001",
        ),
    ],
)
def test_okamoto_nomura_j1_j2_parsers_fail_closed_without_full_evidence_chain(
    source_text,
):
    for parser in (
        literature_runtime_evidence.parse_okamoto_nomura_j1_j2_critical_point,
        literature_runtime_evidence.parse_okamoto_nomura_j1_j2_bkt_reference,
    ):
        with pytest.raises(
            RuntimeEvidenceError,
            match="Okamoto-Nomura J1-J2 critical source",
        ):
            parser(source_text)


def test_kumar_j1_j2_parsers_extract_okamoto_nomura_transition_ratio():
    parsed, trace = (
        literature_runtime_evidence.parse_kumar_j1_j2_critical_point(
            KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT
        )
    )
    approximate, approximate_trace = (
        literature_runtime_evidence.parse_kumar_j1_j2_bkt_reference(
            KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT
        )
    )

    assert parsed == {"critical_j2_over_j1": pytest.approx(0.2411)}
    assert approximate == {
        "critical_j2_over_j1_approx": pytest.approx(0.2411)
    }
    assert trace["parser"] == "parse_kumar_j1_j2_critical_point"
    assert trace["source_profile"] == "arxiv:1006.5052v1"
    assert trace["source_ratio_mapping"] == (
        "J2/J1=x/(1-x); source reports x1=0.1943 and "
        "x1/(1-x1)=0.2411"
    )
    assert trace["text_spans"] == approximate_trace["text_spans"]
    assert all(start < end for start, end in trace["text_spans"])


@pytest.mark.parametrize(
    "source_text",
    [
        KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT.replace(
            "arXiv:1006.5052v1", "arXiv:1006.0000v1"
        ),
        KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT.replace(
            "spin-1/2 Heisenberg", "spin-1 Heisenberg"
        ),
        KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT.replace(
            "J2/J1 = 0.2411", "J2/J1 = 0.3411"
        ),
        KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT.replace(
            "x_1/(1-x_1) = 0.2411", "x_1/(1-x_1) = 0.3411"
        ),
        KUMAR_RAMASESHA_SOOS_J1_J2_SOURCE_TEXT.replace(
            "where a magnetic\ngap E_m opens",
            "where the magnetic gap remains closed",
        ),
    ],
)
def test_kumar_j1_j2_parsers_fail_closed_without_complete_source_chain(
    source_text,
):
    for parser in (
        literature_runtime_evidence.parse_kumar_j1_j2_critical_point,
        literature_runtime_evidence.parse_kumar_j1_j2_bkt_reference,
    ):
        with pytest.raises(
            RuntimeEvidenceError,
            match="Kumar-Ramasesha-Soos J1-J2 source",
        ):
            parser(source_text)


def test_savary_er2ti2o7_parser_extracts_psi2_order_by_quantum_disorder():
    parsed, trace = (
        literature_runtime_evidence
        .parse_savary_er2ti2o7_psi2_order_by_quantum_disorder(
            SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT
        )
    )

    assert parsed == {"psi2_order_selected": True}
    assert trace["parser"] == (
        "parse_savary_er2ti2o7_psi2_order_by_quantum_disorder"
    )
    assert trace["source_model"] == (
        "effective spin-1/2 nearest-neighbor pyrochlore Hamiltonian "
        "with Jzz, Jpm, Jpmpm, and Jzpm anisotropic exchanges"
    )
    assert trace["selection_chain"] == (
        "classical U(1) ground-state manifold -> zero-point-energy "
        "minima alpha=n*pi/3 -> psi2 order"
    )
    assert trace["registered_convention_mapping"] == (
        "source psi2 selection equals registry boolean; no sign, "
        "normalization, or unit conversion"
    )
    assert trace["corrected_source_identity"] == (
        "arXiv:1204.1320v1; DOI:10.1103/PhysRevLett.109.167201"
    )
    assert trace["superseded_registered_doi"] == (
        "10.1103/PhysRevLett.108.037202"
    )
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "Definitive Evidence for Order-by-Quantum-Disorder in Er2Ti2O7",
            "Coulombic Quantum Liquids in Spin-1/2 Pyrochlores",
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "Lucile Savary", "Example Author"
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "arXiv:1204.1320v1", "arXiv:1204.0000v1"
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "effective S = 1/2 quantum spins",
            "classical unit-vector spins",
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "Nearest-neighbor exchange dominates",
            "Long-range dipolar exchange dominates",
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "Jpmpm = 4.2 +/- 0.5", "Jpmpm was not determined"
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "are its classical ground states",
            "are absent from its classical ground states",
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "break the U(1) degeneracy",
            "preserve the U(1) degeneracy",
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "alpha = n pi/3", "alpha = pi/6 + n pi/3"
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "These are exactly the psi2 states",
            "These are exactly the psi1 states",
        ),
        SAVARY_ER2TI2O7_PSI2_SOURCE_TEXT.replace(
            "gives strong evidence for the correctness",
            "finds no experimental distinction",
        ),
    ],
)
def test_savary_er2ti2o7_parser_fails_closed_without_complete_selection_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Savary Er2Ti2O7 order-by-quantum-disorder source",
    ):
        (
            literature_runtime_evidence
            .parse_savary_er2ti2o7_psi2_order_by_quantum_disorder(
                source_text
            )
        )


def test_richter_star_parser_maps_explicit_valence_bond_branch_only():
    parsed, trace = (
        literature_runtime_evidence
        .parse_richter_star_lattice_valence_bond_ground_state(
            RICHTER_STAR_LATTICE_SOURCE_TEXT
        )
    )

    assert parsed == {"spin_liquid_or_valence_bond_reference": True}
    assert trace["parser"] == (
        "parse_richter_star_lattice_valence_bond_ground_state"
    )
    assert trace["source_model"] == (
        "uniform spin-1/2 nearest-neighbor Heisenberg antiferromagnet "
        "on the star lattice with JD=JT=J"
    )
    assert trace["registry_claim_mapping"] == (
        "source explicit valence-bond crystal satisfies the registry "
        "spin-liquid-or-valence-bond umbrella through its valence-bond "
        "branch; no spin-liquid claim is inferred"
    )
    assert trace["corrected_source_identity"] == (
        "DOI:10.1103/PhysRevB.70.174454"
    )
    assert trace["superseded_registered_doi"] == (
        "10.1103/PhysRevB.70.184414"
    )
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "Absence of magnetic order for the spin-half Heisenberg "
            "antiferromagnet\non the star lattice",
            "Magneto-optical effects in double perovskites",
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "A. Honecker", "A. Example"
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "10.1103/PhysRevB.70.174454",
            "10.1103/PhysRevB.70.184414",
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "spin-half Heisenberg antiferromagnet",
            "classical Ising ferromagnet",
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "J_D = J_T = J", "J_D = 4 J_T"
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "most likely dimerized with a gap to all excitations",
            "most likely magnetically ordered and gapless",
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "dominated by local singlet pairing",
            "dominated by long-range Neel order",
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "explicit valence-bond\ncrystal state",
            "semiclassical magnetic\ncrystal state",
        ),
        RICHTER_STAR_LATTICE_SOURCE_TEXT.replace(
            "even in the uniform case\nJ_D = J_T",
            "only for strongly unequal bonds\nJ_D >> J_T",
        ),
    ],
)
def test_richter_star_parser_fails_closed_without_valence_bond_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Richter star-lattice valence-bond source",
    ):
        (
            literature_runtime_evidence
            .parse_richter_star_lattice_valence_bond_ground_state(
                source_text
            )
        )


def test_richter_square_kagome_parser_extracts_corrected_shuriken_reference():
    parsed, trace = (
        literature_runtime_evidence.parse_richter_square_kagome_reference(
            RICHTER_SQUARE_KAGOME_SOURCE_TEXT
        )
    )

    assert parsed == {"square_kagome_reference": True}
    assert trace["parser"] == "parse_richter_square_kagome_reference"
    assert trace["source_model"] == (
        "uniform spin-1/2 nearest-neighbor Heisenberg antiferromagnet "
        "on the square-kagome lattice with JS=JT=J"
    )
    assert trace["registered_lattice_mapping"] == (
        "registry shuriken-lattice alias maps to source square-kagome "
        "lattice; star lattice is explicitly excluded"
    )
    assert trace["corrected_source_identity"] == (
        "arXiv:cond-mat/0411673v1"
    )
    assert trace["superseded_registered_doi"] == (
        "10.1103/PhysRevB.70.174454"
    )
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "The spin-half Heisenberg antiferromagnet on the square-kagome "
            "lattice",
            "The spin-half Heisenberg antiferromagnet on the star lattice",
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "P. Tomczak", "P. Example"
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "cond-mat/0411673v1", "cond-mat/0411000v1"
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "underlying Bravais lattice is a square one",
            "underlying Bravais lattice is triangular",
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "spin-half HAFM", "classical Ising model"
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "J_S = J_T = J", "J_S = 3 J_T"
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "spin-liquid like ground state",
            "semiclassical Neel ground state",
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "Contrary to the star lattice case",
            "As in the star lattice case",
        ),
        RICHTER_SQUARE_KAGOME_SOURCE_TEXT.replace(
            "localized magnons\nlive on the squares",
            "localized magnons\nlive on star-lattice dodecagons",
        ),
    ],
)
def test_richter_square_kagome_parser_fails_closed_without_lattice_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Richter square-kagome source",
    ):
        literature_runtime_evidence.parse_richter_square_kagome_reference(
            source_text
        )


def test_wildes_feps3_parser_extracts_ising_like_zigzag_order():
    parsed, trace = (
        literature_runtime_evidence.parse_wildes_feps3_ising_zigzag_order(
            WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT
        )
    )

    assert parsed == {"ising_like_zigzag_order": True}
    assert trace["parser"] == (
        "parse_wildes_feps3_ising_zigzag_order"
    )
    assert trace["source_model"] == (
        "S=2 FePS3 honeycomb Heisenberg exchange with easy-axis "
        "single-ion anisotropy Delta"
    )
    assert trace["order_chain"] == (
        "moments normal to ab planes -> ferromagnetic zig-zag chains "
        "along a -> antiferromagnetically coupled chains -> Ising-like "
        "antiferromagnetic order"
    )
    assert trace["registered_convention_mapping"] == (
        "source Ising-like zig-zag order equals registry boolean; no "
        "sign, normalization, or unit conversion"
    )
    assert trace["corrected_source_identity"] == (
        "arXiv:2005.12031v1"
    )
    assert trace["superseded_registered_doi"] == (
        "10.1103/PhysRevB.85.094422"
    )
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "Evidence for biquadratic exchange in the quasi-two-dimensional",
            "High-field properties of a cerium intermetallic",
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "M. E. Zhitomirsky", "M. E. Example"
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "arXiv:2005.12031v1", "arXiv:2005.00000v1"
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "honeycomb lattice", "square lattice"
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "Ising-like anisotropy", "negligible anisotropy"
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "high-spin (S = 2) Fe2+ ions",
            "low-spin (S = 0) Fe2+ ions",
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "ferromagnetic zig-zag chains",
            "nonmagnetic zig-zag chains",
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "antiferromagnetically coupled",
            "magnetically decoupled",
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "- Delta sum_i (S_i^z)^2", "+ Dzyaloshinskii-Moriya terms"
        ),
        WILDES_FEPS3_ISING_ZIGZAG_SOURCE_TEXT.replace(
            "single-ion anisotropy dominates the spin-wave gap",
            "single-ion anisotropy is absent",
        ),
    ],
)
def test_wildes_feps3_parser_fails_closed_without_complete_order_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Wildes FePS3 Ising-like zig-zag source",
    ):
        literature_runtime_evidence.parse_wildes_feps3_ising_zigzag_order(
            source_text
        )


def test_dey_ba3irti2o9_parser_extracts_triangular_qsl_candidate_only():
    parsed, trace = (
        literature_runtime_evidence
        .parse_dey_ba3irti2o9_triangular_spin_liquid_candidate(
            DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT
        )
    )

    assert parsed == {"spin_liquid_candidate": True}
    assert trace["parser"] == (
        "parse_dey_ba3irti2o9_triangular_spin_liquid_candidate"
    )
    assert trace["source_geometry"] == (
        "hexagonal Ba3IrTi2O9 with layered, site-diluted triangular "
        "Ir4+ planes and Jeff=1/2 moments"
    )
    assert trace["registry_claim_mapping"] == (
        "source directly supports only the spin-liquid-candidate "
        "boolean for a triangular material; no honeycomb or Kitaev "
        "Hamiltonian is inferred"
    )
    assert trace["registered_model_correction"] == (
        "replace honeycomb Kitaev labeling with triangular Jeff=1/2 "
        "spin-liquid candidate"
    )
    assert trace["corrected_source_identity"] == (
        "DOI:10.1103/PhysRevB.86.140405"
    )
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "triangular lattice compound Ba3IrTi2O9",
            "honeycomb Kitaev compound Ba3IrTi2O9",
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "Tusharkanti Dey", "Example Author"
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "10.1103/PhysRevB.86.140405",
            "10.1103/PhysRevB.86.000000",
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "layered\ntriangular arrangement of Ir4+",
            "layered\nhoneycomb arrangement of Ir4+",
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "Ir4+ (J_eff = 1/2)", "Ir4+ (J_eff = 3/2)"
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "no magnetic ordering down to 0.35 K",
            "magnetic ordering below 10 K",
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "theta_CW approximately -130 K",
            "theta_CW approximately -13 K",
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "quantum spin liquid on a two-dimensional triangular\nlattice",
            "Kitaev magnet on a two-dimensional honeycomb\nlattice",
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "edge-shared triangular lattice", "edge-shared honeycomb lattice"
        ),
        DEY_BA3IRTI2O9_TRIANGULAR_QSL_SOURCE_TEXT.replace(
            "potentially new spin liquid system",
            "conventional ordered magnet",
        ),
    ],
)
def test_dey_ba3irti2o9_parser_fails_closed_without_triangular_qsl_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Dey Ba3IrTi2O9 triangular spin-liquid source",
    ):
        (
            literature_runtime_evidence
            .parse_dey_ba3irti2o9_triangular_spin_liquid_candidate(
                source_text
            )
        )


def test_ghosh_mila_ruby_parser_extracts_localized_magnon_eigenstate_only():
    parsed, trace = (
        literature_runtime_evidence
        .parse_ghosh_mila_ruby_localized_magnon_eigenstate(
            GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT
        )
    )

    assert parsed == {"supports_localized_magnons": True}
    assert trace["parser"] == (
        "parse_ghosh_mila_ruby_localized_magnon_eigenstate"
    )
    assert trace["source_model"] == (
        "spin-1/2 ruby-lattice Heisenberg antiferromagnet with "
        "Jh, Jt, and Jd bonds at Jh=Jt=Jd"
    )
    assert trace["registry_claim_mapping"] == (
        "source supports existence of exact localized one-magnon "
        "eigenstates only; it explicitly rejects a localized-magnon "
        "interpretation of the iPEPS plateau states"
    )
    assert trace["registered_model_correction"] == (
        "replace flat-band plateau wording with localized-magnon "
        "eigenstate existence at the isotropic ruby-lattice point"
    )
    assert trace["corrected_source_identity"] == "arXiv:2512.14173v1"
    assert trace["superseded_registered_doi"] == (
        "10.1103/PhysRevLett.93.107206"
    )
    assert len(trace["text_spans"]) == 5


def test_ghosh_mila_ruby_parser_accepts_pdftotext_layout_interleaving():
    source_text = GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT
    replacements = [
        (
            "denotes a bond of type",
            "denotes a bond right-column words of type",
        ),
        (
            "strictly localized within a region R",
            "strictly localized within right-column words a region R",
        ),
        (
            "Consider a magnon wavefunction",
            "Consider a magnon wave- right-column words function",
        ),
        (
            "processes localizes the magnon",
            "processes localizes right-column words the magnon",
        ),
        (
            "condition is satisfied when the magnon",
            "condition is satisfied when the right-column words magnon",
        ),
        (
            "with an alternating sign structure",
            "with an alternating right-column words sign structure",
        ),
        (
            "construct an exact product state",
            "construct an exact product right-column words state",
        ),
        (
            "every hexagonal plaquette",
            "every hexago- right-column words nal plaquette",
        ),
        (
            "does not appear to correspond to a localized-magnon state",
            "does not appear to correspond to a localized- "
            "right-column words magnon state",
        ),
        (
            "where localized-magnon\neigenstates can occur",
            "where right-column words localized-magnon eigenstates "
            "can occur",
        ),
        (
            "interpreted as strongly localized magnon states",
            "interpreted as right-column words strongly localized "
            "magnon states",
        ),
    ]
    for before, after in replacements:
        assert before in source_text
        source_text = source_text.replace(before, after, 1)

    parsed, _trace = (
        literature_runtime_evidence
        .parse_ghosh_mila_ruby_localized_magnon_eigenstate(source_text)
    )

    assert parsed == {"supports_localized_magnons": True}


@pytest.mark.parametrize(
    "source_text",
    [
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "Heisenberg Model on the Ruby Lattice",
            "Heisenberg Model on the Checkerboard Lattice",
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "Pratyay Ghosh", "Example Author"
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "arXiv:2512.14173v1", "arXiv:2512.00000v1"
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "S_i are S = 1/2 operators", "S_i are S = 1 operators"
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "k in {h, t, d}", "k in {h, t}"
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "J_h = J_t = J_d", "J_h = 2 J_t = J_d", 1
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "strictly localized within a region R",
            "weakly confined near a region R",
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "|Phi> proportional to sum_(i in R) c_i S_i^- |FP>. (4)",
            "|Phi> is an unspecified trial state. (4)",
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "sum_(i in R) J_ij c_i = 0, for all j in R-bar. (5)",
            "sum_(i in R) J_ij c_i is nonzero. (5)",
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "confined to a J_h hexagon with an alternating sign "
            "structure of c_i",
            "spread over the lattice with uniform coefficients",
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "construct an exact product state of single-magnon\nstates",
            "construct an approximate variational state",
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "does not appear to correspond to a localized-magnon state",
            "is exactly the localized-magnon ground state",
        ),
        GHOSH_MILA_RUBY_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "None of the observed plateau states can be\n"
            "interpreted as strongly localized magnon states",
            "All observed plateau states are localized magnons",
        ),
    ],
)
def test_ghosh_mila_ruby_parser_fails_closed_without_full_scope_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Ghosh-Mila ruby localized-magnon source",
    ):
        (
            literature_runtime_evidence
            .parse_ghosh_mila_ruby_localized_magnon_eigenstate(
                source_text
            )
        )


def test_biffin_gamma_li2iro3_parser_extracts_spiral_kitaev_order():
    parsed, trace = (
        literature_runtime_evidence
        .parse_biffin_gamma_li2iro3_spiral_kitaev_order(
            BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT
        )
    )

    assert parsed == {"incommensurate_spiral_order": True}
    assert trace["parser"] == (
        "parse_biffin_gamma_li2iro3_spiral_kitaev_order"
    )
    assert trace["source_model"] == (
        "gamma-Li2IrO3 three-dimensional stripyhoneycomb Kitaev lattice "
        "with a minimal Kitaev-Heisenberg anisotropic-exchange model"
    )
    assert trace["registry_claim_mapping"] == (
        "the observed incommensurate noncoplanar counterrotating "
        "magnetic structure directly supplies the registered "
        "incommensurate-spiral-order boolean"
    )
    assert trace["corrected_source_identity"] == (
        "DOI:10.1103/PhysRevLett.113.197201"
    )
    assert trace["superseded_registered_source_for_order_claim"] == (
        "DOI:10.1038/ncomms5203"
    )
    assert len(trace["text_spans"]) == 5


def test_biffin_gamma_li2iro3_parser_tolerates_dual_column_interleaving():
    source_text = BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT
    source_text = source_text.replace(
        "At low temperatures new magnetic Bragg peaks",
        "At low temper-\n"
        "harmonic honeycombs form structural polytypes in the adjacent "
        "column, with several crystallographic details reported there\n"
        "atures new magnetic Bragg peaks",
    )
    source_text = source_text.replace(
        "satellite positions",
        "satellite\n"
        "spin-liquid states and recently synthesized structural polytypes "
        "are discussed in the adjacent column\n"
        "positions",
    )
    source_text = source_text.replace(
        "with an incommensurate propagation vector",
        "with an incommensu-\n"
        "the stripyhoneycomb network contains edge-sharing octahedra and "
        "three-coordinate iridium sites in the adjacent column\n"
        "rate propagation vector",
    )
    source_text = source_text.replace(
        "indicating coherent three-dimensional magnetic ordering",
        "indicating coherent,\n"
        "edge-sharing octahedra are connected throughout the crystal and "
        "the structural discussion continues in the adjacent column\n"
        "3D magnetic ordering",
    )
    source_text = source_text.replace(
        "with a\npropagation vector q along a",
        "with a propaga-\n"
        "FIG. 4 presents calculated Fourier amplitudes and the measured "
        "magnetic intensities in the adjacent column\n"
        "tion vector q along a",
    )
    source_text = source_text.replace(
        "construct the following\nKitaev-Heisenberg Hamiltonian",
        "construct the following\n"
        "FIG. 4: comparison of the experimental and calculated magnetic "
        "structure factors for the same crystal\n"
        "Kitaev-Heisenberg Hamiltonian",
    )
    source_text = source_text.replace(
        "We take K_c = -15, K_d = -12, J_c = 5, J_d = 2.5,\n"
        "I_cc = -4.5, and J_2 = -0.9 meV.",
        "We take the magnetic scattering scans shown in the adjacent "
        "column into account.\n"
        "The following values for the parameters (in units of meV) are "
        "used: K_c = -15, K_d = -12, J_c = 5, J_d = 2.5,\n"
        "I_cc = -4.5, and J_2 = the moment direction was refined from "
        "azimuthal scans\n"
        "-0.9.",
    )
    source_text = source_text.replace(
        "using the Luttinger-Tisza\napproximation",
        "using\n"
        "the same sample was aligned for polarization-resolved scans in "
        "the adjacent column\n"
        "the Luttinger-Tisza approximation",
    )
    source_text = source_text.replace(
        "mode identical to the coplanar\nprojection",
        "mode identical to the calculated intensities shown in the "
        "adjacent column\n"
        "coplanar projection",
    )
    source_text = source_text.replace(
        "and mode mixing exactly reproduces\nthe observed noncoplanar "
        "structure",
        "and requires mixing with another mode. The mixed\n"
        "polarization analysis and azimuthal scans are discussed in the "
        "adjacent column\n"
        "mode exactly reproduces the observed noncoplanar struc-\n"
        "the refined moment components are tabulated in the adjacent "
        "column\n"
        "ture",
    )
    source_text = source_text.replace(
        "through MRXD measurements on gamma-Li2IrO3 single crystals,\n"
        "we have observed an incommensurate, noncoplanar magnetic "
        "structure with\n"
        "counterrotating moments. A Kitaev-Heisenberg Hamiltonian can "
        "fully explain\n"
        "the observed complex magnetic structure, providing strong "
        "evidence that\n"
        "gamma-Li2IrO3 is an experimental realization of 3D Kitaev "
        "physics",
        "through MRXD measurements on\n"
        "the references and acknowledgments occupy the adjacent column\n"
        "gamma-Li2IrO3 single crystals, we have observed an incommen-\n"
        "the reference list continues in the adjacent column\n"
        "surate, noncoplanar magnetic structure with counterrotating\n"
        "several cited works are listed in the adjacent column\n"
        "moments. A Kitaev-Heisenberg Hamiltonian can fully\n"
        "the acknowledgments continue in the adjacent column\n"
        "explain the observed complex magnetic structure, provid-\n"
        "additional references occupy the adjacent column\n"
        "ing strong evidence that gamma-Li2IrO3 is an experimental\n"
        "the final references continue in the adjacent column\n"
        "realization of 3D Kitaev physics",
    )

    parsed, trace = (
        literature_runtime_evidence
        .parse_biffin_gamma_li2iro3_spiral_kitaev_order(source_text)
    )

    assert parsed == {"incommensurate_spiral_order": True}
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "Kitaev Interactions in gamma-Li2IrO3",
            "Kitaev Interactions in beta-Li2IrO3",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "A. Biffin", "Example Author"
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "10.1103/PhysRevLett.113.197201",
            "10.1103/PhysRevLett.113.000000",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "three-dimensional Kitaev lattice\nof interconnected Ir "
            "honeycombs",
            "two-dimensional triangular lattice",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "magnetic resonant x-ray diffraction",
            "bulk thermodynamic fitting",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "q = (0.57(1), 0, 0)", "q = (0, 0, 0)"
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "incommensurate magnetic structure\nwith noncoplanar and "
            "counterrotating Ir moments",
            "commensurate collinear magnetic structure",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "Kitaev-Heisenberg Hamiltonian as a minimal model",
            "isotropic Heisenberg Hamiltonian as a minimal model",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "K_c = -15, K_d = -12, J_c = 5, J_d = 2.5",
            "K_c = 0, K_d = 0, J_c = 5, J_d = 2.5",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "using the Luttinger-Tisza\napproximation",
            "using an unspecified approximation",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "mode mixing exactly reproduces\nthe observed noncoplanar "
            "structure",
            "mode mixing fails to reproduce the observed structure",
        ),
        BIFFIN_GAMMA_LI2IRO3_SPIRAL_SOURCE_TEXT.replace(
            "experimental realization of 3D Kitaev physics",
            "conventional isotropic magnet",
        ),
    ],
)
def test_biffin_gamma_li2iro3_parser_fails_closed_without_full_order_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Biffin gamma-Li2IrO3 spiral/Kitaev source",
    ):
        (
            literature_runtime_evidence
            .parse_biffin_gamma_li2iro3_spiral_kitaev_order(source_text)
        )


def test_taylor_ising_parser_derives_beta_one_correlation_length():
    parsed, trace = literature_runtime_evidence.parse_taylor_ising_correlation_length(
        TAYLOR_ISING_SOURCE_TEXT
    )

    assert parsed == {
        "correlation_length_beta_1_j_1": pytest.approx(
            -1.0 / literature_runtime_evidence.math.log(
                literature_runtime_evidence.math.tanh(1.0)
            )
        )
    }
    assert trace["parser"] == "parse_taylor_ising_correlation_length"
    assert trace["equation"] == "5"
    assert "exp(-l/xi)" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        TAYLOR_ISING_SOURCE_TEXT.replace("(5)", "(6)"),
        TAYLOR_ISING_SOURCE_TEXT.replace("<s_i s_i+l>", "observable"),
        TAYLOR_ISING_SOURCE_TEXT.replace("tanh^l", "tanh"),
        TAYLOR_ISING_SOURCE_TEXT.replace("J beta", "J gamma"),
    ],
)
def test_taylor_ising_parser_fails_closed_without_complete_equation(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Taylor Ising Eq. \\(5\\)"):
        literature_runtime_evidence.parse_taylor_ising_correlation_length(source_text)


def test_pfeuty_parser_derives_registry_normalized_tfim_critical_point():
    parsed, trace = literature_runtime_evidence.parse_pfeuty_tfim_critical_point(
        PFEUTY_TFIM_SOURCE_TEXT
    )

    assert parsed == {"critical_field_over_exchange": 1.0}
    assert trace["parser"] == "parse_pfeuty_tfim_critical_point"
    assert trace["equations"] == ["2.10", "2.12"]
    assert "sigma=2S" in trace["normalization"]


def test_pfeuty_parser_derives_registry_normalized_tfim_gap():
    parsed, trace = literature_runtime_evidence.parse_pfeuty_tfim_gap(
        PFEUTY_TFIM_SOURCE_TEXT
    )

    assert parsed == {
        "gap_formula": "2J|1-g|",
        "gap_formula_at_g_0_6": pytest.approx(0.8),
    }
    assert trace["parser"] == "parse_pfeuty_tfim_gap"
    assert trace["equations"] == ["2.10", "2.12"]
    assert "Gamma*Lambda_k" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        PFEUTY_TFIM_SOURCE_TEXT.replace(
            "set of Pauli operators", "set of classical variables"
        ),
        PFEUTY_TFIM_SOURCE_TEXT.replace("h = J / (2 Gamma)", "h = J / Gamma"),
        PFEUTY_TFIM_SOURCE_TEXT.replace(
            "Lambda_k^2 = 1 + h^2 + 2 h cos(k)",
            "Lambda_k^2 = 1 + h^2",
        ),
        PFEUTY_TFIM_SOURCE_TEXT.replace(
            "For h = 1, Lambda_pi = 0. (2.12)",
            "For h = 2, Lambda_pi = 0. (2.12)",
        ),
        PFEUTY_TFIM_SOURCE_TEXT.replace(
            "the gap in the excitation spectrum disappears",
            "the excitation spectrum changes",
        ),
    ],
)
def test_pfeuty_tfim_parsers_fail_closed_without_complete_spectrum_derivation(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Pfeuty TFIM spectrum"):
        literature_runtime_evidence.parse_pfeuty_tfim_critical_point(source_text)
    with pytest.raises(RuntimeEvidenceError, match="Pfeuty TFIM spectrum"):
        literature_runtime_evidence.parse_pfeuty_tfim_gap(source_text)


def test_dziarmaga_parser_extracts_tfim_critical_point_and_gap():
    critical, critical_trace = (
        literature_runtime_evidence.parse_dziarmaga_tfim_critical_point(
            DZIARMAGA_TFIM_SOURCE_TEXT
        )
    )
    gap, gap_trace = literature_runtime_evidence.parse_dziarmaga_tfim_gap(
        DZIARMAGA_TFIM_SOURCE_TEXT
    )

    assert critical == {"critical_field_over_exchange": 1.0}
    assert gap == {
        "gap_formula": "2J|1-g|",
        "gap_formula_at_g_0_6": pytest.approx(0.8),
    }
    assert critical_trace["parser"] == (
        "parse_dziarmaga_tfim_critical_point"
    )
    assert gap_trace["parser"] == "parse_dziarmaga_tfim_gap"
    assert critical_trace["source_profile"] == "arxiv:cond-mat/0509490v3"
    assert critical_trace["equations"] == ["1", "6-7", "14-16"]
    assert "k=0" in gap_trace["derivation"]
    assert all(
        start < end for start, end in critical_trace["text_spans"]
    )


@pytest.mark.parametrize(
    "source_text",
    [
        DZIARMAGA_TFIM_SOURCE_TEXT.replace(
            "arXiv:cond-mat/0509490v3", "arXiv:cond-mat/0500000v3"
        ),
        DZIARMAGA_TFIM_SOURCE_TEXT.replace(
            "critical value g = 1", "critical value g = 2"
        ),
        DZIARMAGA_TFIM_SOURCE_TEXT.replace(
            "After Jordan-Wigner transformation",
            "After a classical approximation",
        ),
        DZIARMAGA_TFIM_SOURCE_TEXT.replace(
            "epsilon_k = 2J sqrt([g - cos(ka)]^2 + sin^2(ka))",
            "epsilon_k = J sqrt([g - cos(ka)]^2)",
        ),
    ],
)
def test_dziarmaga_tfim_parsers_fail_closed_without_exact_source_chain(
    source_text,
):
    for parser in (
        literature_runtime_evidence.parse_dziarmaga_tfim_critical_point,
        literature_runtime_evidence.parse_dziarmaga_tfim_gap,
    ):
        with pytest.raises(
            RuntimeEvidenceError,
            match="Dziarmaga TFIM source",
        ):
            parser(source_text)


def test_lieb_schultz_mattis_parser_derives_xx_chain_energy():
    parsed, trace = (
        literature_runtime_evidence.parse_lieb_schultz_mattis_xx_chain_energy(
            LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT
        )
    )

    assert parsed == {"energy_per_site": pytest.approx(-1.0 / math.pi)}
    assert trace["parser"] == "parse_lieb_schultz_mattis_xx_chain_energy"
    assert trace["equations"] == ["2.1", "2.20", "2.21", "2.22a"]
    assert "gamma=0" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT.replace(
            "Two Soluble Models of an Antiferromagnetic Chain",
            "An Unrelated Spin Model",
        ),
        LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT.replace(
            "usual Pauli", "classical"
        ),
        LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT.replace("(2.20)", "(2.19)"),
        LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT.replace("(2.21)", "(2.23)"),
        LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT.replace(
            "isotropic case, gamma = 0", "anisotropic case, gamma = 1"
        ),
        LIEB_SCHULTZ_MATTIS_XX_SOURCE_TEXT.replace("-1/pi", "-2/pi"),
    ],
)
def test_lieb_schultz_mattis_xx_parser_fails_closed_without_exact_limit(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Lieb-Schultz-Mattis XX"):
        literature_runtime_evidence.parse_lieb_schultz_mattis_xx_chain_energy(
            source_text
        )


def test_collura_parser_extracts_exact_xx_chain_energy():
    parsed, trace = literature_runtime_evidence.parse_collura_xx_chain_energy(
        COLLURA_CALABRESE_ESSLER_XX_SOURCE_TEXT
    )

    assert parsed == {"energy_per_site": pytest.approx(-1.0 / math.pi)}
    assert trace["parser"] == "parse_collura_xx_chain_energy"
    assert trace["source_profile"] == "doi:10.1103/PhysRevB.92.125131"
    assert trace["equation"] == "1"
    assert trace["normalization"] == (
        "source and registry both use "
        "J sum_j(Sx_j Sx_j+1 + Sy_j Sy_j+1) at Delta=0"
    )
    assert all(start < end for start, end in trace["text_spans"])


@pytest.mark.parametrize(
    "source_text",
    [
        COLLURA_CALABRESE_ESSLER_XX_SOURCE_TEXT.replace(
            "10.1103/PhysRevB.92.125131",
            "10.1103/PhysRevB.92.000000",
        ),
        COLLURA_CALABRESE_ESSLER_XX_SOURCE_TEXT.replace(
            "Here S_j^alpha are spin operators",
            "Here S_j^alpha are classical vectors",
        ),
        COLLURA_CALABRESE_ESSLER_XX_SOURCE_TEXT.replace(
            "ground state of the XX model (Delta_0 = 0)",
            "ground state of the Ising model (Delta_0 = 1)",
        ),
        COLLURA_CALABRESE_ESSLER_XX_SOURCE_TEXT.replace(
            "E_XX = -1/pi", "E_XX = -2/pi"
        ),
    ],
)
def test_collura_xx_parser_fails_closed_without_exact_source_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Collura-Calabrese-Essler XX source",
    ):
        literature_runtime_evidence.parse_collura_xx_chain_energy(source_text)


def test_pinettes_diep_parser_extracts_simple_cubic_classical_boundary():
    parsed, trace = (
        literature_runtime_evidence.parse_pinettes_diep_simple_cubic_boundary(
            PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT
        )
    )

    assert parsed == {
        "neel_to_collinear_boundary_j2_over_j1": 0.25
    }
    assert trace["parser"] == "parse_pinettes_diep_simple_cubic_boundary"
    assert trace["equation"] == "1"
    assert trace["normalization"] == "J2/J1 with antiferromagnetic J1,J2>0"
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT.replace(
            "simple\ncubic lattice", "square lattice"
        ),
        PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT.replace(
            "nearest-neighbor and next-nearest-neighbor",
            "first-neighbor and third-neighbor",
        ),
        PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT.replace(
            "All interactions are antiferromagnetic",
            "The interactions have unspecified signs",
        ),
        PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT.replace(
            "0 < J2 < 0.25 J1", "0 < J2 < 0.20 J1"
        ),
        PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT.replace(
            "For 0.25 J1 < J2", "For 0.30 J1 < J2"
        ),
        PINETTES_DIEP_SIMPLE_CUBIC_SOURCE_TEXT.replace(
            "J2/J1 = 0.25", "J2/J1 = 0.30"
        ),
    ],
)
def test_pinettes_diep_parser_fails_closed_without_complete_boundary_claim(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Pinettes-Diep"):
        literature_runtime_evidence.parse_pinettes_diep_simple_cubic_boundary(
            source_text
        )


def test_shastry_sutherland_parser_derives_exact_spin_half_dimer_energy():
    parsed, trace = (
        literature_runtime_evidence.parse_shastry_sutherland_exact_dimer_product(
            SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT
        )
    )

    assert parsed == {
        "energy_per_dimer": -0.75,
        "energy_per_spin": -0.375,
    }
    assert trace["parser"] == "parse_shastry_sutherland_exact_dimer_product"
    assert trace["equations"] == ["1", "3", "4"]
    assert "S(S+1)" in trace["derivation"]
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT.replace(
            "EXACT GROUND STATE OF A QUANTUM MECHANICAL ANTIFERROMAGNET",
            "AN APPROXIMATE STATE OF A CLASSICAL FERROMAGNET",
        ),
        SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT.replace(
            "each dashed line represents a\nbond with strength 2 alpha",
            "the bond strengths are not specified",
        ),
        SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT.replace(
            "|psi> = product_<lm> [l,m] (3)",
            "|psi> is a trial wave function",
        ),
        SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT.replace(
            "for a singlet combination", "for an arbitrary combination"
        ),
        SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT.replace(
            "S_i dot (S_l + S_m) [l,m] = 0",
            "S_i dot (S_l + S_m) [l,m] is nonzero",
        ),
        SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT.replace(
            "saturates a lower bound", "provides a variational estimate"
        ),
    ],
)
def test_shastry_sutherland_parser_fails_closed_without_rigorous_dimer_proof(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Shastry-Sutherland"):
        literature_runtime_evidence.parse_shastry_sutherland_exact_dimer_product(
            source_text
        )


def test_fouet_parser_extracts_checkerboard_crossed_plaquette_constraint():
    parsed, trace = (
        literature_runtime_evidence.parse_fouet_checkerboard_classical_constraint(
            FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT
        )
    )

    assert parsed == {"zero_total_spin_per_crossed_plaquette": True}
    assert trace["parser"] == "parse_fouet_checkerboard_classical_constraint"
    assert trace["equation"] == "1.1"
    assert "fully connected crossed square" in trace["normalization"]
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT.replace(
            "The planar pyrochlore: a Valence Bond Crystal.",
            "An unrelated triangular-lattice ferromagnet.",
        ),
        FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT.replace(
            "checkerboard\nlattice", "triangular lattice"
        ),
        FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT.replace(
            "corner-sharing four-spin squares",
            "edge-sharing three-spin triangles",
        ),
        FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT.replace(
            "first-neighbor classical Heisenberg model",
            "quantum Ising model",
        ),
        FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT.replace(
            "(J/2) sum_(alpha units) S_alpha^2",
            "(J/2) sum_(alpha units) S_alpha",
        ),
        FOUET_CHECKERBOARD_CONSTRAINT_SOURCE_TEXT.replace(
            "S_alpha = 0 for all alpha",
            "S_alpha is unrestricted",
        ),
    ],
)
def test_fouet_parser_fails_closed_without_crossed_plaquette_identity(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Fouet checkerboard"):
        literature_runtime_evidence.parse_fouet_checkerboard_classical_constraint(
            source_text
        )


def test_syozi_parser_derives_kagome_ising_ferromagnet_tc():
    parsed, trace = (
        literature_runtime_evidence.parse_syozi_kagome_ising_ferromagnet_tc(
            SYOZI_KAGOME_ISING_SOURCE_TEXT
        )
    )

    assert parsed == {
        "tc_over_j": pytest.approx(
            4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0))
        )
    }
    assert trace["parser"] == "parse_syozi_kagome_ising_ferromagnet_tc"
    assert trace["critical_condition"] == "exp(4 K_c)=3+2 sqrt(3)"
    assert "K=J/(k_B T)" in trace["normalization"]
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        SYOZI_KAGOME_ISING_SOURCE_TEXT.replace(
            "Statistics of Kagome Lattice", "Statistics of Square Lattice"
        ),
        SYOZI_KAGOME_ISING_SOURCE_TEXT.replace(
            "problem of Ising model", "problem of Heisenberg model"
        ),
        SYOZI_KAGOME_ISING_SOURCE_TEXT.replace(
            "nearest neighbors of a lattice point is four",
            "nearest neighbors of a lattice point is six",
        ),
        SYOZI_KAGOME_ISING_SOURCE_TEXT.replace(
            "star-triangle transformation", "mean-field approximation"
        ),
        SYOZI_KAGOME_ISING_SOURCE_TEXT.replace(
            "ferromagnetic case", "unspecified coupling case"
        ),
        SYOZI_KAGOME_ISING_SOURCE_TEXT.replace(
            "exp(4 K) = 3 + 2 sqrt(3)", "exp(4 K) = 3 + 2 sqrt(2)"
        ),
    ],
)
def test_syozi_parser_fails_closed_without_complete_kagome_critical_condition(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Syozi kagome Ising"):
        literature_runtime_evidence.parse_syozi_kagome_ising_ferromagnet_tc(
            source_text
        )


def test_kano_naya_parser_derives_kagome_ising_ferromagnet_tc():
    parsed, trace = (
        literature_runtime_evidence.parse_kano_naya_kagome_ising_ferromagnet_tc(
            KANO_NAYA_KAGOME_ISING_SOURCE_TEXT
        )
    )

    assert parsed == {
        "tc_over_j": pytest.approx(
            4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0))
        )
    }
    assert trace["parser"] == (
        "parse_kano_naya_kagome_ising_ferromagnet_tc"
    )
    assert trace["equation"] == "32"
    assert trace["critical_condition"] == "exp(4 L_c)=3+2 sqrt(3)"
    assert "L=J/(k_B T)" in trace["normalization"]
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "Antiferromagnetism. The Kagome Ising Net",
            "Antiferromagnetism. The Square Ising Net",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "Kenzi KANO and Shigeo NAYA",
            "Kenzi KANO",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "solve exactly the eigenvalue problem of the kagome Ising net",
            "approximately solve the kagome Heisenberg net",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "e^(4 L_c) = 3 + 2 sqrt(3)",
            "e^(4 L_c) = 3 + 2 sqrt(2)",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "L = J/(k T)", "L is an unspecified parameter"
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "J > 0 in the ferromagnetic case",
            "the ferromagnetic sign is unspecified",
        ),
    ],
)
def test_kano_naya_ferromagnet_parser_fails_closed_without_convention_and_equation(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Kano-Naya kagome Ising"):
        literature_runtime_evidence.parse_kano_naya_kagome_ising_ferromagnet_tc(
            source_text
        )


def test_kano_naya_parser_extracts_macroscopic_antiferromagnetic_degeneracy():
    parsed, trace = (
        literature_runtime_evidence.parse_kano_naya_kagome_ising_antiferromagnet_entropy(
            KANO_NAYA_KAGOME_ISING_SOURCE_TEXT
        )
    )

    assert parsed == {"macroscopic_ground_state_degeneracy": True}
    assert trace["parser"] == (
        "parse_kano_naya_kagome_ising_antiferromagnet_entropy"
    )
    assert trace["equation"] == "47"
    assert trace["printed_residual_entropy_per_spin"] == 0.50183
    assert "exp(N s_0 / k_B)" in trace["derivation"]
    assert len(trace["text_spans"]) == 5


def test_kano_naya_parsers_accept_verified_original_scan_ocr_forms():
    ferromagnet, ferromagnet_trace = (
        literature_runtime_evidence.parse_kano_naya_kagome_ising_ferromagnet_tc(
            KANO_NAYA_KAGOME_ISING_OCR_SOURCE_TEXT
        )
    )
    antiferromagnet, antiferromagnet_trace = (
        literature_runtime_evidence.parse_kano_naya_kagome_ising_antiferromagnet_entropy(
            KANO_NAYA_KAGOME_ISING_OCR_SOURCE_TEXT
        )
    )

    assert ferromagnet == {
        "tc_over_j": pytest.approx(
            4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0))
        )
    }
    assert antiferromagnet == {
        "macroscopic_ground_state_degeneracy": True
    }
    assert ferromagnet_trace["equation"] == "32"
    assert antiferromagnet_trace["equation"] == "47"


@pytest.mark.parametrize(
    "source_text",
    [
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "Antiferromagnetism. The Kagome Ising Net",
            "Antiferromagnetism. The Square Ising Net",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "is disordered at all temperatures",
            "orders at a finite temperature",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "possesses a finite zero point entropy",
            "has zero entropy at the zero point",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "There are free spins of N/3",
            "There are no independently free spins",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "21 - 4(cos(omega_1) + cos(omega_2)",
            "20 - 4(cos(omega_1) + cos(omega_2)",
        ),
        KANO_NAYA_KAGOME_ISING_SOURCE_TEXT.replace(
            "(47)\n= 0.50183", "(47)\n= 0.00000"
        ),
    ],
)
def test_kano_naya_antiferromagnet_parser_fails_closed_without_entropy_proof(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Kano-Naya kagome Ising"):
        literature_runtime_evidence.parse_kano_naya_kagome_ising_antiferromagnet_entropy(
            source_text
        )


def test_ising_1925_parser_extracts_no_finite_temperature_transition():
    parsed, trace = (
        literature_runtime_evidence.parse_ising_1925_linear_chain_no_transition(
            ISING_1925_LINEAR_CHAIN_SOURCE_TEXT
        )
    )

    assert parsed == {
        "finite_temperature_transition": False,
        "tc_over_j": 0.0,
    }
    assert trace["parser"] == "parse_ising_1925_linear_chain_no_transition"
    assert trace["equation"] == "8"
    assert "zero-field spontaneous magnetization" in trace["derivation"]
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        ISING_1925_LINEAR_CHAIN_SOURCE_TEXT.replace(
            "Contribution to the Theory of Ferromagnetism",
            "Contribution to the Theory of Paramagnetism",
        ),
        ISING_1925_LINEAR_CHAIN_SOURCE_TEXT.replace(
            "The simple linear chain", "The simple square lattice"
        ),
        ISING_1925_LINEAR_CHAIN_SOURCE_TEXT.replace(
            "only two positions", "continuously many positions"
        ),
        ISING_1925_LINEAR_CHAIN_SOURCE_TEXT.replace(
            "neighboring elements", "arbitrarily distant elements"
        ),
        ISING_1925_LINEAR_CHAIN_SOURCE_TEXT.replace(
            "T is the absolute temperature", "T is an auxiliary variable"
        ),
        ISING_1925_LINEAR_CHAIN_SOURCE_TEXT.replace(
            "no spontaneous magnetization", "spontaneous magnetization"
        ),
        ISING_1925_LINEAR_CHAIN_SOURCE_TEXT.replace(
            "only have a simple maximum", "have two separated maxima"
        ),
    ],
)
def test_ising_1925_parser_fails_closed_without_complete_linear_chain_result(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Ising 1925 linear chain"):
        literature_runtime_evidence.parse_ising_1925_linear_chain_no_transition(
            source_text
        )


def test_husimi_syozi_parser_derives_honeycomb_ising_ferromagnet_tc():
    parsed, trace = (
        literature_runtime_evidence.parse_husimi_syozi_honeycomb_ising_tc(
            HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT
        )
    )

    assert parsed == {
        "tc_over_j": pytest.approx(
            2.0 / math.log(2.0 + math.sqrt(3.0))
        )
    }
    assert trace["parser"] == "parse_husimi_syozi_honeycomb_ising_tc"
    assert trace["critical_condition"] == "cosh(2 H_c)=2"
    assert "H=J/(k_B T)" in trace["normalization"]
    assert len(trace["text_spans"]) == 6


def test_husimi_syozi_parser_derives_triangular_ising_ferromagnet_tc():
    parsed, trace = (
        literature_runtime_evidence.parse_husimi_syozi_triangular_ising_tc(
            HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT
        )
    )

    assert parsed == {
        "tc_over_j": pytest.approx(4.0 / math.log(3.0))
    }
    assert trace["parser"] == "parse_husimi_syozi_triangular_ising_tc"
    assert trace["critical_condition"] == "exp(4 H_c)=3"
    assert "H=J/(k_B T)" in trace["normalization"]
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "The Statistics of Honeycomb and Triangular Lattice. I",
            "The Statistics of the Square Lattice",
        ),
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "10.1143/ptp/5.2.177", "10.1143/ptp/5.2.999"
        ),
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "the exact solution has been obtained",
            "an approximate solution has been proposed",
        ),
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "dual\ntransformation", "mean-field\napproximation"
        ),
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "ch 2H = 2", "ch 2H = 3"
        ),
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "exp(4H) = 3", "exp(4H) = 4"
        ),
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "dual and star-triangle transformations",
            "two uncontrolled approximations",
        ),
        HUSIMI_SYOZI_HEXAGONAL_ISING_SOURCE_TEXT.replace(
            "triangular net exhibits no phase change",
            "triangular net develops the same transition",
        ),
    ],
)
def test_husimi_syozi_parsers_fail_closed_without_complete_exact_claim(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Husimi-Syozi Ising"):
        literature_runtime_evidence.parse_husimi_syozi_honeycomb_ising_tc(
            source_text
        )
    with pytest.raises(RuntimeEvidenceError, match="Husimi-Syozi Ising"):
        literature_runtime_evidence.parse_husimi_syozi_triangular_ising_tc(
            source_text
        )


def test_caspers_parser_derives_majumdar_ghosh_exact_dimer_operand():
    parsed, trace = (
        literature_runtime_evidence.parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states(
            CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT
        )
    )

    assert parsed == {
        "energy_per_site": -0.375,
        "degenerate_dimer_coverings": 2,
    }
    assert trace["parser"] == (
        "parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states"
    )
    assert trace["equation"] == "1"
    assert "J1=1" in trace["normalization"]
    assert "one singlet per two sites" in trace["derivation"]
    assert len(trace["text_spans"]) == 8


def test_caspers_parser_accepts_publisher_and_repository_ocr_format():
    parsed, trace = (
        literature_runtime_evidence.parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states(
            CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_OCR_SOURCE_TEXT
        )
    )

    assert parsed == {
        "energy_per_site": -0.375,
        "degenerate_dimer_coverings": 2,
    }
    assert trace["equation"] == "1"
    assert len(trace["text_spans"]) == 8


def test_caspers_parser_accepts_real_repository_scan_text_layer():
    parsed, trace = (
        literature_runtime_evidence.parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states(
            CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SCAN_TEXT
        )
    )

    assert parsed == {
        "energy_per_site": -0.375,
        "degenerate_dimer_coverings": 2,
    }
    assert trace["equation"] == "1"
    assert trace["equation_extraction"] == (
        "scan_text_equivalent_j2_over_j1_one_half"
    )
    assert len(trace["text_spans"]) == 8


@pytest.mark.parametrize(
    "source_text",
    [
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "The Majumdar-Ghosh chain. Twofold ground state",
            "A generic Heisenberg chain. Unique ground state",
        ),
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "W J Caspers, K M Emmett and W Magnus",
            "W J Caspers and K M Emmett",
        ),
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "H = 4 sum_{j=1}^{2N}", "H = 3 sum_{j=1}^{2N}"
        ),
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "S_i = 1/2", "S_i = 1"
        ),
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "10.1088/0305-4470/17/13/020",
            "10.1088/0305-4470/17/13/999",
        ),
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "nearest-neighbour singlet pairs",
            "nearest-neighbour triplet pairs",
        ),
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "translation over one elementary distance",
            "translation over two elementary distances",
        ),
        CASPERS_EMMETT_MAGNUS_MAJUMDAR_GHOSH_SOURCE_TEXT.replace(
            "two SPS are the only ground states for\n"
            "the system with periodic boundary conditions",
            "two SPS are trial states for\n"
            "the system with open boundary conditions",
        ),
    ],
)
def test_caspers_parser_fails_closed_without_complete_exact_dimer_proof(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Caspers-Emmett-Magnus"):
        literature_runtime_evidence.parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states(
            source_text
        )


def test_lapilli_parser_extracts_q5_clock_two_transition_phase_sequence():
    parsed, trace = (
        literature_runtime_evidence.parse_lapilli_square_clock_three_phase_regime(
            LAPILLI_SQUARE_CLOCK_SOURCE_TEXT
        )
    )

    assert parsed == {
        "transition_count": 2,
        "phase_sequence": ["ordered", "critical", "disordered"],
    }
    assert trace["parser"] == (
        "parse_lapilli_square_clock_three_phase_regime"
    )
    assert trace["equation"] == "1"
    assert trace["registered_q"] == 5
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        LAPILLI_SQUARE_CLOCK_SOURCE_TEXT.replace(
            "Universality Away from Critical Points",
            "Mean-Field Behavior Away from Critical Points",
        ),
        LAPILLI_SQUARE_CLOCK_SOURCE_TEXT.replace(
            "10.1103/PhysRevLett.96.140603",
            "10.1103/PhysRevLett.96.999999",
        ),
        LAPILLI_SQUARE_CLOCK_SOURCE_TEXT.replace(
            "p-state clock model in two dimensions",
            "continuous rotor model in three dimensions",
        ),
        LAPILLI_SQUARE_CLOCK_SOURCE_TEXT.replace(
            "cos(theta_i - theta_j)", "theta_i theta_j"
        ),
        LAPILLI_SQUARE_CLOCK_SOURCE_TEXT.replace(
            "T1 < T < T2 for p > 4", "T1 = T2 for p <= 4"
        ),
        LAPILLI_SQUARE_CLOCK_SOURCE_TEXT.replace(
            "The plotted data include p = 5",
            "Only the p = 8 data are shown",
        ),
        LAPILLI_SQUARE_CLOCK_SOURCE_TEXT.replace(
            "T < T1 (long-range ordered phase), decays as a power law for\n"
            "T1 < T < T2 (quasi-long-range ordered quasiliquid phase), and "
            "decays\nexponentially for T > T2 (disordered phase)",
            "all temperatures show one disordered phase",
        ),
    ],
)
def test_lapilli_parser_fails_closed_without_q5_three_phase_evidence(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Lapilli clock"):
        literature_runtime_evidence.parse_lapilli_square_clock_three_phase_regime(
            source_text
        )


def test_tasaki_lsm_parser_extracts_unique_ground_state_gaplessness_claim():
    parsed, trace = literature_runtime_evidence.parse_tasaki_lsm_half_integer_constraint(
        TASAKI_LSM_SOURCE_TEXT
    )

    assert parsed == {"unique_ground_state_implies_gapless_excitations": True}
    assert trace["parser"] == "parse_tasaki_lsm_half_integer_constraint"
    assert len(trace["text_spans"]) == 1


@pytest.mark.parametrize(
    "source_text",
    [
        TASAKI_LSM_SOURCE_TEXT.replace("one-dimensional", "two-dimensional"),
        TASAKI_LSM_SOURCE_TEXT.replace("half-odd-integer", "integer"),
        TASAKI_LSM_SOURCE_TEXT.replace("gapless excitations", "excitations"),
        TASAKI_LSM_SOURCE_TEXT.replace("infinite volume limit", "finite system"),
        TASAKI_LSM_SOURCE_TEXT.replace("ground state is unique", "ground state exists"),
    ],
)
def test_tasaki_lsm_parser_fails_closed_without_complete_theorem(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Tasaki LSM claim"):
        literature_runtime_evidence.parse_tasaki_lsm_half_integer_constraint(source_text)


def test_onsager_parser_derives_isotropic_square_ising_tc():
    parsed, trace = literature_runtime_evidence.parse_onsager_square_ising_tc(
        ONSAGER_SQUARE_ISING_SOURCE_TEXT
    )

    assert parsed == {
        "tc_over_j": pytest.approx(
            2.0
            / literature_runtime_evidence.math.log(
                1.0 + literature_runtime_evidence.math.sqrt(2.0)
            )
        )
    }
    assert trace["parser"] == "parse_onsager_square_ising_tc"
    assert "J'=J" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace(
            "order-disorder transition", "smooth crossover"
        ),
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace("sinh(2 J/kTc)", "cosh(2 J/kTc)"),
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace("sinh(2 J'/kTc)", "cosh(2 J'/kTc)"),
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace("= 1", "= 2"),
    ],
)
def test_onsager_parser_fails_closed_without_transition_condition(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Onsager critical condition"):
        literature_runtime_evidence.parse_onsager_square_ising_tc(source_text)


def test_dagotto_rice_parser_extracts_exact_decoupled_rung_operands():
    parsed, trace = literature_runtime_evidence.parse_dagotto_rice_strong_rung_limit(
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT
    )

    assert parsed == {"energy_per_rung": -0.75, "gap_to_triplet": 1.0}
    assert trace["parser"] == "parse_dagotto_rice_strong_rung_limit"
    assert "Jleg=0" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace("J' >> J", "J' = J"),
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace("-3/4 J'", "-1/2 J'"),
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace("each rung singlet", "each rung"),
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace(
            "energy J' above", "energy 2J' above"
        ),
    ],
)
def test_dagotto_rice_parser_fails_closed_without_exact_rung_limit(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Dagotto-Rice strong-rung limit"):
        literature_runtime_evidence.parse_dagotto_rice_strong_rung_limit(source_text)


def test_kitaev_exact_solution_parser_extracts_isotropic_gapless_phase():
    parsed, trace = literature_runtime_evidence.parse_kitaev_exact_spin_liquid(
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT
    )

    assert parsed == {
        "is_exactly_solvable": True,
        "isotropic_phase": "gapless_spin_liquid",
    }
    assert trace["parser"] == "parse_kitaev_exact_spin_liquid"


@pytest.mark.parametrize(
    "source_text",
    [
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("exact solution", "approximation"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("free real fermions", "bosons"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("phase B", "phase C"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("fermions are gapless", "fermions are gapped"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("Jx = Jy = Jz", "Jx differs from Jy"),
    ],
)
def test_kitaev_exact_solution_parser_fails_closed_without_full_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Kitaev exact-solution claim"):
        literature_runtime_evidence.parse_kitaev_exact_spin_liquid(source_text)


def test_kitaev_triangle_parser_extracts_gapless_condition():
    parsed, trace = literature_runtime_evidence.parse_kitaev_gapless_triangle_condition(
        KITAEV_TRIANGLE_SOURCE_TEXT
    )

    assert parsed == {
        "gapless_condition": "triangle_inequalities",
        "isotropic_kitaev_point_gapless": True,
    }
    assert trace["parser"] == "parse_kitaev_gapless_triangle_condition"
    assert trace["equation"] == "33"


@pytest.mark.parametrize(
    "source_text",
    [
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("if and only if", "sometimes"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("|Jx| <= |Jy| + |Jz|", "first condition"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("|Jy| <= |Jx| + |Jz|", "second condition"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("|Jz| <= |Jx| + |Jy|", "third condition"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("(33)", "(34)"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("this phase is gapless", "this phase is gapped"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("Jx = Jy = Jz", "Jx differs from Jy"),
    ],
)
def test_kitaev_triangle_parser_fails_closed_without_complete_condition(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Kitaev gapless condition"):
        literature_runtime_evidence.parse_kitaev_gapless_triangle_condition(source_text)


def test_kitaev_field_gap_parser_extracts_complete_nonabelian_chain():
    parsed, trace = literature_runtime_evidence.parse_kitaev_field_nonabelian_gap(
        KITAEV_FIELD_GAP_SOURCE_TEXT
    )

    assert parsed == {"field_opens_non_abelian_gap": True}
    assert trace["parser"] == "parse_kitaev_field_nonabelian_gap"
    assert trace["equations"] == ["45", "48", "50", "51", "55"]


@pytest.mark.parametrize(
    "source_text",
    [
        KITAEV_FIELD_GAP_SOURCE_TEXT.replace(
            "external magnetic\nfield", "generic perturbation"
        ),
        KITAEV_FIELD_GAP_SOURCE_TEXT.replace(
            "third-order effective\nHamiltonian", "first-order effective Hamiltonian"
        ),
        KITAEV_FIELD_GAP_SOURCE_TEXT.replace(
            "kappa proportional to hx hy hz / J^2", "kappa is unspecified"
        ),
        KITAEV_FIELD_GAP_SOURCE_TEXT.replace(
            "which determines the energy gap", "which shifts the energy"
        ),
        KITAEV_FIELD_GAP_SOURCE_TEXT.replace(
            "nu = sgn Delta = plus or minus 1", "nu is unspecified"
        ),
        KITAEV_FIELD_GAP_SOURCE_TEXT.replace(
            "non-Abelian anyons for any odd value of nu",
            "Abelian anyons for any odd value of nu",
        ),
    ],
)
def test_kitaev_field_gap_parser_fails_closed_without_complete_chain(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Kitaev magnetic-field gap"):
        literature_runtime_evidence.parse_kitaev_field_nonabelian_gap(source_text)


def test_kitaev_field_gap_adapter_recomputes_mass_gap_and_nonabelian_parity():
    positive = literature_runtime_evidence.recompute_kitaev_field_nonabelian_gap(
        h_x=0.1,
        h_y=0.2,
        h_z=0.3,
        exchange=1.0,
    )
    negative = literature_runtime_evidence.recompute_kitaev_field_nonabelian_gap(
        h_x=-0.1,
        h_y=0.2,
        h_z=0.3,
        exchange=1.0,
    )
    zero = literature_runtime_evidence.recompute_kitaev_field_nonabelian_gap(
        h_x=0.0,
        h_y=0.2,
        h_z=0.3,
        exchange=1.0,
    )

    expected_mass = 6.0 * math.sqrt(3.0) * 0.1 * 0.2 * 0.3
    assert positive == {
        "field_opens_non_abelian_gap": True,
        "mass": pytest.approx(expected_mass),
        "minimum_positive_energy": pytest.approx(expected_mass),
        "chern_number": 1,
    }
    assert negative["field_opens_non_abelian_gap"] is True
    assert negative["mass"] == pytest.approx(-expected_mass)
    assert negative["minimum_positive_energy"] == pytest.approx(expected_mass)
    assert negative["chern_number"] == -1
    assert zero == {
        "field_opens_non_abelian_gap": False,
        "mass": 0.0,
        "minimum_positive_energy": 0.0,
        "chern_number": 0,
    }
    with pytest.raises(ValueError, match="nonzero finite exchange"):
        literature_runtime_evidence.recompute_kitaev_field_nonabelian_gap(
            h_x=0.1,
            h_y=0.2,
            h_z=0.3,
            exchange=0.0,
        )


def test_toric_code_parser_derives_genus_one_degeneracy():
    parsed, trace = literature_runtime_evidence.parse_kitaev_toric_code_degeneracy(
        KITAEV_TORIC_CODE_SOURCE_TEXT
    )

    assert parsed == {"torus_ground_state_degeneracy": 4}
    assert trace["parser"] == "parse_kitaev_toric_code_degeneracy"
    assert "g=1" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        KITAEV_TORIC_CODE_SOURCE_TEXT.replace("torus", "plane"),
        KITAEV_TORIC_CODE_SOURCE_TEXT.replace("ground state", "excited state"),
        KITAEV_TORIC_CODE_SOURCE_TEXT.replace("4^g-fold", "2^g-fold"),
        KITAEV_TORIC_CODE_SOURCE_TEXT.replace("genus", "area"),
    ],
)
def test_toric_code_parser_fails_closed_without_genus_degeneracy(source_text):
    with pytest.raises(RuntimeEvidenceError, match="toric-code degeneracy claim"):
        literature_runtime_evidence.parse_kitaev_toric_code_degeneracy(source_text)


def test_toric_code_degeneracy_adapter_computes_genus_one_and_rejects_invalid_genus():
    assert literature_spin_model_benchmarks.toric_code_ground_state_degeneracy(
        genus=1
    ) == 4
    assert literature_spin_model_benchmarks.toric_code_ground_state_degeneracy(
        genus=2
    ) == 16
    with pytest.raises(ValueError, match="nonnegative integer"):
        literature_spin_model_benchmarks.toric_code_ground_state_degeneracy(genus=-1)
    with pytest.raises(ValueError, match="nonnegative integer"):
        literature_spin_model_benchmarks.toric_code_ground_state_degeneracy(genus=1.5)


def test_white_huse_parser_extracts_haldane_gap_and_reported_uncertainty():
    parsed, trace = literature_runtime_evidence.parse_white_huse_haldane_gap(
        WHITE_HUSE_HALDANE_SOURCE_TEXT
    )

    assert parsed == {"gap_over_j": 0.41050}
    assert trace["parser"] == "parse_white_huse_haldane_gap"
    assert trace["reported_uncertainty"] == 0.00002


@pytest.mark.parametrize(
    "source_text",
    [
        WHITE_HUSE_HALDANE_SOURCE_TEXT.replace("first excited state", "ground state"),
        WHITE_HUSE_HALDANE_SOURCE_TEXT.replace("one magnon", "two magnons"),
        WHITE_HUSE_HALDANE_SOURCE_TEXT.replace("Haldane gap", "correlation length"),
        WHITE_HUSE_HALDANE_SOURCE_TEXT.replace("0.41050(2)", "0.40000(2)"),
    ],
)
def test_white_huse_parser_fails_closed_without_specific_gap_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="White-Huse Haldane gap"):
        literature_runtime_evidence.parse_white_huse_haldane_gap(source_text)


def test_sandvik_parser_extracts_square_heisenberg_qmc_energy():
    parsed, trace = literature_runtime_evidence.parse_sandvik_square_qmc_energy(
        SANDVIK_SQUARE_QMC_SOURCE_TEXT
    )

    assert parsed == {"energy_per_site": -0.669437}
    assert trace["parser"] == "parse_sandvik_square_qmc_energy"
    assert trace["reported_uncertainty"] == 0.000005


@pytest.mark.parametrize(
    "source_text",
    [
        SANDVIK_SQUARE_QMC_SOURCE_TEXT.replace("two-dimensional", "one-dimensional"),
        SANDVIK_SQUARE_QMC_SOURCE_TEXT.replace("S=1/2", "S=1"),
        SANDVIK_SQUARE_QMC_SOURCE_TEXT.replace("quantum Monte Carlo", "mean field"),
        SANDVIK_SQUARE_QMC_SOURCE_TEXT.replace("-0.669437(5)", "-0.600000(5)"),
    ],
)
def test_sandvik_parser_fails_closed_without_specific_energy_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Sandvik square-QMC energy"):
        literature_runtime_evidence.parse_sandvik_square_qmc_energy(source_text)


def test_jiang_wiese_parser_extracts_square_heisenberg_low_energy_parameters():
    parsed, trace = (
        literature_runtime_evidence.parse_jiang_wiese_square_heisenberg_low_energy_parameters(
            JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT
        )
    )

    assert parsed == {
        "staggered_magnetization": pytest.approx(0.30743),
        "rho_s_over_j": pytest.approx(0.18081),
        "renormalized_velocity_over_j_approx": pytest.approx(1.6586),
    }
    assert trace["parser"] == (
        "parse_jiang_wiese_square_heisenberg_low_energy_parameters"
    )
    assert trace["reported_uncertainties"] == {
        "staggered_magnetization": pytest.approx(0.00001),
        "rho_s_over_j": pytest.approx(0.00011),
        "renormalized_velocity_over_j_approx": pytest.approx(0.0003),
    }
    assert trace["magnetization_normalization"] == (
        "M_s a^2 in spin-operator units per lattice site; not divided by "
        "the spin-1/2 saturation magnetization"
    )
    assert trace["stiffness_normalization"] == "rho_s/J"
    assert trace["velocity_normalization"] == "c/(J a)"
    assert trace["source_identity"] == (
        "doi:10.1103/PhysRevB.83.155120"
    )
    assert trace["superseded_registered_source_identity"] == (
        "doi:10.1103/PhysRevB.56.11678"
    )
    assert trace["superseded_source_reported_parameters"] == {
        "staggered_magnetization": pytest.approx(0.3070),
        "rho_s_over_j": pytest.approx(0.175),
        "renormalized_velocity_over_j_approx": pytest.approx(1.673),
    }
    assert trace["registered_source_correction"] == (
        "The three registry entries cite Sandvik 1997, DOI "
        "10.1103/PhysRevB.56.11678, which reports M=0.3070(3), "
        "rho_s=0.175(2) J, and c=1.673(7) J a. Their registered values "
        "instead match Jiang-Wiese 2011: M_s=0.30743(1)/a^2, "
        "rho_s=0.18081(11) J, and c=1.6586(3) J a."
    )
    assert trace["claim_scope"] == (
        "joint low-energy parameters of the periodic square-lattice "
        "spin-1/2 nearest-neighbor antiferromagnetic Heisenberg model; "
        "the source correction applies to the three registry records "
        "for staggered magnetization, spin stiffness, and spin-wave "
        "velocity"
    )
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    ("parser_name", "field", "expected", "uncertainty"),
    [
        (
            "parse_jiang_wiese_square_heisenberg_spin_stiffness",
            "rho_s_over_j",
            0.18081,
            0.00011,
        ),
        (
            "parse_jiang_wiese_square_heisenberg_staggered_magnetization",
            "staggered_magnetization",
            0.30743,
            0.00001,
        ),
        (
            "parse_jiang_wiese_square_heisenberg_spin_wave_velocity",
            "renormalized_velocity_over_j_approx",
            1.6586,
            0.0003,
        ),
    ],
)
def test_jiang_wiese_single_field_parsers_return_exact_record_shape(
    parser_name, field, expected, uncertainty
):
    parser = getattr(literature_runtime_evidence, parser_name)

    parsed, trace = parser(JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT)

    assert parsed == {field: pytest.approx(expected)}
    assert trace["parser"] == parser_name
    assert trace["source_parser"] == (
        "parse_jiang_wiese_square_heisenberg_low_energy_parameters"
    )
    assert trace["selected_source_field"] == field
    assert trace["reported_uncertainty"] == pytest.approx(uncertainty)
    assert trace["source_joint_parameters"] == {
        "staggered_magnetization": pytest.approx(0.30743),
        "rho_s_over_j": pytest.approx(0.18081),
        "renormalized_velocity_over_j_approx": pytest.approx(1.6586),
    }
    assert len(trace["matched_anchors"]) == 5
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "parser_name",
    [
        "parse_jiang_wiese_square_heisenberg_spin_stiffness",
        "parse_jiang_wiese_square_heisenberg_staggered_magnetization",
        "parse_jiang_wiese_square_heisenberg_spin_wave_velocity",
    ],
)
def test_jiang_wiese_single_field_parsers_inherit_fail_closed_chain(
    parser_name,
):
    parser = getattr(literature_runtime_evidence, parser_name)
    source_text = JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
        "DOI: 10.1103/PhysRevB.83.155120",
        "DOI: 10.1103/PhysRevB.83.000000",
    )

    with pytest.raises(
        RuntimeEvidenceError, match="Jiang-Wiese square-Heisenberg"
    ):
        parser(source_text)


@pytest.mark.parametrize(
    "parser_name",
    [
        "parse_jiang_wiese_square_heisenberg_spin_stiffness",
        "parse_jiang_wiese_square_heisenberg_staggered_magnetization",
        "parse_jiang_wiese_square_heisenberg_spin_wave_velocity",
    ],
)
def test_jiang_wiese_single_field_parsers_reject_non_text(parser_name):
    parser = getattr(literature_runtime_evidence, parser_name)

    with pytest.raises(
        RuntimeEvidenceError, match="Jiang-Wiese square-Heisenberg"
    ):
        parser(None)


@pytest.mark.parametrize(
    "source_text",
    [
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
            "High-precision determination of low-energy effective parameters",
            "Approximate survey of unrelated parameters",
        ),
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
            "F.-J. Jiang and U.-J. Wiese", "F.-J. Jiang"
        ),
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
            "periodic square lattice", "periodic triangular lattice"
        ),
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
            "antiferromagnetic exchange coupling",
            "ferromagnetic exchange coupling",
        ),
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
            "c = 1.6586(3) J a", "c = 1.7000(3) J a"
        ),
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
            "M_s = 0.307 43(1)/a^2", "M_s = 0.300 00(1)/a^2"
        ),
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT.replace(
            "rho_s = 0.180 81(11) J", "rho_s = 0.170 00(11) J"
        ),
    ],
)
def test_jiang_wiese_parser_fails_closed_without_model_and_all_three_values(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Jiang-Wiese square-Heisenberg"
    ):
        literature_runtime_evidence.parse_jiang_wiese_square_heisenberg_low_energy_parameters(
            source_text
        )


def test_blote_luijten_heringa_parser_derives_simple_cubic_ising_tc():
    parsed, trace = (
        literature_runtime_evidence.parse_blote_luijten_heringa_simple_cubic_ising_tc(
            BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT
        )
    )

    assert parsed == {"tc_over_j": pytest.approx(1.0 / 0.2216546)}
    assert trace["parser"] == (
        "parse_blote_luijten_heringa_simple_cubic_ising_tc"
    )
    assert trace["critical_coupling"] == pytest.approx(0.2216546)
    assert trace["reported_critical_coupling_uncertainty"] == pytest.approx(
        0.0000005
    )
    assert trace["abstract_critical_coupling_uncertainty"] == pytest.approx(
        0.0000010
    )
    assert trace["propagated_tc_over_j_uncertainty"] == pytest.approx(
        0.0000005 / 0.2216546**2
    )
    assert trace["conversion"] == "T_c/J = 1/K_c"
    assert trace["registered_hamiltonian_convention"] == (
        "H = -J sum_<nn> sigma_i sigma_j with sigma_i in {-1,+1}; "
        "K_nn = J/(k_B T)"
    )
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "Ising Universality in Three Dimensions",
            "XY Universality in Two Dimensions",
        ),
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "Erik Luijten", "Erik Example"
        ),
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "cond-mat/9509016", "cond-mat/0000000"
        ),
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "simple cubic lattice", "body-centered cubic lattice"
        ),
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "The spins s_i can assume the values +1 and -1.",
            "The spins s_i can assume the values 0 and +1.",
        ),
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "K_3n/K_nn = 0", "K_3n/K_nn = 0.4"
        ),
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "K_c = 0.2216546(10)", "K_c = 0.2216000(10)"
        ),
        BLOTE_LUIJTEN_HERINGA_SIMPLE_CUBIC_ISING_SOURCE_TEXT.replace(
            "0.2216546(5)", "0.2216000(5)"
        ),
    ],
)
def test_blote_luijten_heringa_parser_fails_closed_without_full_source_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Blote-Luijten-Heringa simple-cubic Ising",
    ):
        literature_runtime_evidence.parse_blote_luijten_heringa_simple_cubic_ising_tc(
            source_text
        )


@pytest.mark.parametrize(
    "critical_coupling",
    [True, "0.2216546", 0.0, -0.2216546, math.inf, math.nan],
)
def test_simple_cubic_ising_tc_recompute_rejects_invalid_critical_coupling(
    critical_coupling,
):
    with pytest.raises(RuntimeEvidenceError, match="critical coupling"):
        literature_runtime_evidence.recompute_simple_cubic_ising_tc_from_critical_coupling(
            critical_coupling=critical_coupling
        )


def test_simple_cubic_ising_tc_recompute_inverts_dimensionless_coupling():
    assert (
        literature_runtime_evidence.recompute_simple_cubic_ising_tc_from_critical_coupling(
            critical_coupling=0.2216546
        )
        == {"tc_over_j": pytest.approx(4.511523785204548)}
    )


def test_depenbrock_parser_extracts_kagome_heisenberg_energy_per_site():
    parsed, trace = (
        literature_runtime_evidence.parse_depenbrock_kagome_heisenberg_energy(
            DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT
        )
    )

    assert parsed == {"energy_per_site_approx": pytest.approx(-0.4386)}
    assert trace["parser"] == (
        "parse_depenbrock_kagome_heisenberg_energy"
    )
    assert trace["reported_uncertainty"] == pytest.approx(0.0005)
    assert trace["energy_normalization"] == (
        "E/N per kagome site for H=J sum_<i,j> S_i dot S_j, "
        "nearest-neighbor bonds counted once, J=1"
    )
    assert trace["limit"] == (
        "cylinder length extrapolated to infinity and circumference "
        "extrapolated to the two-dimensional thermodynamic limit"
    )
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "Nature of the Spin Liquid Ground State",
            "Finite-Temperature Magnetic Ordering",
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "Ian P. McCulloch", "Ian P. Example"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "arXiv:1205.4858v2", "arXiv:0000.0000v2"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "S = 1/2", "S = 1"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "kagome lattice", "triangular lattice"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "nearest neighbors", "next-nearest neighbors"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "up to 16,000 DMRG states", "up to 1,600 DMRG states"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "-0.4386(5)", "-0.4379(3)"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "thermodynamic-limit energy", "finite-cylinder energy"
        ),
    ],
)
def test_depenbrock_parser_fails_closed_without_model_and_limit_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Depenbrock kagome-Heisenberg energy"
    ):
        literature_runtime_evidence.parse_depenbrock_kagome_heisenberg_energy(
            source_text
        )


def test_depenbrock_parser_extracts_kagome_energy_and_triplet_gap():
    parsed, trace = (
        literature_runtime_evidence.parse_depenbrock_kagome_heisenberg_energy_and_spin_gap(
            DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT
        )
    )

    assert parsed == {
        "energy_per_site": pytest.approx(-0.4386),
        "spin_gap_over_j": pytest.approx(0.13),
    }
    assert trace["parser"] == (
        "parse_depenbrock_kagome_heisenberg_energy_and_spin_gap"
    )
    assert trace["reported_uncertainties"] == {
        "energy_per_site": pytest.approx(0.0005),
        "spin_gap_over_j": pytest.approx(0.01),
    }
    assert trace["gap_normalization"] == (
        "lowest bulk triplet (S=1) gap Delta E/J with the "
        "nearest-neighbor coefficient J=1"
    )
    assert trace["energy_normalization"] == (
        "E/N per kagome site for H=J sum_<i,j> S_i dot S_j, "
        "nearest-neighbor bonds counted once, J=1"
    )
    assert len(trace["text_spans"]) == 9


@pytest.mark.parametrize(
    "source_text",
    [
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "a spin gap of 0.13(1)", "a spin gap of 0.10(1)"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "spin (triplet) gap", "spin (singlet) gap"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "spin gap to remain finite", "spin gap to vanish"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "Delta E = 0.13(1)", "Delta E = 0.10(1)"
        ),
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT.replace(
            "thermodynamic limit.", "one finite-cylinder result."
        ),
    ],
)
def test_depenbrock_energy_and_gap_parser_fails_closed_without_gap_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Depenbrock kagome triplet gap"
    ):
        literature_runtime_evidence.parse_depenbrock_kagome_heisenberg_energy_and_spin_gap(
            source_text
        )


def test_sandvik_daul_parser_extracts_ring_driven_bond_order():
    parsed, trace = (
        literature_runtime_evidence.parse_sandvik_daul_square_xy_ring_bond_order(
            SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT
        )
    )

    assert parsed == {"ring_exchange_drives_vbs_phase": True}
    assert trace["parser"] == (
        "parse_sandvik_daul_square_xy_ring_bond_order"
    )
    assert trace["source_model"] == (
        "square-lattice spin-1/2 XY model with H=-J sum B_ij-K sum P_ijkl"
    )
    assert trace["source_phase_term"] == (
        "striped bond-plaquette order, analogous to a fourfold-degenerate "
        "columnar spin-Peierls state"
    )
    assert trace["registered_vbs_mapping"] == (
        "bond/spin-Peierls order is mapped to the registry's VBS umbrella; "
        "the source is not a Heisenberg J-Q model"
    )
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "Striped phase in a quantum XY-model",
            "Uniform phase in a quantum Heisenberg model",
        ),
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "S. Daul", "S. Example"
        ),
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "cond-mat/0205270v2", "cond-mat/0000000v2"
        ),
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "square-lattice S = 1/2 XY-model",
            "square-lattice S = 1/2 Heisenberg model",
        ),
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "H = -J sum_<ij> B_ij - K sum_<ijkl> P_ijkl",
            "H = -J sum_<ij> S_i dot S_j",
        ),
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "striped bond-plaquette order emerges",
            "uniform paramagnetic order emerges",
        ),
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "fourfold\ndegenerate columnar spin-Peierls state",
            "featureless nondegenerate paramagnetic state",
        ),
        SANDVIK_DAUL_SQUARE_XY_RING_SOURCE_TEXT.replace(
            "extrapolates\nto a non-zero value as L tends to infinity",
            "extrapolates to zero as L tends to infinity",
        ),
    ],
)
def test_sandvik_daul_parser_fails_closed_without_xy_bond_order_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Sandvik-Daul square-XY ring exchange"
    ):
        literature_runtime_evidence.parse_sandvik_daul_square_xy_ring_bond_order(
            source_text
        )


def test_chaloupka_full_kitaev_heisenberg_parser_extracts_four_ordered_phases():
    parsed, trace = (
        literature_runtime_evidence.parse_chaloupka_full_kitaev_heisenberg_ordered_phases(
            CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT
        )
    )

    assert parsed == {
        "ordered_phases": [
            "ferromagnetic",
            "neel",
            "zigzag",
            "stripy",
        ]
    }
    assert trace["parser"] == (
        "parse_chaloupka_full_kitaev_heisenberg_ordered_phases"
    )
    assert trace["source_parameter_space"] == (
        "K=A sin(phi), J=A cos(phi), phi spanning 0 to 2pi"
    )
    assert trace["source_phase_counts"] == {
        "spin_liquid_phases": 2,
        "spin_ordered_phases": 4,
    }
    assert trace["corrected_source_doi"] == (
        "10.1103/PhysRevLett.110.097204"
    )
    assert trace["superseded_registered_doi"] == (
        "10.1103/PhysRevLett.105.027204"
    )
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "On the Origin of Zigzag Magnetic Order",
            "On the Origin of Uniform Magnetic Order",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "George Jackeli", "George Example"
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "1209.5100v1", "1209.0000v1"
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "extended to its full parameter\nspace",
            "restricted to one parameter point",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "H_ij^(gamma) = 2 K S_i^gamma S_j^gamma + J S_i dot S_j",
            "H_ij = J S_i dot S_j",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "phi vary from 0 to 2 pi",
            "phi fixed at pi over 4",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "a ferromagnetic phase, and a zigzag-AF phase",
            "a ferrimagnetic phase, and a 120-degree phase",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "2 spin-liquid and 4 spin-ordered phases",
            "1 spin-liquid and 2 spin-ordered phases",
        ),
    ],
)
def test_chaloupka_full_kitaev_heisenberg_parser_fails_closed(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Chaloupka full Kitaev-Heisenberg phase diagram",
    ):
        literature_runtime_evidence.parse_chaloupka_full_kitaev_heisenberg_ordered_phases(
            source_text
        )


def test_chaloupka_na2iro3_parser_extracts_zigzag_model_relevance():
    parsed, trace = (
        literature_runtime_evidence.parse_chaloupka_na2iro3_zigzag_relevance(
            CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT
        )
    )

    assert parsed == {"zigzag_order_relevant": True}
    assert trace["parser"] == (
        "parse_chaloupka_na2iro3_zigzag_relevance"
    )
    assert trace["source_model"] == (
        "nearest-neighbor Kitaev-Heisenberg model for localized Ir moments"
    )
    assert trace["na2iro3_fit"] == {
        "j_mev": -4.01,
        "k_mev": 10.45,
        "phi_degrees": 111.0,
        "phi_uncertainty_degrees": 2.0,
    }
    assert trace["corrected_source_doi"] == (
        "10.1103/PhysRevLett.110.097204"
    )
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "Zigzag-type magnetic order is found",
            "Zigzag-type magnetic order is not found",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "zigzag order is a natural ground state",
            "zigzag order is absent from the ground state",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "lending strong support to the Kitaev-Heisenberg model",
            "ruling out the Kitaev-Heisenberg model",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "J = -4.01 meV and K = 10.45 meV",
            "J and K were not determined",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "phi = 111 +/- 2 degrees",
            "phi was unconstrained",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "clarified the origin of zigzag magnetic order in Na2IrO3",
            "left the origin of magnetic order unresolved",
        ),
        CHALOUPKA_FULL_KITAEV_HEISENBERG_SOURCE_TEXT.replace(
            "nearest-neighbor Kitaev-Heisenberg model for localized Ir moments",
            "long-range isotropic model for itinerant electrons",
        ),
    ],
)
def test_chaloupka_na2iro3_parser_fails_closed_without_material_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Chaloupka Na2IrO3 zigzag"
    ):
        literature_runtime_evidence.parse_chaloupka_na2iro3_zigzag_relevance(
            source_text
        )


def test_capriotti_triangular_energy_parser_extracts_published_estimate():
    parsed, trace = literature_runtime_evidence.parse_capriotti_triangular_energy(
        CAPRIOTTI_TRIANGULAR_ENERGY_SOURCE_TEXT
    )

    assert parsed == {"energy_per_site_approx": -0.5458}
    assert trace["parser"] == "parse_capriotti_triangular_energy"
    assert trace["reported_uncertainty"] == pytest.approx(0.0001)
    assert trace["matched_anchors"] == [
        "Heisenberg model on triangular lattice",
        "quantum Monte Carlo and exact diagonalization",
        "thermodynamic-limit ground-state energy per site",
        "e0=-0.5458 +/- 0.0001 in exchange-coupling units",
    ]


@pytest.mark.parametrize(
    "source_text",
    [
        CAPRIOTTI_TRIANGULAR_ENERGY_SOURCE_TEXT.replace(
            "triangular lattice", "square lattice"
        ),
        CAPRIOTTI_TRIANGULAR_ENERGY_SOURCE_TEXT.replace(
            "quantum\nMonte Carlo", "series\nexpansion"
        ),
        CAPRIOTTI_TRIANGULAR_ENERGY_SOURCE_TEXT.replace(
            "thermodynamic limit", "finite cluster"
        ),
        CAPRIOTTI_TRIANGULAR_ENERGY_SOURCE_TEXT.replace("-0.5458", "-0.5000"),
    ],
)
def test_capriotti_triangular_energy_parser_fails_closed_without_complete_claim(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Capriotti triangular energy"):
        literature_runtime_evidence.parse_capriotti_triangular_energy(source_text)


def test_checkerboard_plaquette_parser_extracts_both_registered_claims():
    parsed, trace = literature_runtime_evidence.parse_checkerboard_plaquette_vbc(
        CHECKERBOARD_PLAQUETTE_SOURCE_TEXT
    )

    assert parsed == {
        "plaquette_long_range_order": True,
        "valence_bond_crystal": True,
    }
    assert trace["parser"] == "parse_checkerboard_plaquette_vbc"
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        CHECKERBOARD_PLAQUETTE_SOURCE_TEXT.replace(
            "spin-1/2 Heisenberg model on the checkerboard\nlattice",
            "spin-1/2 Heisenberg chain",
        ),
        CHECKERBOARD_PLAQUETTE_SOURCE_TEXT.replace(
            "long-range order in four-spin S=0 plaquettes",
            "short-range plaquette correlations",
        ),
        CHECKERBOARD_PLAQUETTE_SOURCE_TEXT.replace(
            "is a valence bond\ncrystal", "may be a spin liquid"
        ),
    ],
)
def test_checkerboard_plaquette_parser_fails_closed_without_both_claims(source_text):
    with pytest.raises(RuntimeEvidenceError, match="checkerboard plaquette VBC"):
        literature_runtime_evidence.parse_checkerboard_plaquette_vbc(source_text)


def test_spin_peierls_parser_derives_nonzero_distortion_gap():
    parsed, trace = literature_runtime_evidence.parse_spin_peierls_distortion_gap(
        SPIN_PEIERLS_GAP_SOURCE_TEXT
    )

    assert parsed == {"finite_delta_opens_gap": True}
    assert trace["parser"] == "parse_spin_peierls_distortion_gap"
    assert trace["selector_derivation"] == (
        "a stated zero-temperature gap scaling with lattice distortion "
        "implies a finite gap for finite nonzero distortion"
    )


@pytest.mark.parametrize(
    "source_text",
    [
        SPIN_PEIERLS_GAP_SOURCE_TEXT.replace("spin-1/2", "spin-1"),
        SPIN_PEIERLS_GAP_SOURCE_TEXT.replace(
            "static lattice distortion", "uniform static lattice"
        ),
        SPIN_PEIERLS_GAP_SOURCE_TEXT.replace(
            "energy gap at zero temperature", "ground-state energy"
        ),
        SPIN_PEIERLS_GAP_SOURCE_TEXT.replace(
            "scales as the lattice distortion to the\npower 2/3",
            "is unrelated to the lattice distortion",
        ),
    ],
)
def test_spin_peierls_parser_fails_closed_without_gap_scaling_chain(source_text):
    with pytest.raises(RuntimeEvidenceError, match="spin-Peierls distortion gap"):
        literature_runtime_evidence.parse_spin_peierls_distortion_gap(source_text)


def test_bpcb_parser_extracts_field_induced_luttinger_liquid_regime():
    parsed, trace = literature_runtime_evidence.parse_bpcb_field_induced_ll(
        BPCB_FIELD_LL_SOURCE_TEXT
    )

    assert parsed == {"field_induced_luttinger_liquid_regime": True}
    assert trace["parser"] == "parse_bpcb_field_induced_ll"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        BPCB_FIELD_LL_SOURCE_TEXT.replace("(Hpip)2CuBr4", "another material"),
        BPCB_FIELD_LL_SOURCE_TEXT.replace(
            "gapped quantum-disordered phase", "gapless ordered phase"
        ),
        BPCB_FIELD_LL_SOURCE_TEXT.replace(
            "by an applied magnetic field", "without an applied field"
        ),
        BPCB_FIELD_LL_SOURCE_TEXT.replace(
            "measurements demonstrate spin Luttinger-liquid\nbehavior",
            "measurements do not establish Luttinger-liquid behavior",
        ),
    ],
)
def test_bpcb_parser_fails_closed_without_material_field_and_ll_evidence(source_text):
    with pytest.raises(RuntimeEvidenceError, match="BPCB field-induced LL"):
        literature_runtime_evidence.parse_bpcb_field_induced_ll(source_text)


def test_hasenbusch_parser_extracts_square_xy_bkt_temperature():
    parsed, trace = literature_runtime_evidence.parse_hasenbusch_xy_bkt_temperature(
        HASENBUSCH_XY_BKT_SOURCE_TEXT
    )

    assert parsed == {"tbkt_over_j": 0.89294}
    assert trace["parser"] == "parse_hasenbusch_xy_bkt_temperature"
    assert trace["inverse_beta"] == pytest.approx(1.1199)
    assert trace["equation"] == "published estimate"


@pytest.mark.parametrize(
    "source_text",
    [
        HASENBUSCH_XY_BKT_SOURCE_TEXT.replace("classical XY", "classical Ising"),
        HASENBUSCH_XY_BKT_SOURCE_TEXT.replace("square lattice", "triangular lattice"),
        HASENBUSCH_XY_BKT_SOURCE_TEXT.replace(
            "beta is the inverse temperature", "beta is a coupling"
        ),
        HASENBUSCH_XY_BKT_SOURCE_TEXT.replace("1/0.89294(8)", "1/0.90000(8)"),
    ],
)
def test_hasenbusch_parser_fails_closed_without_exact_bkt_temperature(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Hasenbusch XY BKT temperature"):
        literature_runtime_evidence.parse_hasenbusch_xy_bkt_temperature(source_text)


def test_azurite_parser_extracts_one_third_magnetization_plateau():
    parsed, trace = literature_runtime_evidence.parse_azurite_one_third_plateau(
        AZURITE_PLATEAU_SOURCE_TEXT
    )

    assert parsed == {"one_third_magnetization_plateau": True}
    assert trace["parser"] == "parse_azurite_one_third_plateau"
    assert len(trace["text_spans"]) == 4


def test_azurite_parser_accepts_verified_pdf_extraction_typography():
    source_text = """
    We present a specific heat and inelastic neutron scattering study in
    magnetic fields up into the 1=3 magnetization plateau phase of the diamond
    chain compound azurite Cu3 (CO3)2 (OH)2.
    """

    parsed, _ = literature_runtime_evidence.parse_azurite_one_third_plateau(
        source_text
    )

    assert parsed == {"one_third_magnetization_plateau": True}


@pytest.mark.parametrize(
    "source_text",
    [
        AZURITE_PLATEAU_SOURCE_TEXT.replace("azurite", "another mineral"),
        AZURITE_PLATEAU_SOURCE_TEXT.replace("diamond-chain", "square-lattice"),
        AZURITE_PLATEAU_SOURCE_TEXT.replace("1/3", "1/2"),
        AZURITE_PLATEAU_SOURCE_TEXT.replace(
            "specific-heat and inelastic-neutron-scattering study",
            "qualitative proposal",
        ),
    ],
)
def test_azurite_parser_fails_closed_without_material_plateau_evidence(source_text):
    with pytest.raises(RuntimeEvidenceError, match="azurite one-third plateau"):
        literature_runtime_evidence.parse_azurite_one_third_plateau(source_text)


def test_ba3cosb2o9_parser_extracts_one_third_magnetization_plateau():
    parsed, trace = literature_runtime_evidence.parse_ba3cosb2o9_one_third_plateau(
        BA3COSB2O9_PLATEAU_SOURCE_TEXT
    )

    assert parsed == {"one_third_magnetization_plateau": True}
    assert trace["parser"] == "parse_ba3cosb2o9_one_third_plateau"
    assert len(trace["text_spans"]) == 4


def test_ba3cosb2o9_parser_accepts_verified_pdf_extraction_typography():
    source_text = """
    We report the results of magnetization and specific heat measurements on
    Ba3 CoSb2 O9, in which the magnetic ion has a fictitious spin 1=2, and
    provide evidence that a spin-1=2 Heisenberg antiferromagnet on a regular
    triangular lattice is realized. The entire magnetization curve including
    the one-third quantum magnetization plateau agrees with theory.
    """

    parsed, _ = literature_runtime_evidence.parse_ba3cosb2o9_one_third_plateau(
        source_text
    )

    assert parsed == {"one_third_magnetization_plateau": True}


@pytest.mark.parametrize(
    "source_text",
    [
        BA3COSB2O9_PLATEAU_SOURCE_TEXT.replace("Ba3CoSb2O9", "another material"),
        BA3COSB2O9_PLATEAU_SOURCE_TEXT.replace("spin-1/2", "spin-1"),
        BA3COSB2O9_PLATEAU_SOURCE_TEXT.replace(
            "regular\ntriangular lattice", "distorted square lattice"
        ),
        BA3COSB2O9_PLATEAU_SOURCE_TEXT.replace("one-third", "one-half"),
    ],
)
def test_ba3cosb2o9_parser_fails_closed_without_material_plateau_evidence(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Ba3CoSb2O9 one-third plateau"):
        literature_runtime_evidence.parse_ba3cosb2o9_one_third_plateau(source_text)


def test_kagome_parser_extracts_one_third_magnetization_plateau():
    parsed, trace = literature_runtime_evidence.parse_kagome_one_third_plateau(
        KAGOME_ONE_THIRD_PLATEAU_SOURCE_TEXT
    )

    assert parsed == {"one_third_plateau": True}
    assert trace["parser"] == "parse_kagome_one_third_plateau"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        KAGOME_ONE_THIRD_PLATEAU_SOURCE_TEXT.replace("kagome", "triangular"),
        KAGOME_ONE_THIRD_PLATEAU_SOURCE_TEXT.replace(
            "in an applied\nmagnetic field", "at zero magnetic field"
        ),
        KAGOME_ONE_THIRD_PLATEAU_SOURCE_TEXT.replace(
            "grand canonical density matrix renormalization group analysis",
            "qualitative argument",
        ),
        KAGOME_ONE_THIRD_PLATEAU_SOURCE_TEXT.replace("1/3", "2/3"),
    ],
)
def test_kagome_parser_fails_closed_without_model_method_and_plateau(source_text):
    with pytest.raises(RuntimeEvidenceError, match="kagome one-third plateau"):
        literature_runtime_evidence.parse_kagome_one_third_plateau(source_text)


def test_chubukov_golosov_parser_extracts_triangular_one_third_plateau():
    parsed, trace = (
        literature_runtime_evidence.parse_chubukov_golosov_triangular_plateau(
            CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT
        )
    )

    assert parsed == {"one_third_plateau": True}
    assert trace["parser"] == (
        "parse_chubukov_golosov_triangular_plateau"
    )
    assert trace["source_role"] == "registered primary source"
    assert trace["method"] == "spin-wave 1/S expansion"
    assert trace["field_regime"] == "finite interval h_1<h<h_2"
    assert trace["magnetization_fraction_of_saturation"] == pytest.approx(
        1.0 / 3.0
    )
    assert trace["registry_backend_mismatch"] == (
        "registered ed_or_dmrg; source uses spin-wave 1/S expansion"
    )
    assert len(trace["matched_anchors"]) == 9
    assert len(trace["text_spans"]) == 9


def test_chubukov_golosov_parser_accepts_verified_scan_layout_text():
    parsed, trace = (
        literature_runtime_evidence.parse_chubukov_golosov_triangular_plateau(
            CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SCAN_TEXT
        )
    )

    assert parsed == {"one_third_plateau": True}
    assert trace["scan_layout_forms_accepted"] is True


@pytest.mark.parametrize(
    "source_text",
    [
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "Quantum theory of an antiferromagnet on a triangular lattice in a magnetic field",
            "Classical theory of a ferromagnet on a square lattice",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "A V Chubukov and D I Golosov",
            "A V Chubukov",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "S = 1/2 two-dimensional",
            "S = 1 two-dimensional",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "We start with an isotropic Heisenberg antiferromagnetic on a triangular lattice:",
            "We start with an anisotropic ferromagnet on a square lattice:",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "a traditional spin wave approach, based on the 1/S expansion",
            "an uncontrolled mean-field estimate",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "In the intermediate region, h_1 < h < h_2, the collinear configuration is\n"
            "stable. The absence of broken continuous symmetry then implies that all the\n"
            "excitations have a finite gap.",
            "The collinear configuration is unstable except at a single field.",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "The magnetization remains constant inside the collinear phase. Classically,\n"
            "the magnetization equals one third of the saturation value at h = 1. We\n"
            "calculated the first quantum correction to the magnetization and ascertained\n"
            "that it equals zero, so the magnetization retains its classical value also in\n"
            "the quantum case.",
            "The magnetization varies continuously and its quantum correction is nonzero.",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "The plateau on the magnetization curve\n"
            "results from the stabilization of the collinear phase in the finite region of\n"
            "magnetic fields due to zero-point motion.",
            "The magnetization curve has no plateau.",
        ),
        CHUBUKOV_GOLOSOV_TRIANGULAR_PLATEAU_SOURCE_TEXT.replace(
            "intermediate collinear phase with the constant longitudinal magnetization equal\n"
            "to one third of the saturation value. For quasi-2D Heisenberg and XY\n"
            "antiferromagnets this mode of reorientation is singled out by quantum\n"
            "fluctuations.",
            "intermediate phase with unspecified magnetization and origin.",
        ),
    ],
)
def test_chubukov_golosov_parser_fails_closed_without_complete_plateau_claim(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Chubukov-Golosov triangular plateau",
    ):
        literature_runtime_evidence.parse_chubukov_golosov_triangular_plateau(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1991])
def test_chubukov_golosov_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Chubukov-Golosov triangular plateau",
    ):
        literature_runtime_evidence.parse_chubukov_golosov_triangular_plateau(
            source_text
        )


@pytest.mark.parametrize(
    ("parser_name", "expected"),
    [
        (
            "parse_kageyama_shastry_sutherland_plateaus",
            {"fractional_plateaus_observed": True},
        ),
        (
            "parse_kageyama_shastry_sutherland_material",
            {"orthogonal_dimer_material": True, "magnetization_plateaus": True},
        ),
    ],
)
def test_kageyama_parsers_extract_material_and_fractional_plateau_claims(
    parser_name, expected
):
    parser = getattr(literature_runtime_evidence, parser_name)

    parsed, trace = parser(KAGEYAMA_SHASTRY_SUTHERLAND_SOURCE_TEXT)

    assert parsed == expected
    assert trace["parser"] == parser_name
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        KAGEYAMA_SHASTRY_SUTHERLAND_SOURCE_TEXT.replace(
            "SrCu2(BO3)2", "another material"
        ),
        KAGEYAMA_SHASTRY_SUTHERLAND_SOURCE_TEXT.replace(
            "two-dimensional orthogonal network of Cu\ndimers",
            "one-dimensional chain of Cu ions",
        ),
        KAGEYAMA_SHASTRY_SUTHERLAND_SOURCE_TEXT.replace(
            "high-field magnetization have been measured", "model was proposed"
        ),
        KAGEYAMA_SHASTRY_SUTHERLAND_SOURCE_TEXT.replace(
            "1/4 and\n1/8", "1/2 and\n1"
        ),
    ],
)
@pytest.mark.parametrize(
    "parser_name",
    [
        "parse_kageyama_shastry_sutherland_plateaus",
        "parse_kageyama_shastry_sutherland_material",
    ],
)
def test_kageyama_parsers_fail_closed_without_material_network_and_plateaus(
    parser_name, source_text
):
    parser = getattr(literature_runtime_evidence, parser_name)
    with pytest.raises(RuntimeEvidenceError, match="Kageyama Shastry-Sutherland"):
        parser(source_text)


def test_cacu2o3_parser_extracts_buckled_spin_ladder_material_identity():
    parsed, trace = literature_runtime_evidence.parse_cacu2o3_spin_ladder_material(
        CACU2O3_SPIN_LADDER_SOURCE_TEXT
    )

    assert parsed == {"spin_ladder_material": True}
    assert trace["parser"] == "parse_cacu2o3_spin_ladder_material"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        CACU2O3_SPIN_LADDER_SOURCE_TEXT.replace("CaCu2O3", "another material"),
        CACU2O3_SPIN_LADDER_SOURCE_TEXT.replace("two-leg spin-ladder", "spin chain"),
        CACU2O3_SPIN_LADDER_SOURCE_TEXT.replace("ladder rungs", "chain bonds"),
        CACU2O3_SPIN_LADDER_SOURCE_TEXT.replace(
            "ladderlike structures", "isolated chains"
        ),
    ],
)
def test_cacu2o3_parser_fails_closed_without_complete_ladder_structure(source_text):
    with pytest.raises(RuntimeEvidenceError, match="CaCu2O3 spin ladder"):
        literature_runtime_evidence.parse_cacu2o3_spin_ladder_material(source_text)


def test_ba2cugeo7_parser_extracts_dm_induced_incommensurate_spiral():
    parsed, trace = literature_runtime_evidence.parse_ba2cugeo7_dm_spiral(
        BA2CUGEO7_DM_SPIRAL_SOURCE_TEXT
    )

    assert parsed == {"dm_induced_incommensurate_spiral": True}
    assert trace["parser"] == "parse_ba2cugeo7_dm_spiral"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        BA2CUGEO7_DM_SPIRAL_SOURCE_TEXT.replace("Ba2CuGe2O7", "another material"),
        BA2CUGEO7_DM_SPIRAL_SOURCE_TEXT.replace(
            "Dzyaloshinskii-Moriya spiral antiferromagnet", "collinear ferromagnet"
        ),
        BA2CUGEO7_DM_SPIRAL_SOURCE_TEXT.replace(
            "Bulk magnetic measurements and neutron-diffraction experiments",
            "A qualitative proposal",
        ),
        BA2CUGEO7_DM_SPIRAL_SOURCE_TEXT.replace(
            "is a\nresult of Dzyaloshinskii-Moriya interactions",
            "is unrelated to antisymmetric exchange",
        ),
    ],
)
def test_ba2cugeo7_parser_fails_closed_without_experiment_spiral_and_dm_cause(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Ba2CuGe2O7 DM spiral"):
        literature_runtime_evidence.parse_ba2cugeo7_dm_spiral(source_text)


@pytest.mark.parametrize(
    ("parser_name", "source_text", "expected"),
    [
        (
            "parse_ho2ti2o7_spin_ice_correlations",
            HO2TI2O7_SPIN_ICE_SOURCE_TEXT,
            {"spin_ice_correlations": True},
        ),
        (
            "parse_jarosite_q0_120_order",
            JAROSITE_Q0_ORDER_SOURCE_TEXT,
            {"q_0_120_order": True},
        ),
        (
            "parse_maple_leaf_magnetic_order",
            MAPLE_LEAF_ORDER_SOURCE_TEXT,
            {"magnetic_long_range_order": True},
        ),
    ],
)
def test_material_order_parsers_extract_complete_published_claims(
    parser_name, source_text, expected
):
    parser = getattr(literature_runtime_evidence, parser_name)
    parsed, trace = parser(source_text)

    assert parsed == expected
    assert trace["parser"] == parser_name
    assert len(trace["text_spans"]) >= 4


@pytest.mark.parametrize(
    ("parser_name", "source_text", "error_match"),
    [
        (
            "parse_ho2ti2o7_spin_ice_correlations",
            HO2TI2O7_SPIN_ICE_SOURCE_TEXT.replace("Ho2Ti2O7", "Dy2Ti2O7"),
            "Ho2Ti2O7 spin-ice correlations",
        ),
        (
            "parse_ho2ti2o7_spin_ice_correlations",
            HO2TI2O7_SPIN_ICE_SOURCE_TEXT.replace(
                "establish\nunambiguously", "tentatively suggest"
            ),
            "Ho2Ti2O7 spin-ice correlations",
        ),
        (
            "parse_jarosite_q0_120_order",
            JAROSITE_Q0_ORDER_SOURCE_TEXT.replace("120 degrees", "90 degrees"),
            "jarosite q=0 order",
        ),
        (
            "parse_jarosite_q0_120_order",
            JAROSITE_Q0_ORDER_SOURCE_TEXT.replace(
                "same as the\nchemical unit cell", "larger than the chemical unit cell"
            ),
            "jarosite q=0 order",
        ),
        (
            "parse_maple_leaf_magnetic_order",
            MAPLE_LEAF_ORDER_SOURCE_TEXT.replace("spin-half", "spin-one"),
            "maple-leaf magnetic order",
        ),
        (
            "parse_maple_leaf_magnetic_order",
            MAPLE_LEAF_ORDER_SOURCE_TEXT.replace(
                "is magnetically ordered", "is magnetically disordered"
            ),
            "maple-leaf magnetic order",
        ),
    ],
)
def test_material_order_parsers_fail_closed_without_complete_claim(
    parser_name, source_text, error_match
):
    parser = getattr(literature_runtime_evidence, parser_name)
    with pytest.raises(RuntimeEvidenceError, match=error_match):
        parser(source_text)


@pytest.mark.parametrize(
    ("parser_name", "source_text", "expected"),
    [
        (
            "parse_alpha_rucl3_zigzag_kitaev_gamma",
            ALPHA_RUCL3_SOURCE_TEXT,
            {"zigzag_order": True, "kitaev_gamma_model_reference": True},
        ),
        (
            "parse_beta_li2iro3_spiral_order",
            BETA_LI2IRO3_SOURCE_TEXT,
            {"incommensurate_spiral_order": True},
        ),
        (
            "parse_cs2cucl4_spiral_order",
            CS2CUCL4_SPIRAL_SOURCE_TEXT,
            {"incommensurate_spiral_order": True},
        ),
        (
            "parse_square_dimerized_neel_transition",
            SQUARE_DIMERIZED_TRANSITION_SOURCE_TEXT,
            {"neel_to_dimer_transition": True},
        ),
        (
            "parse_square_jq_neel_vbs_transition",
            SQUARE_JQ_TRANSITION_SOURCE_TEXT,
            {"neel_to_vbs_transition": True},
        ),
    ],
)
def test_direct_order_transition_parsers_extract_registered_claims(
    parser_name, source_text, expected
):
    parser = getattr(literature_runtime_evidence, parser_name)
    parsed, trace = parser(source_text)
    assert parsed == expected
    assert trace["parser"] == parser_name
    assert len(trace["text_spans"]) >= 3


@pytest.mark.parametrize(
    ("parser_name", "source_text", "error_match"),
    [
        (
            "parse_alpha_rucl3_zigzag_kitaev_gamma",
            ALPHA_RUCL3_SOURCE_TEXT.replace("zigzag order", "ferromagnetic order"),
            "alpha-RuCl3 zigzag/Kitaev-Gamma",
        ),
        (
            "parse_alpha_rucl3_zigzag_kitaev_gamma",
            ALPHA_RUCL3_SOURCE_TEXT.replace("Gamma", "isotropic"),
            "alpha-RuCl3 zigzag/Kitaev-Gamma",
        ),
        (
            "parse_beta_li2iro3_spiral_order",
            BETA_LI2IRO3_SOURCE_TEXT.replace("counter-rotating", "collinear"),
            "beta-Li2IrO3 spiral order",
        ),
        (
            "parse_cs2cucl4_spiral_order",
            CS2CUCL4_SPIRAL_SOURCE_TEXT.replace("incommensurate spiral", "commensurate collinear order"),
            "Cs2CuCl4 spiral order",
        ),
        (
            "parse_square_dimerized_neel_transition",
            SQUARE_DIMERIZED_TRANSITION_SOURCE_TEXT.replace("spin-gapped dimer phase", "paramagnetic regime"),
            "square dimerized Neel-dimer transition",
        ),
        (
            "parse_square_jq_neel_vbs_transition",
            SQUARE_JQ_TRANSITION_SOURCE_TEXT.replace("valence-bond solid (VBS)", "featureless state"),
            "square J-Q Neel-VBS transition",
        ),
    ],
)
def test_direct_order_transition_parsers_fail_closed_without_complete_claim(
    parser_name, source_text, error_match
):
    parser = getattr(literature_runtime_evidence, parser_name)
    with pytest.raises(RuntimeEvidenceError, match=error_match):
        parser(source_text)


def test_triangular_classical_parser_and_recompute_cover_full_registry_operand():
    parsed, trace = literature_runtime_evidence.parse_triangular_classical_120_order(
        TRIANGULAR_CLASSICAL_120_SOURCE_TEXT
    )

    expected = {
        "order": "120_degree",
        "q_reciprocal": [1.0 / 3.0, 2.0 / 3.0, 0.0],
    }
    assert parsed == expected
    assert trace["parser"] == "parse_triangular_classical_120_order"
    assert "three-sublattice translation phase" in trace["derivation"]
    assert literature_runtime_evidence.recompute_triangular_classical_120_order(
        candidate_q=[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [1.0 / 3.0, 2.0 / 3.0, 0.0]]
    ) == expected


@pytest.mark.parametrize(
    "source_text",
    [
        TRIANGULAR_CLASSICAL_120_SOURCE_TEXT.replace(
            "nearest-neighbor pairs", "third-neighbor pairs"
        ),
        TRIANGULAR_CLASSICAL_120_SOURCE_TEXT.replace(
            "three sublattices", "two sublattices"
        ),
        TRIANGULAR_CLASSICAL_120_SOURCE_TEXT.replace("2 pi/3", "pi", 1),
        TRIANGULAR_CLASSICAL_120_SOURCE_TEXT.replace(
            "Translation by a nearest-neighbor vector", "A global rotation"
        ),
    ],
)
def test_triangular_classical_parser_fails_closed_without_complete_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="triangular classical 120-degree"):
        literature_runtime_evidence.parse_triangular_classical_120_order(source_text)


def test_fecl3_parser_extracts_helix_and_hexagonal_propagation_vector():
    parsed, trace = literature_runtime_evidence.parse_fecl3_helimagnetic_order(
        FECL3_HELIX_SOURCE_TEXT
    )

    assert parsed == {
        "magnetic_order": "helimagnetic_spiral",
        "propagation_vector_hexagonal": [4.0 / 15.0, 1.0 / 15.0, 3.0 / 2.0],
    }
    assert trace["parser"] == "parse_fecl3_helimagnetic_order"
    assert "threefold-equivalent domain" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        FECL3_HELIX_SOURCE_TEXT.replace("FeCl3", "CrCl3"),
        FECL3_HELIX_SOURCE_TEXT.replace("oppositely oriented", "parallel"),
        FECL3_HELIX_SOURCE_TEXT.replace("helical", "collinear"),
        FECL3_HELIX_SOURCE_TEXT.replace("2 pi/15", "2 pi/10"),
        FECL3_HELIX_SOURCE_TEXT.replace("(b1 + 4 b2)/15", "(b1 + 3 b2)/10"),
    ],
)
def test_fecl3_parser_fails_closed_without_complete_diffraction_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="FeCl3 helimagnetic order"):
        literature_runtime_evidence.parse_fecl3_helimagnetic_order(source_text)


@pytest.mark.parametrize(
    ("parser_name", "expected"),
    [
        ("parse_haydeeite_ferromagnetic_exchange", {"ferromagnetic_kagome_exchange": True}),
        ("parse_na4ir3o8_hyperkagome_spin_liquid", {"hyperkagome_qsl_candidate": True}),
        ("parse_ybmggao4_qsl_candidate", {"triangular_quantum_spin_liquid_candidate": True}),
        ("parse_barlowite_interlayer_coupling", {"interlayer_coupling_relevant": True}),
        (
            "parse_substituted_barlowite_two_parameter_model",
            {
                "significantly_reduced_interkagome_exchange": True,
                "two_parameter_heisenberg_hamiltonian": True,
            },
        ),
        ("parse_pr2zr2o7_quantum_spin_ice", {"quantum_spin_ice_candidate": True}),
    ],
)
def test_material_candidate_parsers_extract_registered_claims(parser_name, expected):
    parser = getattr(literature_runtime_evidence, parser_name)
    parsed, trace = parser(MATERIAL_CANDIDATE_SOURCE_TEXTS[parser_name])
    assert parsed == expected
    assert trace["parser"] == parser_name
    assert len(trace["text_spans"]) >= 3


@pytest.mark.parametrize(
    ("parser_name", "expected"),
    [
        ("parse_herbertsmithite_qsl_candidate", {"qsl_candidate": True}),
        ("parse_kapellasite_competing_exchanges", {"competing_kagome_exchanges": True}),
        ("parse_li2cuo2_frustrated_chain", {"frustrated_ferromagnetic_chain": True}),
        ("parse_u1_pyrochlore_spin_liquid", {"u1_quantum_spin_liquid_candidate": True}),
        ("parse_herbertsmithite_dm_relevance", {"dm_interaction_relevant": True}),
        ("parse_kagome_chiral_spin_liquid_phase", {"chiral_spin_liquid_phase": True}),
        ("parse_kagome_dm_critical_ratio", {"critical_d_over_j_approx": 0.1}),
        ("parse_breathing_kagome_trimerization", {"breathing_anisotropy_controls_trimerization": True}),
        ("parse_ca10cr7o28_qsl_exchange", {"spin_liquid_candidate": True, "mixed_ferromagnetic_antiferromagnetic_exchanges": True}),
        ("parse_hyperkagome_heisenberg_qsl", {"spin_liquid_candidate": True}),
        ("parse_beta_li2iro3_hyperhoneycomb_kitaev", {"hyperhoneycomb_kitaev_material": True}),
        ("parse_triangular_ring_exchange_spin_liquid", {"contains_spin_liquid_region": True}),
        ("parse_triangular_xxz_supersolid", {"contains_supersolid_phase": True}),
        ("parse_volborthite_distorted_kagome", {"distorted_kagome_reference": True}),
        ("parse_nips3_zigzag_order", {"zigzag_or_collinear_order_reference": True}),
        ("parse_kitaev_gamma_phase_content", {"contains_noncollinear_and_zigzag_phases": True}),
        ("parse_ggg_short_range_order", {"short_range_order_without_simple_lro": True}),
        ("parse_honeycomb_j1j2_nonmagnetic_candidate", {"intermediate_nonmagnetic_phase_candidate": True}),
        ("parse_honeycomb_j1j2_intermediate_nonmagnetic", {"intermediate_nonmagnetic_phase": True}),
        ("parse_kagome_j1j2_phase_set", {"phases": ["spin_liquid", "q0_order", "sqrt3xsqrt3_order"]}),
        ("parse_triangular_j1j2_phase_set", {"phases": ["120_degree", "spin_liquid", "stripe"]}),
        ("parse_triangular_j1j2_spin_liquid_window", {"spin_liquid_window_approx": [0.07, 0.15]}),
        ("parse_spin1_haldane_large_d_transition", {"large_d_transition_reference": True}),
        ("parse_bcc_large_j2_collinear_order", {"large_j2_collinear_order": True}),
        ("parse_kagome_topological_entanglement_z2", {"topological_entanglement_entropy": "consistent_with_Z2"}),
    ],
)
def test_direct_source_claim_parsers_extract_complete_registry_operands(
    parser_name, expected
):
    parser = getattr(literature_runtime_evidence, parser_name)
    parsed, trace = parser(DIRECT_SOURCE_CLAIM_TEXTS[parser_name])

    assert parsed == expected
    assert trace["parser"] == parser_name
    assert len(trace["text_spans"]) >= 4


@pytest.mark.parametrize(
    ("parser_name", "removed_anchor"),
    [
        (parser_name, anchor)
        for parser_name, anchors in DIRECT_SOURCE_CLAIM_REMOVALS.items()
        for anchor in anchors
    ],
)
def test_direct_source_claim_parsers_fail_closed_when_any_anchor_is_removed(
    parser_name, removed_anchor
):
    parser = getattr(literature_runtime_evidence, parser_name)
    incomplete_text = DIRECT_SOURCE_CLAIM_TEXTS[parser_name].replace(
        removed_anchor, "omitted"
    )

    with pytest.raises(RuntimeEvidenceError, match="direct source claim"):
        parser(incomplete_text)


@pytest.mark.parametrize("parser_name", sorted(MATERIAL_CANDIDATE_SOURCE_TEXTS))
def test_material_candidate_parsers_fail_closed_when_material_identity_is_removed(
    parser_name,
):
    source_text = MATERIAL_CANDIDATE_SOURCE_TEXTS[parser_name]
    altered = re.sub(
        r"Haydeeite|Na4Ir3O8|YbMgGaO4|Barlowite|barlowite|Pr2Zr2O7",
        "unrelated material",
        source_text,
    )
    with pytest.raises(RuntimeEvidenceError, match="material source claim"):
        getattr(literature_runtime_evidence, parser_name)(altered)


def test_aklt_projector_parser_derives_local_spectrum_and_ground_energy():
    parsed, trace = literature_runtime_evidence.parse_aklt_projector_ground_state(
        AKLT_PROJECTOR_SOURCE_TEXT
    )

    assert parsed == {
        "two_site_projector_eigenvalues": [0.0, 0.0, 1.0],
        "vbs_ground_energy": 0.0,
    }
    assert trace["parser"] == "parse_aklt_projector_ground_state"
    assert "S_total=0,1,2" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        AKLT_PROJECTOR_SOURCE_TEXT.replace("projection operators", "exchange operators"),
        AKLT_PROJECTOR_SOURCE_TEXT.replace("spin 2", "spin 1"),
        AKLT_PROJECTOR_SOURCE_TEXT.replace("neighboring pair", "three-site block"),
        AKLT_PROJECTOR_SOURCE_TEXT.replace("ground-state energy is zero", "ground-state energy is finite"),
        AKLT_PROJECTOR_SOURCE_TEXT.replace("cannot be 2", "can be 2"),
    ],
)
def test_aklt_projector_parser_fails_closed_without_projector_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="AKLT projector claim"):
        literature_runtime_evidence.parse_aklt_projector_ground_state(source_text)


def test_diamond_parser_extracts_exact_localized_magnon_claim():
    parsed, trace = literature_runtime_evidence.parse_diamond_localized_magnon(
        DIAMOND_LOCALIZED_MAGNON_SOURCE_TEXT
    )

    assert parsed == {"has_exact_localized_magnons": True}
    assert trace["parser"] == "parse_diamond_localized_magnon"
    assert trace["matched_anchors"] == [
        "diamond-chain vertical-bond trapping",
        "explicit localized one-magnon state",
        "localized magnons are sector lowest-energy states",
    ]
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        DIAMOND_LOCALIZED_MAGNON_SOURCE_TEXT.replace("diamond chain", "dimer chain"),
        DIAMOND_LOCALIZED_MAGNON_SOURCE_TEXT.replace("vertical bonds", "plaquettes"),
        DIAMOND_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "explicit expressions for the localized one-magnon state",
            "a qualitative magnon picture",
        ),
        DIAMOND_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "lowest-energy states", "candidate states"
        ),
    ],
)
def test_diamond_parser_fails_closed_without_model_specific_exact_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="diamond localized-magnon claim"):
        literature_runtime_evidence.parse_diamond_localized_magnon(source_text)


def test_sawtooth_parser_extracts_exact_localized_magnon_claim():
    parsed, trace = literature_runtime_evidence.parse_sawtooth_localized_magnon(
        SAWTOOTH_LOCALIZED_MAGNON_SOURCE_TEXT
    )

    assert parsed == {"has_exact_localized_magnons": True}
    assert trace["parser"] == "parse_sawtooth_localized_magnon"
    assert trace["matched_anchors"] == [
        "sawtooth-chain neighboring-triangle valley trapping",
        "explicit localized one-magnon state",
        "localized magnons are sector lowest-energy states",
    ]
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        SAWTOOTH_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "sawtooth chain", "zigzag chain"
        ),
        SAWTOOTH_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "neighboring triangles", "unrelated plaquettes"
        ),
        SAWTOOTH_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "explicit expressions",
            "a qualitative magnon picture",
        ),
        SAWTOOTH_LOCALIZED_MAGNON_SOURCE_TEXT.replace(
            "lowest-energy states", "candidate states"
        ),
    ],
)
def test_sawtooth_parser_fails_closed_without_model_specific_exact_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="sawtooth localized-magnon claim"):
        literature_runtime_evidence.parse_sawtooth_localized_magnon(source_text)


def test_dagotto_rice_parser_extracts_two_leg_antiferromagnetic_rung_gap():
    parsed, trace = literature_runtime_evidence.parse_dagotto_rice_two_leg_gap(
        DAGOTTO_RICE_TWO_LEG_GAP_SOURCE_TEXT
    )

    assert parsed == {"has_finite_spin_gap_for_antiferromagnetic_rungs": True}
    assert trace["parser"] == "parse_dagotto_rice_two_leg_gap"
    assert trace["matched_anchors"] == [
        "positive exchange is antiferromagnetic",
        "two-leg ladder has a finite spin gap",
        "J' is the two-leg-ladder rung exchange",
    ]
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        DAGOTTO_RICE_TWO_LEG_GAP_SOURCE_TEXT.replace("J (> 0)", "J (< 0)"),
        DAGOTTO_RICE_TWO_LEG_GAP_SOURCE_TEXT.replace("2-leg ladders", "3-leg ladders"),
        DAGOTTO_RICE_TWO_LEG_GAP_SOURCE_TEXT.replace(
            "finite energy is needed", "no energy is needed"
        ),
        DAGOTTO_RICE_TWO_LEG_GAP_SOURCE_TEXT.replace("along the rungs", "along the chains"),
    ],
)
def test_dagotto_rice_two_leg_gap_parser_fails_closed_without_complete_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Dagotto-Rice two-leg gap"):
        literature_runtime_evidence.parse_dagotto_rice_two_leg_gap(source_text)


def test_haldane_shastry_parser_extracts_exact_jastrow_ground_state():
    parsed, trace = literature_runtime_evidence.parse_haldane_shastry_ground_state(
        HALDANE_SHASTRY_SOURCE_TEXT
    )

    assert parsed == {"has_exact_jastrow_ground_state": True}
    assert trace["parser"] == "parse_haldane_shastry_ground_state"
    assert trace["matched_anchors"] == [
        "construct exact Jastrow-product ground state",
        "one-dimensional isotropic Heisenberg antiferromagnet",
        "inverse-square distance exchange",
    ]
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        HALDANE_SHASTRY_SOURCE_TEXT.replace("exact Jastrow-product", "variational product"),
        HALDANE_SHASTRY_SOURCE_TEXT.replace("ground-state wave", "excited-state wave"),
        HALDANE_SHASTRY_SOURCE_TEXT.replace("one-dimensional (1D)", "two-dimensional"),
        HALDANE_SHASTRY_SOURCE_TEXT.replace("antiferromagnet", "ferromagnet"),
        HALDANE_SHASTRY_SOURCE_TEXT.replace("inverse square", "inverse first power"),
    ],
)
def test_haldane_shastry_parser_fails_closed_without_complete_model_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Haldane-Shastry ground state"):
        literature_runtime_evidence.parse_haldane_shastry_ground_state(source_text)


def test_baxter_parser_extracts_zero_field_eight_vertex_solution():
    parsed, trace = literature_runtime_evidence.parse_baxter_eight_vertex_solution(
        BAXTER_EIGHT_VERTEX_SOURCE_TEXT
    )

    assert parsed == {"is_exactly_solved": True}
    assert trace["parser"] == "parse_baxter_eight_vertex_solution"
    assert trace["matched_anchors"] == [
        "eight-vertex lattice-statistics model",
        "solution of zero-field eight-vertex model is presented",
        "square-lattice models included as special cases",
    ]


@pytest.mark.parametrize(
    "source_text",
    [
        BAXTER_EIGHT_VERTEX_SOURCE_TEXT.replace("Eight-Vertex Model", "Vertex Model"),
        BAXTER_EIGHT_VERTEX_SOURCE_TEXT.replace("zero-field", "finite-field"),
        BAXTER_EIGHT_VERTEX_SOURCE_TEXT.replace("solution", "approximation"),
        BAXTER_EIGHT_VERTEX_SOURCE_TEXT.replace("special cases", "unrelated models"),
    ],
)
def test_baxter_parser_fails_closed_without_complete_eight_vertex_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Baxter eight-vertex solution"):
        literature_runtime_evidence.parse_baxter_eight_vertex_solution(source_text)


def test_baxter_critical_line_parser_extracts_exact_zero_field_manifold():
    parsed, trace = (
        literature_runtime_evidence.parse_baxter_eight_vertex_critical_line(
            BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT
        )
    )

    assert parsed == {"has_exact_critical_line": True}
    assert trace["parser"] == "parse_baxter_eight_vertex_critical_line"
    assert trace["critical_boundary"] == "max(a,b,c,d)=sum(other three)"
    assert len(trace["text_spans"]) == 8


@pytest.mark.parametrize(
    "source_text",
    [
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            "Eight-Vertex Model in Lattice Statistics",
            "Six-Vertex Approximation",
        ),
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            'solution of the zero-field "eight-vertex" model',
            'approximation to the finite-field "eight-vertex" model',
        ),
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            "square lattice Ising, dimer, ice, P, and KDP models",
            "three-dimensional continuum models",
        ),
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            "unchanged by reversal of all arrows", "changed by arrow reversal"
        ),
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            "arbitrary values of a, b, c, and d",
            "one fixed set of weights",
        ),
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            "c > a+b+d", "c < a+b+d"
        ),
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            "cross a boundary of the\nprincipal domain",
            "remain strictly inside the principal domain",
        ),
        BAXTER_EIGHT_VERTEX_CRITICAL_LINE_SOURCE_TEXT.replace(
            "c-a-b-d has a simple zero",
            "c-a-b-d remains nonzero",
        ),
    ],
)
def test_baxter_critical_line_parser_fails_closed_without_exact_manifold(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Baxter critical line"):
        literature_runtime_evidence.parse_baxter_eight_vertex_critical_line(
            source_text
        )


def test_baxter_critical_line_recompute_checks_distinct_boundary_points():
    assert (
        literature_runtime_evidence.recompute_baxter_eight_vertex_critical_line(
            critical_weight_points=[
                {"a": 1.0, "b": 1.0, "c": 3.0, "d": 1.0},
                {"a": 1.5, "b": 0.5, "c": 3.0, "d": 1.0},
            ]
        )
        == {"has_exact_critical_line": True}
    )
    assert literature_runtime_evidence.recompute_baxter_eight_vertex_critical_line(
        critical_weight_points=[
            {"a": 1.0, "b": 1.0, "c": 2.5, "d": 1.0},
            {"a": 1.5, "b": 0.5, "c": 3.0, "d": 1.0},
        ]
    ) == {"has_exact_critical_line": False}


@pytest.mark.parametrize(
    "critical_weight_points",
    [
        [{"a": 1.0, "b": 1.0, "c": 3.0, "d": 1.0}],
        [
            {"a": 1.0, "b": 1.0, "c": 3.0, "d": 1.0},
            {"a": 2.0, "b": 2.0, "c": 6.0, "d": 2.0},
        ],
        [
            {"a": 1.0, "b": 1.0, "c": 3.0, "d": 1.0},
            {"a": 1.0, "b": 0.0, "c": 2.0, "d": 1.0},
        ],
    ],
)
def test_baxter_critical_line_recompute_rejects_non_line_inputs(
    critical_weight_points,
):
    with pytest.raises(RuntimeEvidenceError, match="Baxter critical-line"):
        literature_runtime_evidence.recompute_baxter_eight_vertex_critical_line(
            critical_weight_points=critical_weight_points
        )


def test_lieb_square_ice_parser_extracts_exact_solution_status():
    parsed, trace = literature_runtime_evidence.parse_lieb_square_ice_solution(
        LIEB_SQUARE_ICE_SOURCE_TEXT
    )

    assert parsed == {"is_exactly_solved": True}
    assert trace["parser"] == "parse_lieb_square_ice_solution"
    assert trace["matched_anchors"] == [
        "two-dimensional square planar net",
        "two arrows point into each vertex",
        "exact square-ice result",
    ]


@pytest.mark.parametrize(
    "source_text",
    [
        LIEB_SQUARE_ICE_SOURCE_TEXT.replace("two dimensions", "three dimensions"),
        LIEB_SQUARE_ICE_SOURCE_TEXT.replace("square planar net", "triangular net"),
        LIEB_SQUARE_ICE_SOURCE_TEXT.replace("precisely two", "precisely one"),
        LIEB_SQUARE_ICE_SOURCE_TEXT.replace("Our exact result", "Our estimate"),
    ],
)
def test_lieb_square_ice_parser_fails_closed_without_complete_exact_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Lieb square-ice solution"):
        literature_runtime_evidence.parse_lieb_square_ice_solution(source_text)


def test_yang_gaudin_parser_extracts_exact_spin_half_fermion_solution():
    parsed, trace = literature_runtime_evidence.parse_yang_gaudin_fermion_solution(
        YANG_GAUDIN_SOURCE_TEXT
    )
    assert parsed == {"is_exactly_solved": True}
    assert trace["parser"] == "parse_yang_gaudin_fermion_solution"
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        YANG_GAUDIN_SOURCE_TEXT.replace("one\ndimension", "two\ndimensions"),
        YANG_GAUDIN_SOURCE_TEXT.replace("Repulsive", "Attractive").replace(
            "repulsive", "attractive"
        ),
        YANG_GAUDIN_SOURCE_TEXT.replace("Bethe's hypothesis", "perturbation theory"),
        YANG_GAUDIN_SOURCE_TEXT.replace("spin-1/2 fermions", "bosons"),
    ],
)
def test_yang_gaudin_parser_fails_closed_without_complete_exact_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Yang-Gaudin solution"):
        literature_runtime_evidence.parse_yang_gaudin_fermion_solution(source_text)


def test_lieb_liniger_parser_extracts_exact_solution_and_fermion_limit():
    parsed, trace = literature_runtime_evidence.parse_lieb_liniger_solution(
        LIEB_LINIGER_SOURCE_TEXT
    )
    assert parsed == {
        "is_exactly_solved": True,
        "tonks_girardeau_limit_maps_to_free_fermions": True,
    }
    assert trace["parser"] == "parse_lieb_liniger_solution"
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        LIEB_LINIGER_SOURCE_TEXT.replace("one-dimensional", "two-dimensional"),
        LIEB_LINIGER_SOURCE_TEXT.replace("repulsive delta-function", "finite-range"),
        LIEB_LINIGER_SOURCE_TEXT.replace("solved\nexactly", "approximated"),
        LIEB_LINIGER_SOURCE_TEXT.replace("impenetrable bosons", "soft bosons"),
        LIEB_LINIGER_SOURCE_TEXT.replace("noninteracting Fermi gas", "classical gas"),
    ],
)
def test_lieb_liniger_parser_fails_closed_without_both_registry_claims(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Lieb-Liniger solution"):
        literature_runtime_evidence.parse_lieb_liniger_solution(source_text)


def test_pauling_spin_ice_parser_derives_entropy_formula():
    parsed, trace = literature_runtime_evidence.parse_pauling_spin_ice_entropy(
        PAULING_SPIN_ICE_SOURCE_TEXT
    )
    assert parsed == {"pauling_entropy_per_spin": pytest.approx(0.5 * math.log(1.5))}
    assert trace["parser"] == "parse_pauling_spin_ice_entropy"
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        PAULING_SPIN_ICE_SOURCE_TEXT.replace("Spin ice", "ferromagnets"),
        PAULING_SPIN_ICE_SOURCE_TEXT.replace("Pauling estimated", "A simulation estimated"),
        PAULING_SPIN_ICE_SOURCE_TEXT.replace("(3/2)^(N/2)", "2^(N/2)"),
        PAULING_SPIN_ICE_SOURCE_TEXT.replace("(R/2) ln(3/2)", "R ln(2)"),
    ],
)
def test_pauling_spin_ice_parser_fails_closed_without_complete_formula(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Pauling spin-ice entropy"):
        literature_runtime_evidence.parse_pauling_spin_ice_entropy(source_text)


def test_bkt_universal_jump_parser_extracts_formula_and_unit_temperature_value():
    parsed, trace = literature_runtime_evidence.parse_bkt_universal_jump(
        BKT_UNIVERSAL_JUMP_SOURCE_TEXT
    )
    assert parsed == {
        "formula": "rho_s(T_BKT)=2T_BKT/pi",
        "helicity_modulus_at_t_1": pytest.approx(2.0 / math.pi),
    }
    assert trace["parser"] == "parse_bkt_universal_jump"
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        BKT_UNIVERSAL_JUMP_SOURCE_TEXT.replace("two-dimensional XY", "three-dimensional XY"),
        BKT_UNIVERSAL_JUMP_SOURCE_TEXT.replace("spin-wave stiffness", "compressibility"),
        BKT_UNIVERSAL_JUMP_SOURCE_TEXT.replace("2/pi", "3/pi"),
        BKT_UNIVERSAL_JUMP_SOURCE_TEXT.replace("from below", "from above"),
    ],
)
def test_bkt_universal_jump_parser_fails_closed_without_complete_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="BKT universal jump"):
        literature_runtime_evidence.parse_bkt_universal_jump(source_text)


def test_bkt_universal_jump_operand_covers_all_registered_fields():
    assert literature_runtime_evidence.recompute_bkt_universal_jump_operand(
        temperature=1.0
    ) == {
        "formula": "rho_s(T_BKT)=2T_BKT/pi",
        "helicity_modulus_at_t_1": pytest.approx(2.0 / math.pi),
    }


def test_takhtajan_babujian_parser_extracts_integrable_spin1_critical_point():
    parsed, trace = (
        literature_runtime_evidence.parse_kitazawa_nomura_takhtajan_babujian_point(
            KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT
        )
    )

    assert parsed == {
        "theta_radians": pytest.approx(-math.pi / 4.0),
        "is_integrable": True,
    }
    assert trace["parser"] == (
        "parse_kitazawa_nomura_takhtajan_babujian_point"
    )
    assert trace["source_role"] == (
        "machine-extractable supplemental primary research source"
    )
    assert "cos(theta)" in trace["derivation"]
    assert "sin(theta)" in trace["derivation"]
    assert len(trace["text_spans"]) == 6


def test_takhtajan_babujian_parser_accepts_locked_dual_column_layout_text():
    parsed, trace = (
        literature_runtime_evidence.parse_kitazawa_nomura_takhtajan_babujian_point(
            KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_LAYOUT_TEXT
        )
    )

    assert parsed == {
        "theta_radians": pytest.approx(-math.pi / 4.0),
        "is_integrable": True,
    }
    assert trace["matched_anchors"][-1] == (
        "k=2 criticality confirmed by Bethe ansatz"
    )


@pytest.mark.parametrize(
    "source_text",
    [
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "Takhtajan-Babujian point", "unrelated spin-chain point", 1
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "Atsuhiro Kitazawa and Kiyohide Nomura",
            "Different Authors",
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "S = 1 quantum spin chains", "S = 1/2 quantum spin chains"
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "bilinear, biquadratic", "bilinear, single-ion"
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "(theta = -pi/4, delta = 0)", "(theta = pi/4, delta = 0)"
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "(theta = -pi/4, delta = 0)", "(theta = -pi/4, delta = 1)"
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "+ sin(theta) (S_j dot S_j+1)^2",
            "- sin(theta) (S_j dot S_j+1)^2",
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "integrable\nTakhtajan-Babujian",
            "nonintegrable\nTakhtajan-Babujian",
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "critical properties", "massive properties"
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "k = 2 SU(2) Wess-Zumino-Witten",
            "k = 1 U(1)",
        ),
        KITAZAWA_NOMURA_TAKHTAJAN_BABUJIAN_SOURCE_TEXT.replace(
            "confirmed by Bethe ansatz", "suggested by mean-field theory"
        ),
    ],
)
def test_takhtajan_babujian_parser_fails_closed_without_complete_claim(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Takhtajan-Babujian spin-1 point",
    ):
        literature_runtime_evidence.parse_kitazawa_nomura_takhtajan_babujian_point(
            source_text
        )


def test_uls_parser_derives_spin1_equal_coupling_su3_point():
    parsed, trace = literature_runtime_evidence.parse_uls_spin1_su3_point(
        ULS_SU3_SOURCE_TEXT
    )
    assert parsed == {
        "theta_radians": pytest.approx(math.pi / 4.0),
        "su3_symmetric": True,
    }
    assert trace["parser"] == "parse_uls_spin1_su3_point"
    assert "P_ij = S_i.S_j + (S_i.S_j)^2 - 1" in trace["derivation"]
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        ULS_SU3_SOURCE_TEXT.replace(
            "permute whatever objects", "count whatever objects"
        ),
        ULS_SU3_SOURCE_TEXT.replace(
            "invariant under the\ntotal SU(3) group", "invariant under U(1)"
        ),
        ULS_SU3_SOURCE_TEXT.replace(
            "spin-1 representation", "spin-1/2 representation"
        ),
        ULS_SU3_SOURCE_TEXT.replace("Bethe's ansatz", "mean-field theory"),
    ],
)
def test_uls_parser_fails_closed_without_permutation_su3_spin1_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match=r"ULS spin-1 SU\(3\) point"):
        literature_runtime_evidence.parse_uls_spin1_su3_point(source_text)


def test_uls_recompute_operand_covers_angle_and_symmetry_fields():
    assert literature_runtime_evidence.recompute_uls_spin1_su3_operand() == {
        "theta_radians": pytest.approx(math.pi / 4.0),
        "su3_symmetric": True,
    }


def test_square_compass_parser_extracts_exact_line_symmetry_claim():
    parsed, trace = literature_runtime_evidence.parse_square_compass_line_symmetries(
        SQUARE_COMPASS_SOURCE_TEXT
    )

    assert parsed == {"has_line_flip_symmetries": True}
    assert trace["parser"] == "parse_square_compass_line_symmetries"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        SQUARE_COMPASS_SOURCE_TEXT.replace("anisotropic compass", "anisotropic Ising"),
        SQUARE_COMPASS_SOURCE_TEXT.replace(
            "product_(r in P_gamma)", "sum_(r in P_gamma)"
        ),
        SQUARE_COMPASS_SOURCE_TEXT.replace(
            "any line in the two-dimensional model", "the full lattice"
        ),
        SQUARE_COMPASS_SOURCE_TEXT.replace(
            "commute with the general\nHamiltonian", "do not commute with the general\nHamiltonian"
        ),
    ],
)
def test_square_compass_parser_fails_closed_without_complete_line_symmetry_claim(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="square compass line symmetry"):
        literature_runtime_evidence.parse_square_compass_line_symmetries(source_text)


def test_square_compass_recompute_checks_every_line_operator_against_hamiltonian():
    assert literature_runtime_evidence.recompute_square_compass_line_symmetries(
        length=2, j_x=1.0, j_y=1.0
    ) == {"has_line_flip_symmetries": True}
    assert literature_runtime_evidence.recompute_square_compass_line_symmetries(
        length=3, j_x=0.7, j_y=1.3
    ) == {"has_line_flip_symmetries": True}


def test_aklt_projector_adapter_returns_spectrum_and_zero_vbs_energy():
    assert literature_spin_model_benchmarks.aklt_projector_ground_state_result() == {
        "two_site_projector_eigenvalues": [0.0, 0.0, 1.0],
        "vbs_ground_energy": 0.0,
    }


def test_aklt_angle_parser_derives_ratio_from_spin_two_projector():
    parsed, trace = literature_runtime_evidence.parse_aklt_angle_from_projector(
        AKLT_ANGLE_SOURCE_TEXT
    )

    assert parsed == {
        "aklt_tan_theta": pytest.approx(1.0 / 3.0),
        "theta_radians": pytest.approx(math.atan(1.0 / 3.0)),
    }
    assert trace["parser"] == "parse_aklt_angle_from_projector"
    assert trace["projector_polynomial"] == "P_2(x)=(x+2)(x+1)/6"
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        AKLT_ANGLE_SOURCE_TEXT.replace("spin-1 chain", "spin-1/2 chain"),
        AKLT_ANGLE_SOURCE_TEXT.replace(
            "sum of projection operators onto\nspin 2", "sum of exchange operators"
        ),
        AKLT_ANGLE_SOURCE_TEXT.replace(
            "general bilinear-biquadratic\nHamiltonian", "general bilinear Hamiltonian"
        ),
    ],
)
def test_aklt_angle_parser_fails_closed_without_projector_parameterization(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="AKLT angle"):
        literature_runtime_evidence.parse_aklt_angle_from_projector(source_text)


def test_yang_spontaneous_magnetization_parser_extracts_final_exact_formula():
    parsed, trace = (
        literature_runtime_evidence.parse_yang_spontaneous_magnetization(
            YANG_SPONTANEOUS_MAGNETIZATION_SOURCE_TEXT
        )
    )

    assert parsed == {
        "formula": "[1 - sinh(2 beta J)^(-4)]^(1/8)",
        "magnetization_beta_0_6_j_1": pytest.approx(
            (1.0 - math.sinh(1.2) ** -4) ** 0.125
        ),
    }
    assert trace["parser"] == "parse_yang_spontaneous_magnetization"
    assert trace["equation"] == "96"
    assert len(trace["text_spans"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        YANG_SPONTANEOUS_MAGNETIZATION_SOURCE_TEXT.replace(
            "two-dimensional Ising", "three-dimensional Ising"
        ),
        YANG_SPONTANEOUS_MAGNETIZATION_SOURCE_TEXT.replace(
            "calculated\nexactly", "estimated\nnumerically"
        ),
        YANG_SPONTANEOUS_MAGNETIZATION_SOURCE_TEXT.replace(
            "I = [1 - sinh(2H)^(-4)]^(1/8). (96)", "I = 0. (96)"
        ),
        YANG_SPONTANEOUS_MAGNETIZATION_SOURCE_TEXT.replace("(96)", "(97)"),
    ],
)
def test_yang_spontaneous_magnetization_parser_fails_closed_without_exact_result(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Yang spontaneous magnetization"):
        literature_runtime_evidence.parse_yang_spontaneous_magnetization(source_text)


def test_square_potts_parser_derives_exact_critical_point_and_transition_boundary():
    parsed, trace = literature_runtime_evidence.parse_square_potts_critical_point(
        SQUARE_POTTS_SOURCE_TEXT
    )

    assert parsed == {
        "critical_beta_j": "log(1 + sqrt(q))",
        "continuous_for_q_le_4": True,
    }
    assert trace["parser"] == "parse_square_potts_critical_point"
    assert trace["derivation"] == (
        "x=(exp(K)-1)/sqrt(q); isotropic square x^2=1; "
        "ferromagnetic x=1"
    )
    assert len(trace["matched_anchors"]) == 4
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        SQUARE_POTTS_SOURCE_TEXT.replace(
            "x_n = (exp(K_n) - 1) / sqrt(q). (4.4)",
            "x_n is the temperature variable. (4.4)",
        ),
        SQUARE_POTTS_SOURCE_TEXT.replace(
            "For the square lattice the critical condition is x_1 x_2 = 1. (5.1b)",
            "For the square lattice the critical condition is exact. (5.1b)",
        ),
        SQUARE_POTTS_SOURCE_TEXT.replace(
            "The expression (5.1b) for the critical point of the Potts model on the square\n"
            "lattice follows from duality, which determines the transition at the self-dual\n"
            "point x_1 x_2 = 1.",
            "The square lattice has a critical point.",
        ),
        SQUARE_POTTS_SOURCE_TEXT.replace(
            "In two dimensions the transition is continuous for q <= 4 and first order\n"
            "for q > 4.",
            "In two dimensions the transition changes its order as q varies.",
        ),
    ],
)
def test_square_potts_parser_fails_closed_without_complete_derivation(source_text):
    with pytest.raises(RuntimeEvidenceError, match="square Potts critical point"):
        literature_runtime_evidence.parse_square_potts_critical_point(source_text)


def test_square_potts_recompute_solves_self_dual_equation_and_checks_numeric_adapter():
    assert literature_runtime_evidence.recompute_square_potts_critical_point(
        transition_boundary=4,
        q_checks=(2, 3, 4, 5),
    ) == {
        "critical_beta_j": "log(1 + sqrt(q))",
        "continuous_for_q_le_4": True,
    }


def test_wannier_parser_recomputes_entropy_formula_and_records_printed_conflict():
    parsed, trace = literature_runtime_evidence.parse_wannier_triangular_entropy(
        WANNIER_TRIANGULAR_ISING_SOURCE_TEXT
    )

    assert parsed == {"residual_entropy_per_spin": 0.323066}
    assert trace["parser"] == "parse_wannier_triangular_entropy"
    assert trace["equation"] == "37a"
    assert trace["printed_decimal"] == 0.338314
    assert trace["printed_decimal_matches_formula"] is False
    assert len(trace["matched_anchors"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        WANNIER_TRIANGULAR_ISING_SOURCE_TEXT.replace(
            "triangular net with antiferromagnetic interaction",
            "square net with ferromagnetic interaction",
        ),
        WANNIER_TRIANGULAR_ISING_SOURCE_TEXT.replace(
            "The entropy at absolute zero is finite.",
            "The finite-temperature entropy is studied.",
        ),
        WANNIER_TRIANGULAR_ISING_SOURCE_TEXT.replace(
            "S(0)/R = (2/pi) integral_0^(pi/3) ln(2 cos(omega)) d omega. (37a)",
            "S(0)/R is given by an integral. (37a)",
        ),
    ],
)
def test_wannier_parser_fails_closed_without_complete_entropy_formula(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Wannier triangular Ising entropy"):
        literature_runtime_evidence.parse_wannier_triangular_entropy(source_text)


def test_wannier_entropy_recompute_integrates_source_formula_independently():
    assert literature_runtime_evidence.recompute_wannier_triangular_entropy(
        intervals=10000
    ) == {"residual_entropy_per_spin": 0.323066}


def test_garel_maillard_parser_derives_villain_macroscopic_degeneracy():
    parsed, trace = (
        literature_runtime_evidence.parse_garel_maillard_villain_entropy(
            GAREL_MAILLARD_VILLAIN_SOURCE_TEXT
        )
    )

    assert parsed == {"macroscopic_ground_state_degeneracy": True}
    assert trace["parser"] == "parse_garel_maillard_villain_entropy"
    assert trace["source_role"] == (
        "exact primary follow-up to the registered Villain 1977 source"
    )
    assert trace["formula"] == "S_V=G/pi"
    assert trace["residual_entropy_per_spin"] == pytest.approx(
        0.291560904, abs=1.0e-9
    )
    assert trace["degeneracy_scaling"] == "Omega_N=exp(N G/pi)"
    assert len(trace["matched_anchors"]) == 7
    assert len(trace["text_spans"]) == 7


def test_garel_maillard_parser_accepts_verified_scan_ocr_forms():
    parsed, trace = (
        literature_runtime_evidence.parse_garel_maillard_villain_entropy(
            GAREL_MAILLARD_VILLAIN_SCAN_OCR_SOURCE_TEXT
        )
    )

    assert parsed == {"macroscopic_ground_state_degeneracy": True}
    assert trace["formula"] == "S_V=G/pi"
    assert trace["scan_ocr_pi_glyph_read_as_t"] is True


@pytest.mark.parametrize(
    "source_text",
    [
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "Study of a two-dimensional fully frustrated model",
            "Study of an unfrustrated three-dimensional model",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "T Garel and J M Maillard", "T Garel"
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "fully frustrated Ising model on a square lattice",
            "ferromagnetic Potts model on a triangular lattice",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "(ij) denotes nearest-neighbour pairing, sigma_i = +/- 1",
            "(ij) denotes arbitrary pairing, with continuous spins",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "K1, -K2, K3, -K4", "K1, K2, K3, K4"
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "K1 = K2 = K3 = K4 corresponds to Villain's model",
            "K1 = K2 = K3 = K4 corresponds to Onsager's ferromagnet",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "Double lines denote\nnegative coupling constants (-K2 or -K4)",
            "All lines denote\npositive coupling constants",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "the Villain (1977) model where K_i = K",
            "an unnamed model with unspecified couplings",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "angular integrals of the two partition functions are the same for any\n"
            "temperature",
            "two partition functions are compared qualitatively",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "residual entropy S_V of the Villain\n"
            "model with the Onsager free energy at criticality F_c",
            "finite-temperature heat capacity with an unspecified reference",
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "= G / pi", "= G / (2 pi)"
        ),
        GAREL_MAILLARD_VILLAIN_SOURCE_TEXT.replace(
            "where G is Catalan's constant",
            "where G is an unspecified fitting constant",
        ),
    ],
)
def test_garel_maillard_parser_fails_closed_without_complete_entropy_proof(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Garel-Maillard Villain entropy"
    ):
        literature_runtime_evidence.parse_garel_maillard_villain_entropy(
            source_text
        )


def test_garel_maillard_villain_entropy_recompute_sums_catalan_series():
    assert (
        literature_runtime_evidence.recompute_garel_maillard_villain_entropy(
            series_terms=10000
        )
        == {
            "macroscopic_ground_state_degeneracy": True,
            "residual_entropy_per_spin": pytest.approx(
                0.291560904, abs=1.0e-9
            ),
        }
    )


@pytest.mark.parametrize("series_terms", [True, 0, 63, 64.0])
def test_garel_maillard_villain_entropy_recompute_rejects_invalid_series_size(
    series_terms,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Garel-Maillard Catalan series"
    ):
        literature_runtime_evidence.recompute_garel_maillard_villain_entropy(
            series_terms=series_terms
        )


def test_kano_naya_kagome_entropy_recompute_integrates_equation_47():
    assert (
        literature_runtime_evidence.recompute_kano_naya_kagome_ising_entropy(
            grid_size=256
        )
        == {
            "macroscopic_ground_state_degeneracy": True,
            "residual_entropy_per_spin": pytest.approx(
                0.50183316456, abs=1.0e-12
            ),
        }
    )


@pytest.mark.parametrize("grid_size", [True, 0, 63, 65, 64.0])
def test_kano_naya_kagome_entropy_recompute_rejects_invalid_grid(
    grid_size,
):
    with pytest.raises(RuntimeEvidenceError, match="Kano-Naya entropy grid"):
        literature_runtime_evidence.recompute_kano_naya_kagome_ising_entropy(
            grid_size=grid_size
        )


def test_runtime_collector_recomputes_wannier_triangular_ising_entropy():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["triangular_ising_antiferromagnet_residual_entropy"]
    record = bundle["runtime_evidence_record"]
    expected = {"residual_entropy_per_spin": 0.323066}
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "3d27240feba0806dfd4334f8588adaf1630e273548c51e235a5df8af78d1be02"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["printed_decimal"] == 0.338314
    assert bundle["extraction_trace"]["printed_decimal_matches_formula"] is False
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_wannier_triangular_entropy"
    )


def test_barouch_mccoy_parser_extracts_both_xy_critical_boundaries():
    parsed, trace = literature_runtime_evidence.parse_barouch_mccoy_xy_boundaries(
        BAROUCH_MCCOY_XY_SOURCE_TEXT
    )

    assert parsed == {
        "ising_critical_field": 1.0,
        "anisotropy_transition_gamma": 0.0,
    }
    assert trace["parser"] == "parse_barouch_mccoy_xy_boundaries"
    assert len(trace["matched_anchors"]) == 4
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        BAROUCH_MCCOY_XY_SOURCE_TEXT.replace(
            "Statistical Mechanics of the XY Model", "Statistical Mechanics of the XYZ Model"
        ),
        BAROUCH_MCCOY_XY_SOURCE_TEXT.replace(
            "The Hamiltonian is H = J sum_j [(1+gamma) Sx_j Sx_(j+1)\n"
            "+ (1-gamma) Sy_j Sy_(j+1)] - h sum_j Sz_j, with J positive.",
            "The Hamiltonian contains exchange and field terms.",
        ),
        BAROUCH_MCCOY_XY_SOURCE_TEXT.replace(
            "if |h| < J, the ground-state energy is not an analytic function of\n"
            "gamma at gamma=0.",
            "the ground-state energy depends on gamma.",
        ),
        BAROUCH_MCCOY_XY_SOURCE_TEXT.replace(
            "fails to be an analytic function of h at\n|h|=J for any gamma.",
            "depends smoothly on h.",
        ),
    ],
)
def test_barouch_mccoy_parser_fails_closed_without_both_boundaries(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Barouch-McCoy XY boundaries"):
        literature_runtime_evidence.parse_barouch_mccoy_xy_boundaries(source_text)


def test_xy_boundary_recompute_checks_free_fermion_gap_closures():
    assert literature_runtime_evidence.recompute_xy_critical_boundaries(
        interior_field=0.6,
        anisotropy_probe=0.3,
    ) == {
        "ising_critical_field": 1.0,
        "anisotropy_transition_gamma": 0.0,
    }


def test_runtime_collector_recomputes_xy_chain_critical_boundaries():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["xy_spin_half_chain_anisotropic_critical_line"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "ising_critical_field": 1.0,
        "anisotropy_transition_gamma": 0.0,
    }
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "4134e60f10a7ff98241dec6b6c0924b9876738c823887c0c16b10aec62d3e12f"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["normalization"] == (
        "g=|h|/J and source y=registered gamma"
    )
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_xy_critical_boundaries"
    )


def test_mulder_parser_derives_honeycomb_spiral_ring_condition():
    parsed, trace = (
        literature_runtime_evidence.parse_mulder_honeycomb_spiral_contour(
            MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT
        )
    )

    assert parsed == {
        "ring_condition": "|1+exp(iq1)+exp(iq2)|=|J1|/(2J2)"
    }
    assert trace["parser"] == "parse_mulder_honeycomb_spiral_contour"
    assert trace["source_role"] == (
        "direct honeycomb correction to the registered diamond-lattice source"
    )
    assert trace["equation"] == "5"
    assert trace["neel_boundary_j2_over_j1"] == pytest.approx(1.0 / 6.0)
    assert trace["coordinate_map"] == "(q1,q2)=(Q_b,Q_a+Q_b)"
    assert "structure-factor modulus squared" in trace["derivation"]
    assert len(trace["matched_anchors"]) == 7
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "Spiral order by disorder and lattice nematic order",
            "Collinear order without frustration",
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "A. Mulder, R. Ganesh, L. Capriotti, and A. Paramekanti",
            "A. Mulder and R. Ganesh",
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "J1-J2 Heisenberg model on the two-dimensional honeycomb\nlattice",
            "J1-J2 Ising model on the square\nlattice",
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "H = J1 sum_<ij> S_i dot S_j + J2 sum_<<ij>> S_i dot S_j. (1)",
            "H contains two unspecified interactions. (1)",
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "and we set J1, J2 > 0", "and the coupling signs are unspecified"
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "S1(r) = S[cos(Q dot r) zhat + sin(Q dot r) xhat], (2)\n"
            "S2(r) = -S[cos(Q dot r + phi) zhat + sin(Q dot r + phi) xhat]. (3)",
            "The two sublattices have unspecified spin configurations.",
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "+ J2 S^2[cos(Q_a) + cos(Q_b) + cos(Q_a+Q_b)]. (4)",
            "+ an unspecified next-neighbor contribution. (4)",
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "For J2/J1 > 1/6", "For J2/J1 > 1/4"
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "= (1/2)[(J1/(2 J2))^2 - 3]. (5)",
            "= (1/2)[(J1/J2)^2 - 3]. (5)",
        ),
        MULDER_HONEYCOMB_SPIRAL_SOURCE_TEXT.replace(
            "form a closed contour around\nQ=(0,0) for 1/6 < J2/J1 < 1/2",
            "form isolated points around\nQ=(0,0) in an unspecified range",
        ),
    ],
)
def test_mulder_parser_fails_closed_without_model_and_contour_derivation(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Mulder honeycomb spiral contour"
    ):
        literature_runtime_evidence.parse_mulder_honeycomb_spiral_contour(
            source_text
        )


def test_honeycomb_spiral_recompute_derives_structure_factor_contour():
    assert (
        literature_runtime_evidence.recompute_honeycomb_j1_j2_spiral_contour(
            j1=1.0,
            j2=0.3,
        )
        == {
            "ring_condition": "|1+exp(iq1)+exp(iq2)|=|J1|/(2J2)"
        }
    )


@pytest.mark.parametrize(
    ("j1", "j2"),
    [
        (True, 0.3),
        (1.0, False),
        (0.0, 0.3),
        (1.0, 0.0),
        (1.0, 1.0 / 6.0),
        (1.0, 0.5),
    ],
)
def test_honeycomb_spiral_recompute_rejects_invalid_or_non_probe_regime(
    j1, j2
):
    with pytest.raises(
        RuntimeEvidenceError, match="honeycomb J1-J2 spiral"
    ):
        literature_runtime_evidence.recompute_honeycomb_j1_j2_spiral_contour(
            j1=j1,
            j2=j2,
        )


def test_balla_iqbal_penc_parser_extracts_all_fcc_j1_j2_type_orders():
    parsed, trace = (
        literature_runtime_evidence.parse_balla_iqbal_penc_fcc_type_orders(
            BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT
        )
    )

    assert parsed == {
        "common_orders": ["type_I", "type_II", "type_III"]
    }
    assert trace["parser"] == (
        "parse_balla_iqbal_penc_fcc_type_orders"
    )
    assert trace["source_role"] == (
        "direct corrective primary source for the mismatched Lines 1963 citation"
    )
    assert trace["equation"] == "1"
    assert trace["table"] == "I"
    assert trace["j3_projection"] == "J3=0 with J1>0"
    assert trace["phase_ranges"] == {
        "type_I": "J2<0",
        "type_III": "0<J2/J1<1/2",
        "type_II": "J2/J1>1/2",
    }
    assert trace["registered_source_mismatch"] == (
        "DOI 10.1103/PhysRev.131.546 studies layered CoCl2 and NiCl2, not "
        "the FCC J1-J2 type-order problem"
    )
    assert len(trace["matched_anchors"]) == 12
    assert len(trace["text_spans"]) == 12


def test_balla_iqbal_penc_parser_accepts_verified_two_column_layout_forms():
    parsed, trace = (
        literature_runtime_evidence.parse_balla_iqbal_penc_fcc_type_orders(
            BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_TWO_COLUMN_TEXT
        )
    )

    assert parsed == {
        "common_orders": ["type_I", "type_II", "type_III"]
    }
    assert trace["two_column_layout_forms_accepted"] is True


@pytest.mark.parametrize(
    "source_text",
    [
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "Degenerate manifolds, helimagnets, and multi-Q chiral phases",
            "A molecular-field study of layered ferromagnets",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "Peter Balla, Yasir Iqbal, and Karlo Penc",
            "Peter Balla and Yasir Iqbal",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "arXiv:2007.00376v3", "arXiv:2007.99999v3"
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "classical\nfrustrated Heisenberg model on the face-centered-cubic lattice",
            "quantum Ising model on the simple-cubic lattice",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "H = J1 sum_<i,j>1 S_i dot S_j\n"
            "  + J2 sum_<i,j>2 S_i dot S_j\n"
            "  + J3 sum_<i,j>3 S_i dot S_j. (1)",
            "H contains three unspecified interactions. (1)",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "first (J1), second (J2), and third neighbor (J3)\ninteractions",
            "three interactions with unspecified neighbor shells",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "The fourth column gives the stability region of the commensurate\n"
            "phases, i.e. exchange parameter regions where the Hessian is positive\n"
            "definite. The last column gives the conventional names",
            "The columns contain unspecified qualitative labels",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "X (1, 0, 0)  -2J1 + 3J2 - 4J3  J2 < 4J3 < 2J1 - 2J2  Type I",
            "X (1, 0, 0) has an unspecified energy and stability region",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "L (1/2, 1/2, 1/2)  -3J2  J1 - 2J2 < 2J3 < J1 + J2  Type II",
            "L (1/2, 1/2, 1/2) has an unspecified energy and stability region",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "W (1, 1/2, 0)  -2J1 + J2 + 4J3  8J3 < 2J2 < J1 - 2J3  Type III",
            "W (1, 1/2, 0) has an unspecified energy and stability region",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "which are already present in the J1-J2\nmodels",
            "which require a nonzero third-neighbor coupling",
        ),
        BALLA_IQBAL_PENC_FCC_TYPE_ORDERS_SOURCE_TEXT.replace(
            "We found and analyzed in detail the commensurate Type I, II and III\n"
            "structures",
            "We leave all commensurate structures unidentified",
        ),
    ],
)
def test_balla_iqbal_penc_parser_fails_closed_without_complete_type_order_evidence(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Balla-Iqbal-Penc FCC type orders"
    ):
        literature_runtime_evidence.parse_balla_iqbal_penc_fcc_type_orders(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2020])
def test_balla_iqbal_penc_parser_rejects_non_text_or_empty_source(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Balla-Iqbal-Penc FCC type orders"
    ):
        literature_runtime_evidence.parse_balla_iqbal_penc_fcc_type_orders(
            source_text
        )


def test_fcc_j1_j2_type_order_recompute_projects_table_i_to_j3_zero():
    assert literature_runtime_evidence.recompute_fcc_j1_j2_type_orders(
        j1=1.0,
        type_i_j2=-0.25,
        type_iii_j2=0.25,
        type_ii_j2=0.75,
    ) == {
        "common_orders": ["type_I", "type_II", "type_III"]
    }


@pytest.mark.parametrize(
    ("j1", "type_i_j2", "type_iii_j2", "type_ii_j2"),
    [
        (True, -0.25, 0.25, 0.75),
        (0.0, -0.25, 0.25, 0.75),
        (1.0, False, 0.25, 0.75),
        (1.0, -0.25, math.inf, 0.75),
        (1.0, -0.25, 0.25, math.nan),
        (1.0, 0.0, 0.25, 0.75),
        (1.0, -0.25, 0.0, 0.75),
        (1.0, -0.25, 0.5, 0.75),
        (1.0, -0.25, 0.25, 0.5),
    ],
)
def test_fcc_j1_j2_type_order_recompute_rejects_invalid_or_boundary_probes(
    j1, type_i_j2, type_iii_j2, type_ii_j2
):
    with pytest.raises(RuntimeEvidenceError, match="FCC J1-J2 type orders"):
        literature_runtime_evidence.recompute_fcc_j1_j2_type_orders(
            j1=j1,
            type_i_j2=type_i_j2,
            type_iii_j2=type_iii_j2,
            type_ii_j2=type_ii_j2,
        )


def test_henley_parser_extracts_pyrochlore_constraint_and_pinch_points():
    parsed, trace = (
        literature_runtime_evidence.parse_henley_pyrochlore_coulomb_phase(
            HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT
        )
    )

    assert parsed == {
        "zero_total_spin_per_tetrahedron": True,
        "pinch_points": True,
    }
    assert trace["parser"] == "parse_henley_pyrochlore_coulomb_phase"
    assert trace["source_role"] == (
        "direct corrective source adding the pinch-point result absent from "
        "the registered Moessner-Chalker 1998 paper"
    )
    assert trace["equations"] == ["1.2", "1.3", "1.5", "2.10"]
    assert trace["spin_scope"] == "isotropic classical n=3 Heisenberg"
    assert trace["pinch_point_locations"] == ["K_200", "K_111"]
    assert trace["registered_source_limitation"] == (
        "DOI 10.1103/PhysRevLett.80.2929 establishes L_alpha=0 but does not "
        "contain the pinch-point structure-factor result"
    )
    assert len(trace["matched_anchors"]) == 10
    assert len(trace["text_spans"]) == 10


def test_henley_parser_accepts_verified_two_column_layout_forms():
    parsed, trace = (
        literature_runtime_evidence.parse_henley_pyrochlore_coulomb_phase(
            HENLEY_PYROCHLORE_COULOMB_PHASE_TWO_COLUMN_TEXT
        )
    )

    assert parsed == {
        "zero_total_spin_per_tetrahedron": True,
        "pinch_points": True,
    }
    assert trace["two_column_layout_forms_accepted"] is True


@pytest.mark.parametrize(
    "source_text",
    [
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "POWER-LAW SPIN CORRELATIONS IN PYROCHLORE ANTIFERROMAGNETS",
            "SHORT-RANGE ORDER IN AN UNFRUSTRATED FERROMAGNET",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "arXiv:cond-mat/0407005v1", "arXiv:cond-mat/0407999v1"
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "zero-divergence condition", "unconstrained polarization field"
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "only nearest-neighbor antiferromagnetic exchange",
            "long-range ferromagnetic exchange",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "= (J_spin/2) sum_alpha L_alpha^2. (1.2)",
            "= an unspecified interaction energy. (1.2)",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "L_alpha = sum_(i in alpha) s_i. (1.3)",
            "L_alpha is not defined. (1.3)",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "L_alpha = 0 (1.5)\nis a classical ground state",
            "L_alpha is unrestricted (1.5)",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "isotropic n = 3 component spins",
            "anisotropic n = 2 component spins",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "q_perp^2 / (q_parallel^2 + q_perp^2). (2.10)",
            "an analytic constant. (2.10)",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "a pinch-point singularity of form (2.10) at K_200 and also\n"
            "K_111 reciprocal lattice vectors",
            "no reciprocal-space singularities",
        ),
        HENLEY_PYROCHLORE_COULOMB_PHASE_SOURCE_TEXT.replace(
            "exactly satisfies a divergence condition. The correlations\n"
            "have a pseudo-dipolar form",
            "has no local constraint and exponentially decaying correlations",
        ),
    ],
)
def test_henley_parser_fails_closed_without_complete_coulomb_phase_derivation(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Henley pyrochlore Coulomb phase"
    ):
        literature_runtime_evidence.parse_henley_pyrochlore_coulomb_phase(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2005])
def test_henley_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(
        RuntimeEvidenceError, match="Henley pyrochlore Coulomb phase"
    ):
        literature_runtime_evidence.parse_henley_pyrochlore_coulomb_phase(
            source_text
        )


def test_pyrochlore_coulomb_phase_recompute_checks_energy_and_directional_limits():
    assert (
        literature_runtime_evidence.recompute_pyrochlore_coulomb_phase(
            exchange=1.0,
            momentum_probe=1.0e-3,
        )
        == {
            "zero_total_spin_per_tetrahedron": True,
            "pinch_points": True,
        }
    )


@pytest.mark.parametrize(
    ("exchange", "momentum_probe"),
    [
        (True, 1.0e-3),
        (0.0, 1.0e-3),
        (1.0, False),
        (1.0, 0.0),
        (1.0, -1.0e-3),
        (1.0, math.inf),
        (1.0, math.nan),
    ],
)
def test_pyrochlore_coulomb_phase_recompute_rejects_invalid_probes(
    exchange, momentum_probe
):
    with pytest.raises(RuntimeEvidenceError, match="pyrochlore Coulomb phase"):
        literature_runtime_evidence.recompute_pyrochlore_coulomb_phase(
            exchange=exchange,
            momentum_probe=momentum_probe,
        )


def test_abramchuk_parser_extracts_cu2iro3_honeycomb_iridate_identity():
    parsed, trace = (
        literature_runtime_evidence.parse_abramchuk_cu2iro3_honeycomb_iridate(
            ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT
        )
    )

    assert parsed == {"honeycomb_frustrated_iridate_identity": True}
    assert trace["parser"] == (
        "parse_abramchuk_cu2iro3_honeycomb_iridate"
    )
    assert trace["doi"] == "10.1021/jacs.7b06911"
    assert trace["claim_scope"] == (
        "material identity and layered honeycomb structure only; no "
        "generic Kitaev- or Gamma-model projection"
    )
    assert len(trace["matched_anchors"]) == 7
    assert len(trace["text_spans"]) == 7


def test_abramchuk_parser_accepts_verified_two_column_layout_forms():
    parsed, trace = (
        literature_runtime_evidence.parse_abramchuk_cu2iro3_honeycomb_iridate(
            ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_TWO_COLUMN_TEXT
        )
    )

    assert parsed == {"honeycomb_frustrated_iridate_identity": True}
    assert trace["two_column_layout_forms_accepted"] is True


@pytest.mark.parametrize(
    "source_text",
    [
        ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
            "Cu2IrO3: A New Magnetically Frustrated Honeycomb Iridate",
            "Na2IrO3: An Unrelated Ordered Oxide",
        ),
        ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
            "10.1021/jacs.7b06911", "10.1021/jacs.7b00000"
        ),
        ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
            "the first copper iridium binary metal oxide with the\n"
            "chemical formula Cu2IrO3",
            "an unspecified mixed oxide",
        ),
        ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
            "same monoclinic space group (C2/c) as Na2IrO3\n"
            "with a layered honeycomb structure",
            "unresolved crystal structure",
        ),
        ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
            "edge-sharing (Ir2/3Cu1/3)O6\n"
            "octahedra in honeycomb layers",
            "isolated octahedra in a chain",
        ),
        ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
            "crystallizes in the C2/c space group\n"
            "with honeycomb layers of edge-sharing (Ir2/3Cu1/3)O6 octahedra",
            "has an unresolved bulk structure",
        ),
        ABRAMCHUK_CU2IRO3_HONEYCOMB_IRIDATE_SOURCE_TEXT.replace(
            "a new member of A2IrO3 honeycomb iridates",
            "not assigned to an iridate family",
        ),
    ],
)
def test_abramchuk_parser_fails_closed_without_complete_material_identity(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Abramchuk Cu2IrO3"):
        literature_runtime_evidence.parse_abramchuk_cu2iro3_honeycomb_iridate(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2017])
def test_abramchuk_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Abramchuk Cu2IrO3"):
        literature_runtime_evidence.parse_abramchuk_cu2iro3_honeycomb_iridate(
            source_text
        )


def test_enderle_parser_extracts_licuvo4_incommensurate_helical_order():
    parsed, trace = (
        literature_runtime_evidence.parse_enderle_licuvo4_incommensurate_helimagnet(
            ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT
        )
    )

    assert parsed == {"incommensurate_spiral_order": True}
    assert trace["parser"] == (
        "parse_enderle_licuvo4_incommensurate_helimagnet"
    )
    assert trace["doi"] == "10.1209/epl/i2004-10484-x"
    assert trace["propagation_vector_rlu"] == [0.0, 0.532, 0.0]
    assert trace["pitch_angle_degrees"] == pytest.approx(83.6)
    assert trace["exchange_hierarchy"] == {
        "J1": "ferromagnetic nearest-neighbour",
        "J2": "antiferromagnetic next-nearest-neighbour",
    }
    assert trace["claim_scope"] == (
        "observed incommensurate helical order in LiCuVO4; not a generic "
        "J1-J2-chain phase-diagram claim"
    )
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


def test_enderle_parser_accepts_verified_epl_layout_forms():
    parsed, trace = (
        literature_runtime_evidence.parse_enderle_licuvo4_incommensurate_helimagnet(
            ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_LAYOUT_TEXT
        )
    )

    assert parsed == {"incommensurate_spiral_order": True}
    assert trace["verified_epl_layout_forms_accepted"] is True


@pytest.mark.parametrize(
    "source_text",
    [
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "Quantum helimagnetism of the frustrated spin-1/2 chain LiCuVO4",
            "Collinear order in an unrelated square-lattice material",
        ),
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "10.1209/epl/i2004-10484-x", "10.1209/epl/i2004-00000-x"
        ),
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "nearest-neighbour ferromagnetic,\n"
            "next-nearest-neighbour frustrated, quasi-one-dimensional "
            "helimagnet",
            "unfrustrated collinear ferromagnet",
        ),
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "The magnetic structure is helical\n"
            "with propagation vector (0 0.532 0)",
            "The magnetic structure is unresolved",
        ),
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "ordered phase below TN = 2.1 K, verified by the\n"
            "presence of a magnetic Bragg peak",
            "paramagnetic phase without magnetic Bragg peaks",
        ),
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "ferromagnetic nearest-neighbour\n"
            "intrachain interaction J1, and antiferromagnetic "
            "next-nearest-neighbour\ninteraction J2",
            "two unspecified interactions",
        ),
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "incommensurability translates into a pitch angle\n"
            "of 83.6 +/- 0.6 degrees",
            "commensurability has no measured pitch",
        ),
        ENDERLE_LICUVO4_INCOMMENSURATE_HELIMAGNET_SOURCE_TEXT.replace(
            "frustrated FMnn-AFnnn chain model",
            "unfrustrated nearest-neighbour chain model",
        ),
    ],
)
def test_enderle_parser_fails_closed_without_complete_helimagnet_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Enderle LiCuVO4"):
        literature_runtime_evidence.parse_enderle_licuvo4_incommensurate_helimagnet(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2005])
def test_enderle_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Enderle LiCuVO4"):
        literature_runtime_evidence.parse_enderle_licuvo4_incommensurate_helimagnet(
            source_text
        )


def test_bak_jensen_parser_extracts_mnsi_long_wavelength_helix():
    parsed, trace = (
        literature_runtime_evidence.parse_bak_jensen_mnsi_long_wavelength_helix(
            BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT
        )
    )

    assert parsed == {"long_wavelength_helix": True}
    assert trace["parser"] == (
        "parse_bak_jensen_mnsi_long_wavelength_helix"
    )
    assert trace["doi"] == "10.1088/0022-3719/13/31/002"
    assert trace["wavevector_direction"] == [1, 1, 1]
    assert trace["wavevector_magnitude_inverse_angstrom"] == pytest.approx(
        0.036
    )
    assert trace["reported_period_angstrom"] == pytest.approx(175.0)
    assert trace["computed_period_angstrom"] == pytest.approx(
        2.0 * math.pi / 0.036
    )
    assert trace["mechanism"] == (
        "ferromagnetic Dzyaloshinskii instability"
    )
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


def test_bak_jensen_parser_accepts_verified_iop_scan_ocr_forms():
    parsed, trace = (
        literature_runtime_evidence.parse_bak_jensen_mnsi_long_wavelength_helix(
            BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_IOP_SCAN_TEXT
        )
    )

    assert parsed == {"long_wavelength_helix": True}
    assert trace["verified_iop_scan_ocr_forms_accepted"] is True
    assert trace["wavevector_direction"] == [1, 1, 1]
    assert trace["wavevector_magnitude_inverse_angstrom"] == pytest.approx(
        0.036
    )
    assert trace["reported_period_angstrom"] == pytest.approx(175.0)
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


@pytest.mark.parametrize(
    "source_text",
    [
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "Theory of helical magnetic structures and phase transitions in "
            "MnSi and FeGe",
            "Theory of collinear order in an inversion-symmetric oxide",
        ),
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "10.1088/0022-3719/13/31/002",
            "10.1088/0022-3719/13/31/999",
        ),
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "long-period helical magnetic structures in MnSi and FeGe are\n"
            "shown to be consequences of a ferromagnetic Dzyaloshinskii "
            "instability",
            "short-period collinear structures have an unknown origin",
        ),
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "helical magnetic structure in MnSi. The wavevector is found to "
            "be in the\n"
            "(111) direction, and it is rather small (0.036 A^-1), "
            "indicating a very long\nperiod (175 A)",
            "unresolved magnetic structure with no measured wavevector",
        ),
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "linear in the gradient, destabilises the ferromagnetic\n"
            "structure",
            "quadratic and leaves the ferromagnetic structure stable",
        ),
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "k = |b| / (B1 + B2/3). (6)\n"
            "The smallness of k follows from the smallness of b compared to "
            "B1 + B2/3",
            "k is unspecified. (6)",
        ),
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "S(r) = alpha_k cos(k dot r) - beta_k sin(k dot r). (7)\n"
            "This indeed describes left-handed or right-handed spirals with "
            "a long period",
            "S(r) is uniform. (7)",
        ),
        BAK_JENSEN_MNSI_LONG_WAVELENGTH_HELIX_SOURCE_TEXT.replace(
            "helical magnetic structures in\n"
            "MnSi and FeGe are caused by a ferromagnetic Dzyaloshinskii "
            "instability",
            "collinear structures have no identified mechanism",
        ),
    ],
)
def test_bak_jensen_parser_fails_closed_without_complete_long_helix_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Bak-Jensen MnSi"):
        literature_runtime_evidence.parse_bak_jensen_mnsi_long_wavelength_helix(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1980])
def test_bak_jensen_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Bak-Jensen MnSi"):
        literature_runtime_evidence.parse_bak_jensen_mnsi_long_wavelength_helix(
            source_text
        )


def test_seki_parser_extracts_cu2oseo3_skyrmion_lattice_phase():
    parsed, trace = (
        literature_runtime_evidence.parse_seki_cu2oseo3_skyrmion_lattice_phase(
            SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT
        )
    )

    assert parsed == {"skyrmion_lattice_phase": True}
    assert trace["parser"] == (
        "parse_seki_cu2oseo3_skyrmion_lattice_phase"
    )
    assert trace["doi"] == "10.1126/science.1214143"
    assert trace["thin_film_skyrmion_field_oe"] == pytest.approx(800.0)
    assert trace["skyrmion_disappearance_field_oe"] == pytest.approx(1800.0)
    assert trace["helical_modulation_period_nm"] == pytest.approx(50.0)
    assert trace["bulk_phase_assignment"] == "A phase = SkX state"
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


def test_seki_parser_accepts_verified_science_layout_hyphenation():
    parsed, trace = (
        literature_runtime_evidence.parse_seki_cu2oseo3_skyrmion_lattice_phase(
            SEKI_CU2OSEO3_SKYRMION_LATTICE_SCIENCE_LAYOUT_TEXT
        )
    )

    assert parsed == {"skyrmion_lattice_phase": True}
    assert trace["verified_science_layout_hyphenation_accepted"] is True
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


@pytest.mark.parametrize(
    "source_text",
    [
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "Observation of Skyrmions in a Multiferroic Material",
            "Observation of a Collinear State in a Centrosymmetric Material",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "10.1126/science.1214143",
            "10.1126/science.1214999",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "experimental discovery of\n"
            "magnetoelectric skyrmions in an insulating chiral-lattice "
            "magnet Cu2OSeO3\n"
            "through Lorentz transmission electron microscopy and magnetic "
            "susceptibility\nmeasurements",
            "unconfirmed texture in an unspecified conductor",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "(cubic and chiral) P213",
            "(centrosymmetric) Pnma",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "formation\nof a triangular lattice of skyrmions is observed both "
            "for the (110) and (111)\nplanes",
            "absence of any field-induced texture",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "a skyrmion lattice with identical spin chirality is formed for\n"
            "H = 800 Oe",
            "a collinear state is formed at all fields",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "determined through the measurement of skyrmion density.\n"
            "Skyrmions disappear for H > 1800 Oe",
            "not determined from real-space observations",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "observed A phase represents the SkX\n"
            "state in the bulk form of Cu2OSeO3",
            "A phase remains unidentified in the bulk",
        ),
        SEKI_CU2OSEO3_SKYRMION_LATTICE_SOURCE_TEXT.replace(
            "narrow A phase (SkX state) region",
            "narrow A phase of unknown origin",
        ),
    ],
)
def test_seki_parser_fails_closed_without_complete_skyrmion_chain(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Seki Cu2OSeO3"):
        literature_runtime_evidence.parse_seki_cu2oseo3_skyrmion_lattice_phase(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2012])
def test_seki_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Seki Cu2OSeO3"):
        literature_runtime_evidence.parse_seki_cu2oseo3_skyrmion_lattice_phase(
            source_text
        )


def test_wernsdorfer_parser_extracts_fe8_quantum_tunneling_observation():
    parsed, trace = (
        literature_runtime_evidence.parse_wernsdorfer_sessoli_fe8_quantum_tunneling(
            WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT
        )
    )

    assert parsed == {"macroscopic_quantum_tunneling_observed": True}
    assert trace["parser"] == (
        "parse_wernsdorfer_sessoli_fe8_quantum_tunneling"
    )
    assert trace["doi"] == "10.1126/science.284.5411.133"
    assert trace["spin_ground_state"] == pytest.approx(10.0)
    assert trace["pure_quantum_regime_below_k"] == pytest.approx(0.4)
    assert trace["resonance_step_tesla"] == pytest.approx(0.22)
    assert trace["tunnel_splitting_oscillation_period_tesla"] == pytest.approx(
        0.41
    )
    assert trace["method"] == "micro-SQUID Landau-Zener"
    assert len(trace["matched_anchors"]) == 9
    assert len(trace["text_spans"]) == 9


def test_wernsdorfer_parser_accepts_verified_science_webprint_layout():
    parsed, trace = (
        literature_runtime_evidence
        .parse_wernsdorfer_sessoli_fe8_quantum_tunneling(
            WERNSDORFER_SESSOLI_FE8_SCIENCE_WEBPRINT_LAYOUT_TEXT
        )
    )

    assert parsed == {"macroscopic_quantum_tunneling_observed": True}
    assert trace["doi"] == "10.1126/science.284.5411.133"
    assert trace["verified_science_webprint_identity_accepted"] is True
    assert trace["resonance_step_tesla"] == pytest.approx(0.22)
    assert trace["tunnel_splitting_oscillation_period_tesla"] == pytest.approx(
        0.41
    )


@pytest.mark.parametrize(
    "source_text",
    [
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "Quantum Phase Interference and Parity Effects in Magnetic "
            "Molecular Clusters",
            "Classical Relaxation in a Bulk Ferromagnet",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "10.1126/science.284.5411.133",
            "10.1126/science.284.5411.999",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "molecular clusters of eight iron\n"
            "atoms, which at low temperature behave like a nanomagnet with "
            "a spin ground\nstate of S = 10",
            "a nonmagnetic molecular cluster with spin zero",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "Ising-type magneto-crystalline anisotropy, which\n"
            "generates an energy barrier for reversal of the magnetization "
            "of about 25 K\nfor Fe8",
            "isotropic response with no reversal barrier",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "relaxation time becomes temperature independent below\n"
            "360 mK, showing that a pure tunneling mechanism between the "
            "only populated\nM = +/-10 states is responsible",
            "relaxation remains thermally activated at all temperatures",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "Resonant tunneling is evidenced by six equally\n"
            "separated steps. Below 0.4 K, the hysteresis loops are "
            "temperature\nindependent, demonstrating the pure quantum regime",
            "No tunneling steps or quantum regime were observed",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "Resonant tunneling is\n"
            "evidenced by six equally separated steps of Delta Hz = 0.22 T",
            "The hysteresis curve is featureless",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "This procedure yields the tunneling rate\n"
            "P and thus the tunnel splitting. We found good agreement for "
            "sweeping rates\nbetween 0.5 and 0.001 T/s",
            "This procedure was not compared with the Landau-Zener model",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "tunneling rate oscillates with a period between minima of\n"
            "0.41 T. The corresponding tunnel splittings oscillate with "
            "almost the same\nperiod of 0.41 T",
            "tunneling rate is monotonic with field",
        ),
        WERNSDORFER_SESSOLI_FE8_QUANTUM_TUNNELING_SOURCE_TEXT.replace(
            "very clear oscillation in the tunnel splittings, which is "
            "direct\n"
            "evidence of the role of the topological spin phase",
            "feature too weak to establish a quantum mechanism",
        ),
    ],
)
def test_wernsdorfer_parser_fails_closed_without_complete_tunneling_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Wernsdorfer-Sessoli Fe8"):
        literature_runtime_evidence.parse_wernsdorfer_sessoli_fe8_quantum_tunneling(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1999])
def test_wernsdorfer_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Wernsdorfer-Sessoli Fe8"):
        literature_runtime_evidence.parse_wernsdorfer_sessoli_fe8_quantum_tunneling(
            source_text
        )


def test_kitagawa_parser_extracts_h3liir2o6_no_order_report():
    parsed, trace = (
        literature_runtime_evidence
        .parse_kitagawa_h3liir2o6_no_magnetic_order(
            KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT
        )
    )

    assert parsed == {"no_magnetic_order_reported": True}
    assert trace["parser"] == (
        "parse_kitagawa_h3liir2o6_no_magnetic_order"
    )
    assert trace["doi"] == "10.1038/nature25482"
    assert trace["no_order_down_to_k"] == pytest.approx(0.05)
    assert trace["interaction_energy_k"] == pytest.approx(100.0)
    assert trace["nmr_spin_liquid_floor_k"] == pytest.approx(1.0)
    assert trace["source_representation"] == (
        "Nature publisher article-page text"
    )
    assert trace["claim_scope"] == (
        "the source reports no magnetic ordering in H3LiIr2O6 down to "
        "0.05 K; it does not by itself prove an ideal disorder-free "
        "Kitaev spin liquid"
    )
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


@pytest.mark.parametrize(
    "source_text",
    [
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "A spin-orbital-entangled quantum liquid on a honeycomb lattice",
            "Magnetic order in a square-lattice metal",
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "K. Kitagawa", "K. Example"
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "10.1038/nature25482", "10.1038/nature99999"
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "interacting spins remain quantum-disordered without "
            "spontaneous symmetry\nbreaking",
            "interacting spins develop conventional long-range order",
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "5d-electron honeycomb compound H3LiIr2O6",
            "3d-electron square-lattice compound Example2O3",
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "does not display magnetic ordering down to 0.05 kelvin, "
            "despite\nan interaction energy of about 100 kelvin",
            "orders magnetically at 15 kelvin",
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "nuclear-magnetic-resonance relaxation and the specific heat",
            "an uncalibrated optical image",
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "We therefore\nconclude that H3LiIr2O6 is a quantum spin liquid",
            "We therefore conclude that the sample is a conventional magnet",
        ),
        KITAGAWA_H3LIIR2O6_QUANTUM_LIQUID_SOURCE_TEXT.replace(
            "Evidence from NMR spectroscopy of a spin-liquid ground state",
            "No NMR evidence for a spin-liquid ground state",
        ),
    ],
)
def test_kitagawa_parser_fails_closed_without_complete_no_order_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Kitagawa H3LiIr2O6"):
        literature_runtime_evidence.parse_kitagawa_h3liir2o6_no_magnetic_order(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2018])
def test_kitagawa_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Kitagawa H3LiIr2O6"):
        literature_runtime_evidence.parse_kitagawa_h3liir2o6_no_magnetic_order(
            source_text
        )


def test_ramirez_parser_extracts_dy2ti2o7_pauling_entropy_observation():
    parsed, trace = (
        literature_runtime_evidence
        .parse_ramirez_dy2ti2o7_pauling_entropy(
            RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT
        )
    )

    assert parsed == {"pauling_entropy_observed": True}
    assert trace["parser"] == "parse_ramirez_dy2ti2o7_pauling_entropy"
    assert trace["doi"] == "10.1038/20619"
    assert trace["measured_entropy_fraction_of_r_ln2"] == pytest.approx(0.67)
    assert trace["water_ice_entropy_fraction_of_r_ln2"] == pytest.approx(0.71)
    assert trace["pauling_released_entropy_fraction_of_r_ln2"] == (
        pytest.approx(
            (math.log(2.0) - 0.5 * math.log(1.5)) / math.log(2.0)
        )
    )
    assert trace["pauling_residual_entropy_over_r"] == pytest.approx(
        0.5 * math.log(1.5)
    )
    assert trace["claim_scope"] == (
        "the 1999 calorimetry reports an apparent Pauling residual entropy "
        "for Dy2Ti2O7 over its experimental equilibration window; no claim "
        "is made about the infinitely equilibrated T=0 limit"
    )
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


@pytest.mark.parametrize(
    "source_text",
    [
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "Zero-point entropy in 'spin ice'",
            "Conventional order in an unfrustrated magnet",
        ),
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "A. P. Ramirez", "A. P. Example"
        ),
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "10.1038/20619", "10.1038/99999"
        ),
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "macroscopic\n"
            "degeneracy of possible ground states, such that the system "
            "has finite entropy\nas the temperature tends towards zero",
            "unique ground state with zero entropy at every temperature",
        ),
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "magnet with\n"
            "the pyrochlore structure--termed 'spin ice'--where spin "
            "orientation plays a\nsimilar role",
            "square-lattice ferromagnet without an ice correspondence",
        ),
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "specific-heat data for one such system, Dy2Ti2O7, from which\n"
            "we infer a total spin entropy of 0.67 R ln 2. This is similar "
            "to the value,\n0.71 R ln 2, determined for ice I_h",
            "susceptibility data for an unrelated compound",
        ),
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "restoration of much of the ground-state entropy and new "
            "transitions involving\ntransverse spin degrees of freedom",
            "no field-dependent entropy response",
        ),
        RAMIREZ_DY2TI2O7_PAULING_ENTROPY_SOURCE_TEXT.replace(
            "agreement with Pauling's prediction for the entropy of water "
            "ice I_h,\nR (ln 2 - (1/2) ln (3/2))",
            "disagreement with every ice-model entropy prediction",
        ),
    ],
)
def test_ramirez_parser_fails_closed_without_complete_entropy_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Ramirez Dy2Ti2O7"):
        literature_runtime_evidence.parse_ramirez_dy2ti2o7_pauling_entropy(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1999])
def test_ramirez_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Ramirez Dy2Ti2O7"):
        literature_runtime_evidence.parse_ramirez_dy2ti2o7_pauling_entropy(
            source_text
        )


def test_carteaux_parser_extracts_cr2ge2te6_bulk_ferromagnetic_order():
    parsed, trace = (
        literature_runtime_evidence
        .parse_carteaux_cr2ge2te6_ferromagnetic_order(
            CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT
        )
    )

    assert parsed == {"ferromagnetic_order": True}
    assert trace["parser"] == (
        "parse_carteaux_cr2ge2te6_ferromagnetic_order"
    )
    assert trace["doi"] == "10.1088/0953-8984/7/1/008"
    assert trace["curie_temperature_k"] == pytest.approx(61.0)
    assert trace["spin_axis"] == "c"
    assert trace["ordered_moment_mu_b"] == pytest.approx(2.80)
    assert trace["ordered_moment_uncertainty_mu_b"] == pytest.approx(0.04)
    assert trace["ordered_moment_temperature_k"] == pytest.approx(5.0)
    assert trace["space_group"] == "R3"
    assert trace["source_representation"] == (
        "IOP publisher issue-page abstract text"
    )
    assert trace["registry_material_alias"] == (
        "CrGeTe3 is the reduced-formula shorthand for Cr2Ge2Te6"
    )
    assert trace["claim_scope"] == (
        "bulk Cr2Ge2Te6 ferromagnetic order below 61 K; no claim is made "
        "about the monolayer limit or an ideal honeycomb Heisenberg model"
    )
    assert len(trace["matched_anchors"]) == 7
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "Crystallographic, magnetic and electronic structures of a new "
            "layered\nferromagnetic compound Cr₂Ge₂Te₆",
            "Electronic structure of an unrelated square-lattice compound",
        ),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "V Carteaux", "V Example"
        ),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "issue 1, volume 7", "issue 9, volume 70"
        ),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "\n69\n", "\n70\n"
        ),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "10.1088/0953-8984/7/1/008",
            "10.1088/0953-8984/7/1/999",
        ),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "new layered material belonging to the lamellar ternary\n"
            "M₂X₂Te₆ chalcogenides family",
            "three-dimensional cubic material",
        ).replace("rhombohedral, of space\ngroup R3", "cubic, of space group Fm-3m"),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "X-ray single-crystal\ndiffraction and neutron powder diffraction",
            "an uncalibrated optical image",
        ),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "neutron powder diffraction\n"
            "and susceptibility and magnetization measurements",
            "a mean-field calculation",
        ),
        CARTEAUX_CR2GE2TE6_FERROMAGNETIC_ORDER_SOURCE_TEXT.replace(
            "Below 61 K, Cr₂Ge₂Te₆ is\n"
            "ferromagnetic with spins aligned along the c axis of the cell\n"
            "(mu (Cr³⁺)=2.80(4)_(mu B) at 5 K)",
            "Below 61 K, Cr₂Ge₂Te₆ remains paramagnetic",
        ),
    ],
)
def test_carteaux_parser_fails_closed_without_complete_ferromagnetic_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Carteaux Cr2Ge2Te6"):
        literature_runtime_evidence.parse_carteaux_cr2ge2te6_ferromagnetic_order(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1995])
def test_carteaux_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Carteaux Cr2Ge2Te6"):
        literature_runtime_evidence.parse_carteaux_cr2ge2te6_ferromagnetic_order(
            source_text
        )


def test_cable_parser_extracts_crcl3_ferromagnetic_hexagonal_layers():
    parsed, trace = (
        literature_runtime_evidence.parse_cable_crcl3_ferromagnetic_layers(
            CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT
        )
    )

    assert parsed == {"ferromagnetic_honeycomb_layers": True}
    assert trace["parser"] == "parse_cable_crcl3_ferromagnetic_layers"
    assert trace["doi"] == "10.1016/0022-3697(61)90053-1"
    assert trace["measurement"] == "neutron diffraction"
    assert trace["sample_temperature_range_k"] == pytest.approx([4.2, 298.0])
    assert trace["transition_temperature_k"] == pytest.approx(16.8)
    assert trace["intralayer_alignment"] == "parallel"
    assert trace["interlayer_alignment"] == "opposite"
    assert trace["bulk_order"] == (
        "A-type antiferromagnetic stacking of ferromagnetic layers"
    )
    assert trace["source_representation"] == (
        "Elsevier ScienceDirect publisher abstract text"
    )
    assert trace["claim_scope"] == (
        "ferromagnetic alignment within bulk CrCl3 hexagonal metal-ion "
        "layers, stacked antiferromagnetically; no claim is made that the "
        "bulk crystal is a ferromagnet or about an isolated-monolayer Tc"
    )
    assert len(trace["matched_anchors"]) == 8
    assert len(trace["text_spans"]) == 8


@pytest.mark.parametrize(
    "source_text",
    [
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "Neutron diffraction investigation of antiferromagnetism in CrCl3",
            "Optical investigation of a nonmagnetic cubic material",
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "J. W. Cable", "J. W. Example"
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "Volume 19, Issues 1-2, April 1961, Pages 29-34",
            "Volume 91, Issue 8, April 1999, Pages 290-340",
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "10.1016/0022-3697(61)90053-1",
            "10.1016/0022-3697(61)99999-9",
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "powder and single crystal\n"
            "samples of anhydrous CrCl3 at temperatures from 298 to 4.2 K",
            "a calculated hydrated sample at one unspecified temperature",
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "hexagonal\n"
            "layer-type crystal undergoes a transition at 16.8 K to an "
            "antiferromagnetic\nstate",
            "cubic crystal has no magnetic transition",
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "magnetic moments within each hexagonal layer of metal ions\n"
            "are aligned parallel but adjacent layers of moments are "
            "oppositely directed",
            "moments are disordered both within and between every layer",
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "spontaneous sublattice magnetization is closely perpendicular to\n"
            "the c-axis",
            "sublattice magnetization direction was not determined",
        ),
        CABLE_CRCL3_FERROMAGNETIC_LAYERS_SOURCE_TEXT.replace(
            "(003) antiferromagnetic reflection in an\n"
            "external magnetic field show that the antiferromagnetism can be "
            "destroyed with\nfields of only a few kilo-oersteds",
            "optical reflection is independent of every applied field",
        ),
    ],
)
def test_cable_parser_fails_closed_without_complete_layer_order_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Cable CrCl3"):
        literature_runtime_evidence.parse_cable_crcl3_ferromagnetic_layers(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1961])
def test_cable_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Cable CrCl3"):
        literature_runtime_evidence.parse_cable_crcl3_ferromagnetic_layers(
            source_text
        )


def test_ressouche_parser_extracts_bulk_mnps3_neel_order():
    parsed, trace = (
        literature_runtime_evidence.parse_ressouche_mnps3_neel_order(
            RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT
        )
    )

    assert parsed == {"neel_order_reference": True}
    assert trace["parser"] == "parse_ressouche_mnps3_neel_order"
    assert trace["doi"] == "10.1103/PhysRevB.82.100408"
    assert trace["transition_temperature_k"] == pytest.approx(78.0)
    assert trace["propagation_vector"] == [0, 0, 0]
    assert trace["mn_spin"] == pytest.approx(2.5)
    assert trace["intralayer_order"] == (
        "nearest-neighbor antiparallel on the Mn2+ honeycomb lattice"
    )
    assert trace["interlayer_coupling"] == "ferromagnetic"
    assert trace["source_role"] == (
        "machine-extractable supplemental direct primary research source"
    )
    assert trace["registered_source_relationship"] == (
        "DOI 10.1088/0953-8984/10/28/020 measures MnPS3 spin waves and "
        "the magnetic (020) Bragg order parameter; Ressouche et al. "
        "directly resolve and neutron-polarimetry-test the honeycomb Neel "
        "topology"
    )
    assert trace["claim_scope"] == (
        "bulk MnPS3 nearest-neighbor Neel topology below 78 K; no claim "
        "is made about an isolated monolayer transition or an ideal "
        "two-dimensional Heisenberg theorem"
    )
    assert len(trace["matched_anchors"]) == 7
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "Magnetoelectric MnPS3 as a candidate for ferrotoroidicity",
            "Transport in an unrelated nonmagnetic compound",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "E. Ressouche", "E. Example"
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "10.1103/PhysRevB.82.100408",
            "10.1103/PhysRevB.82.999999",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "using neutron diffraction and polarimetry",
            "using only an uncalibrated optical image",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "collinear antiferromagnetic order at 78 K",
            "paramagnetic response down to 1 K",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "Mn2+ with spin 5/2", "Mn2+ with spin 1/2"
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "form a honeycomb lattice", "form a triangular lattice"
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "integrated\nintensities collected on D15 at 10 K",
            "a room-temperature structural calculation",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "zero propagation vector", "nonzero propagation vector"
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "+−+− sequence", "++++ sequence"
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "each Mn2+ is antiferromagnetically coupled with its nearest "
            "neighbors",
            "each Mn2+ is ferromagnetically coupled with its nearest "
            "neighbors",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "coupling between adjacent planes is ferromagnetic",
            "coupling between adjacent planes was not determined",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "stringent\ntest of CRYOPAD",
            "untested magnetic-structure conjecture",
        ),
        RESSOUCHE_MNPS3_NEEL_ORDER_SOURCE_TEXT.replace(
            "99 observations were fitted\n"
            "using the magnetic structure described before",
            "no observations were compared with the proposed structure",
        ),
    ],
)
def test_ressouche_parser_fails_closed_without_complete_neel_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Ressouche MnPS3"):
        literature_runtime_evidence.parse_ressouche_mnps3_neel_order(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2010])
def test_ressouche_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Ressouche MnPS3"):
        literature_runtime_evidence.parse_ressouche_mnps3_neel_order(
            source_text
        )


def test_furuchi_parser_derives_lieb_lattice_ground_state_spin_per_cell():
    parsed, trace = (
        literature_runtime_evidence
        .parse_furuchi_lieb_lattice_ground_state_spin(
            FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT
        )
    )

    assert parsed == {"ground_state_spin_per_unit_cell": pytest.approx(0.5)}
    assert trace["parser"] == (
        "parse_furuchi_lieb_lattice_ground_state_spin"
    )
    assert trace["source_identity"] == "arXiv:2409.16715v1"
    assert trace["registered_doi"] == "10.1063/1.1724276"
    assert trace["primitive_cell_sublattice_counts"] == {"U": 2, "D": 1}
    assert trace["site_spin"] == pytest.approx(0.5)
    assert trace["theorem_spin_per_unit_cell"] == pytest.approx(0.5)
    assert trace["finite_cluster_spin_per_unit_cell"] == pytest.approx(
        [0.5, 0.5, 0.5]
    )
    assert trace["finite_cluster_sizes"] == [30, 36, 42]
    assert trace["finite_cluster_ground_state_spins"] == [5, 6, 7]
    assert trace["source_role"] == (
        "machine-extractable supplemental direct primary research source"
    )
    assert trace["registered_source_relationship"] == (
        "Lieb-Mattis 1962 supplies the registered general bipartite "
        "energy-ordering theorem; Furuchi et al. supply the target Lieb-"
        "lattice 2:1 primitive-cell sublattice counts and eta=0 spin "
        "normalization"
    )
    assert trace["claim_scope"] == (
        "unfrustrated eta=0 spin-1/2 Lieb-lattice Heisenberg "
        "antiferromagnet; the 1/2-per-cell theorem value is not extended "
        "to finite J-prime frustration"
    )
    assert len(trace["matched_anchors"]) == 7
    assert len(trace["text_spans"]) == 7


@pytest.mark.parametrize(
    "source_text",
    [
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "Collapsing Behavior of the Ferrimagnetic Ground State",
            "Unrelated transport behavior",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "Rito Furuchi", "Rito Example"
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "arXiv:2409.16715v1", "arXiv:2409.00000v1"
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "S = 1/2 Heisenberg antiferromagnet on the Lieb lattice",
            "S = 1 Heisenberg ferromagnet on the square lattice",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "ferrimagnetic ground state in the absence of frustration",
            "nonmagnetic state in the absence of frustration",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "Marshall-Lieb-Mattis (MLM) theorem",
            "an unrelated mean-field conjecture",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "J S_i dot S_j\n"
            "  + sum_<i in U,j in U> J' S_i dot S_j",
            "J n_i n_j + an onsite potential",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "S_i denotes the S = 1/2 spin operator",
            "S_i denotes the S = 1 spin operator",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "sublattice U\nand D are 2 and 1, respectively",
            "sublattice U and D are 2 and 2, respectively",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "This difference in the number of sites leads\n"
            "to the occurrence of a ferrimagnetic ground state",
            "The balanced sublattices produce a singlet ground state",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "ferrimagnetic ground state appears for eta = 0",
            "ferrimagnetic ground state appears only for eta = 1",
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "M_sat = N/2", "M_sat = N"
        ),
        FURUCHI_LIEB_LATTICE_FERRIMAGNET_SOURCE_TEXT.replace(
            "N = 30, 36, and 42 correspond\n"
            "to M_spo = 5, 6, and 7",
            "N = 30, 36, and 42 correspond to M_spo = 5, 6, and 8",
        ),
    ],
)
def test_furuchi_parser_fails_closed_without_complete_per_cell_derivation(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Furuchi Lieb lattice"):
        literature_runtime_evidence.parse_furuchi_lieb_lattice_ground_state_spin(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2024])
def test_furuchi_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Furuchi Lieb lattice"):
        literature_runtime_evidence.parse_furuchi_lieb_lattice_ground_state_spin(
            source_text
        )


def test_hsieh_parser_extracts_nacro2_unconventional_spin_order():
    parsed, trace = (
        literature_runtime_evidence
        .parse_hsieh_nacro2_unconventional_spin_order(
            HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT
        )
    )

    assert parsed == {"unconventional_spin_order_reference": True}
    assert trace["parser"] == (
        "parse_hsieh_nacro2_unconventional_spin_order"
    )
    assert trace["source_identity"] == "arXiv:1405.6184v1"
    assert trace["registered_doi"] == "10.1016/j.physb.2007.10.295"
    assert trace["material"] == "NaCrO2"
    assert trace["cr_spin"] == pytest.approx(1.5)
    assert trace["spin_freezing_onset_k"] == pytest.approx(41.0)
    assert trace["crossover_fraction_tc"] == pytest.approx(0.75)
    assert trace["two_dimensional_order_temperature_k"] == pytest.approx(
        40.0
    )
    assert trace["incommensuration_temperature_k"] == pytest.approx(30.0)
    assert trace["minimum_measurement_temperature_k"] == pytest.approx(1.5)
    assert trace["c_axis_correlation_length_upper_bound_angstrom"] == (
        pytest.approx(16.0)
    )
    assert trace["interplane_layer_count_at_40k"] == 2
    assert trace["low_temperature_correlated_layer_count"] == 4
    assert trace["low_temperature_order"] == (
        "short-range three-dimensional correlations without magnetic "
        "long-range order"
    )
    assert trace["source_role"] == (
        "machine-extractable expanded direct primary research source"
    )
    assert trace["registered_source_relationship"] == (
        "The registered 2008 Physica B article reports the same "
        "NaCrO2 neutron-scattering dimensional crossover; "
        "arXiv:1405.6184v1 is the expanded primary account that supplies "
        "the spin, wave-vector, layer-count, and correlation-length "
        "anchors."
    )
    assert trace["registry_name_note"] == (
        "The benchmark key says nacuo2, but its registered source and "
        "model parameters identify NaCrO2; no NaCuO2 claim is made."
    )
    assert trace["claim_scope"] == (
        "bulk rhombohedrally stacked S=3/2 NaCrO2: a 2D 120-degree "
        "correlated regime crosses into short-range, not long-range, "
        "three-dimensional order through a small incommensuration"
    )
    assert len(trace["matched_anchors"]) == 10
    assert len(trace["text_spans"]) == 10


def test_stodter_parser_accepts_verified_pdf_layout_page_break_forms():
    layout_text = (
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "The couplings J1",
            "The cou-\n\f"
            "                                                               3\n"
            "plings J1",
        ).replace(
            "lead to a weak ferromagnetic network",
            "lead to a weak     T (K)     m a g\n"
            "ferromagnetic network",
        )
    )

    parsed, trace = (
        literature_runtime_evidence
        .parse_stodter_clinoatacamite_distorted_kagome_exchange(layout_text)
    )

    assert parsed == {"distorted_kagome_reference": True}
    assert trace["exchange_values_k"]["J1"] == pytest.approx(-6.8)
    assert trace["exchange_values_k"]["J6"] == pytest.approx(367.7)
    assert trace["reported_interlayer_bound_over_j6"] == pytest.approx(
        0.082
    )
    assert len(trace["matched_anchors"]) == 10
    assert len(trace["text_spans"]) == 10


@pytest.mark.parametrize(
    "source_text",
    [
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "Spin Order by Quantum Frustration",
            "Charge Transport without Magnetic Frustration",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "D. Hsieh", "D. Example"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "high resolution neutron scattering measurements",
            "uncalibrated optical measurements",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "Tc approximately 41 K", "Tc approximately 14 K"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "T approximately 0.75 Tc", "T approximately 0.50 Tc"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "a small incommensuration develops",
            "a commensurate structural peak develops",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "antiferromagnet is the 120-degree spin structure",
            "antiferromagnet is a 90-degree spin structure",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "No magnetic long-range order is\nobserved down to 1.5 K",
            "Magnetic long-range order is observed down to 1.5 K",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "(S = 3/2) ions", "(S = 1/2) ions"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "form a rhombohedrally stacked triangular lattice",
            "form a directly stacked square lattice",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "A 15 g powder sample of NaCrO2",
            "A 1 g powder sample of an unrelated compound",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "NIST Center for Neutron Research",
            "unidentified optical laboratory",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "40 K (N = 2)", "40 K (N = 3)"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "N saturates to 4 from", "N saturates to 8 from"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "xi_c is indeed short-range", "xi_c is resolution-limited"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "(0, 4 pi/3a, 0)", "(0, 0, 0)"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "wave vector at 40 K points to a 120-degree arrangement",
            "wave vector at 40 K points to a 90-degree arrangement",
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "incommensuration at 30 K", "incommensuration at 20 K"
        ),
        HSIEH_NACRO2_UNCONVENTIONAL_SPIN_ORDER_SOURCE_TEXT.replace(
            "reveal a rare 2D\nantiferromagnetic phase in NaCrO2",
            "reveal a conventional 3D ferromagnetic phase in NaCrO2",
        ),
    ],
)
def test_hsieh_parser_fails_closed_without_complete_unconventional_order_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Hsieh NaCrO2"):
        literature_runtime_evidence.parse_hsieh_nacro2_unconventional_spin_order(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2014])
def test_hsieh_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Hsieh NaCrO2"):
        literature_runtime_evidence.parse_hsieh_nacro2_unconventional_spin_order(
            source_text
        )


def test_yang_xie_blume_capel_parser_extracts_square_zero_t_crossing():
    parsed, trace = (
        literature_runtime_evidence
        .parse_yang_xie_square_blume_capel_crossing(
            YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT
        )
    )

    assert parsed == {"square_lattice_d_over_j_crossing": 2.0}
    assert trace["parser"] == (
        "parse_yang_xie_square_blume_capel_crossing"
    )
    assert trace["source_identity"] == "arXiv:1204.5027v2"
    assert trace["registered_doi"] == "10.1103/PhysRev.141.517"
    assert trace["corrected_original_doi"] == (
        "10.1016/0031-8914(66)90027-9"
    )
    assert trace["source_equations"] == ["1", "2", "3"]
    assert trace["spin"] == 1
    assert trace["coordination_number"] == 4
    assert trace["zero_field"] is True
    assert trace["ferromagnetic_exchange"] is True
    assert trace["crossing_condition"] == "D=qJ/2"
    assert trace["source_crossing_ratio"] == pytest.approx(2.0)
    assert trace["ordered_exchange_energy_per_site_over_j"] == pytest.approx(
        -2.0
    )
    assert trace["ordered_anisotropy_energy_per_site_over_j"] == pytest.approx(
        2.0
    )
    assert trace["zero_state_energy_per_site_over_j"] == pytest.approx(0.0)
    assert trace["source_role"] == (
        "machine-extractable supplemental direct primary research source"
    )
    assert trace["registered_source_correction"] == (
        "The registered DOI identifies Blume's UO2 paper; Capel 1966 "
        "DOI 10.1016/0031-8914(66)90027-9 is the matching original "
        "triplet-ion zero-field-splitting source. Yang-Xie "
        "1204.5027v2 cites both and supplies the exact -J sum + D sum "
        "convention used by the registry."
    )
    assert trace["claim_scope"] == (
        "zero-field ferromagnetic spin-1 Blume-Capel model on the "
        "square lattice at T=0; the product-state level crossing is "
        "exact, while no finite-temperature tensor result is used"
    )
    assert len(trace["matched_anchors"]) == 10
    assert len(trace["text_spans"]) == 10


@pytest.mark.parametrize(
    "source_text",
    [
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "The tensor renormalization group study of the general "
            "spin-S Blume-Capel model",
            "Unrelated transport study of a spinless fermion model",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "Li-Ping Yang and Zhi-Yuan Xie",
            "Example Author and Example Collaborator",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "arXiv:1204.5027v2", "arXiv:1204.0000v2"
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "special situation of D = 2J",
            "generic situation with no specified anisotropy",
            1,
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "model on the square lattice",
            "model on the triangular lattice",
            1,
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "H = -J sum_<i,j> S_i S_j",
            "H = +J sum_<i,j> S_i S_j",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "+ D sum_i S_i^2", "+ D sum_i S_i"
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "- h sum_i S_i^z", "- h sum_i (S_i^z)^2"
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "we consider the case of h = 0",
            "we consider an unspecified nonzero field",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "D(S_i^2 + S_j^2)/q",
            "D(S_i + S_j)/q",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "(D/q - J/2)(S_i^2 + S_j^2)",
            "(D/q + J/2)(S_i^2 + S_j^2)",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "ferromagnetic coupling (J > 0)",
            "antiferromagnetic coupling (J < 0)",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "when D > qJ/2", "when D > qJ/3"
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "When D < qJ/2", "When D < qJ/3"
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "D = qJ/2", "D = qJ/3", 1
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "Then q = 4 and\nD = 2J is the special parameter",
            "Then q = 6 and D = 3J is the special parameter",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "(T/J, D/J) = (0, 2)",
            "(T/J, D/J) = (0, 3)",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "In the case of S = 1, there are three optional values: "
            "+/-1 and 0",
            "In the case of S = 2, there are five optional values",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "M. Blume, Phys. Rev. 141, 517 (1966)",
            "M. Blume, Phys. Rev. 141, 999 (1966)",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "H. W. Capel,\n    Physica 32, 966 (1966)",
            "H. W. Example, Physica 32, 999 (1966)",
        ),
    ],
)
def test_yang_xie_blume_capel_parser_fails_closed_without_full_crossing_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Yang-Xie Blume-Capel"):
        literature_runtime_evidence.parse_yang_xie_square_blume_capel_crossing(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2015])
def test_yang_xie_blume_capel_parser_rejects_non_text_or_empty_source(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Yang-Xie Blume-Capel"):
        literature_runtime_evidence.parse_yang_xie_square_blume_capel_crossing(
            source_text
        )


def test_yang_xie_parser_extracts_single_ion_spin1_anisotropy_levels():
    parsed, trace = (
        literature_runtime_evidence
        .parse_yang_xie_single_ion_spin1_anisotropy_levels(
            YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT
        )
    )

    assert parsed == {
        "levels": [0.0, 1.0, 1.0],
        "degeneracies": [1, 2],
    }
    assert parsed == (
        literature_runtime_evidence
        .recompute_single_ion_spin1_anisotropy_levels(anisotropy=1.0)
    )
    assert trace["parser"] == (
        "parse_yang_xie_single_ion_spin1_anisotropy_levels"
    )
    assert trace["source_parser"] == (
        "parse_yang_xie_square_blume_capel_crossing"
    )
    assert trace["source_identity"] == "arXiv:1204.5027v2"
    assert trace["source_equation"] == "1"
    assert trace["spin"] == 1
    assert trace["basis_m_values"] == [-1, 0, 1]
    assert trace["anisotropy_energy_unit"] == "D=1"
    assert trace["derivation"] == "E_m/D = m^2"
    assert trace["level_degeneracies"] == {
        "0.0": 1,
        "1.0": 2,
    }
    assert trace["claim_scope"] == (
        "the isolated spin-1 D(Sz)^2 term in Yang-Xie Eq. (1), "
        "normalized to D=1; exchange and magnetic-field terms are "
        "excluded from the onsite spectrum"
    )
    assert len(trace["matched_anchors"]) == 10
    assert len(trace["text_spans"]) == 10


@pytest.mark.parametrize(
    "source_text",
    [
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "arXiv:1204.5027v2", "arXiv:1204.0000v2"
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "+ D sum_i S_i^2", "+ D sum_i S_i"
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "D is the strength of the single-ion anisotropy",
            "D is an unrelated bond-counting parameter",
        ),
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
            "In the case of S = 1, there are three optional values: "
            "+/-1 and 0",
            "In the case of S = 2, there are five optional values",
        ),
    ],
)
def test_yang_xie_single_ion_parser_fails_closed_without_onsite_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Yang-Xie Blume-Capel"):
        (
            literature_runtime_evidence
            .parse_yang_xie_single_ion_spin1_anisotropy_levels(source_text)
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1])
def test_yang_xie_single_ion_parser_rejects_non_text_or_empty_source(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Yang-Xie Blume-Capel"):
        (
            literature_runtime_evidence
            .parse_yang_xie_single_ion_spin1_anisotropy_levels(source_text)
        )


def test_mazin_parser_extracts_classical_honeycomb_j1_j2_j3_phase_set():
    parsed, trace = (
        literature_runtime_evidence
        .parse_mazin_honeycomb_j1_j2_j3_phase_set(
            MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT
        )
    )

    assert parsed == {
        "phases": ["neel", "spiral", "zigzag", "stripy"],
    }
    assert trace["parser"] == (
        "parse_mazin_honeycomb_j1_j2_j3_phase_set"
    )
    assert trace["source_identity"] == "arXiv:1309.3744v1"
    assert trace["registered_doi"] == "10.1016/0378-4363(79)90002-0"
    assert trace["original_classical_source"] == (
        "Rastelli-Tassi-Reatto, Physica B 97, 1-24 (1979)"
    )
    assert trace["phase_labels"] == [
        "neel",
        "spiral",
        "zigzag",
        "stripy",
    ]
    assert trace["neel_upper_j2_over_j1"] == pytest.approx(1.0 / 6.0)
    assert trace["spiral_j2_over_j1_window"] == pytest.approx(
        [1.0 / 6.0, 1.0 / 2.0]
    )
    assert trace["spiral_branch_count"] == 2
    assert trace["j3_extension_phase"] == "zigzag"
    assert trace["source_role"] == (
        "machine-extractable supplemental direct primary research source"
    )
    assert trace["registered_source_relationship"] == (
        "Rastelli-Tassi-Reatto 1979 is the registered original classical "
        "phase diagram; Fouet-Sindzingre-Lhuillier 2001 explicitly state "
        "that they reproduce that diagram; Mazin 1309.3744v1 supplies the "
        "modern Neel, spiral, stripy, and zigzag labels and reproduces "
        "the J1-J2-J3 boundary figure with Rastelli as reference [1]."
    )
    assert trace["claim_scope"] == (
        "zero-temperature classical antiferromagnetic-J1 honeycomb "
        "J1-J2-J3 Heisenberg phase-label set, with the two spiral "
        "branches normalized to one registry label; no quantum phase "
        "stability or simultaneous four-phase coexistence is claimed"
    )
    assert len(trace["matched_anchors"]) == 9
    assert len(trace["text_spans"]) == 9


@pytest.mark.parametrize(
    "source_text",
    [
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "CaMn2Sb2: a fully frustrated classical magnetic system",
            "Unrelated electronic transport in a square lattice",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "I. I. Mazin", "I. I. Example"
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "arXiv:1309.3744v1", "arXiv:1309.0000v1"
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "classical Heisenberg model\non the honeycomb lattice",
            "quantum Ising model on the square lattice",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "seminal paper of Rastelli et al. from 1979",
            "unidentified review from 2019",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "nearest-neighbor interaction J1 and the\n"
            "second-neighbor interaction J2",
            "onsite interaction U and chemical potential mu",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "J2/J1 < 1/6", "J2/J1 < 1/5"
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "1/6 < J2/J1 < 1/2", "1/6 < J2/J1 < 2/3"
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "there are two degenerate solutions corresponding to two\n"
            "different spiral phases",
            "there is one nondegenerate collinear solution",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "stripe phase\nwith alternating ferromagnetic pairs",
            "featureless paramagnetic state",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "third-neighbor exchange J3", "fourth-neighbor exchange J4"
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "zigzag antiferromagnetism", "uniform ferromagnetism"
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "includes first-, second-,\nand third-nearest neighbors",
            "includes only first-nearest neighbors",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "Phase diagram of the classical J1-J2-J3 Heisenberg model",
            "Spectrum of a quantum single-ion model",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "there are five planar phases",
            "there is one planar phase",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            'the "stripy" (S) phase, where\n'
            "all bonds along one direction are ferromagnetic and double "
            "stripes order\nantiferromagnetically",
            "a stripy label with no magnetic pattern",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "two spiral phases (A and B)", "one spiral phase (A)"
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            'new "zigzag" phase emerging at large J3',
            "new uniform phase unrelated to J3",
        ),
        MAZIN_HONEYCOMB_J1_J2_J3_PHASE_SOURCE_TEXT.replace(
            "E. Rastelli, A. Tassi, and L. Reatto",
            "E. Example, A. Example, and L. Example",
        ),
    ],
)
def test_mazin_parser_fails_closed_without_complete_classical_phase_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Mazin honeycomb"):
        literature_runtime_evidence.parse_mazin_honeycomb_j1_j2_j3_phase_set(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2013])
def test_mazin_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Mazin honeycomb"):
        literature_runtime_evidence.parse_mazin_honeycomb_j1_j2_j3_phase_set(
            source_text
        )


def test_stodter_parser_extracts_clinoatacamite_distorted_kagome_exchange():
    parsed, trace = (
        literature_runtime_evidence
        .parse_stodter_clinoatacamite_distorted_kagome_exchange(
            STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT
        )
    )

    assert parsed == {"distorted_kagome_reference": True}
    assert trace["parser"] == (
        "parse_stodter_clinoatacamite_distorted_kagome_exchange"
    )
    assert trace["source_identity"] == "arXiv:2601.21024v2"
    assert trace["accepted_prl_doi"] == "10.1103/xmh8-68vk"
    assert trace["registered_doi"] == "10.1038/nmat1867"
    assert trace["corrected_historical_doi"] == "10.1038/nmat1986"
    assert trace["in_plane_exchange_paths"] == ["J4", "J5", "J6"]
    assert trace["interlayer_exchange_paths"] == ["J1", "J2", "J3"]
    assert trace["exchange_values_k"] == pytest.approx(
        {
            "J1": -6.8,
            "J2": -14.5,
            "J3": -30.3,
            "J4": 120.1,
            "J5": 211.6,
            "J6": 367.7,
        }
    )
    assert trace["dft_u_ev"] == pytest.approx(7.19)
    assert trace["curie_weiss_temperature_k"] == pytest.approx(-165.0)
    assert trace["reported_interlayer_bound_over_j6"] == pytest.approx(
        0.082
    )
    assert trace["exchange_hierarchy"] == (
        "dominant non-uniform AFM kagome J4-J6; weaker FM "
        "kagome-interlayer J1-J3"
    )
    assert trace["historical_vbs_scenario_supported"] is False
    assert trace["source_role"] == (
        "current machine-extractable corrective direct primary "
        "research source"
    )
    assert trace["registered_source_relationship"] == (
        "The registered DOI 10.1038/nmat1867 is Yamada et al.'s "
        "magnetic-disk vortex paper. Lee et al.'s intended 2007 "
        "clinoatacamite source is DOI 10.1038/nmat1986; Stodter et al. "
        "retain its broad distorted-kagome/interlayer setting, replace "
        "it with a DFT-resolved six-exchange hierarchy, and rule out "
        "Lee et al.'s VBS scenario."
    )
    assert trace["claim_scope"] == (
        "boolean distorted-kagome material-model characterization for "
        "bulk clinoatacamite Cu2Cl(OH)3; the parser does not promote "
        "the superseded VBS interpretation or claim exact classical "
        "minima from the source text"
    )
    assert len(trace["matched_anchors"]) == 10
    assert len(trace["text_spans"]) == 10


@pytest.mark.parametrize(
    "source_text",
    [
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "Competing Ordering Modes in the Distorted Quantum Kagome "
            "Material",
            "Charge Transport in an Undistorted Square-Lattice Metal",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "arXiv:2601.21024v2", "arXiv:2601.00000v2"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "using density-functional theory",
            "without microscopic theory",
            1,
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "belongs to the class of\n"
            "distorted kagome antiferromagnets",
            "belongs to the class of undistorted square ferromagnets",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "non-uniform kagome antiferromagnet with weak\n"
            "ferromagnetic (FM) couplings to the interlayer Cu sites",
            "uniform kagome antiferromagnet without interlayer Cu sites",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "Cu(2) and Cu(3) sites form a slightly distorted kagome motif",
            "Cu(2) and Cu(3) sites form a square motif",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "Cu(1) sites\nare interlayer sites",
            "Cu(1) sites are nonmagnetic vacancies",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "three inequivalent NN Cu-Cu exchange paths\n"
            "(J4-J6) within the kagome layers",
            "one uniform exchange path within the kagome layers",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "three inequivalent NN Cu-Cu exchange\n"
            "paths (J1-J3) between kagome and interlayer sites",
            "no exchange paths between kagome and interlayer sites",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "U = 7.19 eV", "U = 6.00 eV"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "Theta_CW = -165(1) K", "Theta_CW = -65(1) K"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "J1 = -6.8 K", "J1 = 6.8 K"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "J2 = -14.5 K", "J2 = 14.5 K"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "J3 = -30.3 K", "J3 = 30.3 K"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "J4 = 120.1 K", "J4 = -120.1 K"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "J5 = 211.6 K", "J5 = -211.6 K"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "J6 = 367.7 K", "J6 = -367.7 K"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "|Ji| <= 0.082 J6", "|Ji| <= 0.82 J6"
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "rule out the scenario of clinoatacamite as valence bond\n"
            "solid from Ref. [21]",
            "confirm the scenario of clinoatacamite as a valence bond solid",
        ),
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
            "Nat. Mater. 6, 853 (2007)", "Nat. Mater. 6, 270 (2007)"
        ),
    ],
)
def test_stodter_parser_fails_closed_without_complete_exchange_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Stodter clinoatacamite"):
        (
            literature_runtime_evidence
            .parse_stodter_clinoatacamite_distorted_kagome_exchange(
                source_text
            )
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2026])
def test_stodter_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Stodter clinoatacamite"):
        (
            literature_runtime_evidence
            .parse_stodter_clinoatacamite_distorted_kagome_exchange(
                source_text
            )
        )


def test_ishikawa_parser_extracts_edwardsite_spin_half_deformed_kagome():
    parsed, trace = (
        literature_runtime_evidence
        .parse_ishikawa_edwardsite_spin_half_deformed_kagome(
            ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT
        )
    )

    assert parsed == {"kagome_antiferromagnet_reference": True}
    assert trace["parser"] == (
        "parse_ishikawa_edwardsite_spin_half_deformed_kagome"
    )
    assert trace["source_identity"] == "arXiv:1305.2477v1"
    assert trace["journal_doi"] == "10.7566/JPSJ.82.063710"
    assert trace["registered_doi"] == "10.1038/ncomms14113"
    assert trace["source_spin"] == pytest.approx(0.5)
    assert trace["registered_spin"] == pytest.approx(1.0)
    assert trace["source_material_formula"] == (
        "Cd2Cu3(SO4)2(OH)6·4H2O"
    )
    assert trace["registered_material_formula"] == (
        "Cd2Cu3(OH)6(SO4)2"
    )
    assert trace["crystallographic_cu_site_count"] == 4
    assert trace["nonequivalent_cu_cu_bond_count"] == 6
    assert trace["strong_exchange_count"] == 2
    assert trace["weak_exchange_count"] == 4
    assert trace["curie_weiss_temperature_k"] == pytest.approx(-66.2)
    assert trace["htse_average_j_over_kb_k"] == pytest.approx(51.1)
    assert trace["lande_g_factor"] == pytest.approx(2.195)
    assert trace["ordering_temperature_k"] == pytest.approx(4.3)
    assert trace["suggested_order"] == "canted_120_degree_q0"
    assert trace["source_role"] == (
        "machine-extractable corrective direct primary research source"
    )
    assert trace["registered_source_and_model_correction"] == (
        "The registered DOI 10.1038/ncomms14113 is a hydronium-ion "
        "catalysis paper. The intended Edwardsite source is Ishikawa, "
        "Okamoto, and Hiroi, DOI 10.7566/JPSJ.82.063710. It studies "
        "hydrated Cd2Cu3(SO4)2(OH)6·4H2O with Cu spin 1/2, not the "
        "registry's anhydrous-formula spin-1 model."
    )
    assert trace["claim_scope"] == (
        "boolean material-reference claim for hydrated spin-1/2 "
        "deformed-kagome Edwardsite; no validation is claimed for the "
        "registry's spin-1 Hamiltonian, an anhydrous material, or an "
        "exact ideal-kagome classical 120-degree manifold"
    )
    assert len(trace["matched_anchors"]) == 14
    assert len(trace["text_spans"]) == 14


def test_ishikawa_parser_handles_verified_pdf_extraction_artifacts():
    extracted_text = ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT
    extracted_text = extracted_text.replace(
        "distance between kagome layers is 10.0 A",
        "distance between kagome layers is 10.0 ˚ A",
    )
    extracted_text = extracted_text.replace(
        "the Cu-Cu distance in the",
        "the Cu- Cu distance in the",
    )
    extracted_text = extracted_text.replace(
        "magnetic interactions in edwardsite are definitely",
        "magnetic interac-\n"
        "5\n"
        "FIGURE 3. Cp/T (J K-2 mol-1)\n"
        "0 5 10 15 20\n"
        "tions in edwardsite are definitely",
    )
    extracted_text = extracted_text.replace(
        "All\n"
        "the magnetic interactions in edwardsite",
        "All the 5 magnetic interactions in edwardsite",
    )

    parsed, trace = (
        literature_runtime_evidence
        .parse_ishikawa_edwardsite_spin_half_deformed_kagome(
            extracted_text
        )
    )

    assert parsed == {"kagome_antiferromagnet_reference": True}
    assert trace["source_identity"] == "arXiv:1305.2477v1"
    assert trace["source_spin"] == pytest.approx(0.5)
    assert trace["crystallographic_cu_site_count"] == 4
    assert trace["ordering_temperature_k"] == pytest.approx(4.3)
    assert len(trace["matched_anchors"]) == 14
    assert len(trace["text_spans"]) == 14


def test_ishikawa_parser_reconstructs_verified_two_column_page_order():
    def layout_line(left, right, split_column):
        return left.ljust(split_column) + right

    transition_page = "\n".join(
        (
            layout_line(
                "",
                "tions in edwardsite are definitely antiferromagnetic,",
                102,
            ),
            layout_line(
                "",
                "this magnetic phase transition must be due to a canted",
                102,
            ),
            layout_line("", "antiferromagnetic order.", 102),
            layout_line(
                "The heat capacity at zero magnetic field shows a broad "
                "but distinct peak at",
                "",
                102,
            ),
            layout_line(
                "T_N = 4.3 K. Since magnetic interac-",
                "",
                102,
            ),
        )
    )
    angle_lead_page = layout_line(
        "End of the preceding left column.",
        "All the",
        76,
    )
    angle_follow_page = "\n".join(
        (
            layout_line(
                "magnetic interactions in edwardsite must be antiferro-",
                "[6] Reference-column text",
                76,
            ),
            layout_line(
                "magnetic, because the Cu-O(H)-Cu angles are large, i.e.,",
                "[7] Reference-column text",
                76,
            ),
            layout_line(
                "between 109 degrees and 116 degrees.",
                "[8] Reference-column text",
                76,
            ),
        )
    )

    extracted_text = ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT
    extracted_text = extracted_text.replace(
        "The heat capacity at zero magnetic field shows a broad but "
        "distinct peak at\n"
        "T_N = 4.3 K. Since magnetic interactions in edwardsite are "
        "definitely\n"
        "antiferromagnetic, this magnetic phase transition must be due "
        "to a canted\n"
        "antiferromagnetic order.",
        f"\f{transition_page}\f",
    )
    extracted_text = extracted_text.replace(
        "All\n"
        "the magnetic interactions in edwardsite must be "
        "antiferromagnetic because\n"
        "the Cu-O(H)-Cu angles are between 109 degrees and 116 degrees.",
        f"\f{angle_lead_page}\f{angle_follow_page}\f",
    )

    parsed, trace = (
        literature_runtime_evidence
        .parse_ishikawa_edwardsite_spin_half_deformed_kagome(
            extracted_text
        )
    )

    assert parsed == {"kagome_antiferromagnet_reference": True}
    assert trace["ordering_temperature_k"] == pytest.approx(4.3)
    assert trace["crystallographic_cu_site_count"] == 4
    assert trace["nonequivalent_cu_cu_bond_count"] == 6
    assert len(trace["matched_anchors"]) == 14
    assert len(trace["text_spans"]) == 14
    assert trace["text_span_captures"][0].startswith(
        "Magnetic Properties of the Spin-1/2 Deformed Kagome"
    )
    assert trace["text_span_captures"][9].startswith(
        "heat capacity at zero magnetic field"
    )
    assert trace["text_span_captures"][11].startswith(
        "All the magnetic interactions in edwardsite"
    )


@pytest.mark.parametrize(
    "source_text",
    [
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "Magnetic Properties of the Spin-1/2 Deformed Kagome "
            "Antiferromagnet Edwardsite",
            "Catalytic Properties of Hydronium Ions in Zeolites",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "Hajime Ishikawa, Yoshihiko Okamoto, and Zenji Hiroi",
            "Example Author, Example Collaborator, and Example Researcher",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "arXiv:1305.2477v1", "arXiv:1305.0000v1"
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "Cd2Cu3(SO4)2(OH)6*4H2O",
            "Cd2Cu3(SO4)2(OH)6",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "new candidate compound for the spin-1/2\n"
            "kagome antiferromagnet",
            "candidate spin-1 square-lattice ferromagnet",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "magnetic\nsusceptibility and heat capacity measurements",
            "an uncalibrated optical image",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "deformed\n"
            "kagome lattice with an average antiferromagnetic interaction "
            "of 51 K",
            "uniform triangular lattice with an unknown interaction",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "small\nferromagnetic moment below 4.3 K",
            "paramagnetic response down to 0.1 K",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "two-dimensional network of corner-sharing triangles",
            "three-dimensional network of edge-sharing squares",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "Cu2+ ions are aligned in a kagome geometry",
            "Cu2+ ions are aligned in a square geometry",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "distance between kagome layers is 10.0 A",
            "distance between kagome layers is 1.0 A",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "four crystallographic sites", "one crystallographic site"
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "varies within 5%", "varies within 50%"
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "theta_W = -66.2(3) K", "theta_W = 66.2(3) K"
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "spin-1/2 KAFM using the high-temperature-series\n"
            "expansion",
            "spin-1 ferromagnet using mean field only",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "J/k_B = 51.1(1) K", "J/k_B = 15.1(1) K"
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "g = 2.195(1)", "g = 1.195(1)"
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "broad but distinct peak at\nT_N = 4.3 K",
            "featureless heat capacity down to 0.1 K",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "canted\nantiferromagnetic order",
            "uniform ferromagnetic order",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "six nonequivalent Cu-Cu bonds", "one uniform Cu-Cu bond"
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "between 109 degrees and 116 degrees",
            "between 89 degrees and 96 degrees",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "two stronger\nones with J and four weaker ones with J'",
            "six equivalent couplings with J",
        ),
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT.replace(
            "canted 120-degree order with a\nq = 0 propagation vector",
            "collinear ferromagnetic order with an unknown wave vector",
        ),
    ],
)
def test_ishikawa_parser_fails_closed_without_complete_edwardsite_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Ishikawa Edwardsite"):
        literature_runtime_evidence.parse_ishikawa_edwardsite_spin_half_deformed_kagome(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2013])
def test_ishikawa_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Ishikawa Edwardsite"):
        literature_runtime_evidence.parse_ishikawa_edwardsite_spin_half_deformed_kagome(
            source_text
        )


def test_nawa_parser_extracts_scoped_rubr3_kitaev_candidate_claim():
    parsed, trace = (
        literature_runtime_evidence
        .parse_nawa_rubr3_kitaev_candidate_and_competing_interactions(
            NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT
        )
    )

    assert parsed == {"ru_honeycomb_kitaev_candidate": True}
    assert trace["parser"] == (
        "parse_nawa_rubr3_kitaev_candidate_and_competing_interactions"
    )
    assert trace["source_identity"] == "doi:10.1038/s41535-026-00868-6"
    assert trace["registered_doi"] == "10.1088/1361-648X/aa8cf5"
    assert trace["original_material_doi"] == (
        "10.1103/PhysRevB.105.L041112"
    )
    assert trace["material"] == "RuBr3"
    assert trace["structure"] == "layered_honeycomb"
    assert trace["experiment"] == "powder_inelastic_neutron_scattering"
    assert trace["curie_weiss_temperature_k"] == pytest.approx(-58.0)
    assert trace["ordering_temperature_k"] == pytest.approx(34.0)
    assert trace["ordered_moment_mu_b"] == pytest.approx(0.74)
    assert trace["ordered_moment_uncertainty_mu_b"] == pytest.approx(0.12)
    assert trace["moment_tilt_degrees"] == pytest.approx(64.0)
    assert trace["moment_tilt_uncertainty_degrees"] == pytest.approx(12.0)
    assert trace["magnetic_excitation_range_mev"] == pytest.approx(
        [1.5, 15.0]
    )
    assert trace["energy_gap_mev_at_10_k"] == pytest.approx(1.5)
    assert trace["dominant_competing_interaction_options"] == [
        "nearest_neighbor_Gamma",
        "third_neighbor_J3",
    ]
    assert trace["gamma_dominant_model_mev"] == {
        "J1": pytest.approx(-1.8),
        "K": pytest.approx(-7.2),
        "Gamma": pytest.approx(10.5),
        "Gamma_prime": pytest.approx(-2.5),
        "J2": pytest.approx(0.0),
        "J3": pytest.approx(0.0),
        "Jp": pytest.approx(0.15),
    }
    assert trace["j3_dominant_model_mev"] == {
        "J1": pytest.approx(1.5),
        "K": pytest.approx(-8.1),
        "Gamma": pytest.approx(0.0),
        "Gamma_prime": pytest.approx(-0.16),
        "J2": pytest.approx(0.8),
        "J3": pytest.approx(5.8),
        "Jp": pytest.approx(0.15),
    }
    assert trace["fit_status"] == (
        "two phenomenological extreme parameter combinations, not a "
        "simultaneous unique exchange fit"
    )
    assert trace["kitaev_limit_assessment"] == (
        "ground state driven away from the ideal ferromagnetic Kitaev "
        "spin-liquid state"
    )
    assert trace["source_role"] == (
        "machine-extractable corrective direct primary neutron source"
    )
    assert trace["registered_source_and_scope_correction"] == (
        "The registered DOI 10.1088/1361-648X/aa8cf5 is Winter et al.'s "
        "2017 review, whose cached text does not mention RuBr3. The "
        "direct RuBr3 neutron source used here is Nawa et al., DOI "
        "10.1038/s41535-026-00868-6; the first synthesis and zigzag-order "
        "report is Imai et al., DOI 10.1103/PhysRevB.105.L041112."
    )
    assert trace["claim_scope"] == (
        "boolean RuBr3 honeycomb Kitaev-candidate label only; the source "
        "instead finds competing Gamma or J3 interactions that drive the "
        "ordered ground state away from the ideal ferromagnetic Kitaev "
        "spin liquid, and it does not establish a realized spin liquid, "
        "a unique exchange Hamiltonian, exact bond eigenvalues, or an "
        "independently recomputed classical zigzag energy"
    )
    assert len(trace["matched_anchors"]) == 17
    assert len(trace["text_spans"]) == 17


def test_nawa_parser_handles_verified_vor_pdf_parameter_and_column_forms():
    extracted_text = NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT
    extracted_text = extracted_text.replace(
        "The former J1-K-Gamma-Gamma' model includes a large Gamma term "
        "with zero J2\n"
        "and J3: J1 = -1.8, K = -7.2, Gamma = 10.5, Gamma' = -2.5 meV. "
        "The latter\n"
        "J1-K-J2-J3 model includes a large J3 term with zero Gamma: "
        "J1 = 1.5,\n"
        "K = -8.1, J2 = 0.8, J3 = 5.8, Gamma' = -0.16 meV. Interplane "
        "interactions\n"
        "of Jp = 0.15 meV were included in both models.",
        "Fig. 5 | Inelastic neutron scattering spectrum simulated from "
        "a the\n"
        "J1-K-Gamma-Gamma' and b the J1-K-J2-J3 models by using linear "
        "spin wave theory. The\n"
        "parameters used for the simulations are a J1 = -1.8, K = -7.2, "
        "Gamma = 10.5,\n"
        "Gamma0 = -2.5 meV and b J1 = 1.5, K = -8.1, J2 = 0.8, "
        "J3 = 5.8, and Gamma0 = -0.16 meV.\n"
        "Interplane interactions of Jp = 0.15 meV are adopted in both "
        "models. The latter model includes a large J3 term with zero "
        "Gamma.",
    )
    extracted_text = extracted_text.replace(
        "The classical ground\n"
        "state was estimated by the Luttinger-Tisza method. The zigzag\n"
        "antiferromagnetic order was confirmed to be the classical ground "
        "state for the\n"
        "given parameters discussed in the main text.",
        "From the eigenvector of the smallest eigenenergy, the zigzag\n"
        "antiferromagnetic order was confirmed to be the classical ground "
        "state for the\n"
        "given parameters discussed in the main text. First, the classical "
        "ground\n"
        "state was estimated by the Luttinger-Tisza method.",
    )

    parsed, trace = (
        literature_runtime_evidence
        .parse_nawa_rubr3_kitaev_candidate_and_competing_interactions(
            extracted_text
        )
    )

    assert parsed == {"ru_honeycomb_kitaev_candidate": True}
    assert trace["gamma_dominant_model_mev"]["Gamma"] == pytest.approx(
        10.5
    )
    assert trace["j3_dominant_model_mev"]["J3"] == pytest.approx(5.8)
    assert trace["fit_status"].startswith(
        "two phenomenological extreme parameter combinations"
    )
    assert len(trace["matched_anchors"]) == 17
    assert len(trace["text_spans"]) == 17


@pytest.mark.parametrize(
    "source_text",
    [
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Magnetic excitations of the Kitaev model candidate RuBr3",
            "Magnetic excitations of an unspecified layered magnet",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "10.1038/s41535-026-00868-6",
            "10.1038/s41535-026-00000-0",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Kazuhiro Nawa, Yoshinori Imai",
            "Example Author, Example Collaborator",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "powder inelastic neutron scattering on RuBr3 with a layered\n"
            "honeycomb structure",
            "optical microscopy on an unspecified square-lattice powder",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "is isostructural to the low-temperature structure\n"
            "of alpha-RuCl3",
            "has no established structural analogue",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Strongly dispersive magnetic modes were observed near the\n"
            "centre of the antiferromagnetic zone below T_N",
            "No magnetic modes were observed at any wavevector",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "shifts to the Gamma point at 3T_N",
            "does not change with temperature",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "are comparable to or even\n"
            "stronger than ferromagnetic Kitaev interactions",
            "are negligible compared with ferromagnetic Kitaev interactions",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "drive the ground state of\n"
            "RuBr3 away from the ideal ferromagnetic Kitaev spin liquid state",
            "prove an ideal ferromagnetic Kitaev spin liquid ground state",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Curie-Weiss fit is -58 K",
            "Curie-Weiss fit is +58 K",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "zigzag antiferromagnetic order below 34 K",
            "ferromagnetic order below 3.4 K",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "0.74(12) mu_B",
            "7.4(12) mu_B",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "64(12) degrees",
            "14(12) degrees",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Peaks were observed at 0.60 and 1.55\ninverse Angstrom",
            "A single peak was observed at 4.20 inverse Angstrom",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "range from 1.5 to\n15 meV",
            "range from 15 to 150 meV",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "energy gap of 1.5 meV at 10 K",
            "energy gap of 15 meV at 100 K",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "could not conclude that the weak excitations are induced by "
            "the Kitaev\ninteractions",
            "conclusively proved that all weak excitations are Kitaev "
            "fractionalization",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "would not perfectly apply to the pseudospin-1/2 system",
            "is exact for this classical spin-5 system",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "not\npossible to estimate several exchange parameters "
            "simultaneously",
            "possible to determine every exchange parameter uniquely",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "parameters\nare phenomenologically adjusted",
            "parameters are exact analytic constants",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "J1 = -1.8, K = -7.2, Gamma = 10.5, Gamma' = -2.5 meV",
            "J1 = -18, K = -72, Gamma = 105, Gamma' = -25 meV",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "J1 = 1.5,\nK = -8.1, J2 = 0.8, J3 = 5.8, Gamma' = -0.16 meV",
            "J1 = 15, K = -81, J2 = 8, J3 = 58, Gamma' = -1.6 meV",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Jp = 0.15 meV were included in both models",
            "Jp was omitted from both models",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Strong antiferromagnetic\n"
            "interactions coexist with sizable ferromagnetic Kitaev "
            "interactions",
            "Only an ideal Kitaev interaction is present",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "including\n"
            "the Kitaev term K, Heisenberg term J1, and non-diagonal "
            "components Gamma and\nGamma'",
            "including only an isotropic nearest-neighbour term",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "zigzag\n"
            "antiferromagnetic order was confirmed to be the classical "
            "ground state",
            "ferromagnetic order was assumed without an energy calculation",
        ),
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT.replace(
            "Phys. Rev. B 105, L041112 (2022)",
            "Phys. Rev. B 1, 000001 (1900)",
        ),
    ],
)
def test_nawa_parser_fails_closed_without_complete_rubr3_chain(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Nawa RuBr3"):
        literature_runtime_evidence.parse_nawa_rubr3_kitaev_candidate_and_competing_interactions(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2026])
def test_nawa_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Nawa RuBr3"):
        literature_runtime_evidence.parse_nawa_rubr3_kitaev_candidate_and_competing_interactions(
            source_text
        )


def test_boldrin_parser_corrects_vesignieite_distortion_model_to_dominant_j3():
    parsed, trace = (
        literature_runtime_evidence
        .parse_boldrin_vesignieite_dominant_j3_correction(
            BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT
        )
    )

    assert parsed == {"distorted_kagome_relevant": False}
    assert trace["parser"] == (
        "parse_boldrin_vesignieite_dominant_j3_correction"
    )
    assert trace["source_identity"] == (
        "doi:10.1103/PhysRevLett.121.107203"
    )
    assert trace["registered_doi"] == "10.1143/JPSJ.78.043704"
    assert trace["original_material_doi"] == "10.1143/JPSJ.78.033701"
    assert trace["material"] == "BaCu3V2O8(OD)2"
    assert trace["spin"] == pytest.approx(0.5)
    assert trace["structure"] == (
        "nearly_perfect_kagome_with_tiny_scalene_distortion"
    )
    assert trace["structural_distortion_upper_bound_percent"] == (
        pytest.approx(1.0)
    )
    assert trace["curie_weiss_temperature_k"] == pytest.approx(-75.0)
    assert trace["ordering_temperature_k"] == pytest.approx(9.0)
    assert trace["propagation_vector"] == pytest.approx([0.5, 0.0, 0.0])
    assert trace["magnetic_bragg_q_inverse_angstrom"] == pytest.approx(
        [0.64, 1.08, 1.65]
    )
    assert trace["magnetic_structure"] == (
        "hexagonal_multi_k_coplanar_variant_of_triple_k_octahedral"
    )
    assert trace["dominant_exchange"] == "antiferromagnetic_J3"
    assert trace["isotropic_best_fit_mev"] == {
        "J3": pytest.approx(1.9),
        "Jd": pytest.approx(-0.1),
    }
    assert trace["flat_mode_energy_mev"] == pytest.approx(4.0)
    assert trace["exchange_constraints_mev"] == {
        "J3_minus_Jd_approximately": pytest.approx(2.0),
        "abs_Jd_less_than": pytest.approx(0.2),
        "abs_J1_less_than": pytest.approx(0.1),
        "abs_J2_much_less_than": pytest.approx(0.1),
    }
    assert trace["symmetric_exchange_anisotropy_over_j3"] == pytest.approx(
        -0.006
    )
    assert trace["source_role"] == (
        "machine-extractable corrective direct primary neutron source"
    )
    assert trace["registered_source_and_model_correction"] == (
        "The registered DOI 10.1143/JPSJ.78.043704 is a volborthite "
        "magnetization article, not a vesignieite source. The original "
        "vesignieite article is DOI 10.1143/JPSJ.78.033701. Direct neutron "
        "evidence in DOI 10.1103/PhysRevLett.121.107203 finds less than 1% "
        "structural distortion but dominant antiferromagnetic J3 exchange, "
        "so a distortion-dominated nearest-neighbor kagome model is not "
        "supported."
    )
    assert trace["claim_scope"] == (
        "False means that lattice distortion is not the relevant dominant "
        "ingredient of the registered distorted nearest-neighbor model; a "
        "finite tiny scalene distortion remains structurally present, while "
        "the measured magnetic spectrum is governed by J3 and a weak "
        "symmetric exchange anisotropy"
    )
    assert len(trace["matched_anchors"]) == 13
    assert len(trace["text_spans"]) == 13


def test_boldrin_parser_handles_verified_prl_pdf_glyph_forms():
    source_text = BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT
    for old, new in (
        ("S = 1/2", "S ¼ 12"),
        ("T_N = 9 K", "T N ¼ 9 K"),
        ("theta_W = -75 K", "θW ¼ −75 K"),
        ("k = (1/2, 0, 0)", "k ¼ ð1=2; 0; 0Þ"),
        ("J3 > 0", "J 3 > 0"),
        ("E = 4 meV", "E ¼ 4 meV"),
        ("semi-classical", "semiclassical"),
        ("J3 - Jd approximately 2.0", "J3 − J03 ≈ 2.0"),
        (
            "|Jd| < 0.2, |J1| < 0.1, and |J2| << 0.1",
            "jJ03 j < 0.2, jJ1 j < 0.1, and jJ2 j ≪ 0.1",
        ),
        (
            "J3 = 1.9 and Jd = -0.1 meV",
            "J3 ¼ 1.9 and J03 ¼ −0.1 meV",
        ),
        ("delta/J3 = -0.006", "δ=J3 ¼ −0.006"),
        ("spin-1/2", "spin-1=2"),
        ("J. Phys. Soc. Japan", "J. Phys. Soc. Jpn."),
    ):
        source_text = source_text.replace(old, new)

    parsed, trace = (
        literature_runtime_evidence
        .parse_boldrin_vesignieite_dominant_j3_correction(source_text)
    )

    assert parsed == {"distorted_kagome_relevant": False}
    assert trace["isotropic_best_fit_mev"] == {
        "J3": pytest.approx(1.9),
        "Jd": pytest.approx(-0.1),
    }
    assert trace["symmetric_exchange_anisotropy_over_j3"] == pytest.approx(
        -0.006
    )
    assert len(trace["matched_anchors"]) == 13
    assert len(trace["text_spans"]) == 13


def test_boldrin_parser_handles_arxiv_layout_fraction_and_page_break_forms():
    source_text = BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
        "Vesignieite: a S = 1/2",
        "1\nVesignieite: a S = 2",
        1,
    )
    source_text = source_text.replace(
        "The lowering of the kagome symmetry",
        "The lowering of the\n"
        "FIGURE 1 CAPTION AND PAGE BREAK\n"
        "kagome symmetry",
    )
    source_text = source_text.replace(
        "cooperative Jahn-Teller distortion and leads to\n"
        "the formation of two distinct Cu2+ sites",
        "cooperative Jahn-Teller dis-\n"
        "FIGURE 2 RIGHT-COLUMN TEXT\n"
        "tortion and leads to the formation of two distinct Cu2+\n"
        "MAGNETIC BRAGG-PEAK TEXT\n"
        "sites",
    )
    source_text = source_text.replace(
        "First- and\nsecond-neighbor interactions",
        "First- and second neighbor interactions",
    )

    parsed, trace = (
        literature_runtime_evidence
        .parse_boldrin_vesignieite_dominant_j3_correction(source_text)
    )

    assert parsed == {"distorted_kagome_relevant": False}
    assert trace["spin"] == pytest.approx(0.5)
    assert trace["ordering_temperature_k"] == pytest.approx(9.0)
    assert len(trace["matched_anchors"]) == 13
    assert len(trace["text_spans"]) == 13


@pytest.mark.parametrize(
    "source_text",
    [
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "Vesignieite: a S = 1/2 kagome antiferromagnet with dominant "
            "third-neighbor\nexchange",
            "An unrelated square-lattice ferromagnet",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "D. Boldrin, B. Fak",
            "Example Author, Example Collaborator",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "arXiv:1806.03074v1",
            "arXiv:0000.00000v1",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "neutron scattering measurements that deuterated vesignieite",
            "optical microscopy measurements of an unspecified mineral",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "a fully stoichiometric S = 1/2 kagome magnet with <1%\n"
            "lattice distortion",
            "a nonstoichiometric spin-2 chain with 30% lattice distortion",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "dominant antiferromagnetic 3rd-neighbor exchange J3 with\n"
            "minor 1st- or 2nd-neighbour exchange",
            "dominant nearest-neighbor J1 with no further-neighbor exchange",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "tiny scalene distortion of the triangles corresponds to\n"
            "less than 1% difference in the three Cu-Cu bond lengths",
            "large equilateral-to-chain distortion exceeds 30%",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "cooperative Jahn-Teller distortion and leads to\n"
            "the formation of two distinct Cu2+ sites",
            "no structural lowering and only one magnetic site",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "theta_W = -75 K",
            "theta_W = +75 K",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "based on nearest-neighbor exchange J1\n"
            "only are bound to fail",
            "based on nearest-neighbor J1 only are exact",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "Q values of 0.64, 1.08, and 1.65\ninverse Angstrom",
            "Q values of 6.4, 10.8, and 16.5 inverse Angstrom",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "k = (1/2, 0, 0)",
            "k = (0, 0, 0)",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "semi-classical spin-wave theory",
            "an exact thermodynamic identity",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "flat mode at E = 4 meV",
            "flat mode at E = 40 meV",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "J3 - Jd approximately 2.0",
            "J3 - Jd approximately 20.0",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "|Jd| < 0.2, |J1| < 0.1, and |J2| << 0.1",
            "|Jd| < 2, |J1| < 1, and |J2| << 1",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "J3 = 1.9 and Jd = -0.1 meV",
            "J3 = 19 and Jd = -1 meV",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "negligible J1 and dominant J3 exchange energies",
            "dominant J1 and negligible J3 exchange energies",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "First- and\nsecond-neighbor interactions are weak compared "
            "to third-neighbor interactions",
            "First- and second-neighbor interactions dominate over J3",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "delta/J3 = -0.006",
            "delta/J3 = -0.6",
        ),
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT.replace(
            "J. Phys. Soc. Japan 78, 033701\n(2009)",
            "J. Phys. Soc. Japan 78, 043704 (2009)",
        ),
    ],
)
def test_boldrin_parser_fails_closed_without_complete_vesignieite_chain(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Boldrin vesignieite"):
        literature_runtime_evidence.parse_boldrin_vesignieite_dominant_j3_correction(
            source_text
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2018])
def test_boldrin_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Boldrin vesignieite"):
        literature_runtime_evidence.parse_boldrin_vesignieite_dominant_j3_correction(
            source_text
        )


def test_schiffer_parser_corrects_ggg_strong_frustration_source_identity():
    parsed, trace = (
        literature_runtime_evidence
        .parse_schiffer_ggg_strong_frustration_correction(
            SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT
        )
    )

    assert parsed == {"strong_frustration": True}
    assert trace["parser"] == (
        "parse_schiffer_ggg_strong_frustration_correction"
    )
    assert trace["source_identity"] == (
        "doi:10.1103/PhysRevLett.73.2500"
    )
    assert trace["registered_doi"] == "10.1103/PhysRevLett.77.2085"
    assert trace["material"] == "Gd3Ga5O12"
    assert trace["spin"] == pytest.approx(3.5)
    assert trace["structure"] == (
        "two_interpenetrating_corner_sharing_triangular_sublattices"
    )
    assert trace["curie_weiss_temperature_k"] == pytest.approx(-2.0)
    assert trace["single_ion_anisotropy_upper_bound_k"] == (
        pytest.approx(0.04)
    )
    assert trace["nearest_neighbor_dipole_energy_k"] == pytest.approx(0.7)
    assert trace["nearest_neighbor_exchange_energy_k"] == pytest.approx(
        1.5
    )
    assert trace["field_induced_af_phase_upper_temperature_k"] == (
        pytest.approx(0.38)
    )
    assert trace["field_scale_t"] == pytest.approx(1.0)
    assert trace["measurements"] == [
        "specific_heat",
        "magnetic_susceptibility",
    ]
    assert trace["microscopic_model"] == (
        "classical_Heisenberg_nearest_neighbor_antiferromagnetic_"
        "exchange_plus_dipolar_interactions_to_third_neighbor"
    )
    assert trace["source_role"] == (
        "machine-extractable corrective direct primary thermodynamic "
        "and simulation source"
    )
    assert trace["registered_source_and_scope_correction"] == (
        "The registered DOI 10.1103/PhysRevLett.77.2085 is a kagome "
        "SrCr9pGa12-9pO19 coplanarity article, not a Gd3Ga5O12 source. "
        "The direct GGG source used here is Schiffer et al., DOI "
        "10.1103/PhysRevLett.73.2500."
    )
    assert trace["claim_scope"] == (
        "supports only the registered strong-frustration boolean for "
        "GGG; the 1994 source describes two interpenetrating "
        "corner-sharing triangular sublattices and does not itself use "
        "the later hyperkagome label, while its low-temperature "
        "antiferromagnetic phase occurs only in finite field"
    )
    assert len(trace["matched_anchors"]) == 9
    assert len(trace["text_spans"]) == 9


def test_schiffer_parser_handles_verified_1994_prl_ocr_forms():
    source_text = SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT
    for old, new in (
        ("(<0.38 K)", "(((0.38 K)"),
        ("H approximately 1 T", "H —1 T"),
        ("Gd3Ga5O12", "Gd3Ga50, 2"),
        (
            "two interpenetrating corner-sharing triangular sublattices",
            "two interpenetrating corner-sharing triangu-\nlar sublattices",
        ),
        ("theta_W approximately -2 K", "Ow„,, ——2 K"),
        ("two equivalent", "tv o equivalent"),
        ("S = 7/2", "5 = 7/2"),
        ("approximately 0.7 K", "-0. 7 K"),
        (
            "nearest-neighbor isotropic antiferromagnetic exchange "
            "interactions",
            "nearest-\nneighbor isotropic antiferromagnetic exchange "
            "interac-\ntions",
        ),
    ):
        source_text = source_text.replace(old, new)

    parsed, trace = (
        literature_runtime_evidence
        .parse_schiffer_ggg_strong_frustration_correction(source_text)
    )

    assert parsed == {"strong_frustration": True}
    assert trace["spin"] == pytest.approx(3.5)
    assert trace["curie_weiss_temperature_k"] == pytest.approx(-2.0)
    assert trace["nearest_neighbor_dipole_energy_k"] == pytest.approx(0.7)
    assert len(trace["matched_anchors"]) == 9
    assert len(trace["text_spans"]) == 9


@pytest.mark.parametrize(
    "source_text",
    [
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "Frustrated Magnet: Gadolinium Gallium Garnet",
            "Unfrustrated Magnet: Example Ferromagnet",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "P. Schiffer, A. P. Ramirez",
            "Example Author, Example Collaborator",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "unique low temperature (<0.38 K) antiferromagnetic phase "
            "which exists only in\nfinite fields (H approximately 1 T)",
            "zero-field ferromagnetic phase below 38 K",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "measured the specific heat and\nmagnetic susceptibility",
            "performed only optical microscopy",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "two interpenetrating corner-sharing triangular\nsublattices",
            "one unfrustrated square lattice",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "theta_W approximately -2 K",
            "theta_W approximately +20 K",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "Gd spins (S = 7/2) are isotropic",
            "Gd spins (S = 1/2) are strongly Ising-like",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "single ion anisotropy in the gadolinium garnets of less "
            "than\n0.04 K",
            "single ion anisotropy exceeds 4 K",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "nearest neighbor dipole energy is\napproximately 0.7 K "
            "and the nearest neighbor exchange energy is 1.5 K",
            "nearest neighbor dipole and exchange energies are unknown",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "alleviates the local geometric\nfrustration but does not "
            "force the magnetization to saturate",
            "saturates an unfrustrated ferromagnet",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "classical Heisenberg spins at each Gd site coupled with\n"
            "nearest-neighbor isotropic antiferromagnetic exchange "
            "interactions and dipolar\ninteractions to the third nearest "
            "neighbor",
            "noninteracting Ising spins without dipolar interactions",
        ),
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT.replace(
            "unique combination of strong\ngeometric frustration and "
            "dipolar interactions",
            "absence of frustration and dipolar interactions",
        ),
    ],
)
def test_schiffer_parser_fails_closed_without_complete_ggg_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Schiffer GGG strong-frustration correction",
    ):
        (
            literature_runtime_evidence
            .parse_schiffer_ggg_strong_frustration_correction(
                source_text
            )
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 1994])
def test_schiffer_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Schiffer GGG strong-frustration correction",
    ):
        (
            literature_runtime_evidence
            .parse_schiffer_ggg_strong_frustration_correction(
                source_text
            )
        )


def test_quilliam_parser_corrects_gtlg_frustrated_hyperkagome_source():
    parsed, trace = (
        literature_runtime_evidence
        .parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction(
            QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT
        )
    )

    assert parsed == {"garnet_frustrated_magnet": True}
    assert trace["parser"] == (
        "parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction"
    )
    assert trace["source_identity"] == (
        "doi:10.1103/PhysRevB.87.174421"
    )
    assert trace["arxiv_identity"] == "arXiv:1006.2969v2"
    assert trace["registered_doi"] == "10.1103/PhysRevB.92.140407"
    assert trace["material"] == "Gd3Te2Li3O12"
    assert trace["spin"] == pytest.approx(3.5)
    assert trace["structure"] == (
        "two_interpenetrating_hyperkagome_networks_of_corner_sharing_"
        "triangles"
    )
    assert trace["model_terms"] == [
        "nearest_neighbor_antiferromagnetic_Heisenberg_exchange",
        "long_range_dipolar_interaction",
    ]
    assert trace["nearest_neighbor_exchange_k"] == pytest.approx(0.126)
    assert trace["dipolar_interaction_k"] == pytest.approx(0.045)
    assert trace["dipolar_to_exchange_ratio"] == pytest.approx(0.36)
    assert trace["curie_weiss_temperature_k"] == pytest.approx(-2.7)
    assert trace["ordering_temperature_k"] == pytest.approx(0.243)
    assert trace["frustration_index"] == pytest.approx(11.0)
    assert trace["spin_wave_gap_k"] == pytest.approx(0.62)
    assert trace["space_group"] == "Ia-3d (230)"
    assert trace["ordering_assessment"] == (
        "sharp_first_order_transition_with_strong_evidence_of_long_"
        "range_order"
    )
    assert trace["source_role"] == (
        "machine-extractable corrective direct primary specific-heat "
        "and structural source"
    )
    assert trace["registered_source_and_scope_correction"] == (
        "The registered DOI 10.1103/PhysRevB.92.140407 is an Er/Yb "
        "germanate-pyrochlore antiferromagnetic-order article, not a "
        "Gd3Te2Li3O12 source. The direct GTLG source used here is "
        "Quilliam et al., DOI 10.1103/PhysRevB.87.174421, "
        "arXiv:1006.2969v2."
    )
    assert trace["claim_scope"] == (
        "supports only the registered frustrated-garnet boolean and "
        "hyperkagome material mapping; GTLG is highly frustrated but "
        "undergoes a sharp first-order transition with strong evidence "
        "of long-range order, so this is not evidence for a realized "
        "spin-liquid ground state or a fully determined microscopic "
        "Hamiltonian"
    )
    assert len(trace["matched_anchors"]) == 14
    assert len(trace["text_spans"]) == 14


def test_quilliam_parser_handles_verified_aps_and_arxiv_glyph_forms():
    source_text = QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT
    for old, new in (
        ("Gd3Te2Li3O12", "Gd3 Te2 Li3 O12"),
        ("S = 7/2", "S = 7=2"),
        ("approximately 0.1 to 0.14 K", "∼ 0.1 to 0.14 K"),
        ("H_Ex", "HEx"),
        ("H_D", "HD"),
        ("theta_CW approximately -2.7 K", "θCW ≃ −2.7 K"),
        ("Delta approximately 0.62 K", "∆ ≃ 0.62 K"),
        ("Ia-3d (230)", "Ia¯3d (230)"),
    ):
        source_text = source_text.replace(old, new)

    parsed, trace = (
        literature_runtime_evidence
        .parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction(
            source_text
        )
    )

    assert parsed == {"garnet_frustrated_magnet": True}
    assert trace["nearest_neighbor_exchange_k"] == pytest.approx(0.126)
    assert trace["ordering_temperature_k"] == pytest.approx(0.243)
    assert trace["spin_wave_gap_k"] == pytest.approx(0.62)
    assert len(trace["matched_anchors"]) == 14
    assert len(trace["text_spans"]) == 14


def test_quilliam_parser_handles_two_column_and_page_break_forms():
    source_text = QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT
    source_text = source_text.replace(
        "three-dimensional network of corner-sharing\ntriangles",
        "three-\n"
        "GGG RESULTS IN THE ADJACENT COLUMN\n"
        "dimensional network of corner-sharing triangles",
    )
    source_text = source_text.replace(
        "two interpenetrating networks of corner-sharing triangles, "
        "known as\nhyperkagome lattices",
        "two interpenetrating networks of corner-sharing triangles,\n"
        "FIG. 1 CAPTION CONTINUES AFTER A PAGE BREAK\f\n"
        "known as hyperkagome lattices",
    )
    source_text = source_text.replace(
        "transition is clearly first order",
        "transition is clearly first-\norder",
    )
    source_text = source_text.replace(
        "strong evidence of long-range order",
        "strong evidence of long-\nrange order",
    )

    parsed, trace = (
        literature_runtime_evidence
        .parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction(
            source_text
        )
    )

    assert parsed == {"garnet_frustrated_magnet": True}
    assert trace["ordering_assessment"].startswith(
        "sharp_first_order_transition"
    )
    assert len(trace["matched_anchors"]) == 14
    assert len(trace["text_spans"]) == 14


@pytest.mark.parametrize(
    "source_text",
    [
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "Juxtaposition of spin freezing and long range order",
            "Unrelated transport properties",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "J. A. Quilliam, S. Meng",
            "Example Author, Example Collaborator",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "Gd3Te2Li3O12 and Gd3Al5O12 exhibit clear ordering\n"
            "transitions at 243 mK and 175 mK",
            "unidentified compounds show no measured transition",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "nearest-neighbor antiferromagnetic Heisenberg\n"
            "exchange Hamiltonian H0 are highly frustrated",
            "ferromagnetic Ising model is unfrustrated",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "two interpenetrating networks of corner-sharing triangles, "
            "known as\nhyperkagome lattices",
            "one square lattice unrelated to a hyperkagome",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "largely isotropic S = 7/2 Gd3+ moments",
            "strongly Ising S = 1/2 moments",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "exchange scale J1 is approximately 0.1 to 0.14 K",
            "exchange scale J1 is approximately 1.0 to 1.4 K",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "nearest-neighbor exchange interaction\n"
            "H_Ex = sum_<i,j> J1 S_i dot S_j",
            "unspecified interaction without a Heisenberg term",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "and the dipolar interaction\n"
            "H_D = D sum_<i,j> r_nn^3/r_ij^3",
            "and no dipolar interaction",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "J1 = 126 mK for\nGTLG",
            "J1 = 1260 mK for GTLG",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "D = 45 mK. The ratio D/J1 progresses from GAG (0.34) to "
            "GTLG (0.36)",
            "D = 450 mK and D/J1 = 3.6 for GTLG",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "very sharp phase transition at\n243 mK. The transition is "
            "clearly first order",
            "broad crossover at 24.3 K with no transition",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "theta_CW approximately -2.7 K",
            "theta_CW approximately +2.7 K",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "frustration index f = |theta_CW|/T_C = 11",
            "frustration index f = 1",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "gap\nDelta approximately 0.62 K",
            "gap is unknown",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "strong evidence of long-range order",
            "evidence for a realized spin liquid without order",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "space group Ia-3d (230)",
            "space group P1",
        ),
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT.replace(
            "response of a\nhighly frustrated magnet",
            "response of an unfrustrated magnet",
        ),
    ],
)
def test_quilliam_parser_fails_closed_without_complete_gtlg_chain(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Quilliam GTLG frustrated-hyperkagome correction",
    ):
        (
            literature_runtime_evidence
            .parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction(
                source_text
            )
        )


@pytest.mark.parametrize("source_text", [None, "", "   ", 2013])
def test_quilliam_parser_rejects_non_text_or_empty_source(source_text):
    with pytest.raises(
        RuntimeEvidenceError,
        match="Quilliam GTLG frustrated-hyperkagome correction",
    ):
        (
            literature_runtime_evidence
            .parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction(
                source_text
            )
        )


def test_bergman_parser_extracts_diamond_spiral_surface_threshold_and_kernel():
    parsed, trace = literature_runtime_evidence.parse_bergman_diamond_spiral_surface(
        BERGMAN_DIAMOND_SOURCE_TEXT
    )

    assert parsed == {
        "spiral_surface_for_j2_over_j1_gt": 0.125,
    }
    assert trace["parser"] == "parse_bergman_diamond_spiral_surface"
    assert trace["equation"] == "5"
    assert len(trace["matched_anchors"]) == 3


@pytest.mark.parametrize(
    "source_text",
    [
        BERGMAN_DIAMOND_SOURCE_TEXT.replace(
            "frustrated diamond lattice", "frustrated square lattice"
        ),
        BERGMAN_DIAMOND_SOURCE_TEXT.replace(
            "0 <= J2/J1 <= 1/8 the ground state is the Neel phase. For larger J2 the\n"
            "Neel phase is supplanted by degenerate coplanar spin spirals whose wavevectors\n"
            "lie on a two-dimensional spiral surface.",
            "the ground state changes as J2/J1 increases.",
        ),
        BERGMAN_DIAMOND_SOURCE_TEXT.replace(
            "epsilon_pm(q) = 4 J2 [Lambda(q)^2 - 1] +/- 2 J1 Lambda(q). (5)",
            "the two bands are functions of momentum. (5)",
        ),
    ],
)
def test_bergman_parser_fails_closed_without_threshold_and_fourier_kernel(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Bergman diamond spiral surface"):
        literature_runtime_evidence.parse_bergman_diamond_spiral_surface(source_text)


def test_diamond_spiral_recompute_derives_one_eighth_from_band_minimum():
    assert literature_runtime_evidence.recompute_diamond_spiral_surface_threshold(
        lambda_max=2.0,
        below_ratio=0.1,
        above_ratio=0.2,
    ) == {
        "spiral_surface_for_j2_over_j1_gt": 0.125,
    }


def test_runtime_collector_recomputes_diamond_spiral_surface_threshold():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["diamond_j1_j2_spiral_surface_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "spiral_surface_for_j2_over_j1_gt": 0.125,
    }
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "e5eb4209a7a0801c9b8810e5db974b1ea1bcd4eabf9df5f9d3144a5a46cd23a2"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["equation"] == "5"
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_diamond_spiral_surface_threshold"
    )


def test_ross_parser_extracts_complete_local_pyrochlore_exchange_basis():
    parsed, trace = literature_runtime_evidence.parse_ross_pyrochlore_exchange_basis(
        ROSS_PYROCHLORE_EXCHANGE_SOURCE_TEXT
    )

    assert parsed == {"couplings": ["Jzz", "Jpm", "Jpmpm", "Jzpm"]}
    assert trace["parser"] == "parse_ross_pyrochlore_exchange_basis"
    assert trace["equation"] == "4"
    assert len(trace["matched_anchors"]) == 3


@pytest.mark.parametrize("missing_coupling", ["Jzz", "Jpm", "Jpmpm", "Jzpm"])
def test_ross_parser_fails_closed_when_any_exchange_channel_is_missing(
    missing_coupling,
):
    source_text = ROSS_PYROCHLORE_EXCHANGE_SOURCE_TEXT.replace(
        missing_coupling, f"missing_{missing_coupling}"
    )

    with pytest.raises(RuntimeEvidenceError, match="Ross pyrochlore exchange basis"):
        literature_runtime_evidence.parse_ross_pyrochlore_exchange_basis(source_text)


def test_runtime_collector_parses_complete_pyrochlore_exchange_basis():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["pyrochlore_anisotropic_exchange_jzz_jpm_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {"couplings": ["Jzz", "Jpm", "Jpmpm", "Jzpm"]}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "803d6280580a9970c7a54bf463b478564e9d4ca6b6b83d9c0728bae311e43cdc"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["equation"] == "4"
    assert "execution_trace" not in bundle


def test_kane_mele_hubbard_parser_extracts_spin_orbit_exchange_anisotropy():
    parsed, trace = (
        literature_runtime_evidence.parse_kane_mele_hubbard_spin_anisotropy(
            KANE_MELE_HUBBARD_SOURCE_TEXT
        )
    )

    assert parsed == {"spin_orbit_induced_anisotropy": True}
    assert trace["parser"] == "parse_kane_mele_hubbard_spin_anisotropy"
    assert trace["equation"] == "31"
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        KANE_MELE_HUBBARD_SOURCE_TEXT.replace(
            "honeycomb lattice", "square lattice"
        ),
        KANE_MELE_HUBBARD_SOURCE_TEXT.replace(
            "intrinsic\nspin-orbit", "spin-independent"
        ),
        KANE_MELE_HUBBARD_SOURCE_TEXT.replace(
            "At half filling", "Away from half filling"
        ),
        KANE_MELE_HUBBARD_SOURCE_TEXT.replace(
            "strong-coupling limit U -> infinity", "weak-coupling limit"
        ),
        KANE_MELE_HUBBARD_SOURCE_TEXT.replace(
            "-Sx_i Sx_j - Sy_i Sy_j + Sz_i Sz_j",
            "+Sx_i Sx_j + Sy_i Sy_j + Sz_i Sz_j",
        ),
        KANE_MELE_HUBBARD_SOURCE_TEXT.replace(
            "J2 = 4 lambda^2 / U", "J2 is a free parameter"
        ),
    ],
)
def test_kane_mele_hubbard_parser_fails_closed_without_complete_anisotropy_claim(
    source_text,
):
    with pytest.raises(
        RuntimeEvidenceError, match="Kane-Mele-Hubbard spin anisotropy"
    ):
        literature_runtime_evidence.parse_kane_mele_hubbard_spin_anisotropy(
            source_text
        )


def test_yb2ti2o7_parser_extracts_material_specific_exchange_fit_reference():
    parsed, trace = literature_runtime_evidence.parse_yb2ti2o7_exchange_fit(
        YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT
    )

    assert parsed == {"anisotropic_exchange_fit_reference": True}
    assert trace["parser"] == "parse_yb2ti2o7_exchange_fit"
    assert trace["equations"] == ["3", "4", "5"]
    assert len(trace["text_spans"]) == 6


@pytest.mark.parametrize(
    "source_text",
    [
        YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT.replace("Yb2Ti2O7", "Er2Ti2O7"),
        YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT.replace(
            "inelastic neutron scattering", "bulk magnetization"
        ),
        YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT.replace(
            "spin-wave theory", "mean-field theory"
        ),
        YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT.replace(
            "unambiguously extract all\nthe microscopic exchange parameters",
            "estimate one exchange parameter",
        ),
        YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT.replace(
            "J1, J2, J3, and J4", "J1 and J2"
        ),
        YB2TI2O7_EXCHANGE_FIT_SOURCE_TEXT.replace("Jzpm", "missing_channel"),
    ],
)
def test_yb2ti2o7_parser_fails_closed_without_material_method_and_full_fit(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Yb2Ti2O7 exchange fit"):
        literature_runtime_evidence.parse_yb2ti2o7_exchange_fit(source_text)


def test_harris_spin_ice_parser_derives_normalized_tetrahedron_levels():
    parsed, trace = (
        literature_runtime_evidence.parse_harris_spin_ice_tetrahedron_levels(
            HARRIS_SPIN_ICE_TETRAHEDRON_SOURCE_TEXT
        )
    )

    assert parsed == {
        "two_in_two_out_energy": -2.0,
        "three_in_one_out_energy": 0.0,
        "all_in_all_out_energy": 6.0,
        "two_in_two_out_degeneracy": 6,
    }
    assert trace["parser"] == "parse_harris_spin_ice_tetrahedron_levels"
    assert trace["normalization"] == "J_eff=1 in H=J_eff sum_<ij> sigma_i sigma_j"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        HARRIS_SPIN_ICE_TETRAHEDRON_SOURCE_TEXT.replace(
            "ferromagnetic pyrochlore", "antiferromagnetic square lattice"
        ),
        HARRIS_SPIN_ICE_TETRAHEDRON_SOURCE_TEXT.replace(
            "<111>-type directions", "global <001> direction"
        ),
        HARRIS_SPIN_ICE_TETRAHEDRON_SOURCE_TEXT.replace(
            "single tetrahedron", "single triangle"
        ),
        HARRIS_SPIN_ICE_TETRAHEDRON_SOURCE_TEXT.replace(
            "two spins in\nand two spins out", "all spins in"
        ),
        HARRIS_SPIN_ICE_TETRAHEDRON_SOURCE_TEXT.replace(
            "identical to the ice rule", "unrelated to the ice rule"
        ),
    ],
)
def test_harris_spin_ice_parser_fails_closed_without_complete_ice_rule_context(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Harris spin-ice tetrahedron"):
        literature_runtime_evidence.parse_harris_spin_ice_tetrahedron_levels(
            source_text
        )


def test_spin_ice_tetrahedron_adapter_enumerates_all_sixteen_configurations():
    assert literature_runtime_evidence.recompute_spin_ice_tetrahedron_levels(
        effective_exchange=1.0
    ) == {
        "two_in_two_out_energy": -2.0,
        "three_in_one_out_energy": 0.0,
        "all_in_all_out_energy": 6.0,
        "two_in_two_out_degeneracy": 6,
    }


@pytest.mark.parametrize("effective_exchange", [0.0, -1.0, True, "1"])
def test_spin_ice_tetrahedron_adapter_rejects_invalid_exchange(
    effective_exchange,
):
    with pytest.raises(RuntimeEvidenceError, match="effective exchange"):
        literature_runtime_evidence.recompute_spin_ice_tetrahedron_levels(
            effective_exchange=effective_exchange
        )


def test_runtime_collector_adds_three_source_bound_anisotropy_and_ice_routes():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    kane_bundle = evidence[
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference"
    ]
    kane_record = kane_bundle["runtime_evidence_record"]
    assert kane_record["evidence_mode"] == "local_source_parse"
    assert kane_record["source_sha256"] == (
        "9b9feade7128d59015c15aa056c564bc05270134d50e9e642e870be76327c596"
    )
    assert kane_record["source_operand"] == {
        "spin_orbit_induced_anisotropy": True
    }
    assert kane_record["registry_operand"] == kane_record["source_operand"]
    assert kane_record["comparison"] == {
        "kind": "exact_field_map",
        "matched": True,
    }
    assert kane_bundle["extraction_trace"]["parser"] == (
        "parse_kane_mele_hubbard_spin_anisotropy"
    )
    assert "execution_trace" not in kane_bundle

    yb_bundle = evidence["yb2ti2o7_pyrochlore_exchange_reference"]
    yb_record = yb_bundle["runtime_evidence_record"]
    assert yb_record["evidence_mode"] == "local_source_parse"
    assert yb_record["source_sha256"] == (
        "803d6280580a9970c7a54bf463b478564e9d4ca6b6b83d9c0728bae311e43cdc"
    )
    assert yb_record["source_operand"] == {
        "anisotropic_exchange_fit_reference": True
    }
    assert yb_record["registry_operand"] == yb_record["source_operand"]
    assert yb_record["comparison"] == {
        "kind": "exact_field_map",
        "matched": True,
    }
    assert yb_bundle["extraction_trace"]["parser"] == (
        "parse_yb2ti2o7_exchange_fit"
    )
    assert "execution_trace" not in yb_bundle

    ice_bundle = evidence["spin_ice_tetrahedron_nn_ice_rule"]
    ice_record = ice_bundle["runtime_evidence_record"]
    ice_expected = {
        "two_in_two_out_energy": -2.0,
        "three_in_one_out_energy": 0.0,
        "all_in_all_out_energy": 6.0,
        "two_in_two_out_degeneracy": 6,
    }
    assert ice_record["evidence_mode"] == "local_recompute"
    assert ice_record["source_sha256"] == (
        "8adfbb06f3dc888f49ac5aebd82830ac9e5495287ea567f742390471b9625238"
    )
    assert ice_record["source_operand"] == ice_expected
    assert ice_record["computed_operand"] == ice_expected
    assert ice_record["registry_operand"] == ice_expected
    assert ice_record["comparison"] == {
        "kind": "exact_field_map",
        "matched": True,
    }
    assert ice_bundle["extraction_trace"]["parser"] == (
        "parse_harris_spin_ice_tetrahedron_levels"
    )
    assert ice_bundle["execution_trace"]["adapter"] == (
        "recompute_spin_ice_tetrahedron_levels"
    )


def test_kharkov_parser_derives_square_j1_j3_spiral_condition():
    parsed, trace = (
        literature_runtime_evidence.parse_kharkov_square_j1_j3_lifshitz(
            KHARKOV_SQUARE_J1_J3_SOURCE_TEXT
        )
    )

    assert parsed == {"spiral_condition": "cos(Q)=J1/(4J3)"}
    assert trace["parser"] == "parse_kharkov_square_j1_j3_lifshitz"
    assert trace["equation"] == "34"
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        KHARKOV_SQUARE_J1_J3_SOURCE_TEXT.replace(
            "staggered magnetization", "uniform magnetization"
        ),
        KHARKOV_SQUARE_J1_J3_SOURCE_TEXT.replace(
            "Q is the pitch of the spiral", "Q is an unspecified parameter"
        ),
        KHARKOV_SQUARE_J1_J3_SOURCE_TEXT.replace(
            "square lattice", "triangular lattice"
        ),
        KHARKOV_SQUARE_J1_J3_SOURCE_TEXT.replace(
            "third-nearest-neighbor", "second-nearest-neighbor"
        ),
        KHARKOV_SQUARE_J1_J3_SOURCE_TEXT.replace(
            "In the classical limit", "In a quantum approximation"
        ),
        KHARKOV_SQUARE_J1_J3_SOURCE_TEXT.replace("J3/J1 = 1/4", "J3/J1 = 1/3"),
    ],
)
def test_kharkov_parser_fails_closed_without_model_convention_and_boundary(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="square J1-J3 Lifshitz"):
        literature_runtime_evidence.parse_kharkov_square_j1_j3_lifshitz(
            source_text
        )


def test_square_j1_j3_adapter_derives_symbolic_condition_from_bond_energy():
    assert literature_runtime_evidence.recompute_square_j1_j3_spiral_condition(
        below_ratio=0.2,
        above_ratio=0.5,
    ) == {"spiral_condition": "cos(Q)=J1/(4J3)"}


@pytest.mark.parametrize(
    ("below_ratio", "above_ratio"),
    [
        (0.0, 0.5),
        (0.25, 0.5),
        (0.2, 0.25),
        (0.5, 0.2),
        (True, 0.5),
    ],
)
def test_square_j1_j3_adapter_requires_probes_straddling_lifshitz_point(
    below_ratio,
    above_ratio,
):
    with pytest.raises(RuntimeEvidenceError, match="J1-J3 Lifshitz probes"):
        literature_runtime_evidence.recompute_square_j1_j3_spiral_condition(
            below_ratio=below_ratio,
            above_ratio=above_ratio,
        )


def test_liu_parser_extracts_multiple_distinct_paramagnetic_regions():
    parsed, trace = (
        literature_runtime_evidence.parse_liu_square_j1_j2_j3_paramagnets(
            LIU_SQUARE_J1_J2_J3_SOURCE_TEXT
        )
    )

    assert parsed == {"multiple_paramagnetic_regions": True}
    assert trace["parser"] == "parse_liu_square_j1_j2_j3_paramagnets"
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        LIU_SQUARE_J1_J2_J3_SOURCE_TEXT.replace("spin-1/2", "spin-1"),
        LIU_SQUARE_J1_J2_J3_SOURCE_TEXT.replace(
            "square-lattice", "honeycomb-lattice"
        ),
        LIU_SQUARE_J1_J2_J3_SOURCE_TEXT.replace(
            "finite projected entangled pair state (PEPS)", "mean-field"
        ),
        LIU_SQUARE_J1_J2_J3_SOURCE_TEXT.replace(
            "paramagnetic\nstates", "magnetically ordered states"
        ),
        LIU_SQUARE_J1_J2_J3_SOURCE_TEXT.replace(
            "two successive gapless quantum spin liquid (QSL) and VBS phases",
            "one broad crossover",
        ),
        LIU_SQUARE_J1_J2_J3_SOURCE_TEXT.replace(
            "valence-bond solid (VBS)", "featureless regime"
        ).replace("VBS phases", "featureless regimes"),
    ],
)
def test_liu_parser_fails_closed_without_two_source_identified_paramagnets(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="multiple paramagnetic regions"):
        literature_runtime_evidence.parse_liu_square_j1_j2_j3_paramagnets(
            source_text
        )


def test_gong_parser_extracts_long_range_plaquette_vbs_reference():
    parsed, trace = literature_runtime_evidence.parse_gong_square_j1_j2_pvb(
        GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT
    )

    assert parsed == {"columnar_or_plaquette_vbs_reference": True}
    assert trace["parser"] == "parse_gong_square_j1_j2_pvb"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT.replace("spin-1/2", "spin-1"),
        GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT.replace(
            "square lattice", "triangular lattice"
        ),
        GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT.replace(
            "first- and second-neighbor antiferromagnetic", "nearest-neighbor"
        ),
        GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT.replace(
            "density matrix renormalization group", "mean-field"
        ),
        GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT.replace(
            "plaquette valence-bond (PVB)", "featureless"
        ),
        GONG_SQUARE_J1_J2_PVB_SOURCE_TEXT.replace(
            "long-range PVB order in the two-dimensional limit",
            "short-range correlations on finite cylinders",
        ),
    ],
)
def test_gong_parser_fails_closed_without_model_method_and_long_range_pvb(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="square J1-J2 plaquette VBS"):
        literature_runtime_evidence.parse_gong_square_j1_j2_pvb(source_text)


def test_runtime_collector_adds_three_square_lattice_phase_routes():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    lifshitz_bundle = evidence["square_j1_j3_classical_lifshitz_reference"]
    lifshitz_record = lifshitz_bundle["runtime_evidence_record"]
    lifshitz_expected = {"spiral_condition": "cos(Q)=J1/(4J3)"}
    assert lifshitz_record["evidence_mode"] == "local_recompute"
    assert lifshitz_record["source_sha256"] == (
        "86e915e6ab37f05914df708c551cb82a4ffa6f67b0fadda2b08430a4cee486cd"
    )
    assert lifshitz_record["source_operand"] == lifshitz_expected
    assert lifshitz_record["computed_operand"] == lifshitz_expected
    assert lifshitz_record["registry_operand"] == lifshitz_expected
    assert lifshitz_record["comparison"] == {
        "kind": "exact_field_map",
        "matched": True,
    }
    assert lifshitz_bundle["execution_trace"]["adapter"] == (
        "recompute_square_j1_j3_spiral_condition"
    )

    multiple_bundle = evidence["j1_j2_j3_square_quantum_phase_reference"]
    multiple_record = multiple_bundle["runtime_evidence_record"]
    assert multiple_record["evidence_mode"] == "local_source_parse"
    assert multiple_record["source_sha256"] == (
        "5fc1945c780a2b4d6cba45490123acef5634d0210c1e0466566d751cb8c24846"
    )
    assert multiple_record["source_operand"] == {
        "multiple_paramagnetic_regions": True
    }
    assert multiple_record["registry_operand"] == multiple_record["source_operand"]
    assert multiple_record["comparison"]["matched"] is True

    pvb_bundle = evidence["j1_j2_square_dqcp_columnar_vbs_reference"]
    pvb_record = pvb_bundle["runtime_evidence_record"]
    assert pvb_record["evidence_mode"] == "local_source_parse"
    assert pvb_record["source_sha256"] == (
        "1fcc33834d0a3467cb89cffda2aec5186dd042ce3d995a3a97aabf5682f3d3bb"
    )
    assert pvb_record["source_operand"] == {
        "columnar_or_plaquette_vbs_reference": True
    }
    assert pvb_record["registry_operand"] == pvb_record["source_operand"]
    assert pvb_record["comparison"]["matched"] is True


def test_moessner_parser_extracts_pyrochlore_constraint_and_zero_mode_band():
    parsed, trace = (
        literature_runtime_evidence.parse_moessner_pyrochlore_flat_band(
            MOESSNER_PYROCHLORE_FLAT_BAND_SOURCE_TEXT
        )
    )

    assert parsed == {
        "local_constraint": "sum_tetrahedron_spins_zero",
        "lowest_lt_flat_band": True,
    }
    assert trace["parser"] == "parse_moessner_pyrochlore_flat_band"
    assert "zero-frequency band" in trace["derivation"]
    assert len(trace["text_spans"]) == 4


def test_moessner_parser_accepts_verified_two_column_ocr_interleaving():
    source_text = MOESSNER_PYROCHLORE_FLAT_BAND_SOURCE_TEXT.replace(
        "For a generic ground state,",
        "If the ground state is a generic one,",
    ).replace(
        "finite frequencies",
        "finite Heisenberg spins, it sets an upper limit of 0.04 quartic "
        "frequencies",
    )

    parsed, _trace = (
        literature_runtime_evidence.parse_moessner_pyrochlore_flat_band(
            source_text
        )
    )

    assert parsed == {
        "local_constraint": "sum_tetrahedron_spins_zero",
        "lowest_lt_flat_band": True,
    }


@pytest.mark.parametrize(
    "source_text",
    [
        MOESSNER_PYROCHLORE_FLAT_BAND_SOURCE_TEXT.replace(
            "classical Heisenberg", "quantum Ising"
        ),
        MOESSNER_PYROCHLORE_FLAT_BAND_SOURCE_TEXT.replace(
            "pyrochlore lattice", "kagome lattice"
        ),
        MOESSNER_PYROCHLORE_FLAT_BAND_SOURCE_TEXT.replace(
            "L_a = 0 for each unit separately",
            "L_a is unconstrained",
        ),
        MOESSNER_PYROCHLORE_FLAT_BAND_SOURCE_TEXT.replace(
            "one quarter have zero frequency",
            "one quarter have a finite frequency",
        ),
    ],
)
def test_moessner_parser_fails_closed_without_model_constraint_and_flat_zero_modes(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="pyrochlore flat-band"):
        literature_runtime_evidence.parse_moessner_pyrochlore_flat_band(
            source_text
        )


def test_richter_parser_normalizes_square_j1_j2_window_outward():
    parsed, trace = (
        literature_runtime_evidence.parse_richter_square_j1_j2_window(
            RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT
        )
    )

    assert parsed == {"nonmagnetic_window_approx": [0.4, 0.6]}
    assert trace["parser"] == "parse_richter_square_j1_j2_window"
    assert trace["raw_transition_points"] == [0.454, 0.588]
    assert trace["normalization"] == "outward_to_one_decimal"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT.replace(
            "spin-1/2", "spin-1"
        ),
        RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT.replace(
            "square lattice", "triangular lattice"
        ),
        RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT.replace(
            "coupled cluster method", "mean-field method"
        ),
        RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT.replace(
            "magnetically disordered\nquantum paramagnetic phase",
            "ferromagnetically ordered phase",
        ),
        RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT.replace(
            "Neel and collinear antiferromagnetic phases",
            "two unspecified phases",
        ),
    ],
)
def test_richter_parser_fails_closed_without_model_method_and_phase_context(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="square J1-J2 window"):
        literature_runtime_evidence.parse_richter_square_j1_j2_window(
            source_text
        )


def test_richter_parser_does_not_copy_the_registered_window():
    changed = RICHTER_SQUARE_J1_J2_WINDOW_SOURCE_TEXT.replace(
        "J2c1 = 0.454 J1", "J2c1 = 0.512 J1"
    )

    parsed, _ = literature_runtime_evidence.parse_richter_square_j1_j2_window(
        changed
    )

    assert parsed == {"nonmagnetic_window_approx": [0.5, 0.6]}


def test_gardner_parser_extracts_tb2ti2o7_cooperative_paramagnet_candidate():
    parsed, trace = literature_runtime_evidence.parse_tb2ti2o7_cooperative_paramagnet(
        GARDNER_TB2TI2O7_SOURCE_TEXT
    )

    assert parsed == {"spin_liquid_candidate": True}
    assert trace["parser"] == "parse_tb2ti2o7_cooperative_paramagnet"
    assert len(trace["text_spans"]) == 5


@pytest.mark.parametrize(
    "source_text",
    [
        GARDNER_TB2TI2O7_SOURCE_TEXT.replace("Tb2Ti2O7", "Y2Ti2O7"),
        GARDNER_TB2TI2O7_SOURCE_TEXT.replace(
            "pyrochlore antiferromagnet", "square-lattice ferromagnet"
        ),
        GARDNER_TB2TI2O7_SOURCE_TEXT.replace(
            "Neutron scattering, muon spin relaxation, and dc susceptibility",
            "A mean-field calculation",
        ),
        GARDNER_TB2TI2O7_SOURCE_TEXT.replace(
            "remains paramagnetic down to 0.07 K rather than ordering into a\n"
            "conventional Neel or spin-glass-like state",
            "orders into a conventional Neel state at 0.07 K",
        ),
        GARDNER_TB2TI2O7_SOURCE_TEXT.replace(
            "persistent spin\ndynamics", "static frozen moments"
        ),
        GARDNER_TB2TI2O7_SOURCE_TEXT.replace(
            "cooperative paramagnet", "conventional antiferromagnet"
        ),
    ],
)
def test_gardner_parser_fails_closed_without_material_methods_and_dynamic_disorder(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="Tb2Ti2O7 cooperative"):
        literature_runtime_evidence.parse_tb2ti2o7_cooperative_paramagnet(
            source_text
        )


def test_ramirez_parser_extracts_absence_of_conventional_order_in_scgo():
    parsed, trace = literature_runtime_evidence.parse_scgo_unconventional_low_t_state(
        RAMIREZ_SCGO_SOURCE_TEXT
    )

    assert parsed == {"no_conventional_order_down_to_low_t": True}
    assert trace["parser"] == "parse_scgo_unconventional_low_t_state"
    assert len(trace["text_spans"]) == 4


@pytest.mark.parametrize(
    "source_text",
    [
        RAMIREZ_SCGO_SOURCE_TEXT.replace("SrCr8Ga4O19", "Tb2Ti2O7"),
        RAMIREZ_SCGO_SOURCE_TEXT.replace(
            "kagome lattice", "unfrustrated square lattice"
        ),
        RAMIREZ_SCGO_SOURCE_TEXT.replace(
            "Curie-Weiss temperature is 515 K", "Curie-Weiss scale is unknown"
        ),
        RAMIREZ_SCGO_SOURCE_TEXT.replace(
            "no conventional ordering anomaly is seen until 3.5 K",
            "conventional long-range order appears at 500 K",
        ),
        RAMIREZ_SCGO_SOURCE_TEXT.replace(
            "spin-glass-type freezing transition rather than conventional"
            "\nlong-range magnetic order",
            "conventional antiferromagnetic long-range order",
        ),
    ],
)
def test_ramirez_parser_fails_closed_without_scgo_frustration_and_nonconventional_state(
    source_text,
):
    with pytest.raises(RuntimeEvidenceError, match="SCGO low-temperature"):
        literature_runtime_evidence.parse_scgo_unconventional_low_t_state(
            source_text
        )


def test_runtime_collector_adds_four_verified_current_source_routes():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    expected_by_name = {
        "pyrochlore_heisenberg_coulomb_phase_flat_band": (
            "7e8270b928af3e4be502d39eae3a4340649e0c007246515bbdbb02af3a1e4d05",
            {
                "local_constraint": "sum_tetrahedron_spins_zero",
                "lowest_lt_flat_band": True,
            },
            "parse_moessner_pyrochlore_flat_band",
        ),
        "j1_j2_square_spin_half_neel_collinear_transition_reference": (
            "3f1ed02ca7bf2f31f2d6fe05e5fea066db55287d91df82fe8e08eb04c7117324",
            {"nonmagnetic_window_approx": [0.4, 0.6]},
            "parse_richter_square_j1_j2_window",
        ),
        "tb2ti2o7_pyrochlore_spin_liquid_reference": (
            "7b21ba6fcbb943247e6e3240979ab98729b8f26c5ff6a331428b866ba3eb622a",
            {"spin_liquid_candidate": True},
            "parse_tb2ti2o7_cooperative_paramagnet",
        ),
        "scgo_kagome_bilayer_spin_liquid_reference": (
            "596736ead12e551521607016c2340f2e6112009ee6dacf9cdcbdc9ea72d62196",
            {"no_conventional_order_down_to_low_t": True},
            "parse_scgo_unconventional_low_t_state",
        ),
    }

    for benchmark_name, (
        expected_sha256,
        expected_operand,
        expected_parser,
    ) in expected_by_name.items():
        bundle = evidence[benchmark_name]
        record = bundle["runtime_evidence_record"]
        assert record["evidence_mode"] == "local_source_parse"
        assert record["source_sha256"] == expected_sha256
        assert record["source_operand"] == expected_operand
        assert record["registry_operand"] == expected_operand
        assert record["comparison"] == {
            "kind": "exact_field_map",
            "matched": True,
        }
        assert bundle["extraction_trace"]["parser"] == expected_parser
        assert "execution_trace" not in bundle


def test_runtime_collector_recomputes_square_potts_critical_point():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["square_potts_exact_critical_point"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "critical_beta_j": "log(1 + sqrt(q))",
        "continuous_for_q_le_4": True,
    }
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "df5d8ded4bbd88b7cdcd47f27b53c91f5dfaffe22b4717f67669707c0d5aaaae"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_square_potts_critical_point"
    )
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_square_potts_critical_point"
    )


def test_runtime_collector_parses_q5_clock_three_phase_regime():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["square_clock_q5_two_bkt_transitions"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "transition_count": 2,
        "phase_sequence": ["ordered", "critical", "disordered"],
    }
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "ebc24f7c73ea0d84ed489082274d72ca08cb96504c0ad92a4ee1c2cdcc0d2604"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_lapilli_square_clock_three_phase_regime"
    )
    assert bundle["extraction_trace"]["registered_q"] == 5
    assert "execution_trace" not in bundle


def test_audit_rejects_legacy_prose_without_runtime_record():
    audit = build_literature_reproduction_audit(runtime_evidence_enabled=False)
    rows = {row["name"]: row for row in audit["rows"]}

    assert rows["majundar_ghosh_chain_exact_dimer_point"][
        "strict_literature_match_label"
    ] == "no"
    assert rows["cri3_honeycomb_ferromagnet_reference"][
        "strict_literature_match_label"
    ] == "no"


def test_structural_validator_accepts_matching_source_parse_bundle():
    category = (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", _source_parse_bundle()
        )
    )

    assert category == "strict_local_source_parsed"


def test_structural_validator_accepts_source_parse_with_absolute_tolerance():
    bundle = _source_parse_bundle()
    record = bundle["runtime_evidence_record"]
    record["source_operand"] = {"ferromagnetic_order": 0.41050}
    record["registry_operand"] = {"ferromagnetic_order": 0.41048}
    record["comparison"] = {
        "kind": "absolute_tolerance",
        "absolute_tolerance": 0.00005,
        "absolute_differences": {"ferromagnetic_order": 0.00002},
        "matched": True,
    }

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", bundle
        )
        == "strict_local_source_parsed"
    )


@pytest.mark.parametrize(
    "comparison",
    [
        {
            "kind": "absolute_tolerance",
            "absolute_tolerance": -1.0,
            "absolute_differences": {"ferromagnetic_order": 0.00002},
            "matched": True,
        },
        {
            "kind": "absolute_tolerance",
            "absolute_tolerance": 0.00001,
            "absolute_differences": {"ferromagnetic_order": 0.00002},
            "matched": True,
        },
        {
            "kind": "absolute_tolerance",
            "absolute_tolerance": 0.00005,
            "absolute_differences": {"ferromagnetic_order": 0.0},
            "matched": True,
        },
    ],
)
def test_structural_validator_rejects_invalid_absolute_tolerance_comparison(comparison):
    bundle = _source_parse_bundle()
    record = bundle["runtime_evidence_record"]
    record["source_operand"] = {"ferromagnetic_order": 0.41050}
    record["registry_operand"] = {"ferromagnetic_order": 0.41048}
    record["comparison"] = comparison

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", bundle
        )
        is None
    )


def test_structural_validator_rejects_source_parse_when_comparison_does_not_match():
    bundle = _source_parse_bundle()
    bundle["runtime_evidence_record"]["comparison"]["matched"] = False

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_runtime_evidence_with_empty_source_hash():
    record = {**_runtime_source_parse_record(), "source_sha256": ""}
    extraction_trace = {**_extraction_trace(), "source_sha256": ""}
    bundle = {
        "runtime_evidence_record": record,
        "extraction_trace": extraction_trace,
    }

    assert _structural_label(bundle) == "no"


def _local_recompute_bundle(*, adapter="xxx_spin_half_chain_bethe_energy_per_site"):
    benchmark_name = "xxx_spin_half_chain_bethe_ground_state"
    operand = {"energy_per_site": -0.4431471805599453}
    record = {
        **_runtime_source_parse_record(),
        "benchmark_name": benchmark_name,
        "evidence_mode": "local_recompute",
        "source_operand": operand,
        "computed_operand": operand,
        "registry_operand": operand,
    }
    execution_trace = {
        "benchmark_name": benchmark_name,
        "source_sha256": record["source_sha256"],
        "adapter_parameters": {"exchange": 1.0},
        "computed_operand": operand,
    }
    if adapter is not None:
        execution_trace["adapter"] = adapter
    extraction_trace = {
        **_extraction_trace(),
        "benchmark_name": benchmark_name,
    }
    return {
        "runtime_evidence_record": record,
        "execution_trace": execution_trace,
        "extraction_trace": extraction_trace,
    }


def _source_parse_bundle():
    return {
        "runtime_evidence_record": _runtime_source_parse_record(),
        "extraction_trace": _extraction_trace(),
    }


def _mutate_bundle(bundle, *changes):
    mutated = deepcopy(bundle)
    for path, value in changes:
        target = mutated
        for key in path[:-1]:
            target = target[key]
        if value is MISSING:
            target.pop(path[-1], None)
        else:
            target[path[-1]] = value
    return mutated


def _normalized_changes(changes):
    if (
        len(changes) == 2
        and isinstance(changes[0], tuple)
        and all(isinstance(key, str) for key in changes[0])
    ):
        return (changes,)
    return changes


def _structural_label(bundle, *, benchmark_name=None):
    if benchmark_name is None:
        benchmark_name = bundle["runtime_evidence_record"]["benchmark_name"]
    category = (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
    )
    return "yes" if category is not None else "no"


def test_structural_validator_rejects_runtime_comparison_without_exact_field_map_kind():
    bundle = _mutate_bundle(
        _source_parse_bundle(),
        (("runtime_evidence_record", "comparison", "kind"), "approximate"),
    )

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "source_sha256",
    [
        pytest.param("a" * 63, id="wrong-length"),
        pytest.param("A" * 64, id="uppercase-hex"),
        pytest.param("g" * 64, id="non-hex"),
    ],
)
def test_structural_validator_rejects_malformed_source_sha256(source_sha256):
    bundle = _mutate_bundle(
        _source_parse_bundle(),
        (("runtime_evidence_record", "source_sha256"), source_sha256),
        (("extraction_trace", "source_sha256"), source_sha256),
    )

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "path,value",
    [
        pytest.param(
            ("runtime_evidence_record", "benchmark_name"),
            "wrong_benchmark",
            id="record-benchmark-mismatch",
        ),
        pytest.param(
            ("extraction_trace", "benchmark_name"),
            "wrong_benchmark",
            id="extraction-benchmark-mismatch",
        ),
        pytest.param(
            ("extraction_trace", "source_sha256"),
            "b" * 64,
            id="extraction-sha-mismatch",
        ),
    ],
)
def test_structural_validator_rejects_runtime_or_extraction_identity_mismatch(path, value):
    benchmark_name = "cri3_honeycomb_ferromagnet_reference"
    bundle = _mutate_bundle(_source_parse_bundle(), (path, value))

    assert _structural_label(bundle, benchmark_name=benchmark_name) == "no"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            (("runtime_evidence_record", "source_operand"), MISSING),
            id="source-operand-missing",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_operand"), MISSING),
            id="registry-operand-missing",
        ),
        pytest.param(
            (
                (("runtime_evidence_record", "source_operand"), MISSING),
                (("runtime_evidence_record", "registry_operand"), MISSING),
            ),
            id="source-and-registry-operands-missing",
        ),
    ],
)
def test_structural_validator_rejects_source_parse_with_missing_required_operands(changes):
    bundle = _mutate_bundle(_source_parse_bundle(), *_normalized_changes(changes))

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_local_recompute_with_missing_computed_operand():
    bundle = _mutate_bundle(
        _local_recompute_bundle(),
        (("runtime_evidence_record", "computed_operand"), MISSING),
        (("execution_trace", "computed_operand"), MISSING),
    )

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "path,value",
    [
        pytest.param(("extraction_trace", "parser"), MISSING, id="parser-missing"),
        pytest.param(("extraction_trace", "parser"), "", id="parser-empty"),
        pytest.param(
            ("extraction_trace", "matched_anchors"),
            MISSING,
            id="matched-anchors-missing",
        ),
        pytest.param(
            ("extraction_trace", "matched_anchors"), [], id="matched-anchors-empty"
        ),
        pytest.param(
            ("extraction_trace", "matched_anchors"),
            [""],
            id="matched-anchors-invalid-item",
        ),
        pytest.param(
            ("extraction_trace", "matched_anchors"),
            "anchor",
            id="matched-anchors-bare-string",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"), MISSING, id="text-spans-missing"
        ),
        pytest.param(("extraction_trace", "text_spans"), [], id="text-spans-empty"),
        pytest.param(
            ("extraction_trace", "text_spans"), "0:1", id="text-spans-bare-string"
        ),
        pytest.param(
            ("extraction_trace", "text_spans"), [[0, 0]], id="text-span-empty"
        ),
        pytest.param(
            ("extraction_trace", "text_spans"), [[-1, 2]], id="text-span-negative"
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [["0", 2]],
            id="text-span-noninteger",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [[0, 1, 2]],
            id="text-span-wrong-arity",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [[True, 2]],
            id="text-span-boolean-start",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [[0, False]],
            id="text-span-boolean-end",
        ),
    ],
)
def test_structural_validator_rejects_malformed_extraction_trace_structure(path, value):
    bundle = _mutate_bundle(_source_parse_bundle(), (path, value))

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            (("runtime_evidence_record", "source_id"), MISSING),
            id="source-id-missing",
        ),
        pytest.param(
            (("runtime_evidence_record", "source_id"), ""), id="source-id-empty"
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector"), None),
            id="selector-nonmapping",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), []),
            id="selector-path-empty",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), "path"),
            id="selector-path-bare-string",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), [""]),
            id="selector-path-empty-item",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), ["  "]),
            id="selector-path-whitespace-item",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), []),
            id="selector-fields-empty",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), "field"),
            id="selector-fields-bare-string",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), [""]),
            id="selector-fields-empty-item",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), ["  "]),
            id="selector-fields-whitespace-item",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "registry_selector", "fields"),
                ["ferromagnetic_order", "ferromagnetic_order"],
            ),
            id="selector-fields-duplicate",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "registry_selector", "fields"),
                ["different_field"],
            ),
            id="selector-fields-do-not-match-operands",
        ),
        pytest.param(
            (
                (("runtime_evidence_record", "source_operand"), {}),
                (("runtime_evidence_record", "registry_operand"), {}),
            ),
            id="operands-empty",
        ),
        pytest.param(
            (
                (("runtime_evidence_record", "source_operand"), "value"),
                (("runtime_evidence_record", "registry_operand"), "value"),
            ),
            id="operands-nonmapping",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "source_operand"),
                {"different_field": True},
            ),
            id="source-operand-selector-key-mismatch",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "registry_operand"),
                {"different_field": True},
            ),
            id="registry-operand-selector-key-mismatch",
        ),
    ],
)
def test_structural_validator_rejects_malformed_record_provenance_selector_or_operands(changes):
    bundle = _mutate_bundle(_source_parse_bundle(), *_normalized_changes(changes))

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            (("execution_trace", "adapter_parameters"), MISSING),
            id="adapter-parameters-missing",
        ),
        pytest.param(
            (("execution_trace", "adapter_parameters"), []),
            id="adapter-parameters-nonmapping",
        ),
        pytest.param(
            (("execution_trace", "computed_operand"), {}),
            id="trace-computed-operand-empty",
        ),
        pytest.param(
            (("execution_trace", "computed_operand"), "value"),
            id="trace-computed-operand-nonmapping",
        ),
        pytest.param(
            (("execution_trace", "benchmark_name"), "wrong_benchmark"),
            id="execution-benchmark-mismatch",
        ),
        pytest.param(
            (("execution_trace", "source_sha256"), "b" * 64),
            id="execution-sha-mismatch",
        ),
        pytest.param(
            (
                ("execution_trace", "computed_operand"),
                {"different_field": -0.4431471805599453},
            ),
            id="trace-computed-operand-selector-key-mismatch",
        ),
        pytest.param(
            (
                (
                    ("runtime_evidence_record", "computed_operand"),
                    {"different_field": -0.4431471805599453},
                ),
                (
                    ("execution_trace", "computed_operand"),
                    {"different_field": -0.4431471805599453},
                ),
            ),
            id="record-computed-operand-selector-key-mismatch",
        ),
    ],
)
def test_structural_validator_rejects_malformed_local_recompute_execution_structure(changes):
    bundle = _mutate_bundle(_local_recompute_bundle(), *_normalized_changes(changes))

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "adapter",
    [
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
    ],
)
def test_structural_validator_rejects_local_recompute_without_named_adapter(adapter):
    bundle = _local_recompute_bundle(adapter=adapter)

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_local_recompute_when_trace_computed_operand_mismatches():
    bundle = _local_recompute_bundle()
    bundle["execution_trace"]["computed_operand"] = {"energy_per_site": -0.44}

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_local_recompute_without_three_matching_operands():
    bundle = _local_recompute_bundle()
    record = bundle["runtime_evidence_record"]
    record["computed_operand"] = {"energy_per_site": -0.44}
    bundle["execution_trace"]["computed_operand"] = record["computed_operand"]

    assert _structural_label(bundle) == "no"


def test_runtime_collector_executes_xxx_adapter_on_audit_path(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(*, exchange):
        calls.append(exchange)
        return 0.25 - 0.6931471805599453

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "xxx_spin_half_chain_bethe_energy_per_site",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [1.0]
    record = evidence["xxx_spin_half_chain_bethe_ground_state"][
        "runtime_evidence_record"
    ]
    assert record["comparison"]["matched"] is True
    assert record["computed_operand"] == record["source_operand"]


def test_registry_selector_override_can_only_narrow_registered_fields():
    selector = {
        "path": ("standard_result",),
        "fields": ("formula", "correlation_length_beta_1_j_1"),
    }

    narrowed = literature_runtime_evidence._narrow_registry_selector(
        selector, ("correlation_length_beta_1_j_1",)
    )

    assert narrowed == {
        "path": ["standard_result"],
        "fields": ["correlation_length_beta_1_j_1"],
    }
    with pytest.raises(RuntimeEvidenceError, match="registered selector fields"):
        literature_runtime_evidence._narrow_registry_selector(
            selector, ("unregistered",)
        )


def test_runtime_collector_recomputes_taylor_ising_correlation_length(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(*, beta, exchange):
        calls.append({"beta": beta, "exchange": exchange})
        return -1.0 / literature_runtime_evidence.math.log(
            literature_runtime_evidence.math.tanh(beta * exchange)
        )

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "classical_ising_chain_correlation_length",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [{"beta": 1.0, "exchange": 1.0}]
    record = evidence["one_dimensional_classical_ising_correlation_length"][
        "runtime_evidence_record"
    ]
    assert record["registry_selector"] == {
        "path": ["standard_result"],
        "fields": ["correlation_length_beta_1_j_1"],
    }
    assert "formula" not in record["source_operand"]
    assert record["source_operand"] == record["computed_operand"]
    assert record["computed_operand"] == record["registry_operand"]
    assert record["comparison"]["matched"] is True


def test_runtime_collector_parses_tasaki_lsm_constraint():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["lieb_schultz_mattis_half_integer_constraint"]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_operand"] == {
        "unique_ground_state_implies_gapless_excitations": True
    }
    assert record["source_operand"] == record["registry_operand"]
    assert record["comparison"]["matched"] is True
    assert "execution_trace" not in bundle


def test_runtime_collector_recomputes_onsager_square_ising_tc(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(exchange=1.0):
        calls.append(exchange)
        return 2.0 * exchange / literature_runtime_evidence.math.log(
            1.0 + literature_runtime_evidence.math.sqrt(2.0)
        )

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "two_dimensional_ising_square_tc",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [1.0]
    record = evidence["two_dimensional_square_ising_onsager_tc"][
        "runtime_evidence_record"
    ]
    assert record["source_operand"] == record["computed_operand"]
    assert record["computed_operand"] == record["registry_operand"]
    assert record["comparison"]["matched"] is True


def test_runtime_collector_recomputes_decoupled_two_leg_rung_spectrum(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(*, j_rung, j_leg):
        calls.append({"j_rung": j_rung, "j_leg": j_leg})
        return {
            "strong_rung_limit": True,
            "rung_singlet_energy": -0.75,
            "rung_triplet_energy": 0.25,
            "rung_gap": 1.0,
        }

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "spin_ladder_strong_rung_gap_status",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [{"j_rung": 1.0, "j_leg": 0.0}]
    record = evidence["two_leg_ladder_strong_rung_exact_limit"][
        "runtime_evidence_record"
    ]
    expected = {"energy_per_rung": -0.75, "gap_to_triplet": 1.0}
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"]["matched"] is True


def test_runtime_collector_parses_general_two_leg_antiferromagnetic_rung_gap():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["spin_ladder_rung_singlet_gap_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {"has_finite_spin_gap_for_antiferromagnetic_rungs": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "f98d47e008e6245bb1ea9f6fa8c5c7dc13ce4c0e3eb36d9b8c7962024a7cef09"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == "parse_dagotto_rice_two_leg_gap"
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_haldane_shastry_exact_ground_state():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["haldane_shastry_chain_exact_ground_state"]
    record = bundle["runtime_evidence_record"]
    expected = {"has_exact_jastrow_ground_state": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "02e23e3ed3ecd2f313200c5fcd338e2c21aa20a0eb2c662dec0eba0ffc0d845e"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_haldane_shastry_ground_state"
    )
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_and_recomputes_two_baxter_claims():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["eight_vertex_zero_field_exact_solution_status"]
    record = bundle["runtime_evidence_record"]
    expected = {"is_exactly_solved": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "5466c1555c8dd11d46282158b86aeeaf1ddacfd71df92eaa1b6fa158adb4b7a0"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_baxter_eight_vertex_solution"
    )
    assert "execution_trace" not in bundle

    critical_line_bundle = evidence[
        "square_ashkin_teller_exact_critical_line"
    ]
    critical_line_record = critical_line_bundle["runtime_evidence_record"]
    critical_line_expected = {"has_exact_critical_line": True}
    assert critical_line_record["evidence_mode"] == "local_recompute"
    assert critical_line_record["source_sha256"] == (
        "5466c1555c8dd11d46282158b86aeeaf1ddacfd71df92eaa1b6fa158adb4b7a0"
    )
    assert critical_line_record["source_operand"] == critical_line_expected
    assert critical_line_record["computed_operand"] == critical_line_expected
    assert critical_line_record["registry_operand"] == critical_line_expected
    assert critical_line_record["comparison"] == {
        "kind": "exact_field_map",
        "matched": True,
    }
    assert critical_line_bundle["extraction_trace"]["parser"] == (
        "parse_baxter_eight_vertex_critical_line"
    )
    assert critical_line_bundle["execution_trace"]["adapter"] == (
        "recompute_baxter_eight_vertex_critical_line"
    )


def test_runtime_collector_parses_lieb_square_ice_exact_solution_status():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["square_six_vertex_ice_exact_solution_status"]
    record = bundle["runtime_evidence_record"]
    expected = {"is_exactly_solved": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "df7a0f803a6cf0cafa4527d1fd9c1d98e586845097912377cc99a93d97bbf365"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == "parse_lieb_square_ice_solution"
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_yang_gaudin_exact_fermion_solution():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["gaudin_yang_spin_half_fermion_bethe_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {"is_exactly_solved": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "0c5a2ecff72e1bfdc083c2e5e0ded173b53af0f81e782cf1e08c7990f49992a3"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_yang_gaudin_fermion_solution"
    )
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_lieb_liniger_solution_and_fermion_limit():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["lieb_liniger_delta_bose_gas_bethe_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "is_exactly_solved": True,
        "tonks_girardeau_limit_maps_to_free_fermions": True,
    }
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "558e741b5d48795f6a1bd1b866ef3ed25d460ded46ff115029ca7ef8df0e8ff8"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == "parse_lieb_liniger_solution"
    assert "execution_trace" not in bundle


def test_runtime_collector_recomputes_pauling_spin_ice_entropy():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["pyrochlore_dipolar_spin_ice_pauling_entropy"]
    record = bundle["runtime_evidence_record"]
    expected = {"pauling_entropy_per_spin": 0.5 * math.log(1.5)}
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "7290fa424886bfa7e215578710dece5b1d5f83ab9814f7a27dcd2c80327f801d"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == "parse_pauling_spin_ice_entropy"
    assert bundle["execution_trace"]["adapter"] == "pauling_spin_ice_entropy_per_spin"


def test_runtime_collector_recomputes_bkt_universal_jump_all_fields():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["two_dimensional_xy_bkt_universal_jump"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "formula": "rho_s(T_BKT)=2T_BKT/pi",
        "helicity_modulus_at_t_1": 2.0 / math.pi,
    }
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "f9b73a740336ea1ac9131eed706c3c13c73988e4516934c4f2ee069f441fdc90"
    )
    assert record["registry_selector"]["fields"] == [
        "formula",
        "helicity_modulus_at_t_1",
    ]
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == "parse_bkt_universal_jump"
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_bkt_universal_jump_operand"
    )


def test_runtime_collector_recomputes_uls_spin1_su3_point_all_fields():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["uimin_lai_sutherland_spin1_su3_point"]
    record = bundle["runtime_evidence_record"]
    expected = {"theta_radians": math.pi / 4.0, "su3_symmetric": True}
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "b18e0b9e3e95958e0f0be8154e88b8f1f907bdafce0e9338d25699870c4f77a5"
    )
    assert record["registry_selector"]["fields"] == [
        "theta_radians",
        "su3_symmetric",
    ]
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == "parse_uls_spin1_su3_point"
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_uls_spin1_su3_operand"
    )


def test_runtime_collector_recomputes_aklt_bilinear_biquadratic_angle():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["bilinear_biquadratic_spin1_chain_aklt_angle"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "aklt_tan_theta": 1.0 / 3.0,
        "theta_radians": math.atan(1.0 / 3.0),
    }
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "1a0734ffb58e1fcba8570fe4ce6a36014bad3b07d8d3a34fcf13451af186ffc8"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_aklt_angle_from_projector"
    )
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_aklt_angle_from_spin_two_projector"
    )


def test_runtime_collector_recomputes_yang_spontaneous_magnetization():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["two_dimensional_square_ising_spontaneous_magnetization"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "formula": "[1 - sinh(2 beta J)^(-4)]^(1/8)",
        "magnetization_beta_0_6_j_1": (1.0 - math.sinh(1.2) ** -4) ** 0.125,
    }
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "070a6ef65a1280da504a01b4f61eeae4024622056d30f835b652f3ed22b010ed"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_yang_spontaneous_magnetization"
    )
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_yang_spontaneous_magnetization_operand"
    )


def test_runtime_collector_recomputes_square_compass_line_symmetries():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["square_compass_model_directional_exchange_degeneracy"]
    record = bundle["runtime_evidence_record"]
    expected = {"has_line_flip_symmetries": True}
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "2ee0d9810035a80767795a859f139d2940ababa81e0094df0f3d934e7ab231b9"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_square_compass_line_symmetries"
    )
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_square_compass_line_symmetries"
    )
    assert bundle["execution_trace"]["adapter_parameters"] == {
        "length": 3,
        "j_x": 1.0,
        "j_y": 1.0,
    }


def test_runtime_collector_parses_two_distinct_kitaev_claims_from_shared_source():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    exact_record = evidence["kitaev_honeycomb_exact_spin_liquid_limit"][
        "runtime_evidence_record"
    ]
    triangle_record = evidence["kitaev_honeycomb_gapless_triangle_condition"][
        "runtime_evidence_record"
    ]
    assert exact_record["source_sha256"] == triangle_record["source_sha256"]
    assert exact_record["source_sha256"] == (
        "eb99541ee61044a6028edc53aad19dd80afed7e96778350a38420f36269e93ba"
    )
    assert exact_record["source_operand"] == {
        "is_exactly_solvable": True,
        "isotropic_phase": "gapless_spin_liquid",
    }
    assert triangle_record["source_operand"] == {
        "gapless_condition": "triangle_inequalities",
        "isotropic_kitaev_point_gapless": True,
    }
    assert exact_record["source_operand"] == exact_record["registry_operand"]
    assert triangle_record["source_operand"] == triangle_record["registry_operand"]
    assert exact_record["comparison"]["matched"] is True
    assert triangle_record["comparison"]["matched"] is True


def test_runtime_collector_recomputes_kitaev_field_nonabelian_gap():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence[
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference"
    ]
    record = bundle["runtime_evidence_record"]
    expected = {
        "field_opens_non_abelian_gap": True,
    }
    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "eb99541ee61044a6028edc53aad19dd80afed7e96778350a38420f36269e93ba"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_kitaev_field_nonabelian_gap"
    )
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_kitaev_field_nonabelian_gap"
    )
    assert bundle["execution_trace"]["adapter_parameters"] == {
        "h_x": 0.1,
        "h_y": 0.2,
        "h_z": 0.3,
        "exchange": 1.0,
    }


def test_runtime_collector_parses_white_huse_gap_with_registry_tolerance():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    record = evidence["haldane_spin1_chain_gap_reference"][
        "runtime_evidence_record"
    ]
    assert record["source_sha256"] == (
        "a6bff20bc37a0c16484645b07225682d98f843512abcb09f570fb87b966065c1"
    )
    assert record["source_operand"] == {"gap_over_j": 0.41050}
    assert record["registry_operand"] == {"gap_over_j": 0.41048}
    assert record["comparison"]["kind"] == "absolute_tolerance"
    assert record["comparison"]["absolute_tolerance"] == 0.00005
    assert record["comparison"]["absolute_differences"]["gap_over_j"] == (
        pytest.approx(0.00002)
    )
    assert record["comparison"]["matched"] is True


def test_runtime_collector_parses_sandvik_square_qmc_energy_exactly():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    record = evidence["square_spin_half_heisenberg_qmc_energy"][
        "runtime_evidence_record"
    ]
    expected = {"energy_per_site": -0.669437}
    assert record["source_sha256"] == (
        "f5fc182cbf87f55375357e0bcd1c10ca1e665d09b33a5c52d39a74aa1aa63332"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {
        "kind": "exact_field_map",
        "matched": True,
    }


def test_runtime_collector_parses_capriotti_triangular_energy_with_registry_tolerance():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["triangular_heisenberg_spin_half_energy_reference"]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "2d1e3e63fbb3dce7432148b6be0bda83c9ff9a95cd88f6e7165db24f6d334684"
    )
    assert record["source_operand"] == {"energy_per_site_approx": -0.5458}
    assert record["registry_operand"] == {"energy_per_site_approx": -0.545}
    assert record["comparison"]["kind"] == "absolute_tolerance"
    assert record["comparison"]["absolute_tolerance"] == 0.005
    assert record["comparison"]["absolute_differences"][
        "energy_per_site_approx"
    ] == pytest.approx(0.0008)
    assert record["comparison"]["matched"] is True
    assert bundle["extraction_trace"]["parser"] == (
        "parse_capriotti_triangular_energy"
    )
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_checkerboard_plaquette_vbc_claims():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["checkerboard_heisenberg_plaquette_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "plaquette_long_range_order": True,
        "valence_bond_crystal": True,
    }
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "76977e533c91730d5f094398396e291a1b000574926ef9b95dd3d167a8d0804b"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_checkerboard_plaquette_vbc"
    )
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_spin_peierls_finite_distortion_gap():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["spin_peierls_chain_dimerization_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {"finite_delta_opens_gap": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "4e608aaa697bee4daafe9045f8cc8ad404e7fba57cf8a2e0e0ea6a7766c9491e"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_spin_peierls_distortion_gap"
    )
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_bpcb_field_induced_ll():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["bpcb_spin_ladder_field_induced_order_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {"field_induced_luttinger_liquid_regime": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "4aa3620ad296890147af981052faf5eae3b8dbd8fcbf6241b88d46a18a743596"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_bpcb_field_induced_ll"
    )
    assert "execution_trace" not in bundle


def test_runtime_collector_parses_hasenbusch_xy_bkt_temperature():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["two_dimensional_xy_bkt_temperature_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {"tbkt_over_j": 0.89294}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "b60cf3b4a5beddb2f0977e4d9186b51f429a102c600397ce621dfe7019b38b0d"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_hasenbusch_xy_bkt_temperature"
    )
    assert bundle["extraction_trace"]["inverse_beta"] == pytest.approx(1.1199)
    assert "execution_trace" not in bundle


@pytest.mark.parametrize(
    ("benchmark_name", "source_sha256", "parser_name"),
    [
        (
            "azurite_diamond_chain_plateau_reference",
            "250399f671a152e1af803094e42274dd68d36b21e80f73ddafac5b5132e54c97",
            "parse_azurite_one_third_plateau",
        ),
        (
            "ba3cosb2o9_triangular_plateau_reference",
            "5c9213771be2b7b3b81f19747d51281ca73c46c4fccc2b92a53201af200aab69",
            "parse_ba3cosb2o9_one_third_plateau",
        ),
    ],
)
def test_runtime_collector_parses_one_third_plateau_sources(
    benchmark_name, source_sha256, parser_name
):
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence[benchmark_name]
    record = bundle["runtime_evidence_record"]
    expected = {"one_third_magnetization_plateau": True}
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == source_sha256
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == parser_name
    assert "execution_trace" not in bundle


@pytest.mark.parametrize(
    ("benchmark_name", "source_sha256", "expected", "parser_name"),
    [
        (
            "kagome_one_third_magnetization_plateau_reference",
            "deb2151816fe8a3f60b20210a0af6029447addcbce505251c1813f26006cab92",
            {"one_third_plateau": True},
            "parse_kagome_one_third_plateau",
        ),
        (
            "shastry_sutherland_magnetization_plateaus_reference",
            "7156b098ac1b1ee3c4acbda4307cd51e90b45f6c7f878c575adea92a9d35444f",
            {"fractional_plateaus_observed": True},
            "parse_kageyama_shastry_sutherland_plateaus",
        ),
        (
            "sr_cu2_bo3_2_shastry_sutherland_material_reference",
            "7156b098ac1b1ee3c4acbda4307cd51e90b45f6c7f878c575adea92a9d35444f",
            {"orthogonal_dimer_material": True, "magnetization_plateaus": True},
            "parse_kageyama_shastry_sutherland_material",
        ),
    ],
)
def test_runtime_collector_parses_kagome_and_shastry_sutherland_plateaus(
    benchmark_name, source_sha256, expected, parser_name
):
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence[benchmark_name]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == source_sha256
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == parser_name
    assert "execution_trace" not in bundle


@pytest.mark.parametrize(
    ("benchmark_name", "source_sha256", "expected", "parser_name"),
    [
        (
            "cacu2o3_spin_ladder_reference",
            "c17ae440a1808d17fe8d545a518e47f3e6628831ffb3b996b98bdc5f7c1ecbcc",
            {"spin_ladder_material": True},
            "parse_cacu2o3_spin_ladder_material",
        ),
        (
            "ba2cugeo7_dm_spiral_reference",
            "924dd8300f74e47819f466e0b8304302afd40bc08918547386f7f4bca4f05b8b",
            {"dm_induced_incommensurate_spiral": True},
            "parse_ba2cugeo7_dm_spiral",
        ),
    ],
)
def test_runtime_collector_parses_cacu2o3_and_ba2cugeo7_sources(
    benchmark_name, source_sha256, expected, parser_name
):
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)
    bundle = evidence[benchmark_name]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == source_sha256
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == parser_name
    assert "execution_trace" not in bundle


@pytest.mark.parametrize(
    ("benchmark_name", "source_sha256", "expected", "parser_name"),
    [
        (
            "ho2ti2o7_spin_ice_neutron_reference",
            "25ea96a095f65783a109a5dc1c58893e881b962b112cbd31b60eba2bc226cd97",
            {"spin_ice_correlations": True},
            "parse_ho2ti2o7_spin_ice_correlations",
        ),
        (
            "jarosite_kagome_dzyaloshinskii_moriya_reference",
            "85d2617417172ae644f6e59ac96f218bf740077cef4f65727a2e33961d1e5b48",
            {"q_0_120_order": True},
            "parse_jarosite_q0_120_order",
        ),
        (
            "maple_leaf_lattice_heisenberg_reference",
            "ff2f0856ed51037f89a44210f2f887e29bc9d51f4605c0cbb4106400cbed7be0",
            {"magnetic_long_range_order": True},
            "parse_maple_leaf_magnetic_order",
        ),
    ],
)
def test_runtime_collector_parses_material_order_sources(
    benchmark_name, source_sha256, expected, parser_name
):
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)
    bundle = evidence[benchmark_name]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == source_sha256
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == parser_name
    assert "execution_trace" not in bundle


@pytest.mark.parametrize(
    ("benchmark_name", "source_sha256", "expected", "parser_name"),
    [
        (
            "alpha_rucl3_kitaev_gamma_zigzag_reference",
            "55d6a7c41523255b73e54bcf28e1f62013b839cf1e48b2648e31e094afab704b",
            {"zigzag_order": True, "kitaev_gamma_model_reference": True},
            "parse_alpha_rucl3_zigzag_kitaev_gamma",
        ),
        (
            "beta_li2iro3_spiral_kitaev_gamma_reference",
            "1a4b81cda8b92bfa1e964818793cf03bb430271ed9d35f0a082f7b4aeef16fd0",
            {"incommensurate_spiral_order": True},
            "parse_beta_li2iro3_spiral_order",
        ),
        (
            "cs2cucl4_anisotropic_triangular_spiral_reference",
            "34f77f5892caa88f7e146fb0da286a94a3dfaa586e866c66aceeb4df40fd336b",
            {"incommensurate_spiral_order": True},
            "parse_cs2cucl4_spiral_order",
        ),
        (
            "square_dimerized_heisenberg_critical_reference",
            "1a86eaa464a4bc5fd43165c7416513a8de7de82682b724895a299ee8a150d3ad",
            {"neel_to_dimer_transition": True},
            "parse_square_dimerized_neel_transition",
        ),
        (
            "square_jq_model_deconfined_critical_reference",
            "2500c3aa5dc6a57c745a4976bb0cfaebed514cc3ac255f99f171ba0742b9ecea",
            {"neel_to_vbs_transition": True},
            "parse_square_jq_neel_vbs_transition",
        ),
    ],
)
def test_runtime_collector_parses_direct_order_transition_sources(
    benchmark_name, source_sha256, expected, parser_name
):
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)
    bundle = evidence[benchmark_name]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == source_sha256
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == parser_name
    assert "execution_trace" not in bundle


def test_runtime_collector_recomputes_triangular_classical_120_order():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)
    bundle = evidence["triangular_nn_classical_120_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "order": "120_degree",
        "q_reciprocal": [1.0 / 3.0, 2.0 / 3.0, 0.0],
    }

    assert record["evidence_mode"] == "local_recompute"
    assert record["source_sha256"] == (
        "7a25146a21b00639fb312cec73f5ce27655bf5c702aa9a1a436c3d8f5ee7e4e9"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == (
        "parse_triangular_classical_120_order"
    )
    assert bundle["execution_trace"]["adapter"] == (
        "recompute_triangular_classical_120_order"
    )


def test_runtime_collector_parses_fecl3_helimagnetic_order():
    _require_runtime_cache()
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)
    bundle = evidence["fecl3_honeycomb_antiferromagnet_reference"]
    record = bundle["runtime_evidence_record"]
    expected = {
        "magnetic_order": "helimagnetic_spiral",
        "propagation_vector_hexagonal": [4.0 / 15.0, 1.0 / 15.0, 3.0 / 2.0],
    }

    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == (
        "e16aaefeccd60323d8bdaadaf4892c8ed9243d714ceb0a9e7665d0c8b81171ba"
    )
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == "parse_fecl3_helimagnetic_order"
    assert "execution_trace" not in bundle


@pytest.mark.parametrize(
    ("benchmark_name", "source_sha256", "expected", "parser_name"),
    [
        ("haydeeite_ferromagnetic_kagome_reference", "c89d4d3a0a3e8c0c4b1cbe256e0b47a5fc9441d078d52e1db8a75bf507bf847e", {"ferromagnetic_kagome_exchange": True}, "parse_haydeeite_ferromagnetic_exchange"),
        ("na4ir3o8_hyperkagome_material_reference", "5c7e8c8812196c60eb9c6b470d3af735ee7005d8b50509d53f37e755707ab15f", {"hyperkagome_qsl_candidate": True}, "parse_na4ir3o8_hyperkagome_spin_liquid"),
        ("ybmggao4_triangular_spin_liquid_reference", "bb4a036f145e51c774ac546780c00b20efebbed3d395587d18f8d12ef6cef7c5", {"triangular_quantum_spin_liquid_candidate": True}, "parse_ybmggao4_qsl_candidate"),
        ("barlowite_kagome_material_reference", "58dd8838f381874dd443682b612feb2b781f1dcbe714f7765a3274c26a78307d", {"interlayer_coupling_relevant": True}, "parse_barlowite_interlayer_coupling"),
        ("zn_barlowite_kagome_qsl_reference", "d0e4a6a024e2e97bd498cf3a90cfa1fbf397a6ed6fc4672033426f304e29ba69", {"significantly_reduced_interkagome_exchange": True, "two_parameter_heisenberg_hamiltonian": True}, "parse_substituted_barlowite_two_parameter_model"),
        ("pr2zr2o7_quantum_spin_ice_reference", "2714f5e412ddc79620945bf448efd89c3f828713c3fa7e3926b48ad6a6f8e0b1", {"quantum_spin_ice_candidate": True}, "parse_pr2zr2o7_quantum_spin_ice"),
    ],
)
def test_runtime_collector_parses_material_candidate_sources(
    benchmark_name, source_sha256, expected, parser_name
):
    _require_runtime_cache()
    bundle = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)[benchmark_name]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == source_sha256
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == parser_name
    assert "execution_trace" not in bundle


@pytest.mark.parametrize(
    ("benchmark_name", "source_sha256", "expected", "parser_name"),
    [
        ("herbertsmithite_kagome_qsl_reference", "84b83ef93c18f02bc57215b8713118823664793baab2b844e19a1b4ae4514e76", {"qsl_candidate": True}, "parse_herbertsmithite_qsl_candidate"),
        ("kapellasite_kagome_j1_jd_reference", "e232c503ae09f347ee89a7793fbbc60ba4fb90a65a135a7b1aa1aef6d99920ce", {"competing_kagome_exchanges": True}, "parse_kapellasite_competing_exchanges"),
        ("li2cuo2_frustrated_ferromagnetic_chain_reference", "d4c136d735e5baea62a774d14d3a20c60ee4ef1edf650f2897a38afb06922156", {"frustrated_ferromagnetic_chain": True}, "parse_li2cuo2_frustrated_chain"),
        ("quantum_spin_ice_u1_qsl_reference", "3652c5217b8c8149992d4f60f45a2fff6f319b9acc78c7ca31fab40bb6ec61ca", {"u1_quantum_spin_liquid_candidate": True}, "parse_u1_pyrochlore_spin_liquid"),
        ("zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference", "ead9e2c2b454b557c14e8661aeb8f598315b52ba0b6050fdac22c6cda9c58755", {"dm_interaction_relevant": True}, "parse_herbertsmithite_dm_relevance"),
        ("kagome_chiral_spin_liquid_j1_j2_jchi_reference", "3a86504461857d652a479c1a048b4ecd9c1f20ad254d21a5fd53e10d80ac9e20", {"chiral_spin_liquid_phase": True}, "parse_kagome_chiral_spin_liquid_phase"),
        ("kagome_dzyaloshinskii_moriya_critical_reference", "a7af9d4d686d1e2ea76aba6bfd73bdbcad71865f69e3a29ea172c69d33763e49", {"critical_d_over_j_approx": 0.1}, "parse_kagome_dm_critical_ratio"),
        ("breathing_kagome_heisenberg_reference", "5db20f98308ee6d02c725c3be0bd5a98723bfc0353157bda65bfd370f901cb02", {"breathing_anisotropy_controls_trimerization": True}, "parse_breathing_kagome_trimerization"),
        ("ca10cr7o28_bilayer_breathing_kagome_reference", "1d64379f503a449054089279b4e82370847a08d33ced93fecec361eaa5729a71", {"spin_liquid_candidate": True, "mixed_ferromagnetic_antiferromagnetic_exchanges": True}, "parse_ca10cr7o28_qsl_exchange"),
        ("hyperkagome_heisenberg_spin_liquid_reference", "f8911835e5bc55dbba4648e65e2f3635031af8e892bc8424ea4f62ec4fa392f8", {"spin_liquid_candidate": True}, "parse_hyperkagome_heisenberg_qsl"),
        ("li2iro3_hyperhoneycomb_kitaev_reference", "a9e978e8b54ab3ff068ec2088a17596fca2ed6de5e881c4f536bdc9119d12d97", {"hyperhoneycomb_kitaev_material": True}, "parse_beta_li2iro3_hyperhoneycomb_kitaev"),
        ("triangular_ring_exchange_spin_liquid_reference", "bafa32426710b8664fb49e99cebd35f9e13dcf45351111d47abc83e55fc5312a", {"contains_spin_liquid_region": True}, "parse_triangular_ring_exchange_spin_liquid"),
        ("triangular_xxz_supersolid_phase_reference", "80f6a10c904edc453e16bd44a1afd9e4c2b1d01831c02f3ea18cfde6f1390402", {"contains_supersolid_phase": True}, "parse_triangular_xxz_supersolid"),
        ("volborthite_kagome_distorted_reference", "038728ec1e945de280a01351554d5aa45b6ffcce3e60b97a390c6dbce5abf156", {"distorted_kagome_reference": True}, "parse_volborthite_distorted_kagome"),
        ("ni_ps3_honeycomb_antiferromagnet_reference", "3a638380c5f1ef7d4d410f953e411dc57d06dae53219e91d6554300353068f09", {"zigzag_or_collinear_order_reference": True}, "parse_nips3_zigzag_order"),
        ("honeycomb_kitaev_gamma_phase_diagram_reference", "502e9bd14c48f77a5f648d05ed2a1e0089c9096046db4474262fcbb5f15b1e85", {"contains_noncollinear_and_zigzag_phases": True}, "parse_kitaev_gamma_phase_content"),
        ("garnet_gd3ga5o12_spin_liquid_reference", "12b502a5f92df32bb68e8bb1a9cfffce021851d1548774ba7e7a987da0e968dd", {"short_range_order_without_simple_lro": True}, "parse_ggg_short_range_order"),
        ("honeycomb_spin_half_j1_j2_quantum_phase_reference", "36ea460633930c0931b03949e0bc26b754c127639b7c8ec3028bf94716bafe87", {"intermediate_nonmagnetic_phase_candidate": True}, "parse_honeycomb_j1j2_nonmagnetic_candidate"),
        ("j1_j2_honeycomb_neel_spin_liquid_transition_reference", "36ea460633930c0931b03949e0bc26b754c127639b7c8ec3028bf94716bafe87", {"intermediate_nonmagnetic_phase": True}, "parse_honeycomb_j1j2_intermediate_nonmagnetic"),
        ("kagome_j1_j2_heisenberg_phase_diagram_reference", "3a61b8c5686f7a38a8ff7cdf8a1588400847702852931cc395df900bb6d1e594", {"phases": ["spin_liquid", "q0_order", "sqrt3xsqrt3_order"]}, "parse_kagome_j1j2_phase_set"),
        ("triangular_j1_j2_spin_half_phase_diagram_reference", "9f6ba6319c210fc4fb40cd345472472f3dba95faacaf00da996159c468112e1d", {"phases": ["120_degree", "spin_liquid", "stripe"]}, "parse_triangular_j1j2_phase_set"),
        ("j1_j2_triangular_spin_liquid_window_reference", "efc3e306602617a2dcf10a45ee05712067483dcf75477e0b2ed0f70c56e404a5", {"spin_liquid_window_approx": [0.07, 0.15]}, "parse_triangular_j1j2_spin_liquid_window"),
        ("spin1_chain_large_d_transition_reference", "8eddc6a4669c713860b3288ec54108247086ce0cd6cf0e6beb0449f1f5729b0e", {"large_d_transition_reference": True}, "parse_spin1_haldane_large_d_transition"),
        ("bcc_j1_j2_heisenberg_collinear_reference", "3590db8ee0ef825b8c161a78546e95bc3480253d66b360d71f3813ca7c6d5ec5", {"large_j2_collinear_order": True}, "parse_bcc_large_j2_collinear_order"),
        ("kagome_heisenberg_topological_entanglement_reference", "8004903212f33fd73ca03e0424170afd29d7d96c89040252fa686d737f193121", {"topological_entanglement_entropy": "consistent_with_Z2"}, "parse_kagome_topological_entanglement_z2"),
    ],
)
def test_runtime_collector_parses_next_direct_source_batch(
    benchmark_name, source_sha256, expected, parser_name
):
    _require_runtime_cache()
    bundle = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)[benchmark_name]
    record = bundle["runtime_evidence_record"]

    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_sha256"] == source_sha256
    assert record["source_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"] == {"kind": "exact_field_map", "matched": True}
    assert bundle["extraction_trace"]["parser"] == parser_name
    assert "execution_trace" not in bundle


def test_runtime_collector_recomputes_aklt_projector_ground_state(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter():
        calls.append(True)
        return {
            "two_site_projector_eigenvalues": [0.0, 0.0, 1.0],
            "vbs_ground_energy": 0.0,
        }

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "aklt_projector_ground_state_result",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [True]
    record = evidence["aklt_spin1_chain_projector_ground_state"][
        "runtime_evidence_record"
    ]
    expected = {
        "two_site_projector_eigenvalues": [0.0, 0.0, 1.0],
        "vbs_ground_energy": 0.0,
    }
    assert record["source_sha256"] == (
        "1a0734ffb58e1fcba8570fe4ce6a36014bad3b07d8d3a34fcf13451af186ffc8"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"]["matched"] is True


def test_runtime_collector_parses_distinct_localized_magnon_claims_from_shared_source():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    diamond = evidence["diamond_chain_localized_magnon_flat_band"]
    sawtooth = evidence["sawtooth_chain_localized_magnon_flat_band"]
    expected = {"has_exact_localized_magnons": True}
    expected_sha256 = (
        "cd16bd2abe7c57e0b34e89e47c5e38618e7406595d3ca82d63e79305ccfe66c9"
    )
    for bundle in (diamond, sawtooth):
        record = bundle["runtime_evidence_record"]
        assert record["evidence_mode"] == "local_source_parse"
        assert record["source_sha256"] == expected_sha256
        assert record["source_operand"] == expected
        assert record["registry_operand"] == expected
        assert record["comparison"] == {
            "kind": "exact_field_map",
            "matched": True,
        }
        assert "execution_trace" not in bundle
    assert diamond["extraction_trace"]["parser"] == (
        "parse_diamond_localized_magnon"
    )
    assert sawtooth["extraction_trace"]["parser"] == (
        "parse_sawtooth_localized_magnon"
    )


def test_runtime_collector_recomputes_toric_code_genus_one_degeneracy(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(*, genus):
        calls.append(genus)
        return 4**genus

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "toric_code_ground_state_degeneracy",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [1]
    record = evidence["square_toric_code_exact_topological_degeneracy"][
        "runtime_evidence_record"
    ]
    expected = {"torus_ground_state_degeneracy": 4}
    assert record["source_sha256"] == (
        "095171071c8735471da47b929da4d2623d847dff9873d40930cdc169b96cb514"
    )
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"]["matched"] is True


def test_runtime_audit_writers_serialize_structured_evidence(tmp_path):
    _require_runtime_cache()
    audit = build_literature_reproduction_audit()
    csv_path = tmp_path / "audit.csv"
    markdown_path = tmp_path / "audit.md"
    gaps_path = tmp_path / "gaps.md"

    write_audit_csv(audit, csv_path)
    write_audit_markdown(audit, markdown_path)
    write_remaining_strict_reproduction_gaps_markdown(audit, gaps_path)

    with csv_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = {row["name"]: row for row in csv.DictReader(handle)}
    markdown_text = markdown_path.read_text(encoding="utf-8")
    gaps_text = gaps_path.read_text(encoding="utf-8")
    audit_rows = {row["name"]: row for row in audit["rows"]}
    for name in {
        "aklt_spin1_chain_projector_ground_state",
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "azurite_diamond_chain_plateau_reference",
        "barlowite_kagome_material_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "na4ir3o8_hyperkagome_material_reference",
        "pr2zr2o7_quantum_spin_ice_reference",
        "ybmggao4_triangular_spin_liquid_reference",
        "zn_barlowite_kagome_qsl_reference",
        "ba3cosb2o9_triangular_plateau_reference",
        "ba2cugeo7_dm_spiral_reference",
        "ho2ti2o7_spin_ice_neutron_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "maple_leaf_lattice_heisenberg_reference",
        "cacu2o3_spin_ladder_reference",
        "kagome_one_third_magnetization_plateau_reference",
        "shastry_sutherland_magnetization_plateaus_reference",
        "sr_cu2_bo3_2_shastry_sutherland_material_reference",
        "bilinear_biquadratic_spin1_chain_aklt_angle",
        "bpcb_spin_ladder_field_induced_order_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "checkerboard_heisenberg_plaquette_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "cs2cucl4_anisotropic_triangular_spiral_reference",
        "diamond_chain_localized_magnon_flat_band",
        "diamond_j1_j2_spiral_surface_reference",
        "eight_vertex_zero_field_exact_solution_status",
        "square_ashkin_teller_exact_critical_line",
        "fecl3_honeycomb_antiferromagnet_reference",
        "gaudin_yang_spin_half_fermion_bethe_reference",
        "haldane_spin1_chain_gap_reference",
        "haldane_shastry_chain_exact_ground_state",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "lieb_liniger_delta_bose_gas_bethe_reference",
        "lieb_schultz_mattis_half_integer_constraint",
        "one_dimensional_classical_ising_correlation_length",
        "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
        "pyrochlore_dipolar_spin_ice_pauling_entropy",
        "square_compass_model_directional_exchange_degeneracy",
        "square_dimerized_heisenberg_critical_reference",
        "square_jq_model_deconfined_critical_reference",
        "square_potts_exact_critical_point",
        "square_clock_q5_two_bkt_transitions",
        "square_toric_code_exact_topological_degeneracy",
        "square_spin_half_heisenberg_qmc_energy",
        "square_six_vertex_ice_exact_solution_status",
        "sawtooth_chain_localized_magnon_flat_band",
        "spin_peierls_chain_dimerization_reference",
        "spin_ladder_rung_singlet_gap_reference",
        "two_dimensional_square_ising_onsager_tc",
        "two_dimensional_square_ising_spontaneous_magnetization",
        "two_dimensional_xy_bkt_temperature_reference",
        "two_dimensional_xy_bkt_universal_jump",
        "two_leg_ladder_strong_rung_exact_limit",
        "triangular_heisenberg_spin_half_energy_reference",
        "triangular_nn_classical_120_reference",
        "triangular_ising_antiferromagnet_residual_entropy",
        "uimin_lai_sutherland_spin1_su3_point",
        "xy_spin_half_chain_anisotropic_critical_line",
        "xxx_spin_half_chain_bethe_ground_state",
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
        "j1_j2_j3_square_quantum_phase_reference",
        "j1_j2_square_dqcp_columnar_vbs_reference",
        "square_j1_j3_classical_lifshitz_reference",
        "spin_ice_tetrahedron_nn_ice_rule",
        "yb2ti2o7_pyrochlore_exchange_reference",
        "pyrochlore_heisenberg_coulomb_phase_flat_band",
        "j1_j2_square_spin_half_neel_collinear_transition_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
    }:
        for field in (
            "runtime_evidence_record",
            "execution_trace",
            "extraction_trace",
        ):
            assert json.loads(csv_rows[name][field]) == audit_rows[name][field]
    assert "strict_local_recomputed: `21`" in markdown_text
    assert "strict_local_source_parsed: `76`" in markdown_text
    assert "Supported: `97`" in markdown_text
    assert "Missing: `58`" in markdown_text
    assert "Complete: `False`" in markdown_text
    assert "97 of 155 entries are strict" in gaps_text
    assert "absolute_tolerance" in markdown_text
    assert "absolute_differences" in markdown_text
    haldane_csv_record = json.loads(
        csv_rows["haldane_spin1_chain_gap_reference"]["runtime_evidence_record"]
    )
    assert haldane_csv_record["comparison"]["absolute_tolerance"] == 0.00005
    assert haldane_csv_record["comparison"]["absolute_differences"][
        "gap_over_j"
    ] == pytest.approx(0.00002)


def test_runtime_audit_has_exactly_the_ninety_seven_cache_backed_strict_routes():
    _require_runtime_cache()
    audit = build_literature_reproduction_audit()
    supported_names = {
        "aklt_spin1_chain_projector_ground_state",
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "azurite_diamond_chain_plateau_reference",
        "barlowite_kagome_material_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "na4ir3o8_hyperkagome_material_reference",
        "pr2zr2o7_quantum_spin_ice_reference",
        "ybmggao4_triangular_spin_liquid_reference",
        "zn_barlowite_kagome_qsl_reference",
        "ba3cosb2o9_triangular_plateau_reference",
        "ba2cugeo7_dm_spiral_reference",
        "ho2ti2o7_spin_ice_neutron_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "maple_leaf_lattice_heisenberg_reference",
        "cacu2o3_spin_ladder_reference",
        "kagome_one_third_magnetization_plateau_reference",
        "shastry_sutherland_magnetization_plateaus_reference",
        "sr_cu2_bo3_2_shastry_sutherland_material_reference",
        "bilinear_biquadratic_spin1_chain_aklt_angle",
        "bpcb_spin_ladder_field_induced_order_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "checkerboard_heisenberg_plaquette_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "cs2cucl4_anisotropic_triangular_spiral_reference",
        "diamond_chain_localized_magnon_flat_band",
        "diamond_j1_j2_spiral_surface_reference",
        "eight_vertex_zero_field_exact_solution_status",
        "square_ashkin_teller_exact_critical_line",
        "fecl3_honeycomb_antiferromagnet_reference",
        "gaudin_yang_spin_half_fermion_bethe_reference",
        "haldane_spin1_chain_gap_reference",
        "haldane_shastry_chain_exact_ground_state",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "lieb_liniger_delta_bose_gas_bethe_reference",
        "lieb_schultz_mattis_half_integer_constraint",
        "one_dimensional_classical_ising_correlation_length",
        "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
        "pyrochlore_dipolar_spin_ice_pauling_entropy",
        "square_compass_model_directional_exchange_degeneracy",
        "square_dimerized_heisenberg_critical_reference",
        "square_jq_model_deconfined_critical_reference",
        "square_potts_exact_critical_point",
        "square_clock_q5_two_bkt_transitions",
        "square_toric_code_exact_topological_degeneracy",
        "square_spin_half_heisenberg_qmc_energy",
        "square_six_vertex_ice_exact_solution_status",
        "sawtooth_chain_localized_magnon_flat_band",
        "spin_peierls_chain_dimerization_reference",
        "spin_ladder_rung_singlet_gap_reference",
        "two_dimensional_square_ising_onsager_tc",
        "two_dimensional_square_ising_spontaneous_magnetization",
        "two_dimensional_xy_bkt_temperature_reference",
        "two_dimensional_xy_bkt_universal_jump",
        "two_leg_ladder_strong_rung_exact_limit",
        "triangular_heisenberg_spin_half_energy_reference",
        "triangular_nn_classical_120_reference",
        "triangular_ising_antiferromagnet_residual_entropy",
        "uimin_lai_sutherland_spin1_su3_point",
        "xy_spin_half_chain_anisotropic_critical_line",
        "xxx_spin_half_chain_bethe_ground_state",
        "herbertsmithite_kagome_qsl_reference",
        "kapellasite_kagome_j1_jd_reference",
        "li2cuo2_frustrated_ferromagnetic_chain_reference",
        "quantum_spin_ice_u1_qsl_reference",
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference",
        "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
        "kagome_dzyaloshinskii_moriya_critical_reference",
        "breathing_kagome_heisenberg_reference",
        "ca10cr7o28_bilayer_breathing_kagome_reference",
        "hyperkagome_heisenberg_spin_liquid_reference",
        "li2iro3_hyperhoneycomb_kitaev_reference",
        "triangular_ring_exchange_spin_liquid_reference",
        "triangular_xxz_supersolid_phase_reference",
        "volborthite_kagome_distorted_reference",
        "ni_ps3_honeycomb_antiferromagnet_reference",
        "honeycomb_kitaev_gamma_phase_diagram_reference",
        "garnet_gd3ga5o12_spin_liquid_reference",
        "honeycomb_spin_half_j1_j2_quantum_phase_reference",
        "j1_j2_honeycomb_neel_spin_liquid_transition_reference",
        "kagome_j1_j2_heisenberg_phase_diagram_reference",
        "triangular_j1_j2_spin_half_phase_diagram_reference",
        "j1_j2_triangular_spin_liquid_window_reference",
        "spin1_chain_large_d_transition_reference",
        "bcc_j1_j2_heisenberg_collinear_reference",
        "kagome_heisenberg_topological_entanglement_reference",
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
        "j1_j2_j3_square_quantum_phase_reference",
        "j1_j2_square_dqcp_columnar_vbs_reference",
        "square_j1_j3_classical_lifshitz_reference",
        "spin_ice_tetrahedron_nn_ice_rule",
        "yb2ti2o7_pyrochlore_exchange_reference",
        "pyrochlore_heisenberg_coulomb_phase_flat_band",
        "j1_j2_square_spin_half_neel_collinear_transition_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
    }
    registry_names = {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}
    strict_names = {
        row["name"]
        for row in audit["rows"]
        if row["strict_literature_match_label"] == "yes"
    }
    remaining_names = {
        row["name"]
        for row in audit["rows"]
        if row["strict_literature_match_label"] == "no"
    }

    assert strict_names == supported_names
    assert remaining_names == registry_names - supported_names
    assert len(remaining_names) == 58
    assert audit["runtime_evidence_coverage"] == {
        "supported_names": sorted(supported_names),
        "missing_names": sorted(registry_names - supported_names),
        "extra_names": [],
        "invalid_names": [],
        "supported": 97,
        "missing": 58,
        "extra": 0,
        "invalid": 0,
        "complete": False,
    }


def test_public_audit_api_rejects_runtime_evidence_injection():
    signature = inspect.signature(build_literature_reproduction_audit)

    assert "runtime_evidence_by_name" not in signature.parameters
    with pytest.raises(TypeError):
        build_literature_reproduction_audit(runtime_evidence_by_name={})


def test_runtime_disabled_audit_is_hermetic_and_has_no_strict_rows():
    audit = build_literature_reproduction_audit(runtime_evidence_enabled=False)

    assert audit["strict_category_counts"] == {
        "executable_projection": 0,
        "local_projection_only": 155,
        "reference_only": 0,
        "strict_local_recomputed": 0,
        "strict_local_source_parsed": 0,
    }
    assert all(row["runtime_evidence_record"] is None for row in audit["rows"])
    assert all(row["execution_trace"] is None for row in audit["rows"])
    assert all(row["extraction_trace"] is None for row in audit["rows"])
    assert audit["runtime_evidence_coverage"]["supported"] == 0
    assert audit["runtime_evidence_coverage"]["missing"] == 155
    assert audit["runtime_evidence_coverage"]["complete"] is False


def test_structural_validator_rejects_nonfinite_operands():
    for nonfinite in (float("nan"), float("inf"), float("-inf")):
        bundle = _source_parse_bundle()
        bundle["runtime_evidence_record"]["source_operand"] = {
            "ferromagnetic_order": nonfinite
        }
        bundle["runtime_evidence_record"]["registry_operand"] = {
            "ferromagnetic_order": nonfinite
        }

        assert (
            literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
                "cri3_honeycomb_ferromagnet_reference", bundle
            )
            is None
        )


def test_structural_validator_rejects_boolean_integer_false_match():
    bundle = _source_parse_bundle()
    bundle["runtime_evidence_record"]["source_operand"] = {
        "ferromagnetic_order": 1
    }

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", bundle
        )
        is None
    )


def test_structural_validator_rejects_non_json_operand_values():
    bundle = _source_parse_bundle()
    bundle["runtime_evidence_record"]["source_operand"] = {
        "ferromagnetic_order": {"not", "json"}
    }
    bundle["runtime_evidence_record"]["registry_operand"] = {
        "ferromagnetic_order": {"not", "json"}
    }

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", bundle
        )
        is None
    )


def test_malformed_collected_evidence_is_hidden_and_writers_remain_total(
    monkeypatch, tmp_path
):
    malformed_bundle = _source_parse_bundle()
    malformed_bundle["runtime_evidence_record"].pop("comparison")
    monkeypatch.setattr(
        literature_reproduction_audit,
        "collect_runtime_evidence",
        lambda registry_entries, *, cache_root: {
            "cri3_honeycomb_ferromagnet_reference": malformed_bundle
        },
    )

    audit = build_literature_reproduction_audit(cache_root=tmp_path)
    row = {row["name"]: row for row in audit["rows"]}[
        "cri3_honeycomb_ferromagnet_reference"
    ]
    assert row["strict_literature_match_label"] == "no"
    assert row["runtime_evidence_record"] is None
    assert row["execution_trace"] is None
    assert row["extraction_trace"] is None

    csv_path = tmp_path / "audit.csv"
    markdown_path = tmp_path / "audit.md"
    gaps_path = tmp_path / "gaps.md"
    write_audit_csv(audit, csv_path)
    write_audit_markdown(audit, markdown_path)
    write_remaining_strict_reproduction_gaps_markdown(audit, gaps_path)
    assert csv_path.is_file()
    assert markdown_path.is_file()
    assert gaps_path.is_file()


def test_collector_extraction_traces_declare_coordinate_space():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert set(evidence) == {
        "aklt_spin1_chain_projector_ground_state",
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "azurite_diamond_chain_plateau_reference",
        "barlowite_kagome_material_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "na4ir3o8_hyperkagome_material_reference",
        "pr2zr2o7_quantum_spin_ice_reference",
        "ybmggao4_triangular_spin_liquid_reference",
        "zn_barlowite_kagome_qsl_reference",
        "ba3cosb2o9_triangular_plateau_reference",
        "ba2cugeo7_dm_spiral_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "ho2ti2o7_spin_ice_neutron_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "maple_leaf_lattice_heisenberg_reference",
        "cacu2o3_spin_ladder_reference",
        "kagome_one_third_magnetization_plateau_reference",
        "shastry_sutherland_magnetization_plateaus_reference",
        "sr_cu2_bo3_2_shastry_sutherland_material_reference",
        "bilinear_biquadratic_spin1_chain_aklt_angle",
        "bpcb_spin_ladder_field_induced_order_reference",
        "checkerboard_heisenberg_plaquette_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "cs2cucl4_anisotropic_triangular_spiral_reference",
        "diamond_chain_localized_magnon_flat_band",
        "diamond_j1_j2_spiral_surface_reference",
        "eight_vertex_zero_field_exact_solution_status",
        "square_ashkin_teller_exact_critical_line",
        "fecl3_honeycomb_antiferromagnet_reference",
        "gaudin_yang_spin_half_fermion_bethe_reference",
        "haldane_spin1_chain_gap_reference",
        "haldane_shastry_chain_exact_ground_state",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "lieb_liniger_delta_bose_gas_bethe_reference",
        "lieb_schultz_mattis_half_integer_constraint",
        "one_dimensional_classical_ising_correlation_length",
        "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
        "pyrochlore_dipolar_spin_ice_pauling_entropy",
        "square_compass_model_directional_exchange_degeneracy",
        "square_dimerized_heisenberg_critical_reference",
        "square_jq_model_deconfined_critical_reference",
        "square_potts_exact_critical_point",
        "square_clock_q5_two_bkt_transitions",
        "square_toric_code_exact_topological_degeneracy",
        "square_spin_half_heisenberg_qmc_energy",
        "square_six_vertex_ice_exact_solution_status",
        "sawtooth_chain_localized_magnon_flat_band",
        "spin_peierls_chain_dimerization_reference",
        "spin_ladder_rung_singlet_gap_reference",
        "two_dimensional_square_ising_onsager_tc",
        "two_dimensional_square_ising_spontaneous_magnetization",
        "two_dimensional_xy_bkt_temperature_reference",
        "two_dimensional_xy_bkt_universal_jump",
        "two_leg_ladder_strong_rung_exact_limit",
        "triangular_heisenberg_spin_half_energy_reference",
        "triangular_nn_classical_120_reference",
        "triangular_ising_antiferromagnet_residual_entropy",
        "uimin_lai_sutherland_spin1_su3_point",
        "xy_spin_half_chain_anisotropic_critical_line",
        "xxx_spin_half_chain_bethe_ground_state",
        "herbertsmithite_kagome_qsl_reference",
        "kapellasite_kagome_j1_jd_reference",
        "li2cuo2_frustrated_ferromagnetic_chain_reference",
        "quantum_spin_ice_u1_qsl_reference",
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference",
        "kagome_chiral_spin_liquid_j1_j2_jchi_reference",
        "kagome_dzyaloshinskii_moriya_critical_reference",
        "breathing_kagome_heisenberg_reference",
        "ca10cr7o28_bilayer_breathing_kagome_reference",
        "hyperkagome_heisenberg_spin_liquid_reference",
        "li2iro3_hyperhoneycomb_kitaev_reference",
        "triangular_ring_exchange_spin_liquid_reference",
        "triangular_xxz_supersolid_phase_reference",
        "volborthite_kagome_distorted_reference",
        "ni_ps3_honeycomb_antiferromagnet_reference",
        "honeycomb_kitaev_gamma_phase_diagram_reference",
        "garnet_gd3ga5o12_spin_liquid_reference",
        "honeycomb_spin_half_j1_j2_quantum_phase_reference",
        "j1_j2_honeycomb_neel_spin_liquid_transition_reference",
        "kagome_j1_j2_heisenberg_phase_diagram_reference",
        "triangular_j1_j2_spin_half_phase_diagram_reference",
        "j1_j2_triangular_spin_liquid_window_reference",
        "spin1_chain_large_d_transition_reference",
        "bcc_j1_j2_heisenberg_collinear_reference",
        "kagome_heisenberg_topological_entanglement_reference",
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
        "j1_j2_j3_square_quantum_phase_reference",
        "j1_j2_square_dqcp_columnar_vbs_reference",
        "square_j1_j3_classical_lifshitz_reference",
        "spin_ice_tetrahedron_nn_ice_rule",
        "yb2ti2o7_pyrochlore_exchange_reference",
        "pyrochlore_heisenberg_coulomb_phase_flat_band",
        "j1_j2_square_spin_half_neel_collinear_transition_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
    }
    assert all(
        bundle["extraction_trace"]["coordinate_space"]
        == "whitespace_normalized_extracted_text"
        for bundle in evidence.values()
    )


def test_structural_coverage_reports_missing_extra_and_invalid_names():
    valid_name = "cri3_honeycomb_ferromagnet_reference"
    invalid_name = "invalid_route"
    registry_entries = [{"name": valid_name}, {"name": invalid_name}]
    invalid_bundle = _source_parse_bundle()
    invalid_bundle["runtime_evidence_record"]["benchmark_name"] = invalid_name
    evidence = {
        valid_name: _source_parse_bundle(),
        invalid_name: invalid_bundle,
        "extra_route": _source_parse_bundle(),
    }

    coverage = literature_runtime_evidence.structurally_validate_runtime_evidence_coverage(
        registry_entries, evidence
    )

    assert coverage == {
        "supported_names": [valid_name],
        "missing_names": [],
        "extra_names": ["extra_route"],
        "invalid_names": [invalid_name],
        "supported": 1,
        "missing": 0,
        "extra": 1,
        "invalid": 1,
        "complete": False,
    }


def test_authoritative_runtime_coverage_collects_verified_local_sources(monkeypatch):
    _require_runtime_cache()
    calls = []
    real_collector = literature_runtime_evidence.collect_runtime_evidence

    def recorded_collector(registry_entries, *, cache_root):
        calls.append(cache_root)
        return real_collector(registry_entries, cache_root=cache_root)

    monkeypatch.setattr(
        literature_runtime_evidence, "collect_runtime_evidence", recorded_collector
    )
    coverage = literature_runtime_evidence.collect_runtime_evidence_coverage(
        LITERATURE_STANDARD_RESULTS,
        cache_root=literature_runtime_evidence.DEFAULT_CACHE_ROOT,
    )

    assert calls == [literature_runtime_evidence.DEFAULT_CACHE_ROOT]
    assert coverage["supported"] == 97
    assert coverage["missing"] == 58
    assert coverage["extra"] == 0
    assert coverage["invalid"] == 0
    assert coverage["complete"] is False


def test_runtime_completion_assertion_rejects_current_incomplete_coverage():
    _require_runtime_cache()

    with pytest.raises(RuntimeEvidenceError, match="58 missing"):
        literature_runtime_evidence.assert_complete_runtime_evidence(
            LITERATURE_STANDARD_RESULTS
        )


def test_recompute_blume_capel_square_zero_temperature_crossing():
    assert (
        literature_runtime_evidence.recompute_blume_capel_zero_temperature_crossing(
            coordination_number=4,
            exchange=1.0,
        )
        == {"square_lattice_d_over_j_crossing": 2.0}
    )


def test_recompute_single_ion_spin1_anisotropy_levels_and_degeneracies():
    assert literature_runtime_evidence.recompute_single_ion_spin1_anisotropy_levels(
        anisotropy=1.0
    ) == {
        "levels": [0.0, 1.0, 1.0],
        "degeneracies": [1, 2],
    }


@pytest.mark.parametrize(
    ("adapter_name", "expected_tc"),
    [
        (
            "recompute_honeycomb_ising_ferromagnet_tc",
            2.0 / math.log(2.0 + math.sqrt(3.0)),
        ),
        (
            "recompute_kagome_ising_ferromagnet_tc",
            4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0)),
        ),
        (
            "recompute_triangular_ising_ferromagnet_tc",
            4.0 / math.log(3.0),
        ),
    ],
)
def test_recompute_exact_two_dimensional_ising_transition_temperatures(
    adapter_name, expected_tc
):
    adapter = getattr(literature_runtime_evidence, adapter_name)

    assert adapter(exchange=1.0) == {
        "tc_over_j": pytest.approx(expected_tc)
    }


def test_recompute_one_dimensional_ising_has_no_finite_temperature_transition():
    assert (
        literature_runtime_evidence.recompute_one_dimensional_ising_no_finite_t_transition(
            exchange=1.0
        )
        == {
            "finite_temperature_transition": False,
            "tc_over_j": 0.0,
        }
    )


def test_recompute_transverse_field_ising_chain_critical_point():
    assert (
        literature_runtime_evidence.recompute_transverse_field_ising_chain_critical_point(
            exchange=1.0
        )
        == {"critical_field_over_exchange": 1.0}
    )


def test_recompute_transverse_field_ising_chain_gap():
    assert literature_runtime_evidence.recompute_transverse_field_ising_chain_gap(
        field_over_exchange=0.6,
        exchange=1.0,
    ) == {
        "gap_formula": "2J|1-g|",
        "gap_formula_at_g_0_6": pytest.approx(0.8),
    }


def test_recompute_xx_spin_half_chain_free_fermion_energy():
    assert literature_runtime_evidence.recompute_xx_spin_half_chain_free_fermion_energy(
        exchange=1.0
    ) == {"energy_per_site": pytest.approx(-1.0 / math.pi)}


def test_recompute_shastry_sutherland_exact_dimer_energy():
    assert literature_runtime_evidence.recompute_shastry_sutherland_exact_dimer_energy(
        dimer_exchange=1.0
    ) == {
        "energy_per_dimer": -0.75,
        "energy_per_spin": -0.375,
    }


def test_recompute_majumdar_ghosh_exact_dimer_operand():
    assert literature_runtime_evidence.recompute_majumdar_ghosh_exact_dimer_operand(
        j1=1.0,
        j2_over_j1=0.5,
    ) == {
        "energy_per_site": -0.375,
        "degenerate_dimer_coverings": 2,
    }


def test_recompute_checkerboard_crossed_plaquette_constraint():
    assert (
        literature_runtime_evidence.recompute_checkerboard_crossed_plaquette_constraint(
            exchange=1.0
        )
        == {"zero_total_spin_per_crossed_plaquette": True}
    )


def test_recompute_simple_cubic_j1_j2_boundary():
    assert literature_runtime_evidence.recompute_simple_cubic_j1_j2_boundary(
        j1=1.0
    ) == {"neel_to_collinear_boundary_j2_over_j1": 0.25}


def test_recompute_takhtajan_babujian_integrable_operand():
    assert (
        literature_runtime_evidence.recompute_takhtajan_babujian_integrable_operand()
        == {
            "theta_radians": -math.pi / 4.0,
            "is_integrable": True,
        }
    )


def test_recompute_xxz_spin_half_chain_phase_boundaries():
    assert literature_runtime_evidence.recompute_xxz_spin_half_chain_phase_boundaries() == {
        "ferromagnetic_boundary_delta": -1.0,
        "neel_boundary_delta": 1.0,
        "gapless_interval": [-1.0, 1.0],
    }


@pytest.mark.parametrize(
    ("adapter_name", "parameters"),
    [
        (
            "recompute_blume_capel_zero_temperature_crossing",
            {"coordination_number": 0, "exchange": 1.0},
        ),
        (
            "recompute_single_ion_spin1_anisotropy_levels",
            {"anisotropy": float("nan")},
        ),
        (
            "recompute_honeycomb_ising_ferromagnet_tc",
            {"exchange": 0.0},
        ),
        (
            "recompute_kagome_ising_ferromagnet_tc",
            {"exchange": -1.0},
        ),
        (
            "recompute_triangular_ising_ferromagnet_tc",
            {"exchange": float("inf")},
        ),
        (
            "recompute_one_dimensional_ising_no_finite_t_transition",
            {"exchange": 0.0},
        ),
        (
            "recompute_transverse_field_ising_chain_critical_point",
            {"exchange": -1.0},
        ),
        (
            "recompute_transverse_field_ising_chain_gap",
            {"field_over_exchange": 0.6, "exchange": 0.0},
        ),
        (
            "recompute_xx_spin_half_chain_free_fermion_energy",
            {"exchange": float("nan")},
        ),
        (
            "recompute_shastry_sutherland_exact_dimer_energy",
            {"dimer_exchange": 0.0},
        ),
        (
            "recompute_majumdar_ghosh_exact_dimer_operand",
            {"j1": 1.0, "j2_over_j1": 0.4},
        ),
        (
            "recompute_checkerboard_crossed_plaquette_constraint",
            {"exchange": 0.0},
        ),
        (
            "recompute_simple_cubic_j1_j2_boundary",
            {"j1": float("inf")},
        ),
    ],
)
def test_exact_model_recompute_adapters_fail_closed_on_invalid_parameters(
    adapter_name, parameters
):
    adapter = getattr(literature_runtime_evidence, adapter_name)

    with pytest.raises(RuntimeEvidenceError):
        adapter(**parameters)


@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_require_finite_real_rejects_huge_integers_as_runtime_evidence_errors(value):
    with pytest.raises(RuntimeEvidenceError, match="finite real number"):
        literature_runtime_evidence._require_finite_real(
            value, label="huge-integer test"
        )


def test_exact_gap_recomputes_do_not_depend_on_benchmark_helpers(monkeypatch):
    def corrupted_helper(*args, **kwargs):
        raise AssertionError("benchmark helper must not be called")

    for helper_name in (
        "blume_capel_square_zero_temperature_level_crossing",
        "single_ion_spin1_anisotropy_levels",
        "transverse_field_ising_chain_gap",
        "xx_spin_half_chain_free_fermion_energy_per_site",
        "shastry_sutherland_dimer_energy_per_spin",
        "majumdar_ghosh_energy_per_site",
        "checkerboard_crossed_plaquette_ground_state_constraint_status",
        "pyrochlore_tetrahedron_heisenberg_energy_identity",
        "spin1_bilinear_biquadratic_integrable_angle",
        "xxz_spin_half_chain_phase_label",
    ):
        monkeypatch.setattr(
            literature_runtime_evidence.benchmark_functions,
            helper_name,
            corrupted_helper,
        )

    assert literature_runtime_evidence.recompute_blume_capel_zero_temperature_crossing(
        coordination_number=4, exchange=1.0
    ) == {"square_lattice_d_over_j_crossing": 2.0}
    assert literature_runtime_evidence.recompute_single_ion_spin1_anisotropy_levels(
        anisotropy=1.0
    ) == {"levels": [0.0, 1.0, 1.0], "degeneracies": [1, 2]}
    assert literature_runtime_evidence.recompute_transverse_field_ising_chain_critical_point(
        exchange=1.0
    ) == {"critical_field_over_exchange": 1.0}
    assert literature_runtime_evidence.recompute_transverse_field_ising_chain_gap(
        field_over_exchange=0.6, exchange=1.0
    ) == {
        "gap_formula": "2J|1-g|",
        "gap_formula_at_g_0_6": pytest.approx(0.8),
    }
    assert literature_runtime_evidence.recompute_xx_spin_half_chain_free_fermion_energy(
        exchange=1.0
    ) == {"energy_per_site": pytest.approx(-1.0 / math.pi)}
    assert literature_runtime_evidence.recompute_shastry_sutherland_exact_dimer_energy(
        dimer_exchange=1.0
    ) == {"energy_per_dimer": -0.75, "energy_per_spin": -0.375}
    assert literature_runtime_evidence.recompute_majumdar_ghosh_exact_dimer_operand(
        j1=1.0, j2_over_j1=0.5
    ) == {"energy_per_site": -0.375, "degenerate_dimer_coverings": 2}
    assert literature_runtime_evidence.recompute_checkerboard_crossed_plaquette_constraint(
        exchange=1.0
    ) == {"zero_total_spin_per_crossed_plaquette": True}
    assert literature_runtime_evidence.recompute_takhtajan_babujian_integrable_operand() == {
        "theta_radians": -math.pi / 4.0,
        "is_integrable": True,
    }
    assert literature_runtime_evidence.recompute_xxz_spin_half_chain_phase_boundaries() == {
        "ferromagnetic_boundary_delta": -1.0,
        "neel_boundary_delta": 1.0,
        "gapless_interval": [-1.0, 1.0],
    }
    assert literature_runtime_evidence.recompute_pyrochlore_coulomb_phase(
        exchange=1.0, momentum_probe=1.0e-3
    ) == {"zero_total_spin_per_tetrahedron": True, "pinch_points": True}


def test_collura_xx_energy_is_the_source_formula_not_a_benchmark_helper(monkeypatch):
    monkeypatch.setattr(
        literature_runtime_evidence.benchmark_functions,
        "xx_spin_half_chain_free_fermion_energy_per_site",
        lambda *args, **kwargs: 123.0,
    )

    parsed, _ = literature_runtime_evidence.parse_collura_xx_chain_energy(
        COLLURA_CALABRESE_ESSLER_XX_SOURCE_TEXT
    )

    assert parsed == {"energy_per_site": pytest.approx(-1.0 / math.pi)}


def _exact_gap_manifest_parser_names():
    design_text = (
        PROJECT_ROOT
        / "docs/superpowers/specs/2026-07-31-literature-evidence-155-of-155-design.md"
    ).read_text(encoding="utf-8")
    parser_names = set()
    for heading in (
        "### Thirty-seven direct local-source parses",
        "### Twenty-one local recomputations",
    ):
        table = []
        started = False
        for line in design_text[design_text.index(heading) :].splitlines()[1:]:
            if line.startswith("|"):
                started = True
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if not all(set(cell) <= {"-", ":", " "} for cell in cells):
                    table.append(cells)
            elif started:
                break
        header, *rows = table
        parser_index = header.index("Parser")
        parser_names.update(row[parser_index] for row in rows)
    assert len(parser_names) == 58
    return parser_names


def _exact_gap_positive_fixtures(parser_names):
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    fixtures = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in parser_names
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id.endswith("SOURCE_TEXT")
        ):
            continue
        fixtures.setdefault(node.func.attr, globals()[node.args[0].id])
    for parser_name in (
        "parse_jiang_wiese_square_heisenberg_spin_stiffness",
        "parse_jiang_wiese_square_heisenberg_staggered_magnetization",
        "parse_jiang_wiese_square_heisenberg_spin_wave_velocity",
    ):
        fixtures[parser_name] = JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT
    assert set(fixtures) == parser_names
    return fixtures


def test_unmigrated_exact_gap_parser_traces_keep_the_temporary_coordinate_view():
    parser_names = (
        _exact_gap_manifest_parser_names()
        - set(literature_runtime_evidence._PREPARED_TRACE_PARSER_BUILDERS)
    )
    assert parser_names == PREPARED_TRACE_BATCH_D_REMAINING
    assert len(parser_names) == 14
    fixtures = _exact_gap_positive_fixtures(
        _exact_gap_manifest_parser_names()
    )
    source_sha256 = "a" * 64

    for parser_name in parser_names:
        source_text = fixtures[parser_name]
        source_operand, trace = getattr(
            literature_runtime_evidence, parser_name
        )(source_text)
        coordinate_view = literature_runtime_evidence.trace_coordinate_view(
            source_text
        )
        assert trace["coordinate_space"] == (
            "canonical_normalized_extracted_text_v1"
        )
        assert trace["coordinate_contract_version"] == 1
        for start, end in trace["text_spans"]:
            assert coordinate_view[start:end].strip()

        benchmark_name = f"trace-contract-{parser_name}"
        selector_fields = sorted(source_operand)
        bundle = {
            "runtime_evidence_record": {
                "benchmark_name": benchmark_name,
                "evidence_mode": "local_source_parse",
                "source_id": "fixture-source",
                "source_sha256": source_sha256,
                "registry_selector": {
                    "path": ["standard_result"],
                    "fields": selector_fields,
                },
                "source_operand": source_operand,
                "registry_operand": source_operand,
                "comparison": {
                    "kind": "exact_field_map",
                    "matched": True,
                },
            },
            "extraction_trace": {
                **trace,
                "benchmark_name": benchmark_name,
                "source_sha256": source_sha256,
            },
        }
        assert (
            literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
                benchmark_name, bundle
            )
            == "strict_local_source_parsed"
        )


PREPARED_TRACE_BATCH_A_BUILDERS = {
    "parse_yang_xie_square_blume_capel_crossing": (
        "yang_xie_extracted_text",
        1,
    ),
    "parse_yang_xie_single_ion_spin1_anisotropy_levels": (
        "yang_xie_extracted_text",
        1,
    ),
    "parse_jiang_wiese_square_heisenberg_spin_stiffness": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_jiang_wiese_square_heisenberg_staggered_magnetization": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_jiang_wiese_square_heisenberg_spin_wave_velocity": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_depenbrock_kagome_heisenberg_energy": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_depenbrock_kagome_heisenberg_energy_and_spin_gap": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_stodter_clinoatacamite_distorted_kagome_exchange": (
        "stodter_pdf_layout_search_text",
        1,
    ),
    "parse_ishikawa_edwardsite_spin_half_deformed_kagome": (
        "ishikawa_pdf_layout_search_text",
        1,
    ),
    "parse_nawa_rubr3_kitaev_candidate_and_competing_interactions": (
        "nawa_pdf_layout_search_text",
        1,
    ),
    "parse_schiffer_ggg_strong_frustration_correction": (
        "schiffer_pdf_layout_search_text",
        1,
    ),
    "parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction": (
        "quilliam_pdf_layout_search_text",
        1,
    ),
    "parse_boldrin_vesignieite_dominant_j3_correction": (
        "boldrin_pdf_layout_search_text",
        1,
    ),
}


PREPARED_TRACE_BATCH_A_FIXTURES = {
    "parse_yang_xie_square_blume_capel_crossing": (
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT
    ),
    "parse_yang_xie_single_ion_spin1_anisotropy_levels": (
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT
    ),
    "parse_jiang_wiese_square_heisenberg_spin_stiffness": (
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT
    ),
    "parse_jiang_wiese_square_heisenberg_staggered_magnetization": (
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT
    ),
    "parse_jiang_wiese_square_heisenberg_spin_wave_velocity": (
        JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT
    ),
    "parse_depenbrock_kagome_heisenberg_energy": (
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT
    ),
    "parse_depenbrock_kagome_heisenberg_energy_and_spin_gap": (
        DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT
    ),
    "parse_stodter_clinoatacamite_distorted_kagome_exchange": (
        STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT
    ),
    "parse_ishikawa_edwardsite_spin_half_deformed_kagome": (
        ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT
    ),
    "parse_nawa_rubr3_kitaev_candidate_and_competing_interactions": (
        NAWA_RUBR3_MAGNETIC_EXCITATIONS_SOURCE_TEXT
    ),
    "parse_schiffer_ggg_strong_frustration_correction": (
        SCHIFFER_GGG_STRONG_FRUSTRATION_SOURCE_TEXT
    ),
    "parse_quilliam_gtlg_frustrated_hyperkagome_garnet_correction": (
        QUILLIAM_GTLG_FRUSTRATED_HYPERKAGOME_SOURCE_TEXT
    ),
    "parse_boldrin_vesignieite_dominant_j3_correction": (
        BOLDRIN_VESIGNIEITE_DOMINANT_J3_SOURCE_TEXT
    ),
}


PREPARED_TRACE_BATCH_B_BUILDERS = {
    "parse_dziarmaga_tfim_critical_point": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_dziarmaga_tfim_gap": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_collura_xx_chain_energy": (
        "collura_xx_extracted_text",
        1,
    ),
    "parse_pinettes_diep_simple_cubic_boundary": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_shastry_sutherland_exact_dimer_product": (
        "shastry_sutherland_dual_ocr_search_text",
        1,
    ),
    "parse_fouet_checkerboard_classical_constraint": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_kano_naya_kagome_ising_ferromagnet_tc": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_kano_naya_kagome_ising_antiferromagnet_entropy": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_garel_maillard_villain_entropy": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_husimi_syozi_honeycomb_ising_tc": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_husimi_syozi_triangular_ising_tc": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_caspers_emmett_magnus_majumdar_ghosh_dimer_ground_states": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_ising_1925_linear_chain_no_transition": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_hirata_nomura_xxz_phase_boundaries": (
        "hirata_nomura_extracted_text",
        1,
    ),
    "parse_kumar_j1_j2_critical_point": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_kumar_j1_j2_bkt_reference": (
        "dash_normalized_extracted_text",
        1,
    ),
}


PREPARED_TRACE_BATCH_B_FIXTURES = {
    parser_name: _exact_gap_positive_fixtures(
        _exact_gap_manifest_parser_names()
    )[parser_name]
    for parser_name in PREPARED_TRACE_BATCH_B_BUILDERS
}


PREPARED_TRACE_BATCH_B_CORES = {
    parser_name: f"_{parser_name}_prepared"
    for parser_name in PREPARED_TRACE_BATCH_B_BUILDERS
}


PREPARED_TRACE_BATCH_C_BUILDERS = {
    "parse_savary_er2ti2o7_psi2_order_by_quantum_disorder": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_richter_star_lattice_valence_bond_ground_state": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_richter_square_kagome_reference": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_wildes_feps3_ising_zigzag_order": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_dey_ba3irti2o9_triangular_spin_liquid_candidate": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_ghosh_mila_ruby_localized_magnon_eigenstate": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_biffin_gamma_li2iro3_spiral_kitaev_order": (
        "dash_normalized_extracted_text",
        1,
    ),
    "parse_mulder_honeycomb_spiral_contour": (
        "whitespace_normalized_extracted_text",
        1,
    ),
    "parse_balla_iqbal_penc_fcc_type_orders": (
        "balla_fcc_layout_search_text",
        1,
    ),
    "parse_henley_pyrochlore_coulomb_phase": (
        "ligature_dash_dehyphenated_extracted_text",
        1,
    ),
    "parse_abramchuk_cu2iro3_honeycomb_iridate": (
        "ligature_dash_normalized_extracted_text",
        1,
    ),
    "parse_enderle_licuvo4_incommensurate_helimagnet": (
        "ligature_dash_normalized_extracted_text",
        1,
    ),
    "parse_bak_jensen_mnsi_long_wavelength_helix": (
        "ligature_dash_normalized_extracted_text",
        1,
    ),
    "parse_seki_cu2oseo3_skyrmion_lattice_phase": (
        "seki_science_layout_search_text",
        1,
    ),
    "parse_wernsdorfer_sessoli_fe8_quantum_tunneling": (
        "wernsdorfer_science_webprint_search_text",
        1,
    ),
}


PREPARED_TRACE_BATCH_C_FIXTURES = {
    parser_name: _exact_gap_positive_fixtures(
        _exact_gap_manifest_parser_names()
    )[parser_name]
    for parser_name in PREPARED_TRACE_BATCH_C_BUILDERS
}


PREPARED_TRACE_BATCH_C_CORES = {
    parser_name: f"_{parser_name}_prepared"
    for parser_name in PREPARED_TRACE_BATCH_C_BUILDERS
}


PREPARED_TRACE_BATCH_D_REMAINING = {
    "parse_cable_crcl3_ferromagnetic_layers",
    "parse_carteaux_cr2ge2te6_ferromagnetic_order",
    "parse_ramirez_dy2ti2o7_pauling_entropy",
    "parse_kitagawa_h3liir2o6_no_magnetic_order",
    "parse_mazin_honeycomb_j1_j2_j3_phase_set",
    "parse_chaloupka_na2iro3_zigzag_relevance",
    "parse_chaloupka_full_kitaev_heisenberg_ordered_phases",
    "parse_furuchi_lieb_lattice_ground_state_spin",
    "parse_ressouche_mnps3_neel_order",
    "parse_hsieh_nacro2_unconventional_spin_order",
    "parse_sandvik_daul_square_xy_ring_bond_order",
    "parse_chubukov_golosov_triangular_plateau",
    "parse_blote_luijten_heringa_simple_cubic_ising_tc",
    "parse_kitazawa_nomura_takhtajan_babujian_point",
}


def _independently_normalize_ligatures_and_dashes(source_text):
    normalized = source_text
    for old, new in (
        ("ﬁ", "fi"),
        ("ﬂ", "fl"),
        ("ﬀ", "ff"),
        ("ﬃ", "ffi"),
        ("ﬄ", "ffl"),
        ("−", "-"),
        ("–", "-"),
        ("—", "-"),
    ):
        normalized = normalized.replace(old, new)
    return re.sub(r"\s+", " ", normalized).strip()


def _independently_rebuild_batch_c_view(source_text, builder_id):
    if builder_id in {
        "whitespace_normalized_extracted_text",
        "dash_normalized_extracted_text",
    }:
        return _independently_rebuild_batch_b_view(source_text, builder_id)
    if builder_id == "ligature_dash_normalized_extracted_text":
        return _independently_normalize_ligatures_and_dashes(source_text)
    if builder_id == "ligature_dash_dehyphenated_extracted_text":
        normalized = source_text
        for old, new in (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("·", " dot "),
        ):
            normalized = normalized.replace(old, new)
        normalized = re.sub(r"(?<=\w)-\s+(?=\w)", "", normalized)
        return re.sub(r"\s+", " ", normalized).strip()
    if builder_id == "balla_fcc_layout_search_text":
        normalized = source_text
        for old, new in (
            ("ﬁ", "fi"),
            ("ﬂ", "fl"),
            ("ﬀ", "ff"),
            ("ﬃ", "ffi"),
            ("ﬄ", "ffl"),
            ("−", "-"),
            ("–", "-"),
            ("—", "-"),
            ("·", " dot "),
        ):
            normalized = normalized.replace(old, new)
        normalized = re.sub(r"(?<=\w)-\s+(?=\w)", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized + "\n" + "#" * 5000 + "\n" + source_text
    if builder_id == "seki_science_layout_search_text":
        def normalize(text):
            text = re.sub(
                r"(?<=[A-Za-z])-\s*\r?\n\s*(?=[a-z])", "", text
            )
            for old, new in (
                ("ﬁ", "fi"),
                ("ﬂ", "fl"),
                ("ﬀ", "ff"),
                ("ﬃ", "ffi"),
                ("ﬄ", "ffl"),
                ("−", "-"),
                ("–", "-"),
                ("—", "-"),
                ("∼", "~"),
            ):
                text = text.replace(old, new)
            return re.sub(r"\s+", " ", text).strip()

        pages = source_text.split("\f")
        wide_left_raw = "\n".join(
            line[:138]
            for page in pages
            for line in page.splitlines()
        )
        two_column_raw = "\n".join(
            line[:112]
            for page in pages
            for line in page.splitlines()
        )
        column_major_raw = "\n".join(
            "\n".join(line[start:end] for line in page.splitlines())
            for page in pages
            for start, end in ((0, 55), (55, 112), (112, None))
        )
        search_text = " ".join(
            (
                normalize(source_text),
                normalize(wide_left_raw),
                normalize(two_column_raw),
                normalize(column_major_raw),
            )
        )
        separator = "\n" + "#" * 5000 + "\n"
        return separator.join((search_text, source_text, column_major_raw))
    if builder_id == "wernsdorfer_science_webprint_search_text":
        normalized = _independently_normalize_ligatures_and_dashes(
            source_text
        )
        webprint_left_raw = "\n".join(
            line[:108] for line in source_text.splitlines()
        )
        webprint_left_normalized = (
            _independently_normalize_ligatures_and_dashes(
                webprint_left_raw
            )
        )
        return " ".join((normalized, webprint_left_normalized))
    raise AssertionError(f"unexpected Batch C builder: {builder_id}")


def _independently_rebuild_batch_b_view(source_text, builder_id):
    whitespace_normalized = re.sub(r"\s+", " ", source_text).strip()
    if builder_id == "whitespace_normalized_extracted_text":
        return whitespace_normalized
    if builder_id == "dash_normalized_extracted_text":
        return (
            whitespace_normalized.replace("−", "-")
            .replace("–", "-")
            .replace("—", "-")
        )
    if builder_id == "collura_xx_extracted_text":
        return (
            whitespace_normalized.replace("−", "-")
            .replace("–", "-")
            .replace("—", "-")
            .replace("π", "pi")
        )
    if builder_id == "hirata_nomura_extracted_text":
        return whitespace_normalized.replace("−", "-").replace("–", "-")
    if builder_id == "shastry_sutherland_dual_ocr_search_text":
        spaced_word = re.compile(
            r"(?<![A-Za-z])(?:[A-Za-z]\s+){3,}[A-Za-z](?![A-Za-z])"
        )
        collapsed = spaced_word.sub(
            lambda match: re.sub(r"\s+", "", match.group(0)),
            whitespace_normalized,
        )
        return whitespace_normalized + "\n" + "#" * 5000 + "\n" + collapsed
    raise AssertionError(f"unexpected Batch B builder: {builder_id}")


def _prepared_trace_bundle(parser_name, source_text):
    source_operand, trace = getattr(
        literature_runtime_evidence, parser_name
    )(source_text)
    benchmark_name = f"prepared-trace-{parser_name}"
    source_sha256 = "a" * 64
    bundle = {
        "runtime_evidence_record": {
            "benchmark_name": benchmark_name,
            "evidence_mode": "local_source_parse",
            "source_id": "fixture-source",
            "source_sha256": source_sha256,
            "registry_selector": {
                "path": ["standard_result"],
                "fields": sorted(source_operand),
            },
            "source_operand": source_operand,
            "registry_operand": source_operand,
            "comparison": {"kind": "exact_field_map", "matched": True},
        },
        "extraction_trace": {
            **trace,
            "benchmark_name": benchmark_name,
            "source_sha256": source_sha256,
        },
    }
    return benchmark_name, bundle


def test_batch_a_prepared_trace_registry_is_exact():
    assert {
        parser_name: literature_runtime_evidence._PREPARED_TRACE_PARSER_BUILDERS[
            parser_name
        ]
        for parser_name in PREPARED_TRACE_BATCH_A_BUILDERS
    } == PREPARED_TRACE_BATCH_A_BUILDERS
    assert set(PREPARED_TRACE_BATCH_A_FIXTURES) == set(
        PREPARED_TRACE_BATCH_A_BUILDERS
    )
    assert len(PREPARED_TRACE_BATCH_A_BUILDERS) == 13


def test_batch_b_prepared_trace_registry_is_exact_within_batch():
    registered = dict(
        literature_runtime_evidence._PREPARED_TRACE_PARSER_BUILDERS
    )
    assert {
        parser_name: registered[parser_name]
        for parser_name in PREPARED_TRACE_BATCH_B_BUILDERS
    } == PREPARED_TRACE_BATCH_B_BUILDERS
    assert set(PREPARED_TRACE_BATCH_A_BUILDERS).isdisjoint(
        PREPARED_TRACE_BATCH_B_BUILDERS
    )
    assert set(PREPARED_TRACE_BATCH_B_FIXTURES) == set(
        PREPARED_TRACE_BATCH_B_BUILDERS
    )
    assert len(PREPARED_TRACE_BATCH_B_BUILDERS) == 16


def test_batch_c_prepared_trace_registry_and_cumulative_set_are_exact():
    registered = dict(
        literature_runtime_evidence._PREPARED_TRACE_PARSER_BUILDERS
    )
    prior_builders = {
        **PREPARED_TRACE_BATCH_A_BUILDERS,
        **PREPARED_TRACE_BATCH_B_BUILDERS,
    }
    assert set(registered) - set(prior_builders) == set(
        PREPARED_TRACE_BATCH_C_BUILDERS
    )
    assert registered == {
        **prior_builders,
        **PREPARED_TRACE_BATCH_C_BUILDERS,
    }
    assert set(PREPARED_TRACE_BATCH_C_FIXTURES) == set(
        PREPARED_TRACE_BATCH_C_BUILDERS
    )
    assert len(PREPARED_TRACE_BATCH_C_BUILDERS) == 15
    assert len(registered) == 44
    assert (
        _exact_gap_manifest_parser_names() - set(registered)
        == PREPARED_TRACE_BATCH_D_REMAINING
    )
    assert len(PREPARED_TRACE_BATCH_D_REMAINING) == 14


@pytest.mark.parametrize(
    "parser_name", PREPARED_TRACE_BATCH_C_BUILDERS
)
def test_batch_c_trace_replays_independently_declared_prepared_view(
    parser_name,
):
    source_text = PREPARED_TRACE_BATCH_C_FIXTURES[parser_name]
    builder_id, version = PREPARED_TRACE_BATCH_C_BUILDERS[parser_name]
    benchmark_name, bundle = _prepared_trace_bundle(parser_name, source_text)
    trace = bundle["extraction_trace"]

    independently_rebuilt = _independently_rebuild_batch_c_view(
        source_text, builder_id
    )
    assert trace["coordinate_space"] == "private_prepared_extracted_text"
    assert trace["coordinate_builder"] == builder_id
    assert type(trace["coordinate_contract_version"]) is int
    assert trace["coordinate_contract_version"] == version
    assert trace["coordinate_view_length"] == len(independently_rebuilt)
    assert trace["coordinate_view_sha256"] == hashlib.sha256(
        independently_rebuilt.encode("utf-8")
    ).hexdigest()
    assert len(trace["text_span_sha256"]) == len(trace["text_spans"])
    assert len(trace["text_span_captures"]) == len(trace["text_spans"])
    for span, digest, capture in zip(
        trace["text_spans"],
        trace["text_span_sha256"],
        trace["text_span_captures"],
    ):
        start, end = span
        independently_replayed_capture = independently_rebuilt[start:end]
        assert 0 <= start < end <= len(independently_rebuilt)
        assert capture == independently_replayed_capture
        assert capture
        assert digest == hashlib.sha256(
            independently_replayed_capture.encode("utf-8")
        ).hexdigest()

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        == "strict_local_source_parsed"
    )


@pytest.mark.parametrize(
    "parser_name", PREPARED_TRACE_BATCH_C_BUILDERS
)
def test_batch_c_public_parsers_prepare_exactly_once(
    monkeypatch, parser_name
):
    source_text = PREPARED_TRACE_BATCH_C_FIXTURES[parser_name]
    preparation_calls = []
    original_builder = literature_runtime_evidence._build_prepared_view

    def recording_builder(*args, **kwargs):
        preparation_calls.append((args, kwargs))
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        literature_runtime_evidence,
        "_build_prepared_view",
        recording_builder,
    )

    getattr(literature_runtime_evidence, parser_name)(source_text)

    assert len(preparation_calls) == 1


@pytest.mark.parametrize(
    "parser_name", PREPARED_TRACE_BATCH_C_BUILDERS
)
def test_batch_c_prepared_cores_do_not_prepare_normalize_or_rebuild_layout(
    monkeypatch, parser_name
):
    source_text = PREPARED_TRACE_BATCH_C_FIXTURES[parser_name]
    builder_id, version = PREPARED_TRACE_BATCH_C_BUILDERS[parser_name]
    prepared = literature_runtime_evidence._build_prepared_view(
        source_text, builder_id=builder_id, version=version
    )
    expected = getattr(literature_runtime_evidence, parser_name)(source_text)
    core = getattr(
        literature_runtime_evidence,
        PREPARED_TRACE_BATCH_C_CORES[parser_name],
    )
    core_source = inspect.getsource(core)
    core_tree = ast.parse(core_source)
    forbidden_attributes = {"replace", "split", "splitlines", "join"}
    assert not any(
        isinstance(node, ast.Call)
        and (
            (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden_attributes
            )
            or (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "re"
                and node.func.attr == "sub"
            )
            or (
                isinstance(node.func, ast.Name)
                and (
                    node.func.id.startswith("_build_")
                    or "normalize" in node.func.id
                )
            )
        )
        for node in ast.walk(core_tree)
    )

    def forbidden_preparation(*args, **kwargs):
        raise AssertionError("prepared core rebuilt its input")

    def forbidden_normalization(*args, **kwargs):
        raise AssertionError("prepared core normalized its input again")

    monkeypatch.setattr(
        literature_runtime_evidence,
        "_build_prepared_view",
        forbidden_preparation,
    )
    monkeypatch.setattr(
        literature_runtime_evidence.re,
        "sub",
        forbidden_normalization,
    )
    core_result = core(prepared.text)

    assert literature_runtime_evidence._finalize_prepared_trace(
        core_result, prepared
    ) == expected


@pytest.mark.parametrize(
    "parser_name", PREPARED_TRACE_BATCH_B_BUILDERS
)
def test_batch_b_trace_replays_independently_declared_prepared_view(
    parser_name,
):
    source_text = PREPARED_TRACE_BATCH_B_FIXTURES[parser_name]
    builder_id, version = PREPARED_TRACE_BATCH_B_BUILDERS[parser_name]
    benchmark_name, bundle = _prepared_trace_bundle(parser_name, source_text)
    trace = bundle["extraction_trace"]

    independently_rebuilt = _independently_rebuild_batch_b_view(
        source_text, builder_id
    )
    assert trace["coordinate_space"] == "private_prepared_extracted_text"
    assert trace["coordinate_builder"] == builder_id
    assert type(trace["coordinate_contract_version"]) is int
    assert trace["coordinate_contract_version"] == version
    assert trace["coordinate_view_length"] == len(independently_rebuilt)
    assert trace["coordinate_view_sha256"] == hashlib.sha256(
        independently_rebuilt.encode("utf-8")
    ).hexdigest()
    assert len(trace["text_span_sha256"]) == len(trace["text_spans"])
    assert len(trace["text_span_captures"]) == len(trace["text_spans"])
    for span, digest, capture in zip(
        trace["text_spans"],
        trace["text_span_sha256"],
        trace["text_span_captures"],
    ):
        start, end = span
        independently_replayed_capture = independently_rebuilt[start:end]
        assert start < end <= len(independently_rebuilt)
        assert capture == independently_replayed_capture
        assert digest == hashlib.sha256(
            independently_replayed_capture.encode("utf-8")
        ).hexdigest()

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        == "strict_local_source_parsed"
    )


@pytest.mark.parametrize(
    "parser_name", PREPARED_TRACE_BATCH_B_BUILDERS
)
def test_batch_b_public_parsers_prepare_exactly_once(
    monkeypatch, parser_name
):
    source_text = PREPARED_TRACE_BATCH_B_FIXTURES[parser_name]
    preparation_calls = []
    original_builder = literature_runtime_evidence._build_prepared_view

    def recording_builder(*args, **kwargs):
        preparation_calls.append((args, kwargs))
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        literature_runtime_evidence,
        "_build_prepared_view",
        recording_builder,
    )

    getattr(literature_runtime_evidence, parser_name)(source_text)

    assert len(preparation_calls) == 1


@pytest.mark.parametrize(
    "parser_name,sibling_name",
    [
        (
            "parse_dziarmaga_tfim_gap",
            "parse_dziarmaga_tfim_critical_point",
        ),
        (
            "parse_kano_naya_kagome_ising_antiferromagnet_entropy",
            "parse_kano_naya_kagome_ising_ferromagnet_tc",
        ),
        (
            "parse_husimi_syozi_triangular_ising_tc",
            "parse_husimi_syozi_honeycomb_ising_tc",
        ),
        (
            "parse_kumar_j1_j2_bkt_reference",
            "parse_kumar_j1_j2_critical_point",
        ),
    ],
)
def test_batch_b_related_pairs_do_not_recurse_through_public_sibling(
    monkeypatch, parser_name, sibling_name
):
    def forbidden_public_recursion(*args, **kwargs):
        raise AssertionError("related parser recursed through public sibling")

    monkeypatch.setattr(
        literature_runtime_evidence,
        sibling_name,
        forbidden_public_recursion,
    )

    getattr(literature_runtime_evidence, parser_name)(
        PREPARED_TRACE_BATCH_B_FIXTURES[parser_name]
    )


@pytest.mark.parametrize(
    "parser_name", PREPARED_TRACE_BATCH_B_BUILDERS
)
def test_batch_b_prepared_cores_do_not_prepare_or_normalize_again(
    monkeypatch, parser_name
):
    source_text = PREPARED_TRACE_BATCH_B_FIXTURES[parser_name]
    builder_id, version = PREPARED_TRACE_BATCH_B_BUILDERS[parser_name]
    prepared = literature_runtime_evidence._build_prepared_view(
        source_text, builder_id=builder_id, version=version
    )
    expected = getattr(literature_runtime_evidence, parser_name)(source_text)

    def forbidden_preparation(*args, **kwargs):
        raise AssertionError("prepared core rebuilt its input")

    def forbidden_normalization(*args, **kwargs):
        raise AssertionError("prepared core normalized its input again")

    monkeypatch.setattr(
        literature_runtime_evidence,
        "_build_prepared_view",
        forbidden_preparation,
    )
    monkeypatch.setattr(
        literature_runtime_evidence.re,
        "sub",
        forbidden_normalization,
    )
    core_result = getattr(
        literature_runtime_evidence,
        PREPARED_TRACE_BATCH_B_CORES[parser_name],
    )(prepared.text)

    assert literature_runtime_evidence._finalize_prepared_trace(
        core_result, prepared
    ) == expected


def test_shastry_sutherland_dual_ocr_view_traces_both_declared_halves():
    source_text = SHASTRY_SUTHERLAND_EXACT_DIMER_SOURCE_TEXT.replace(
        "ANTIFERROMAGNET", "A N T I F E R R O M A G N E T"
    )
    _, trace = (
        literature_runtime_evidence.parse_shastry_sutherland_exact_dimer_product(
            source_text
        )
    )

    independently_rebuilt = _independently_rebuild_batch_b_view(
        source_text, "shastry_sutherland_dual_ocr_search_text"
    )
    separator_start = independently_rebuilt.index("\n" + "#" * 5000 + "\n")
    separator_end = separator_start + 5002
    assert trace["text_spans"][3][1] <= separator_start
    assert any(start >= separator_end for start, _ in trace["text_spans"])
    assert all(
        not (start < separator_end and end > separator_start)
        for start, end in trace["text_spans"]
    )


@pytest.mark.parametrize(
    "parser_name", PREPARED_TRACE_BATCH_A_BUILDERS
)
def test_batch_a_trace_replays_exact_declared_prepared_view(parser_name):
    source_text = PREPARED_TRACE_BATCH_A_FIXTURES[parser_name]
    builder_id, version = PREPARED_TRACE_BATCH_A_BUILDERS[parser_name]
    benchmark_name, bundle = _prepared_trace_bundle(
        parser_name, source_text
    )
    trace = bundle["extraction_trace"]

    prepared = literature_runtime_evidence._build_prepared_view(
        source_text, builder_id=builder_id, version=version
    )
    assert trace["coordinate_space"] == "private_prepared_extracted_text"
    assert trace["coordinate_builder"] == builder_id
    assert type(trace["coordinate_contract_version"]) is int
    assert trace["coordinate_contract_version"] == version
    assert trace["coordinate_view_length"] == len(prepared.text)
    assert trace["coordinate_view_sha256"] == hashlib.sha256(
        prepared.text.encode("utf-8")
    ).hexdigest()
    assert len(trace["text_span_sha256"]) == len(trace["text_spans"])
    assert len(trace["text_span_captures"]) == len(trace["text_spans"])
    for span, digest, capture in zip(
        trace["text_spans"],
        trace["text_span_sha256"],
        trace["text_span_captures"],
    ):
        start, end = span
        independently_replayed_capture = prepared.text[start:end]
        assert capture == independently_replayed_capture
        assert digest == hashlib.sha256(
            independently_replayed_capture.encode("utf-8")
        ).hexdigest()

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        == "strict_local_source_parsed"
    )


def test_stodter_page_break_trace_keeps_dehyphenated_anchor_alignment():
    source_text = STODTER_CLINOATACAMITE_DISTORTED_KAGOME_SOURCE_TEXT.replace(
        "Our findings further",
        "Our find-\n\f7\nings further",
    ).replace("from Ref. [21]", "from Ref.\n\f[21]")

    _, trace = (
        literature_runtime_evidence
        .parse_stodter_clinoatacamite_distorted_kagome_exchange(source_text)
    )

    assert trace["text_span_captures"][8].startswith("Our findings")
    assert "Ref. [21]" in trace["text_span_captures"][8]
    assert trace["text_span_captures"][9].startswith("[21]")
    assert "[21] S.-H. Lee" in trace["text_span_captures"][9]


def test_ishikawa_trace_anchors_are_exact_slices_of_derived_layout_view():
    _, trace = (
        literature_runtime_evidence
        .parse_ishikawa_edwardsite_spin_half_deformed_kagome(
            ISHIKAWA_EDWARDSITE_DEFORMED_KAGOME_SOURCE_TEXT
        )
    )

    assert trace["text_span_captures"][0].startswith(
        "Magnetic Properties of the Spin-1/2 Deformed Kagome"
    )
    assert trace["text_span_captures"][3].startswith(
        "Edwardsite has a deformed kagome lattice"
    )


def test_yang_xie_plus_minus_variant_keeps_bibliography_alignment():
    source_text = YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT.replace(
        "+/-1 and 0", "±1 and 0"
    )

    _, trace = literature_runtime_evidence.parse_yang_xie_square_blume_capel_crossing(
        source_text
    )

    assert trace["text_span_captures"][-1].startswith("[1] M. Blume")


@pytest.mark.parametrize(
    "parser_name,dependency_name,source_text",
    [
        (
            "parse_yang_xie_single_ion_spin1_anisotropy_levels",
            "parse_yang_xie_square_blume_capel_crossing",
            YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
        ),
        (
            "parse_jiang_wiese_square_heisenberg_spin_stiffness",
            "parse_jiang_wiese_square_heisenberg_low_energy_parameters",
            JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT,
        ),
        (
            "parse_jiang_wiese_square_heisenberg_staggered_magnetization",
            "parse_jiang_wiese_square_heisenberg_low_energy_parameters",
            JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT,
        ),
        (
            "parse_jiang_wiese_square_heisenberg_spin_wave_velocity",
            "parse_jiang_wiese_square_heisenberg_low_energy_parameters",
            JIANG_WIESE_SQUARE_HEISENBERG_SOURCE_TEXT,
        ),
        (
            "parse_depenbrock_kagome_heisenberg_energy_and_spin_gap",
            "parse_depenbrock_kagome_heisenberg_energy",
            DEPENBROCK_KAGOME_HEISENBERG_SOURCE_TEXT,
        ),
    ],
)
def test_composed_batch_a_parsers_prepare_once_without_public_recursion(
    monkeypatch, parser_name, dependency_name, source_text
):
    preparation_calls = []
    original_builder = literature_runtime_evidence._build_prepared_view

    def recording_builder(*args, **kwargs):
        preparation_calls.append((args, kwargs))
        return original_builder(*args, **kwargs)

    def forbidden_public_recursion(*args, **kwargs):
        raise AssertionError("composed parser recursed through public parser")

    monkeypatch.setattr(
        literature_runtime_evidence,
        "_build_prepared_view",
        recording_builder,
    )
    monkeypatch.setattr(
        literature_runtime_evidence,
        dependency_name,
        forbidden_public_recursion,
    )

    getattr(literature_runtime_evidence, parser_name)(source_text)

    assert len(preparation_calls) == 1


@pytest.mark.parametrize(
    "version", [True, 1.0, "1", 2]
)
def test_prepared_trace_schema_rejects_nonexact_or_unsupported_version(version):
    benchmark_name, bundle = _prepared_trace_bundle(
        "parse_yang_xie_square_blume_capel_crossing",
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
    )
    bundle["extraction_trace"]["coordinate_contract_version"] = version

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        is None
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("coordinate_builder", "unknown_builder"),
        ("coordinate_view_sha256", "not-a-sha256"),
        ("coordinate_view_length", 0),
        ("text_span_sha256", ["0" * 64] * 10),
    ],
)
def test_prepared_trace_schema_rejects_bad_builder_hash_span_or_digest(
    field, value
):
    benchmark_name, bundle = _prepared_trace_bundle(
        "parse_yang_xie_square_blume_capel_crossing",
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
    )
    bundle["extraction_trace"][field] = value

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        is None
    )


def test_prepared_trace_schema_rejects_out_of_range_span():
    benchmark_name, bundle = _prepared_trace_bundle(
        "parse_yang_xie_square_blume_capel_crossing",
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
    )
    trace = bundle["extraction_trace"]
    trace["text_spans"][0] = [0, trace["coordinate_view_length"] + 1]

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        is None
    )


@pytest.mark.parametrize(
    "missing_field",
    [
        "coordinate_builder",
        "coordinate_contract_version",
        "coordinate_view_sha256",
        "coordinate_view_length",
        "text_span_sha256",
        "text_span_captures",
    ],
)
def test_prepared_trace_schema_rejects_missing_coordinate_metadata(
    missing_field
):
    benchmark_name, bundle = _prepared_trace_bundle(
        "parse_yang_xie_square_blume_capel_crossing",
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
    )
    bundle["extraction_trace"].pop(missing_field)

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        is None
    )


def test_prepared_trace_schema_rejects_extra_coordinate_metadata():
    benchmark_name, bundle = _prepared_trace_bundle(
        "parse_yang_xie_square_blume_capel_crossing",
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
    )
    bundle["extraction_trace"]["coordinate_view_extra"] = "contradiction"

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        is None
    )


@pytest.mark.parametrize(
    "parser_label",
    [
        "parse_jiang_wiese_square_heisenberg_low_energy_parameters",
        "unknown_prepared_trace_parser",
        [],
        {},
    ],
)
def test_prepared_trace_schema_rejects_unregistered_parser_label(
    parser_label,
):
    benchmark_name, bundle = _prepared_trace_bundle(
        "parse_yang_xie_square_blume_capel_crossing",
        YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
    )
    bundle["extraction_trace"]["parser"] = parser_label

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        is None
    )


@pytest.mark.parametrize("prepared", [False, True])
@pytest.mark.parametrize("invalid_key", [1, b"coordinate_view_extra"])
def test_structural_validator_rejects_non_string_trace_keys(
    prepared, invalid_key
):
    if prepared:
        benchmark_name, bundle = _prepared_trace_bundle(
            "parse_yang_xie_square_blume_capel_crossing",
            YANG_XIE_BLUME_CAPEL_CROSSING_SOURCE_TEXT,
        )
    else:
        bundle = _source_parse_bundle()
        benchmark_name = bundle["runtime_evidence_record"]["benchmark_name"]
    bundle["extraction_trace"][invalid_key] = "malformed"

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
        is None
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("coordinate_builder", "yang_xie_extracted_text"),
        ("coordinate_contract_version", 1),
        ("coordinate_view_sha256", "a" * 64),
        ("coordinate_view_length", 100),
        ("text_span_sha256", ["a" * 64, "b" * 64]),
        ("text_span_captures", ["honeycomb network", "order"]),
    ],
)
def test_legacy_trace_schema_rejects_prepared_view_metadata(field, value):
    bundle = _source_parse_bundle()
    bundle["extraction_trace"][field] = value

    assert _structural_label(bundle) == "no"
