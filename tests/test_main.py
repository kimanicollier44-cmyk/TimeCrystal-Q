import cmath, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as tc

PI = math.pi


def test_max_qubits(): assert tc.MAX_QUBITS == 10
def test_basis_norm(): assert abs(tc.norm(tc.basis_state(4, 5)) - 1.0) < 1e-12
def test_basis_rejects_too_many():
    try:
        tc.basis_state(11); assert False
    except ValueError:
        pass
def test_pi_pulse_flips_spin():
    st = tc.basis_state(3, 0); tc.apply_x_rotation(st, 3, 0, PI)
    assert abs(tc.z_expectation(st, 3, 0) + 1.0) < 1e-12
def test_half_pulse_equal_superposition():
    st = tc.basis_state(2, 0); tc.apply_x_rotation(st, 2, 0, PI / 2.0)
    assert abs(tc.z_expectation(st, 2, 0)) < 1e-12
def test_two_pi_spinor_sign():
    st = tc.basis_state(2, 0); tc.apply_x_rotation(st, 2, 0, 2.0 * PI)
    assert abs(st[0] + 1.0) < 1e-12
def test_zz_phase_up_up():
    st = tc.basis_state(2, 0); tc.apply_zz_phase(st, 2, 0, 1, 0.7)
    assert abs(st[0] - cmath.exp(-0.7j)) < 1e-12
def test_zz_phase_up_down():
    st = tc.basis_state(2, 2); tc.apply_zz_phase(st, 2, 0, 1, 0.7)
    assert abs(st[2] - cmath.exp(0.7j)) < 1e-12
def test_zz_keeps_magnetization():
    st = tc.basis_state(2, 0); tc.apply_zz_phase(st, 2, 0, 1, 0.7)
    assert abs(tc.z_expectation(st, 2, 0) - 1.0) < 1e-12
def test_z_field_phase():
    st = tc.basis_state(2, 0); tc.apply_z_field(st, 2, 0, 0.5)
    assert abs(st[0] - cmath.exp(-0.5j)) < 1e-12
def test_disorder_deterministic():
    a = tc.make_disorder(6, PI / 4.0, PI, 42); b = tc.make_disorder(6, PI / 4.0, PI, 42)
    assert a == b
def test_disorder_ranges():
    couplings, fields = tc.make_disorder(8, PI / 4.0, PI, 1)
    assert len(couplings) == 7 and len(fields) == 8
    assert all(0.6 * PI / 4.0 <= p <= 1.4 * PI / 4.0 for p in couplings)
    assert all(-PI <= h <= PI for h in fields)
def test_disorder_zero_interaction():
    couplings, _ = tc.make_disorder(5, 0.0, PI, 3)
    assert all(p == 0.0 for p in couplings)
def test_perfect_series_alternates():
    s = tc.run_series(8, 1.0, PI / 4.0, PI, 12, 2021)
    assert all(abs(s[k] - (-1.0 if k % 2 == 0 else 1.0)) < 1e-9 for k in range(12))
def test_perfect_amplitude_one():
    s = tc.run_series(8, 1.0, PI / 4.0, PI, 40, 2021)
    assert abs(tc.subharmonic_amplitude(s) - 1.0) < 1e-9
def test_perfect_persistence_one():
    s = tc.run_series(8, 1.0, PI / 4.0, PI, 40, 2021)
    assert abs(tc.persistence(s) - 1.0) < 1e-9
def test_perfect_classified_dtc():
    s = tc.run_series(8, 1.0, PI / 4.0, PI, 40, 2021)
    assert tc.classify_run(s) == "DTC"
def test_subharmonic_peak_dominant():
    s = tc.run_series(8, 1.0, PI / 4.0, PI, 40, 2021)
    assert tc.subharmonic_peak_share(s) > 0.99
def test_dft_power_at_half_frequency():
    s = [(-1.0) ** k for k in range(1, 41)]
    assert abs(tc.dft_power(s, 0.5) - 1.0) < 1e-9
    assert tc.dft_power(s, 0.25) < 1e-9
def test_amplitude_zero_series(): assert tc.subharmonic_amplitude([]) == 0.0
def test_dtc_amplitude_high():
    s = tc.run_series(8, 0.90, PI / 4.0, PI, 40, 2021)
    assert tc.subharmonic_amplitude(s) > 0.6
def test_dtc_classified_dtc():
    s = tc.run_series(8, 0.90, PI / 4.0, PI, 40, 2021)
    assert tc.classify_run(s) == "DTC"
def test_interaction_protects():
    dtc = tc.run_series(8, 0.90, PI / 4.0, PI, 40, 2021)
    noint = tc.run_series(8, 0.90, 0.0, PI, 40, 2021)
    assert tc.subharmonic_amplitude(dtc) > tc.subharmonic_amplitude(noint)
def test_no_interaction_melts():
    s = tc.run_series(8, 0.90, 0.0, PI, 40, 2021)
    assert tc.subharmonic_amplitude(s) < 0.45
def test_clean_chain_prethermal_finite_size():
    # Honest finite-size fact at n = 8: the clean chain also answers
    # rigidly on lab timescales (prethermal), it does not melt.
    s = tc.run_series(8, 0.90, PI / 4.0, 0.0, 40, 2021)
    assert tc.subharmonic_amplitude(s) > 0.8
def test_magnetization_bounded():
    s = tc.run_series(8, 0.90, PI / 4.0, PI, 40, 2021)
    assert all(abs(m) <= 1.0 + 1e-9 for m in s)
