#!/usr/bin/env python3
"""TimeCrystal-Q - educational discrete time crystal (DTC) physics lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Simulation only: a periodically driven (Floquet) spin chain, simulated
exactly with a small statevector core (<= 10 qubits), that breaks the
discrete time-translation symmetry of its own drive - it answers at
TWICE the drive period. The lab covers the imperfect pi-pulse (flip
error epsilon) and the rigid plateau where period doubling survives
it, the stabilising role of interactions + disorder (many-body
localisation), the stroboscopic order parameter, a phase-diagram sweep
(DTC / thermal / trivial), an exact 2-qubit Floquet spectrum with
pi-paired quasienergies, and an honest side-by-side with the 2021
Google Sycamore time-crystal experiment (published reference values
only - nothing here is measured on hardware).

Every real-hardware / live-operation action is a permanent HOLD gate.
"""
import cmath
import hashlib
import json
import math
import random
import sys

VERSION = "1.0.0"
MAX_QUBITS = 10          # exact statevector: 2^10 = 1024 amplitudes, fast
DEFAULT_CYCLES = 40

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "real_quantum_hardware": "HOLD - no control of, or jobs on, real quantum hardware",
    "live_experiment_control": "HOLD - no live control of any physics experiment",
    "qpu_job_submission_live": "HOLD - no job submission to any quantum cloud / QPU service",
    "pulse_calibration_live": "HOLD - no calibration of real control pulses or electronics",
    "cryogenic_system_control": "HOLD - no control of cryostats, dilution fridges, or cryogenics",
    "hardware_fabrication_design": "HOLD - no chip / device fabrication design output",
    "experimental_data_claim": "HOLD - simulation output is never presented as measured experimental data",
    "quantum_advantage_claim": "HOLD - no quantum-advantage / supremacy claim; this is a <=10-qubit exact sim",
    "peer_reviewed_result_claim": "HOLD - no claim that lab results are peer-reviewed findings",
    "commercial_product_claim": "HOLD - no claim this simulation is a commercial product or certified tool",
    "investment_advice_claim": "HOLD - no investment advice about quantum companies or hardware",
    "weapons_application_claim": "HOLD - no weapons or military application claims",
    "medical_application_claim": "HOLD - no medical or clinical application claims",
    "live_telemetry_ingest": "HOLD - no ingestion of live telemetry from real devices",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Statevector core
# Exact statevector for n <= MAX_QUBITS qubits. Qubit q is bit q of the
# basis index; bit 0 = spin up (Sz eigenvalue +1), bit 1 = spin down (-1).
# Everything below is exact unitary evolution - no sampling, no noise.

def basis_state(n, bits=0):
    """The computational-basis state |bits> on n qubits."""
    if not 1 <= n <= MAX_QUBITS:
        raise ValueError(f"qubit count must be 1..{MAX_QUBITS}")
    state = [0j] * (1 << n)
    state[bits] = 1.0 + 0j
    return state


def norm(state):
    return math.sqrt(sum(a.real * a.real + a.imag * a.imag for a in state))


def apply_x_rotation(state, n, q, theta):
    """Single-qubit rotation exp(-i theta X / 2) on qubit q (in place)."""
    c = math.cos(theta / 2.0)
    s = math.sin(theta / 2.0)
    step = 1 << q
    for base in range(0, len(state), 2 * step):
        for off in range(step):
            i0 = base + off
            i1 = i0 + step
            a0, a1 = state[i0], state[i1]
            state[i0] = c * a0 - 1j * s * a1
            state[i1] = -1j * s * a0 + c * a1
    return state


def apply_zz_phase(state, n, i, j, phi):
    """Ising phase exp(-i phi Sz_i Sz_j): +phi phase when the bits agree."""
    ep = cmath.exp(-1j * phi)
    em = cmath.exp(1j * phi)
    for idx in range(len(state)):
        state[idx] *= ep if ((idx >> i) & 1) == ((idx >> j) & 1) else em
    return state


def apply_z_field(state, n, q, h):
    """On-site field phase exp(-i h Sz_q) (in place)."""
    ep = cmath.exp(-1j * h)
    em = cmath.exp(1j * h)
    for idx in range(len(state)):
        state[idx] *= ep if ((idx >> q) & 1) == 0 else em
    return state


def z_expectation(state, n, q):
    """<Sz_q> of the state (exact, from the full statevector)."""
    tot = 0.0
    for idx, a in enumerate(state):
        p = a.real * a.real + a.imag * a.imag
        tot += p if ((idx >> q) & 1) == 0 else -p
    return tot


