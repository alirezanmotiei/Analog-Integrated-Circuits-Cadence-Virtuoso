#!/usr/bin/env python3
"""Two-stage Miller-compensated CMOS operational amplifier benchmark.

Matches the TSMC 180nm (L = 360 nm) hand-design derivation documented in
reports/CA3_Final_Project_TwoStage_Miller_CMFB_OpAmp.pdf and evaluates all
specifications programmatically before reporting pass/fail status.

Author: Alireza Najafi Motiei (University of Tehran)
"""

import math
import sys


def analyze_two_stage_opamp() -> bool:
    """Compute small-signal op-amp metrics and verify against CA3 targets."""
    # -------------------------------------------------------------------------
    # 1. Process & Hand-Design Parameters (TSMC 180nm CMOS, L = 360 nm)
    # -------------------------------------------------------------------------
    vdd = 1.8            # Supply voltage (V)
    temp_c = 27.0        # Nominal temperature (C)

    # Bias currents (CA3 Section 1: I0=100uA, ID1=300uA, ID2=ID3=150uA, ID6=ID7=320.45uA)
    i0 = 100.0e-6        # Reference mirror branch current (A)
    id1 = 300.0e-6       # Differential pair tail current (A)
    id6 = 320.45e-6      # Second-stage output branch current (A)
    total_current = i0 + id1 + id6

    # Small-signal transconductances (CA3 hand derivation)
    gm_in = 2.67e-3      # Input pair M2/M3 transconductance (S)
    gm_out = 6.41e-3     # Output driver M6/M7 transconductance (S)

    # Effective channel-length-modulated output resistances (L = 360 nm estimate)
    # Yielding nominal Spectre-matched open-loop DC gain (~64.5-64.8 dB)
    ro_in = 30.0e3       # Input pair half-circuit output resistance (Ohm)
    ro_load1 = 30.0e3    # Stage-1 active load output resistance (Ohm)
    ro_out_n = 13.5e3    # Stage-2 NMOS output resistance (Ohm)
    ro_out_p = 13.5e3    # Stage-2 PMOS output resistance (Ohm)

    # Miller compensation & capacitive load (CA3 Table 1-1)
    cc = 1.213e-12       # Miller compensation capacitor (F)
    cl = 3.0e-12         # Output load capacitance (F)
    rz = 343.5           # Nulling resistor pushing RHP zero to LHP (-2 * GBW) (Ohm)

    # -------------------------------------------------------------------------
    # 2. Stage-by-Stage Small-Signal Derivations
    # -------------------------------------------------------------------------
    rout1 = (ro_in * ro_load1) / (ro_in + ro_load1)
    av1 = gm_in * rout1
    av1_db = 20.0 * math.log10(av1)

    rout2 = (ro_out_n * ro_out_p) / (ro_out_n + ro_out_p)
    av2 = gm_out * rout2
    av2_db = 20.0 * math.log10(av2)

    av_total = av1 * av2
    av_total_db = 20.0 * math.log10(av_total)

    # -------------------------------------------------------------------------
    # 3. Frequency Response, Pole-Zero Locations & Phase Margin
    # -------------------------------------------------------------------------
    c_eff = cc * (1.0 + av2)
    wp1 = 1.0 / (rout1 * c_eff)
    fp1 = wp1 / (2.0 * math.pi)

    # Unity-gain bandwidth (assumed targeted >= 300 MHz, designed at 350 MHz)
    w_gbw = gm_in / cc
    f_gbw = w_gbw / (2.0 * math.pi)

    # Second non-dominant pole at output node
    wp2 = gm_out / cl
    fp2 = wp2 / (2.0 * math.pi)

    # Zero location with nulling resistor Rz:
    # wz = 1 / (Cc * (1/gm_out - Rz)); negative wz indicates LHP zero when Rz > 1/gm_out.
    r_diff = (1.0 / gm_out) - rz
    if abs(r_diff) > 1e-6:
        wz = 1.0 / (cc * r_diff)
        fz = wz / (2.0 * math.pi)
    else:
        fz = float("inf")

    # Phase contribution: LHP zero (fz < 0) adds positive phase lead atan(f_gbw / |fz|);
    # RHP zero (fz > 0) subtracts phase atan(f_gbw / fz).
    phase_lag_p2_deg = math.degrees(math.atan(f_gbw / fp2))
    if math.isinf(fz):
        phase_zero_deg = 0.0
    elif fz < 0.0:
        phase_zero_deg = math.degrees(math.atan(f_gbw / abs(fz)))
    else:
        phase_zero_deg = -math.degrees(math.atan(f_gbw / fz))

    pm_deg = 90.0 - phase_lag_p2_deg + phase_zero_deg

    # Slew rate & voltage headroom (CA3 Table 1-1: Vov_tail=0.1V, Vov_in=0.15V, Vov_out=0.1V)
    slew_rate_v_us = (id1 / cc) * 1e-6
    vth_n = 0.50
    vth_p = 0.60
    vov_tail = 0.10
    vov_in = 0.15
    vov6 = 0.10
    vov7 = 0.10

    # PMOS-input stage ICMR bounds (CA3 Page 3)
    icmr_min = max(0.0, vth_n + vov_tail - vth_p)
    icmr_max = vdd - vth_p - vov_in - vov_tail
    out_swing_min = vov7
    out_swing_max = vdd - vov6
    p_diss_mw = total_current * vdd * 1e3

    # -------------------------------------------------------------------------
    # 4. Programmatic Specification Verification
    # -------------------------------------------------------------------------
    specs = [
        ("Differential DC Gain (Av0)", f"{av_total_db:.2f} dB ({av_total:.1f} V/V)", ">= 64.0 dB", av_total_db >= 64.0),
        ("Unity-Gain Bandwidth (UGBW)", f"{f_gbw/1e6:.2f} MHz", ">= 300.0 MHz", f_gbw / 1e6 >= 300.0),
        ("Non-Dominant Pole (fp2)", f"{fp2/1e6:.2f} MHz", ">= 331.4 MHz", fp2 / 1e6 >= 331.4),
        ("Phase Margin (PM @ UGBW)", f"{pm_deg:.2f} deg", ">= 70.0 deg", pm_deg >= 70.0),
        ("Slew Rate (SR)", f"{slew_rate_v_us:.2f} V/us", ">= 200.0 V/us", slew_rate_v_us >= 200.0),
        ("Total Branch Current (I_sum)", f"{total_current*1e3:.3f} mA", "<= 1.000 mA", total_current * 1e3 <= 1.0),
        ("Static Power (P_diss)", f"{p_diss_mw:.2f} mW", "<= 1.80 mW", p_diss_mw <= 1.80),
        ("Output Swing Window", f"[{out_swing_min:.2f}V, {out_swing_max:.2f}V]", ">= 1.40 Vpp", (out_swing_max - out_swing_min) >= 1.40),
    ]
    all_passed = all(ok for _, _, _, ok in specs)

    print("=" * 84)
    print(" TWO-STAGE MILLER CMOS OP-AMP: ANALYTICAL SMALL-SIGNAL BENCHMARK (CA3 HAND DESIGN)")
    print(f" Technology: TSMC 180nm CMOS (L = 360 nm) | VDD = {vdd}V | Temp = {temp_c}C")
    print(" School of Electrical & Computer Engineering, University of Tehran")
    print("=" * 84)
    print(f"{'Performance Metric':<32} | {'Analytical Value':<24} | {'Target':<13} | Status")
    print("-" * 84)
    for name, val, target, ok in specs:
        status = "PASS" if ok else "FAIL"
        print(f"{name:<32} | {val:<24} | {target:<13} | {status}")
    print("-" * 84)
    print(f"{'Stage 1 / Stage 2 Gain':<32} | {av1_db:.2f} dB / {av2_db:.2f} dB")
    print(f"{'Dominant Pole (fp1)':<32} | {fp1/1e3:.2f} kHz")
    print(f"{'Compensation Zero (fz)':<32} | {fz/1e6:.2f} MHz (LHP)" if fz < 0 else f"{'Compensation Zero (fz)':<32} | {fz/1e6:.2f} MHz")
    print(f"{'Approx. PMOS ICMR Window':<32} | [{icmr_min:.2f}V, {icmr_max:.2f}V]")
    print("=" * 84)
    if all_passed:
        print("Verification Status: ALL ANALYTICAL SPECIFICATIONS SATISFIED")
    else:
        failed_names = ", ".join(name for name, _, _, ok in specs if not ok)
        print(f"Verification Status: FAILED ({failed_names})")
    print("=" * 84)
    return all_passed


if __name__ == "__main__":
    sys.exit(0 if analyze_two_stage_opamp() else 1)