def test_series_deterministic():
    a = tc.run_series(6, 0.9, PI / 4.0, PI, 20, 5)
    b = tc.run_series(6, 0.9, PI / 4.0, PI, 20, 5)
    assert a == b
def test_epsilon_of(): assert abs(tc.epsilon_of(0.9) - 0.1) < 1e-12
def test_classify_thermal_flat_series():
    assert tc.classify_run([0.01, -0.01] * 20) == "thermal"
def test_run_report_shape():
    r = tc.run_report()
    assert r["phase"] == "DTC" and r["n_qubits"] == 8 and r["gate"] == "PROCEED"
def test_plateau_widths():
    scan = tc.plateau_scan()
    w_dtc = tc.plateau_width(scan["dtc"]["epsilons"], scan["dtc"]["amplitudes"])
    w_noint = tc.plateau_width(scan["no_interaction"]["epsilons"],
                               scan["no_interaction"]["amplitudes"])
    assert w_dtc > w_noint
def test_plateau_width_helper():
    assert tc.plateau_width((0.0, 0.1, 0.2), (0.9, 0.6, 0.4)) == 0.1
    assert tc.plateau_width((0.0, 0.1), (0.4, 0.9)) == 0.0
def test_phase_diagram_corners():
    grid = tc.phase_diagram()
    assert grid[(0.0, 0.25)] == "DTC"
    assert grid[(0.10, 0.0)] != "DTC"
def test_phase_diagram_counts():
    counts = tc.phase_counts(tc.phase_diagram())
    assert counts.get("DTC", 0) >= 4
    assert counts.get("thermal", 0) + counts.get("trivial", 0) >= 4
def test_unitary_orthonormal():
    u = tc.floquet_unitary(2, 1.0, PI / 4.0, PI, 3)
    for i in range(4):
        for j in range(4):
            v = sum(u[r][i].conjugate() * u[r][j] for r in range(4))
            assert abs(v - (1.0 if i == j else 0.0)) < 1e-9
def test_charpoly_of_identity():
    ident = [[1.0 + 0j if i == j else 0j for j in range(3)] for i in range(3)]
    coeffs = tc.charpoly_coeffs(ident)
    assert all(abs(coeffs[k] - v) < 1e-9 for k, v in enumerate((1, -3, 3, -1)))
def test_eigenvalues_on_unit_circle():
    roots = tc.poly_roots(tc.charpoly_coeffs(tc.floquet_unitary(2, 1.0, PI / 4.0, PI, 3)))
    assert all(abs(abs(r) - 1.0) < 1e-6 for r in roots)
def test_quasienergies_range():
    assert all(0.0 <= p < 2.0 * PI for p in tc.quasienergies())
def test_pi_pairing_exact(): assert tc.pi_pairing_error() < 1e-6
def test_pi_pairing_breaks(): assert tc.pi_pairing_error(g=0.9) > 1e-3
def test_floquet_squared_diagonal(): assert tc.floquet_squared_offdiagonal() < 1e-9
def test_sycamore_reference():
    assert tc.SYCAMORE_2021["qubits_used"] == 20
    assert "Nature" in tc.SYCAMORE_2021["venue"]
    assert "REFERENCE" in tc.SYCAMORE_2021["status"]
def test_sycamore_comparison_honest():
    comp = tc.sycamore_comparison()
    assert comp["this_lab"]["gate"] == "HOLD"
    assert "NOT a replication" in comp["this_lab"]["claim"]
def test_classifier_dtc_point(): assert tc.classify_phase(0.02, PI / 4.0, PI) == "DTC"
def test_classifier_melted_point(): assert tc.classify_phase(0.30, 0.0, 0.0) != "DTC"
def test_knn_train_size(): assert len(tc.knn_train()) == 54
def test_knn_train_labels_valid():
    assert all(label in ("DTC", "thermal", "trivial") for _, label in tc.knn_train())
def test_holds_count(): assert len(tc.HOLD_GATES) == 14
def test_holds_all_hold(): assert all(v.startswith("HOLD") for v in tc.HOLD_GATES.values())
def test_gate():
    assert tc.gate("real_quantum_hardware") == "HOLD"
    assert tc.gate("experimental_data_claim") == "HOLD"
    assert tc.gate("run_simulation") == "PROCEED"
def test_hold_demo_exit_code(): assert tc.main(["hold-demo", "qpu_job_submission_live"]) == 2
def test_hold_demo_ungated(): assert tc.main(["hold-demo", "run_simulation"]) == 0
def test_carbon4():
    d = tc.carbon4_decide()
    assert d["can_override_hold"] is False and d["live_calls"] == 0 and len(d["trace_sha256_16"]) == 16
    assert d["pipeline"] == ["MAP", "MODEL", "STRESS", "DECIDE"] and d["tighten_only"] is True
def test_claude(): assert tc.claude_advisor()["can_override_hold"] is False
def test_flow():
    f = tc.google_flow_plan(); assert f["rendered"] is False and f["live"] == 0
def test_checks_all_pass():
    checks = tc.run_checks(); assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]
def test_checks_count(): assert len(tc.run_checks()) == 41
def test_demo_exit_zero(capsys):
    assert tc.main([]) == 0
    out = capsys.readouterr().out
    assert "CHECKS 41/41" in out and "VERDICT PROCEED" in out