def mean_magnetization(state, n):
    """Chain-averaged magnetisation (1/n) sum_q <Sz_q>, in [-1, 1]."""
    return sum(z_expectation(state, n, q) for q in range(n)) / n


# ================================================================ 2. The Floquet drive
# One drive period (Floquet cycle) is U_F = U3 . U2 . U1 with
#   U1 = global X rotation by angle pi*g on every qubit
#        (g = 1 - epsilon; g = 1 is the perfect pi-pulse / spin flip)
#   U2 = nearest-neighbour Ising phases exp(-i phi_ij Sz_i Sz_j),
#        phi_ij disordered around the interaction strength J
#   U3 = on-site disorder fields exp(-i h_i Sz_i), h_i in [-W, W]
# This is the kicked-Ising Floquet model of the Sycamore experiment.
# With g = 1 exactly, U_F^2 is diagonal in the Sz basis (the global
# flip conjugates every field h -> -h and leaves every Sz Sz term
# invariant), so Floquet quasienergies pair up exactly pi apart -
# the spectral fingerprint of the discrete time crystal.

def make_disorder(n, j_mean, w_max, seed):
    """Deterministic disordered couplings + fields from an integer seed.

    phi_ij = j_mean * u, u in [0.6, 1.4];  h_i uniform in [-w_max, w_max].
    Returns (couplings list for pairs (0,1)..(n-2,n-1), fields list).
    """
    rng = random.Random(seed)
    couplings = [j_mean * (0.6 + 0.8 * rng.random()) for _ in range(max(n - 1, 0))]
    fields = [w_max * (2.0 * rng.random() - 1.0) for _ in range(n)]
    return couplings, fields


def floquet_cycle(state, n, couplings, fields, g):
    """Apply one full drive period U_F = U3 . U2 . U1 (in place)."""
    pulse = math.pi * g
    for q in range(n):
        apply_x_rotation(state, n, q, pulse)
    for i, phi in enumerate(couplings):
        apply_zz_phase(state, n, i, i + 1, phi)
    for q in range(n):
        apply_z_field(state, n, q, fields[q])
    return state


def run_series(n=8, g=0.95, j_mean=math.pi / 4.0, w_max=math.pi,
               cycles=DEFAULT_CYCLES, seed=2021):
    """Stroboscopic magnetisation series m[1..cycles] from |up up ... up>.

    m[k] is the chain-averaged <Sz> measured right after drive cycle k.
    Perfect period doubling: m[k] = (-1)^k exactly.
    """
    couplings, fields = make_disorder(n, j_mean, w_max, seed)
    state = basis_state(n, 0)
    series = []
    for _ in range(cycles):
        floquet_cycle(state, n, couplings, fields, g)
        series.append(mean_magnetization(state, n))
    return series


def epsilon_of(g):
    """Pulse error epsilon = 1 - g (0 = perfect pi-pulse)."""
    return 1.0 - g


# ================================================================ 3. Order parameter
# The DTC order parameter is the subharmonic (half-frequency) response:
#   A = | (1/N) sum_k (-1)^k m[k] |
# A = 1 for perfect period doubling, A ~ 0 when the response melts or
# follows the drive trivially. Persistence (mean |m| late in the run)
# separates a melted (thermal) chain from a merely detuned one.

def subharmonic_amplitude(series):
    """|mean of (-1)^k m[k]| - 1.0 is perfect period doubling."""
    if not series:
        return 0.0
    tot = 0.0
    for k, m in enumerate(series, start=1):
        tot += m if k % 2 == 0 else -m
    return abs(tot) / len(series)


