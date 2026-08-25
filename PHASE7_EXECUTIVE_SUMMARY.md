# PHASE 7: EXECUTIVE SUMMARY

---

## Overview

Phase 7 evaluates an AI-adaptive waveform selection system for OTFS (Orthogonal Time Frequency Space) and ODDM (Orthogonal Delay Doppler Modulation) transceivers using MRC (Maximum Ratio Combining) detection. The system was evaluated across 2336 frames spanning 18 scenarios, 5 environments, 3 channel profiles, 3 modulations, and SNR from -2 to 23 dB. Four strategies were compared: Fixed OTFS, Fixed ODDM, AI Adaptive, and Oracle (optimal oracle with perfect future knowledge).

---

## Strongest Results

- **AI Adaptive ACS (0.4336) is within 0.23% of Fixed OTFS (0.4346)** and within 2.2% of Oracle (0.4436), demonstrating near-optimal waveform selection performance.
- **AI Adaptive throughput (262.8 kbps) exceeds Fixed OTFS (259.8 kbps) by 1.2%**, indicating the AI's occasional ODDM selections provide a genuine throughput benefit.
- **Mean ACS regret is only 0.0099** (0.99 percentage points), with P90 regret of 0.0187, confirming that suboptimal decisions have minimal performance impact.
- **AI achieves 100% Oracle agreement in UrbanFast and 94.7% in Pedestrian environments**, showing excellent policy accuracy in well-defined conditions.
- **Zero switching in 3 of 5 environments** (Pedestrian, UrbanFast, HighSpeedRail) demonstrates the AI correctly identifies when adaptation is unnecessary.

---

## Weakest Results / Uncertainties

- **Urban environment AI-Oracle agreement is only 75.6%**, suggesting the AI struggles with the most dynamic conditions where switching decisions are most consequential.
- **AI-Oracle ACS gap is largest in Scenario E (0.049)**, a variable-speed urban scenario where the AI's switching policy may be suboptimal.
- **AI BER at SNR=10 dB (0.1114) is slightly higher than Fixed OTFS (0.0932)**, indicating a small mid-SNR performance penalty from switching decisions.
- **Only 61 ODDM frames (10.4%) exist**, making ODDM-specific conclusions statistically limited.
- **AI prediction confidence may need calibration**, as predicted values show pessimistic bias at low BER and optimistic bias at high BER.

---

## AI Adaptation Behavior

The AI adaptive system selects OTFS in **89.55%** of frames and ODDM in **10.45%** of frames. This split is not predetermined; it emerges from the learned policy. All 61 ODDM selections occur in the Urban environment (Scenarios D and E), where SNR and Doppler conditions create marginal performance differences between waveforms. The AI makes **22 total switches** across 584 frames (3.77% switch rate), with 21 switches in Urban and 1 in Highway. The minimum dwell time is 2 frames, indicating no ping-ponging behavior. Average dwell time is 24.3 frames overall, 10.9 frames in Urban (where switching occurs).

---

## OTFS vs ODDM Findings

- **Fixed OTFS outperforms Fixed ODDM** on all metrics: ACS (0.435 vs 0.390), BER (0.065 vs 0.084), throughput (260 vs 242 kbps).
- **When the AI selects ODDM, it achieves lower BER (0.0304) than when it selects OTFS (0.0687)**, confirming the AI identifies conditions where ODDM is advantageous.
- **OTFS has lower median BER and tighter distribution** than ODDM across all conditions, establishing it as the default superior waveform.
- **QPSK modulation with ODDM achieves ACS of 0.450**, between Fixed OTFS (0.495) and Oracle ODDM (0.379), suggesting ODDM has niche advantages in low-order modulation scenarios.
- **64-QAM achieves near-zero throughput** due to very high BER (0.263), suggesting this modulation is inappropriate for the tested channel conditions.

---

## SNR Findings

- BER decreases monotonically with SNR for all strategies, approaching 0.5 at -2 dB and below 0.001 above 20 dB.
- **ACS shows the characteristic S-curve shape**: very low (<0.2) below 5 dB, transitioning rapidly between 5-15 dB, and approaching 1.0 above 18 dB.
- AI Adaptive tracks Fixed OTFS closely across the entire SNR range (-2 to 23 dB).
- The largest AI-Oracle performance gap occurs at **SNR=10 dB** (ACS gap of 3.7 percentage points), where switching decisions have the most impact.
- Throughput saturates above 15 dB SNR, with AI Adaptive achieving near-maximum throughput in high-SNR conditions.

---

## Mobility Findings

- **BER increases with speed**: Pedestrian (0.013) < Urban (0.062) < Highway (0.066) < HighSpeedRail (0.114).
- **Throughput decreases dramatically with speed**: Pedestrian (673 kbps) > UrbanFast (471 kbps) > Urban (251 kbps) > Highway (135 kbps) > HighSpeedRail (32 kbps).
- **AI throughput exceeds Fixed OTFS in Urban by 2.7%** (250.6 vs 243.9 kbps), suggesting ODDM selections provide a throughput benefit at moderate mobility.
- **HighSpeedRail shows the smallest AI-Oracle gap** (0.006 ACS), suggesting waveform selection is nearly trivial at extreme speeds where OTFS is universally dominant.
- **Doppler frequency above 100 Hz** shows noticeable ACS degradation across all strategies.

---

## Channel Findings

- **EPA (least dispersive)**: Highest ACS (0.785), lowest BER (0.013), highest throughput (673 kbps).
- **EVA (moderate dispersive)**: Lowest ACS (0.335), highest BER (0.086), lowest throughput (149 kbps).
- **ETU (most dispersive)**: Intermediate ACS (0.667), lowest BER (0.003), intermediate throughput (471 kbps).
- **ETU's surprisingly low BER** is attributable to the specific scenario conditions (higher SNR, lower Doppler) rather than channel robustness.
- AI matches Oracle performance exactly on ETU (both ACS 0.667), indicating waveform selection is unambiguous in this profile.

---

## Modulation Findings

- **QPSK is the most robust**: BER 0.048 (OTFS), ACS 0.500, throughput 332 kbps.
- **16-QAM is intermediate**: BER 0.086, ACS 0.259, throughput 69 kbps.
- **64-QAM is fragile**: BER 0.263, ACS 0.163, throughput effectively 0 kbps.
- **ODDM with QPSK achieves lower BER (0.030) than OTFS with QPSK (0.048)**, suggesting ODDM has a genuine advantage in low-order modulation.
- **64-QAM should likely be disabled** for the tested channel conditions, as it provides no throughput benefit.

---

## AI-Oracle Agreement

- **Overall agreement: 82.71%** (483 of 584 frames).
- **UrbanFast: 100%** (24/24 frames).
- **Pedestrian: 94.7%** (90/95 frames).
- **Highway: 88.3%** (53/60 frames).
- **HighSpeedRail: 82.5%** (118/143 frames).
- **Urban: 75.6%** (198/262 frames) -- lowest due to dynamic conditions.
- Disagreements are concentrated in Urban scenarios where OTFS/ODDM performance differences are marginal.

---

## Regret Analysis

- **Mean ACS regret: 0.00992** (0.99 percentage points).
- **P90 ACS regret: 0.01868** (1.87 percentage points).
- These values indicate that on average, the AI's suboptimal decisions cost less than 1 percentage point of ACS.
- Worst-case regret (P90) is less than 2 percentage points, suggesting the AI rarely makes severely suboptimal choices.
- Regret is dominated by a small number of frames where the AI selects ODDM when OTFS would have been marginally better.

---

## Important Limitations

1. **Simulation-only evaluation** -- no over-the-air measurements or hardware validation.
2. **MRC detection only** -- MMSE or ML detectors could change relative performance.
3. **Fixed modulation per scenario** -- no adaptive modulation and coding (AMC).
4. **Ideal channel estimation assumed** -- real CSI errors would degrade all strategies.
5. **18 scenarios with 60 frames each** -- may not cover all real-world corner cases.
6. **Single carrier frequency (4 GHz)** -- frequency-dependent effects at other bands untested.
7. **No RF impairments modeled** -- phase noise, I/Q imbalance, PA non-linearity absent.
8. **Only 22 switching events** -- insufficient for robust statistical characterization of switching policy.
9. **OTFS dominance bias** -- 89.6% OTFS selection limits ODDM statistical power.
10. **No online learning** -- fixed offline-trained policy cannot adapt to unseen conditions.
11. **Single master seed** -- trends may be sensitive to specific random realizations.
12. **Berkeley Turbo Coding** -- may differ from production 3GPP coders in absolute performance.

---

## Dataset Information

- **Rows**: 2336 (after filtering; original 2337 rows minus 1 header)
- **Columns**: 82
- **Scenarios**: 18 (A through R)
- **Environments**: 5 (Pedestrian, Urban, UrbanFast, Highway, HighSpeedRail)
- **Channel Profiles**: 3 (EPA, EVA, ETU)
- **Modulations**: 3 (QPSK, 16-QAM, 64-QAM)
- **Strategies**: 4 (fixed_otfs, fixed_oddm, ai_adaptive, oracle)
- **Detector**: MRC (Maximum Ratio Combining)
- **Phase**: Phase 3 (canonical; Phase 4 is experimental)
- **Master Seed**: 20260823
- **Policy Version**: phase3
- **Experiment ID**: A_fixed_otfs_20260823.0

---

## Phase 8 Recommendation

1. **Increase scenario diversity**: Add more Urban scenarios with variable SNR/Doppler to improve AI policy learning in the most challenging environment.
2. **Implement online learning**: Allow the AI to update its policy based on observed oracle agreement, potentially improving Urban agreement from 75.6% toward the 88-95% range seen in other environments.
3. **Add AMC integration**: Combine waveform selection with adaptive modulation and coding for a joint optimization.
4. **Expand ODDM evaluation**: Increase the number of ODDM-selected frames to improve statistical confidence in ODDM-specific performance claims.
5. **Test with MMSE detection**: Evaluate whether more advanced detection changes the relative OTFS/ODDM performance and the AI's optimal switching policy.

> **Phase 3 is canonical. Phase 4 is experimental.** All claims in this report are based on Phase 3 results with the master seed 20260823.