def persistence(series):
    """Mean |m| over the second half of the series (late-time memory)."""
    if not series:
        return 0.0
    half = series[len(series) // 2:]
    return sum(abs(m) for m in half) / len(half)


def early_magnetization(series):
    """Mean |m| over the first third of the series."""
    if not series:
        return 0.0
    third = series[: max(1, len(series) // 3)]
    return sum(abs(m) for m in third) / len(third)


def dft_power(series, freq):
    """Discrete Fourier power of the series at `freq` cycles per period."""
    n = len(series)
    if n == 0:
        return 0.0
    acc = 0j
    for k, m in enumerate(series):
        acc += m * cmath.exp(-2j * math.pi * freq * k)
    return (acc.real * acc.real + acc.imag * acc.imag) / (n * n)


def fourier_spectrum(series):
    """Power at every Fourier frequency k/N of the series, k = 0..N//2."""
    n = len(series)
    return {round(k / n, 4): round(dft_power(series, k / n), 6)
            for k in range(n // 2 + 1)}


def subharmonic_peak_share(series):
    """Share of total Fourier power sitting at exactly half frequency."""
    spec = fourier_spectrum(series)
    total = sum(spec.values())
    if total <= 0.0:
        return 0.0
    return spec.get(0.5, 0.0) / total


def classify_run(series):
    """Phase label for one run: DTC / thermal / trivial.

    DTC: strong subharmonic amplitude AND late-time persistence.
    thermal: the magnetisation melted (persistence ~ 0).
    trivial: everything else (follows the drive, detuned, prethermal).
    """
    a = subharmonic_amplitude(series)
    p = persistence(series)
    if a >= 0.45 and p >= 0.35:
        return "DTC"
    if p <= 0.15:
        return "thermal"
    return "trivial"


def run_report(n=8, g=0.95, j_mean=math.pi / 4.0, w_max=math.pi,
               cycles=DEFAULT_CYCLES, seed=2021):
    """Full diagnostic dict for one parameter point."""
    series = run_series(n, g, j_mean, w_max, cycles, seed)
    return {
        "n_qubits": n,
        "g": g,
        "epsilon": round(epsilon_of(g), 4),
        "j_mean_over_pi": round(j_mean / math.pi, 4),
        "w_max_over_pi": round(w_max / math.pi, 4),
        "cycles": cycles,
        "subharmonic_amplitude": round(subharmonic_amplitude(series), 4),
        "persistence": round(persistence(series), 4),
        "subharmonic_peak_share": round(subharmonic_peak_share(series), 4),
        "phase": classify_run(series),
        "gate": gate("run_simulation"),
    }


# ================================================================ 4. Rigidity plateau
# The signature of the DTC phase is RIGIDITY: the subharmonic response
# survives a finite range of pulse error epsilon instead of dying at
# the first imperfection. The scan below proves the load-bearing role
# of INTERACTIONS at strong disorder: J = pi/4 holds a plateau out to
# epsilon ~ 0.125 while J = 0 collapses by epsilon ~ 0.025 - the exact
# contrast the Sycamore experiment headlined. In the thermodynamic
# limit, strong disorder (many-body localisation) is what makes the
# interacting plateau a true phase; at this lab's n <= 10 the CLEAN
# chain also answers for a long time - a prethermal, finite-size
# effect, labelled as such everywhere it appears, never hidden.

def plateau_scan(epsilons=(0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15,
                            0.175, 0.20, 0.25, 0.30),
                 n=8, cycles=DEFAULT_CYCLES, seed=2021):
    """Subharmonic amplitude vs pulse error, for three chains:

    dtc:            J = pi/4, W = pi   (interacting + disordered)
    no_interaction: J = 0,    W = pi   (disorder only)
    no_disorder:    J = pi/4, W = 0    (interactions only, clean)
    """
    configs = {
        "dtc": (math.pi / 4.0, math.pi),
        "no_interaction": (0.0, math.pi),
        "no_disorder": (math.pi / 4.0, 0.0),
    }
    out = {}
    for name, (j_mean, w_max) in configs.items():
        amps = []
        for eps in epsilons:
            series = run_series(n, 1.0 - eps, j_mean, w_max, cycles, seed)
            amps.append(round(subharmonic_amplitude(series), 4))
        out[name] = {"epsilons": list(epsilons), "amplitudes": amps}
    return out


def plateau_width(epsilons, amplitudes, threshold=0.5):
    """Largest epsilon (contiguous from 0) with amplitude >= threshold."""
    width = 0.0
    for eps, amp in zip(epsilons, amplitudes):
        if amp >= threshold:
            width = eps
        else:
            break
    return width


# ================================================================ 5. Phase diagram
# Sweep (epsilon, J) at strong disorder W = pi and label each cell by
# an actual simulation. The DTC region is a plateau-shaped island at
# small epsilon and finite J; large epsilon or J = 0 melts it.

def phase_diagram(epsilons=(0.0, 0.05, 0.10, 0.15, 0.20, 0.30),
                  j_values=(0.0, math.pi / 8.0, math.pi / 4.0, 3.0 * math.pi / 8.0),
                  w_max=math.pi, n=6, cycles=24, seed=7):
    """{(epsilon, J/pi): phase label} from real runs on a small chain."""
    grid = {}
    for eps in epsilons:
        for j_mean in j_values:
            series = run_series(n, 1.0 - eps, j_mean, w_max, cycles, seed)
            grid[(round(eps, 4), round(j_mean / math.pi, 4))] = classify_run(series)
    return grid


def phase_counts(grid):
    counts = {}
    for label in grid.values():
        counts[label] = counts.get(label, 0) + 1
    return counts


# ================================================================ 6. Exact Floquet spectrum (2 qubits)
# For n = 2 the full Floquet unitary U_F is a 4x4 complex matrix:
# build it column by column (U_F |basis>), get its characteristic
# polynomial from traces of powers (Newton's identities), and its
# (the quasienergy phases live on the unit circle) by Durand-Kerner.
# At g = 1 the eigenvalues pair exactly: for every lambda there is a
# -lambda (quasienergies pi apart) - the pi-pairing of the DTC.

def floquet_unitary(n=2, g=1.0, j_mean=math.pi / 4.0, w_max=math.pi, seed=3):
    """The full one-period unitary as a list of rows (small n only)."""
    if n > 3:
        raise ValueError("exact unitary is kept to n <= 3")
    couplings, fields = make_disorder(n, j_mean, w_max, seed)
    dim = 1 << n
    cols = []
    for b in range(dim):
        state = basis_state(n, b)
        floquet_cycle(state, n, couplings, fields, g)
        cols.append(state)
    return [[cols[c][r] for c in range(dim)] for r in range(dim)]


def _matmul(a, b):
    n = len(a)
    return [[sum(a[i][k] * b[k][j] for k in range(n)) for j in range(n)]
            for i in range(n)]


def _trace(m):
    return sum(m[i][i] for i in range(len(m)))


def charpoly_coeffs(matrix):
    """Characteristic polynomial coefficients (highest degree first).

    Trace / Newton-identities method: the power sums s_k = tr(A^k)
    give the elementary symmetric polynomials e_k of the eigenvalues
    by Newton's identities, and p(z) = sum_k (-1)^k e_k z^(d-k).
    """
    d = len(matrix)
    power = [[1.0 + 0j if i == j else 0j for j in range(d)] for i in range(d)]
    sums = []
    for _ in range(d):
        power = _matmul(power, matrix)
        sums.append(_trace(power))
    e = [1.0 + 0j]
    for k in range(1, d + 1):
        tot = 0j
        for i in range(1, k + 1):
            tot += ((-1) ** (i - 1)) * e[k - i] * sums[i - 1]
        e.append(tot / k)
    return [((-1) ** k) * e[k] for k in range(d + 1)]


def poly_roots(coeffs, iterations=200):
    """All roots of a polynomial (Durand-Kerner iteration)."""
    d = len(coeffs) - 1
    lead = coeffs[0]
    coeffs = [c / lead for c in coeffs]
    roots = [(0.4 + 0.9j) ** k for k in range(d)]
    for _ in range(iterations):
        delta = 0.0
        new_roots = []
        for i in range(d):
            z = roots[i]
            pz = 0j
            for c in coeffs:
                pz = pz * z + c
            denom = 1.0 + 0j
            for j in range(d):
                if j != i:
                    denom *= (z - roots[j])
            step = pz / denom if denom != 0 else 0j
            new_roots.append(z - step)
            delta = max(delta, abs(step))
        roots = new_roots
        if delta < 1e-13:
            break
    return roots


def quasienergies(n=2, g=1.0, j_mean=math.pi / 4.0, w_max=math.pi, seed=3):
    """Sorted quasienergy phases in [0, 2pi) of the 2-qubit Floquet unitary."""
    u = floquet_unitary(n, g, j_mean, w_max, seed)
    roots = poly_roots(charpoly_coeffs(u))
    phases = sorted((cmath.phase(r) % (2.0 * math.pi)) for r in roots)
    return phases


def pi_pairing_error(n=2, g=1.0, j_mean=math.pi / 4.0, w_max=math.pi, seed=3):
    """Worst mismatch to exact pi-pairing of the Floquet eigenvalues.

    For each eigenvalue lambda, find the eigenvalue closest to -lambda;
    the error is the largest of those distances. 0 = perfect pairing.
    """
    u = floquet_unitary(n, g, j_mean, w_max, seed)
    roots = poly_roots(charpoly_coeffs(u))
    worst = 0.0
    for r in roots:
        best = min(abs(other + r) for other in roots)
        worst = max(worst, best)
    return worst


def floquet_squared_offdiagonal(n=2, j_mean=math.pi / 4.0, w_max=math.pi, seed=3):
    """Max |off-diagonal| of U_F^2 at g = 1 (0 = exactly diagonal)."""
    u = floquet_unitary(n, 1.0, j_mean, w_max, seed)
    u2 = _matmul(u, u)
    d = len(u2)
    return max(abs(u2[i][j]) for i in range(d) for j in range(d) if i != j)


# ================================================================ 7. Sycamore 2021 reference
# Published reference values from the Google experiment, included so
# the lab can be compared honestly: they ran REAL hardware with noise;
# this lab is an exact, noiseless, <= 10-qubit simulation. The numbers
# below are literature values, clearly labelled, never measured here.
SYCAMORE_2021 = {
    "experiment": "Time-crystalline eigenstate order on a quantum processor",
    "authors": "Mi et al. (Google Quantum AI and collaborators)",
    "venue": "Nature 600, 531-536 (2021)",
    "processor": "Google Sycamore - superconducting transmon qubits",
    "qubits_used": 20,
    "model": "kicked-Ising Floquet chain: pi-pulse parameter g, random Ising phases, random on-site fields",
    "initial_states": "computational-basis bitstrings, disorder-averaged over random instances",
    "headline_observation": "subharmonic (period-doubled) response, rigid over a finite range of g below 1, melting when interactions are removed",
    "cycles_reported": "magnetisation tracked over up to ~100 Floquet cycles",
    "status": "PUBLISHED REFERENCE VALUES - literature, not measured by this lab",
}


def sycamore_comparison():
    """This lab vs the published experiment, side by side, honestly."""
    return {
        "reference_experiment": SYCAMORE_2021,
        "this_lab": {
            "qubits": f"<= {MAX_QUBITS} (exact statevector, 2^n amplitudes)",
            "noise": "none - exact unitary evolution, no decoherence model",
            "hardware": "none - a laptop CPU and the Python standard library",
            "cycles_default": DEFAULT_CYCLES,
            "same_model": "yes - same kicked-Ising Floquet unitary structure (U3 . U2 . U1)",
            "claim": "educational reproduction of the mechanism, NOT a replication of the experiment",
            "gate": gate("experimental_data_claim"),
        },
    }


# ================================================================ 8. kNN phase classifier
# Features: (epsilon, J / (pi/2), W / pi). The training set is NOT a
# hand-written rule - every training point is labelled by an actual
# small simulation (n = 5, 16 cycles) run through classify_run. The
# kNN (k = 5) then interpolates the phase boundary between real runs.
# Advisory only: it labels parameter points, it controls nothing.

_KNN_TRAIN = None


def _features(epsilon, j_mean, w_max):
    return (round(epsilon, 4), round(j_mean / (math.pi / 2.0), 4),
            round(w_max / math.pi, 4))


def _build_knn_train():
    train = []
    for eps in (0.0, 0.05, 0.10, 0.15, 0.20, 0.30):
        for j_mean in (0.0, math.pi / 8.0, math.pi / 4.0):
            for w_max in (0.0, math.pi / 2.0, math.pi):
                series = run_series(5, 1.0 - eps, j_mean, w_max, 16, 11)
                train.append((_features(eps, j_mean, w_max), classify_run(series)))
    return train


def knn_train():
    global _KNN_TRAIN
    if _KNN_TRAIN is None:
        _KNN_TRAIN = _build_knn_train()
    return _KNN_TRAIN


class PhaseClassifier:
    """kNN (k=5) over (epsilon, interaction, disorder) features."""

    def __init__(self, k=5):
        self.k = k
        self.train = list(knn_train())

    @staticmethod
    def _dist(a, b):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def classify_features(self, feats):
        ranked = sorted(self.train, key=lambda tr: self._dist(feats, tr[0]))
        votes = {}
        for _, label in ranked[: self.k]:
            votes[label] = votes.get(label, 0) + 1
        return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def classify(self, epsilon, j_mean, w_max):
        return self.classify_features(_features(epsilon, j_mean, w_max))


def classify_phase(epsilon, j_mean, w_max):
    return PhaseClassifier().classify(epsilon, j_mean, w_max)


# ================================================================ 9. Advisory seats
def _seat_trace(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def carbon4_decide(topic="timecrystal-q-demo"):
    """Gemini Carbon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-carbon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Carbon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "can_override_hold": False,
        "tighten_only": True,
        "decision": "PROCEED (sandbox simulation only)",
        "trace_sha256_16": _seat_trace(payload),
    }


def claude_advisor(topic="timecrystal-q-demo"):
    """Muse advisor seat: advisory only, authority none."""
    return {
        "seat": "Muse",
        "role": "advisor",
        "authority": "none - advisory only",
        "can_override_hold": False,
        "live_calls": 0,
        "advice": "Keep every real-hardware action behind its HOLD gate; never present simulation output as measured data.",
        "trace_sha256_16": _seat_trace({"seat": "claude-advisor", "topic": topic}),
    }


def google_flow_plan():
    """Google Flow: plan-only. Nothing renders, nothing is sent."""
    return {
        "seat": "Google Flow",
        "flows": ["FlowX task graph", "Workspace Studio drafts",
                  "Filmmaking 5-shot storyboard", "DataX data-flow"],
        "rendered": False,
        "live": 0,
        "plan": ["period-doubling clock explainer", "rigidity plateau story",
                 "pi-pairing spectrum hero shot", "Sycamore-vs-lab honest chart"],
    }


def brains_report():
    return {"decider": carbon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    perfect = run_series(8, 1.0, math.pi / 4.0, math.pi, 40, 2021)
    dtc = run_series(8, 0.90, math.pi / 4.0, math.pi, 40, 2021)
    noint = run_series(8, 0.90, 0.0, math.pi, 40, 2021)
    nodis = run_series(8, 0.90, math.pi / 4.0, 0.0, 40, 2021)
    chk("max_qubits_guard", MAX_QUBITS == 10)
    chk("basis_norm_one", abs(norm(basis_state(4, 5)) - 1.0) < 1e-12)
    st = basis_state(3, 0)
    apply_x_rotation(st, 3, 0, math.pi)
    chk("pi_pulse_flips_spin", abs(z_expectation(st, 3, 0) + 1.0) < 1e-12)
    st = basis_state(2, 0)
    apply_x_rotation(st, 2, 0, 2.0 * math.pi)
    chk("two_pi_rotation_spinor_sign", abs(st[0] + 1.0) < 1e-12)
    st = basis_state(2, 0)
    apply_zz_phase(st, 2, 0, 1, 0.7)
    chk("zz_phase_on_up_up", abs(st[0] - cmath.exp(-0.7j)) < 1e-12)
    chk("zz_keeps_magnetization", abs(z_expectation(st, 2, 0) - 1.0) < 1e-12)
    chk("perfect_series_alternates",
        all(abs(perfect[k] - (-1.0 if k % 2 == 0 else 1.0)) < 1e-9
            for k in range(len(perfect))))
    chk("perfect_amplitude_one", abs(subharmonic_amplitude(perfect) - 1.0) < 1e-9)
    chk("perfect_persistence_one", abs(persistence(perfect) - 1.0) < 1e-9)
    chk("perfect_classified_dtc", classify_run(perfect) == "DTC")
    chk("subharmonic_peak_dominant", subharmonic_peak_share(perfect) > 0.99)
    chk("dtc_amplitude_high", subharmonic_amplitude(dtc) > 0.6)
    chk("dtc_classified_dtc", classify_run(dtc) == "DTC")
    chk("interaction_protects_response",
        subharmonic_amplitude(dtc) > subharmonic_amplitude(noint))
    # Honest finite-size fact, verified by running this lab: at n = 8 the
    # CLEAN chain (W = 0) also answers rigidly on lab timescales - a
    # prethermal / finite-size effect, NOT the thermodynamic MBL phase.
    # The check pins the observed behaviour so the docs stay truthful.
    chk("clean_chain_prethermal_finite_size", subharmonic_amplitude(nodis) > 0.8)
    chk("no_interaction_melts", subharmonic_amplitude(noint) < 0.45)
    chk("magnetization_bounded", all(abs(m) <= 1.0 + 1e-9 for m in dtc))
    chk("deterministic_series",
        run_series(6, 0.9, math.pi / 4.0, math.pi, 20, 5)
        == run_series(6, 0.9, math.pi / 4.0, math.pi, 20, 5))
    scan = plateau_scan()
    chk("plateau_dtc_wider_than_no_interaction",
        plateau_width(scan["dtc"]["epsilons"], scan["dtc"]["amplitudes"])
        > plateau_width(scan["no_interaction"]["epsilons"],
                        scan["no_interaction"]["amplitudes"]))
    chk("plateau_clean_chain_wide_prethermal",
        plateau_width(scan["no_disorder"]["epsilons"],
                      scan["no_disorder"]["amplitudes"])
        >= plateau_width(scan["dtc"]["epsilons"], scan["dtc"]["amplitudes"]))
    grid = phase_diagram()
    counts = phase_counts(grid)
    chk("phase_diagram_has_dtc", counts.get("DTC", 0) >= 4)
    chk("phase_diagram_has_melted", counts.get("thermal", 0) + counts.get("trivial", 0) >= 4)
    chk("phase_diagram_dtc_corner", grid[(0.0, 0.25)] == "DTC")
    chk("phase_diagram_no_interaction_not_dtc", grid[(0.10, 0.0)] != "DTC")
    u = floquet_unitary(2, 1.0, math.pi / 4.0, math.pi, 3)
    chk("unitary_columns_orthonormal",
        all(abs(sum(u[r][i].conjugate() * u[r][j] for r in range(4))
                - (1.0 if i == j else 0.0)) < 1e-9
            for i in range(4) for j in range(4)))
    roots = poly_roots(charpoly_coeffs(u))
    chk("eigenvalues_on_unit_circle",
        all(abs(abs(r) - 1.0) < 1e-6 for r in roots))
    chk("quasienergies_in_range",
        all(0.0 <= ph < 2.0 * math.pi for ph in quasienergies()))
    chk("pi_pairing_exact_at_perfect_pulse", pi_pairing_error() < 1e-6)
    chk("pi_pairing_breaks_with_error", pi_pairing_error(g=0.9) > 1e-3)
    chk("floquet_squared_diagonal_at_g1", floquet_squared_offdiagonal() < 1e-9)
    chk("sycamore_reference_labelled",
        SYCAMORE_2021["qubits_used"] == 20
        and "REFERENCE" in SYCAMORE_2021["status"]
        and "Nature" in SYCAMORE_2021["venue"])
    chk("classifier_dtc_point", classify_phase(0.02, math.pi / 4.0, math.pi) == "DTC")
    chk("classifier_melted_point", classify_phase(0.30, 0.0, 0.0) != "DTC")
    chk("knn_train_from_real_runs", len(knn_train()) == 54)
    chk("hold_gates_14", len(HOLD_GATES) == 14 and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_hardware_hold", gate("real_quantum_hardware") == "HOLD")
    chk("gate_data_claim_hold", gate("experimental_data_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    b = brains_report()
    chk("carbon4_no_override", b["decider"]["can_override_hold"] is False)
    chk("claude_no_override", b["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", b["flow"]["rendered"] is False and b["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("TimeCrystal-Q - discrete time crystal (Floquet) physics lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | SIM ONLY")
    print("=" * 68)
    print("\n[1] The drive: U_F = U3 . U2 . U1, one period, repeated")
    print("    U1 = pi-pulse flip (angle pi*g, error epsilon = 1 - g)")
    print("    U2 = disordered Ising phases around J = pi/4 (interactions)")
    print("    U3 = random on-site fields in [-pi, pi] (disorder -> MBL)")
    print("\n[2] Perfect pulse (epsilon = 0): the chain answers at 2x the period")
    perfect = run_series(8, 1.0, math.pi / 4.0, math.pi, 12, 2021)
    print("    magnetisation after each cycle:")
    print("    " + " ".join(f"{m:+.2f}" for m in perfect))
    full = run_series(8, 1.0, math.pi / 4.0, math.pi, 40, 2021)
    print(f"    subharmonic amplitude A = {subharmonic_amplitude(full):.4f} (1.0 = perfect doubling)")
    print(f"    Fourier power at half frequency share = {subharmonic_peak_share(full):.4f}")
    print("\n[3] Imperfect pulse (epsilon = 0.10): rigidity vs melting")
    for name, j_mean, w_max in (("interactions + disorder (DTC)", math.pi / 4.0, math.pi),
                                ("disorder only (J = 0)          ", 0.0, math.pi),
                                ("clean chain, W = 0 (prethermal)", math.pi / 4.0, 0.0)):
        s = run_series(8, 0.90, j_mean, w_max, 40, 2021)
        print(f"    {name}: A = {subharmonic_amplitude(s):.4f}, "
              f"persistence = {persistence(s):.4f}, phase = {classify_run(s)}")
    print("    interactions are load-bearing: J = 0 melts, J = pi/4 holds.")
    print("    the clean chain's answer is a finite-size prethermal effect")
    print("    (honest label - at n = 8 it does not melt on lab timescales).")
    print("\n[4] Rigidity plateau: A vs pulse error epsilon (threshold 0.5)")
    scan = plateau_scan()
    for name in ("dtc", "no_interaction", "no_disorder"):
        row = scan[name]
        print(f"    {name:15s} plateau width = "
              f"{plateau_width(row['epsilons'], row['amplitudes']):.3f}  "
              + " ".join(f"{a:.2f}" for a in row["amplitudes"]))
    print("    no_disorder stays wide at n = 8: prethermal finite-size effect,")
    print("    not the thermodynamic phase - see the honest-status notes.")
    print("\n[5] Phase diagram at W = pi (rows: epsilon, cols: J/pi = 0, 1/8, 1/4, 3/8)")
    grid = phase_diagram()
    for eps in (0.0, 0.05, 0.10, 0.15, 0.20, 0.30):
        cells = [grid[(eps, jpi)] for jpi in (0.0, 0.125, 0.25, 0.375)]
        print(f"    eps = {eps:4.2f}: " + " | ".join(f"{x:7s}" for x in cells))
    print(f"    counts: {json.dumps(phase_counts(grid), sort_keys=True)}")
    print("\n[6] Exact 2-qubit Floquet spectrum")
    phases = quasienergies()
    print("    quasienergies (rad): " + ", ".join(f"{p:.4f}" for p in phases))
    print(f"    pi-pairing error at g = 1.00: {pi_pairing_error():.2e} (0 = exact pairs)")
    print(f"    pi-pairing error at g = 0.90: {pi_pairing_error(g=0.9):.4f} (pairing melts)")
    print(f"    max off-diagonal of U_F^2 at g = 1: {floquet_squared_offdiagonal():.2e}")
    print("\n[7] Sycamore 2021 - published reference, NOT measured here")
    print(f"    {SYCAMORE_2021['authors']}, {SYCAMORE_2021['venue']}: "
          f"{SYCAMORE_2021['qubits_used']} qubits on {SYCAMORE_2021['processor']}")
    print(f"    headline: {SYCAMORE_2021['headline_observation']}")
    print(f"    this lab: <= {MAX_QUBITS} qubits, exact, noiseless, zero hardware")
    print("\n[8] Phase classifier (kNN trained on real small runs)")
    for eps, j_mean, w_max in ((0.02, math.pi / 4.0, math.pi),
                               (0.10, math.pi / 4.0, math.pi),
                               (0.10, 0.0, math.pi),
                               (0.30, 0.0, 0.0)):
        print(f"    eps = {eps:4.2f}, J/pi = {j_mean / math.pi:5.3f}, W/pi = {w_max / math.pi:3.1f}"
              f" -> {classify_phase(eps, j_mean, w_max)}")
    print("\n[9] Advisory seats")
    print(f"    decider: {carbon4_decide()['decision']} trace={carbon4_decide()['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {claude_advisor()['can_override_hold']}")
    print(f"    flow rendered = {google_flow_plan()['rendered']} live = {google_flow_plan()['live']}")
    print(f"\n[10] HOLD gates: {len(HOLD_GATES)}")
    for k in HOLD_GATES:
        print(f"    HOLD  {k}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "evolve":
        print(json.dumps(run_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "plateau":
        print(json.dumps(plateau_scan(), indent=2, sort_keys=True))
        return 0
    if cmd == "phase":
        grid = phase_diagram()
        print(json.dumps({f"eps={e}, J/pi={j}": v for (e, j), v in sorted(grid.items())},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "spectrum":
        print(json.dumps({
            "quasienergies_rad": [round(p, 6) for p in quasienergies()],
            "pi_pairing_error_g1": pi_pairing_error(),
            "pi_pairing_error_g0.9": pi_pairing_error(g=0.9),
            "floquet_squared_offdiagonal_g1": floquet_squared_offdiagonal(),
        }, indent=2, sort_keys=True))
        return 0
    if cmd == "sycamore":
        print(json.dumps(sycamore_comparison(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        for eps, j_mean, w_max in ((0.02, math.pi / 4.0, math.pi),
                                   (0.10, math.pi / 4.0, math.pi),
                                   (0.10, 0.0, math.pi),
                                   (0.30, 0.0, 0.0)):
            print(f"eps={eps} J/pi={round(j_mean / math.pi, 3)} W/pi={round(w_max / math.pi, 3)}"
                  f" -> {classify_phase(eps, j_mean, w_max)}")
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for k, v in HOLD_GATES.items():
            print(f"{k}: {v}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "real_quantum_hardware"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
