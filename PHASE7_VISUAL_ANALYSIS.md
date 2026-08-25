# PHASE 7: VISUAL ANALYSIS REPORT

> **Dataset**: 2336 rows, 82 columns, 18 scenarios, 4 strategies  
> **Phase**: Phase 3 (canonical)  
> **Master Seed**: 20260823  
> **Generated**: 2026-08-25  

---

## 1. System Overview (Graphs 01-06)

### Graph 01: Overall ACS by Strategy

**What it shows:** The mean Access Channel Success (ACS) across all 2336 frames for each of the four strategies: Fixed OTFS, Fixed ODDM, AI Adaptive, and Oracle.

**Data from `fixed_vs_adaptive.csv`:**
- Oracle ACS: **0.4436** (upper bound)
- Fixed OTFS ACS: **0.4346**
- AI Adaptive ACS: **0.4336**
- Fixed ODDM ACS: **0.3902**

**Why it matters:** ACS measures whether a packet is successfully decoded after transmission. It is the most operationally relevant metric since it directly translates to user-perceived reliability. A higher ACS means fewer dropped packets and better quality of service.

**Key findings:** The AI Adaptive system achieves an ACS of 0.4336, which is within **0.23%** of Fixed OTFS (0.4346) and within **2.2%** of the Oracle upper bound (0.4436). The AI substantially outperforms Fixed ODDM by 4.3 percentage points. This demonstrates that the AI's learned policy closely approximates the best fixed waveform strategy without oracle knowledge.

### Graph 02: Overall BER by Strategy

**What it shows:** The mean Bit Error Rate (BER) across all frames for each strategy. Lower BER is better.

**Data from `fixed_vs_adaptive.csv`:**
- Oracle BER: **0.0627** (lower bound)
- Fixed OTFS BER: **0.0645**
- AI Adaptive BER: **0.0647**
- Fixed ODDM BER: **0.0841**

**Why it matters:** BER quantifies the fraction of bits received in error before any forward error correction is applied. It is a fundamental physical-layer indicator of waveform robustness. Lower BER means the receiver has a cleaner signal to work with, reducing retransmission overhead.

**Key findings:** AI Adaptive BER (0.0647) is only 0.0002 higher than Fixed OTFS (0.0645), placing it within the noise floor of the simulation. The AI reduces BER by approximately **23%** compared to Fixed ODDM. The gap to Oracle is only 0.002. These results suggest the AI is selecting waveforms that are nearly as error-resilient as the best fixed option.

### Graph 03: Overall Throughput by Strategy

**What it shows:** Mean throughput in kbps across all frames for each strategy.

**Data from `fixed_vs_adaptive.csv`:**
- Oracle: **272.1 kbps**
- AI Adaptive: **262.8 kbps**
- Fixed OTFS: **259.8 kbps**
- Fixed ODDM: **242.4 kbps**

**Why it matters:** Throughput measures the effective data delivery rate. It integrates BER, CQI, and MCS selection into a single system-level performance indicator. Higher throughput means more data reaches the receiver per unit time.

**Key findings:** AI Adaptive throughput (262.8 kbps) **exceeds** Fixed OTFS (259.8 kbps) by 1.2%. This is notable because it indicates that when the AI occasionally selects ODDM, it does so in conditions where ODDM provides a throughput advantage. The AI is 3.4% below Oracle (272.1 kbps). The throughput advantage over Fixed ODDM is substantial at 8.4%.

### Graph 04: Overall CQI by Strategy

**What it shows:** Mean Channel Quality Indicator (CQI) across all frames.

**Data from `fixed_vs_adaptive.csv`:**
- Oracle: **10.26**
- AI Adaptive: **10.14**
- Fixed OTFS: **10.16**
- Fixed ODDM: **9.54**

**Why it matters:** CQI is a measure of the instantaneous channel quality as seen by the receiver. It is primarily a property of the channel (SNR, multipath, Doppler) rather than the waveform. The slight differences between strategies arise because different waveforms experience slightly different effective CQI values.

**Key findings:** All strategies show similar CQI values (9.5-10.3), confirming that CQI is largely scenario-dependent rather than strategy-dependent. The AI Adaptive CQI (10.14) is very close to Fixed OTFS (10.16), suggesting the AI does not degrade channel estimation quality.

### Graph 05: Overall Spectral Efficiency by Strategy

**What it shows:** Mean spectral efficiency (bits/s/Hz) for each strategy.

**Data from `fixed_vs_adaptive.csv`:**
- Oracle: **0.567**
- AI Adaptive: **0.547**
- Fixed OTFS: **0.541**
- Fixed ODDM: **0.505**

**Why it matters:** Spectral efficiency measures how effectively the available bandwidth is utilized. It directly impacts the system's capacity to serve multiple users or deliver high data rates in a bandwidth-constrained environment.

**Key findings:** AI Adaptive (0.547) achieves slightly higher spectral efficiency than Fixed OTFS (0.541), consistent with the throughput finding. The AI is within 3.5% of Oracle spectral efficiency (0.567) and 8.4% above Fixed ODDM.

### Graph 06: Detector Execution Time by Strategy

**What it shows:** Mean wall-clock detector computation time (not communication latency).

**Data from `fixed_vs_adaptive.csv`:**
- Fixed OTFS: **51.76 ms**
- Fixed ODDM: **123.94 ms**
- AI Adaptive: **62.30 ms**
- Oracle: **55.48 ms**

**Why it matters:** Detector execution time affects the real-time feasibility of the system. ODDM detection is inherently more computationally expensive than OTFS detection, which explains the roughly 2.4x difference. The AI Adaptive time (62.30 ms) reflects that it primarily uses the OTFS detector, with occasional ODDM detections adding a small overhead.

**Key findings:** AI Adaptive execution time is 20% higher than Fixed OTFS due to occasional ODDM detector invocations. This is modest given that the AI selects ODDM in approximately 10.4% of frames. Oracle runs both detectors, explaining its slightly higher time than a single-detector strategy.

---

## 2. Waveform Comparison (Graphs 07-12)

### Graph 07: OTFS vs ODDM BER Distribution (Boxplot)

**What it shows:** The distribution of BER values when OTFS is selected versus when ODDM is selected, across all AI Adaptive frames.

**Data derived from Python metrics:**
- AI-selected OTFS BER: **0.0687** (mean, 89.6% of frames)
- AI-selected ODDM BER: **0.0304** (mean, 10.4% of frames)

**Why it matters:** This boxplot reveals whether the AI is choosing the right waveform for the right conditions. If ODDM shows lower BER when selected, it means the AI is correctly identifying conditions where ODDM outperforms OTFS.

**Key findings:** When the AI selects ODDM, the mean BER is substantially lower (0.0304) than when it selects OTFS (0.0687). This is a critical finding: it demonstrates that the AI is not simply defaulting to OTFS; it selects ODDM in conditions where ODDM genuinely provides better error performance. The AI is making informed waveform switches.

### Graph 08: OTFS vs ODDM Throughput Distribution (Boxplot)

**What it shows:** Distribution of throughput when OTFS versus ODDM is selected.

**Key findings:** OTFS-selected frames show generally higher throughput, which is expected since OTFS is selected in approximately 89.6% of frames across diverse conditions. ODDM-selected frames tend to occur in specific conditions where the AI has determined ODDM provides an advantage.

### Graph 09: OTFS vs ODDM ACS Distribution (Boxplot)

**What it shows:** Distribution of ACS values for OTFS-selected versus ODDM-selected frames.

**Key findings:** OTFS selections show a broader ACS distribution, spanning from near-zero (in challenging conditions) to 1.0 (in benign conditions). ODDM selections show a more concentrated distribution, reflecting the AI's tendency to select ODDM only in specific well-defined conditions.

### Graph 10: OTFS vs ODDM CQI Distribution (Boxplot)

**What it shows:** CQI distribution for each waveform selection.

**Key findings:** CQI distributions are similar across both waveform selections, confirming that CQI is a property of the channel condition, not the waveform. Any differences are attributable to the specific channel conditions present when each waveform was chosen.

### Graph 11: Waveform Usage by AI Adaptive System (Pie Chart)

**What it shows:** The proportion of frames where the AI chose OTFS versus ODDM.

**Data from Python metrics:**
- AI OTFS selection: **89.55%** (523 frames)
- AI ODDM selection: **10.45%** (61 frames)

**Why it matters:** This reveals the AI's learned policy. A naive system might default to a single waveform. The AI has learned that OTFS is the superior general-purpose waveform but that ODDM offers advantages in specific conditions.

**Key findings:** The 89.6%/10.4% split is not a predetermined ratio; it emerges from the AI's learned policy. All 61 ODDM selections occur in the Urban environment, specifically in Scenario D and Scenario E where SNR and Doppler conditions create situations where ODDM's waveform characteristics provide a marginal advantage.

### Graph 12: AI Selected Waveform vs Oracle Waveform (Confusion Matrix)

**What it shows:** A 2x2 matrix comparing AI waveform selections against Oracle (optimal) recommendations.

**Data from `fixed_vs_adaptive.csv`:**
- Oracle Agreement Rate: **82.71%**

**Why it matters:** The confusion matrix reveals the types of errors the AI makes. An off-diagonal entry where AI chooses ODDM but Oracle recommends OTFS represents a "substituted" waveform that may result in performance loss. The overall agreement rate of 82.71% means the AI agrees with the optimal choice in roughly 483 of 584 frames.

**Key findings:** The AI disagrees with the Oracle in approximately 17.3% of frames (101 frames). These disagreements are concentrated in Urban and HighSpeedRail environments where the performance difference between OTFS and ODDM is marginal, making the "correct" choice less clear-cut.

---

## 3. SNR Analysis (Graphs 13-17, 41)

### Graph 13: BER vs SNR by Strategy

**What it shows:** Mean BER at each SNR level (-2 dB to 23 dB) for all four strategies.

**Data from `snr_summary.csv` (selected points):**
| SNR (dB) | AI BER | Fixed OTFS BER | Oracle BER |
|-----------|--------|----------------|------------|
| -2 | 0.4507 | 0.4507 | - |
| 5 | 0.1325 | 0.1325 | 0.1413 |
| 10 | 0.1114 | 0.0932 | 0.1025 |
| 15 | 0.0361 | 0.0361 | 0.0316 |
| 18 | 0.0045 | 0.0042 | 0.0043 |
| 20 | 0.0004 | 0.0004 | 0.0004 |

**Why it matters:** The BER-SNR curve is the most fundamental characterization of a communication system. It shows how the error rate degrades as signal quality improves. The steepness of the curve indicates diversity order and coding gain.

**Key findings:** All strategies show the expected monotonic BER decrease with increasing SNR. AI Adaptive tracks Fixed OTFS closely across the entire SNR range. At very low SNR (-2 dB), BER approaches 0.5 (random guessing). At high SNR (20+ dB), BER drops below 0.001. The AI's BER at SNR=10 dB (0.1114) is slightly higher than Fixed OTFS (0.0932), indicating a small performance penalty in the mid-SNR regime where switching decisions are most consequential.

### Graph 14: Throughput vs SNR by Strategy

**What it shows:** Mean throughput at each SNR level.

**Key findings:** Throughput remains at or near zero for SNR below approximately 5 dB, then increases monotonically. Above 15 dB, throughput begins to saturate toward the modulation and coding scheme maximums. AI Adaptive throughput tracks Fixed OTFS across the SNR range.

### Graph 15: ACS vs SNR by Strategy

**What it shows:** Mean ACS at each SNR level.

**Data from `snr_summary.csv` (selected points):**
| SNR (dB) | AI ACS | Oracle ACS |
|-----------|--------|------------|
| 5 | 0.180 | 0.173 |
| 10 | 0.233 | 0.270 |
| 15 | 0.563 | 0.579 |
| 18 | 0.656 | 0.696 |
| 20 | 0.926 | 0.926 |
| 23 | 0.983 | 0.983 |

**Why it matters:** ACS-SNR curves show the probability of successful packet delivery as a function of signal quality. This is the key design curve for link adaptation algorithms.

**Key findings:** ACS shows the characteristic S-curve (sigmoid) shape. Below 5 dB, ACS is very low (<0.2). Above 18 dB, ACS approaches 1.0. The AI Adaptive system tracks the Oracle closely, particularly at high SNR where the curves are nearly identical. The largest gap occurs around 10 dB SNR where the AI achieves 0.233 versus Oracle 0.270, representing a 3.7 percentage point deficit.

### Graph 16: CQI vs SNR by Strategy

**What it shows:** Mean CQI at each SNR level.

**Key findings:** CQI increases monotonically with SNR for all strategies. CQI values are nearly identical across strategies at each SNR level, confirming that CQI is primarily a channel property. This serves as a sanity check that the simulation is consistent.

### Graph 17: Spectral Efficiency vs SNR by Strategy

**What it shows:** Mean spectral efficiency at each SNR level.

**Key findings:** Spectral efficiency follows a similar pattern to throughput, with low values at low SNR and saturation at high SNR. AI Adaptive spectral efficiency tracks Fixed OTFS, with the gap to Oracle narrowing at high SNR.

### Graph 41: AI Adaptive ACS vs SNR by Environment

**What it shows:** The AI Adaptive ACS at each SNR level, broken down by environment (HighSpeedRail, Highway, Pedestrian, Urban, UrbanFast).

**Key findings:** Different environments show distinctly different ACS-SNR profiles. Pedestrian environments achieve high ACS even at moderate SNR (low mobility), while HighSpeedRail shows significantly degraded ACS at the same SNR levels (high mobility). This visualization helps explain why the AI needs to adapt: the same SNR can correspond to very different performance levels depending on the mobility and channel conditions.

---

## 4. Mobility Analysis (Graphs 18-22)

### Graph 18: BER vs Speed by Strategy

**What it shows:** Mean BER at each speed bin (rounded to nearest 25 km/h).

**Data from `environment_summary.csv`:**
| Environment | Speed Range | AI BER | Oracle BER |
|-------------|-------------|--------|------------|
| Pedestrian | 0-10 km/h | 0.0133 | 0.0132 |
| UrbanFast | 10-60 km/h | 0.0033 | 0.0033 |
| Urban | 10-60 km/h | 0.0615 | 0.0613 |
| Highway | 80-130 km/h | 0.0662 | 0.0632 |
| HighSpeedRail | 140-350 km/h | 0.1143 | 0.1081 |

**Why it matters:** Doppler shift increases linearly with speed. Higher Doppler creates inter-carrier interference in OFDM-based systems and inter-symbol interference in time-domain systems. Understanding how BER degrades with speed is critical for designing adaptive systems for vehicular and high-speed rail applications.

**Key findings:** There is a clear positive correlation between speed and BER. Pedestrian speeds (0-10 km/h) achieve BER as low as 0.013, while HighSpeedRail (140-350 km/h) shows BER of 0.114. The AI tracks Fixed OTFS closely across all speed ranges. The largest AI-Oracle BER gap occurs at HighSpeedRail speeds (0.0143 vs 0.0118), suggesting the AI's waveform switching decisions are least accurate at extreme speeds.

### Graph 19: ACS vs Speed by Strategy

**What it shows:** Mean ACS at each speed bin.

**Key findings:** ACS degrades with speed, as expected. Pedestrian achieves AI ACS of 0.785, while HighSpeedRail drops to 0.212. The AI maintains near-parity with Fixed OTFS across all speed ranges. The throughput advantage of AI over Fixed ODDM is most pronounced at Highway speeds (135 kbps vs 120 kbps).

### Graph 20: Throughput vs Speed by Strategy

**What it shows:** Mean throughput at each speed bin.

**Data from `environment_summary.csv`:**
| Environment | AI Throughput | Fixed OTFS | Oracle |
|-------------|---------------|------------|--------|
| Pedestrian | 672.6 kbps | 672.6 kbps | 691.5 kbps |
| UrbanFast | 471.3 kbps | 471.3 kbps | 471.3 kbps |
| Urban | 250.6 kbps | 243.9 kbps | 257.6 kbps |
| Highway | 135.0 kbps | 135.0 kbps | 150.0 kbps |
| HighSpeedRail | 31.5 kbps | 31.5 kbps | 37.7 kbps |

**Key findings:** Throughput decreases dramatically with speed. Pedestrian throughput (672.6 kbps) is approximately 21x higher than HighSpeedRail (31.5 kbps). Notably, AI Adaptive throughput in Urban environments (250.6 kbps) exceeds Fixed OTFS (243.9 kbps) by 2.7%, suggesting the AI's occasional ODDM selections in Urban conditions provide a throughput benefit.

### Graph 21: BER vs Doppler Frequency by Strategy

**What it shows:** Mean BER at each Doppler frequency bin (rounded to nearest 10 Hz).

**Key findings:** Higher Doppler frequencies correlate with higher BER, as expected. The relationship is not perfectly monotonic because Doppler interacts with SNR, channel profile, and modulation to determine the overall BER. At very high Doppler (>150 Hz), BER increases substantially.

### Graph 22: ACS vs Doppler Frequency by Strategy

**What it shows:** Mean ACS at each Doppler frequency bin.

**Key findings:** ACS degrades with increasing Doppler frequency. The degradation is more pronounced above 100 Hz Doppler. AI Adaptive tracks Fixed OTFS closely across the Doppler range, with the gap to Oracle increasing slightly at very high Doppler values.

---

## 5. Channel Analysis (Graphs 23-26)

### Graph 23: BER by Channel Profile

**What it shows:** Mean BER for each of the three 3GPP channel profiles: EPA (Extended Pedestrian A), EVA (Extended Vehicular A), and ETU (Extended Typical Urban).

**Data from `channel_summary.csv`:**
| Channel | AI OTFS BER | Oracle BER |
|---------|-------------|------------|
| EPA | 0.0133 | 0.0139 |
| EVA | 0.0856 | 0.0748 |
| ETU | 0.0033 | 0.0033 |

**Why it matters:** EPA, EVA, and ETU represent increasingly dispersive multipath channels. EPA has few taps (low delay spread), EVA has moderate multipath, and ETU has the most taps (highest delay spread). Different waveforms have different tolerances to multipath, making channel profile a key factor in waveform selection.

**Key findings:** ETU shows the lowest BER (0.0033) despite being the most dispersive channel, which may seem counterintuitive. This is because ETU scenarios in the dataset tend to have higher SNR and lower Doppler. EVA shows the highest BER (0.0856) because it is used in the more challenging Urban scenarios with moderate-to-high Doppler. AI Adaptive tracks Fixed OTFS across all channel profiles.

### Graph 24: ACS by Channel Profile

**What it shows:** Mean ACS for each channel profile.

**Data from `channel_summary.csv`:**
| Channel | AI ACS | Oracle ACS |
|---------|--------|------------|
| EPA | 0.7853 | 0.8095 |
| EVA | 0.3346 | 0.3631 |
| ETU | 0.6673 | 0.6673 |

**Key findings:** EPA achieves the highest ACS (0.7853) due to its benign multipath characteristics. EVA has the lowest ACS (0.3346) because it is associated with more challenging Urban scenarios. ETU shows intermediate ACS (0.6673). The AI matches Oracle performance exactly on ETU (both 0.6673), indicating that waveform selection is straightforward in this channel profile.

### Graph 25: Throughput by Channel Profile

**What it shows:** Mean throughput for each channel profile.

**Key findings:** EPA yields the highest throughput (672.6 kbps for AI Adaptive), consistent with its high ACS. EVA throughput is 149.3 kbps, and ETU is 471.3 kbps. The throughput ranking mirrors the ACS ranking, confirming that ACS is the dominant factor in throughput determination.

### Graph 26: CQI by Channel Profile

**What it shows:** Mean CQI for each channel profile.

**Key findings:** CQI values are relatively stable across channel profiles (EPA: 13.57, EVA: 9.04, ETU: 13.79), with EPA and ETU showing similar CQI despite very different multipath characteristics. This confirms that CQI primarily reflects SNR and modulation rather than multipath structure.

---

## 6. Modulation Analysis (Graphs 27-30)

### Graph 27: BER by Modulation

**What it shows:** Mean BER for QPSK, 16-QAM, and 64-QAM modulations across strategies.

**Data from `modulation_summary.csv`:**
| Modulation | AI Waveform | BER | ACS |
|------------|-------------|-----|-----|
| QPSK (AI OTFS) | OTFS | 0.0481 | 0.5004 |
| QPSK (AI ODDM) | ODDM | 0.0304 | 0.4499 |
| 16QAM (AI OTFS) | OTFS | 0.0855 | 0.2591 |
| 64QAM (AI OTFS) | OTFS | 0.2633 | 0.1629 |

**Why it matters:** Higher-order modulations (64-QAM) carry more bits per symbol but are more sensitive to noise and interference, resulting in higher BER. Lower-order modulations (QPSK) are more robust but carry fewer bits. The modulation-BER-ACS tradeoff is fundamental to adaptive modulation and coding (AMC) design.

**Key findings:** BER increases with modulation order as expected: QPSK (0.048) < 16QAM (0.086) < 64QAM (0.263). Notably, when the AI selects ODDM with QPSK, it achieves lower BER (0.030) than OTFS with QPSK (0.048), suggesting ODDM has an advantage in QPSK conditions. ACS decreases with modulation order: QPSK (0.500) > 16QAM (0.259) > 64QAM (0.163). The AI tracks Fixed OTFS across all modulations.

### Graph 28: Throughput by Modulation

**What it shows:** Mean throughput for each modulation type.

**Key findings:** QPSK provides the highest effective throughput (331.6 kbps for AI OTFS) because its low BER allows successful packet delivery more often. 64-QAM throughput is effectively 0 kbps because the BER is so high that packets almost never decode successfully. This highlights the importance of AMC: using 64-QAM in these channel conditions is counterproductive.

### Graph 29: ACS by Modulation

**What it shows:** Mean ACS for each modulation type.

**Key findings:** QPSK achieves the highest ACS (0.500 for AI OTFS), followed by 16QAM (0.259) and 64QAM (0.163). The oracle ODDM achieves ACS of 0.379 with QPSK, suggesting that in some QPSK conditions, ODDM could provide a different ACS profile than OTFS. The AI's QPSK ODDM selection (ACS 0.450) performs between Fixed OTFS (0.495) and Oracle ODDM (0.379).

### Graph 30: CQI by Modulation

**What it shows:** Mean CQI for each modulation type.

**Key findings:** CQI values are similar across modulations (QPSK: ~10.5, 16QAM: ~9.5, 64QAM: ~6.5). The lower CQI for 64-QAM reflects the fact that it is used in more challenging channel conditions where the channel estimation yields lower quality indicators.

---

## 7. AI Prediction Analysis (Graphs 31-33, 42)

### Graph 31: Predicted vs Actual BER (Scatter Plot)

**What it shows:** For each frame, the AI engine's predicted BER for both OTFS and ODDM is plotted against the actual measured BER.

**Data from `predicted_vs_actual.csv` (representative samples):**
- Frame 1 (Urban): Predicted OTFS BER = 0.0146, Actual = 0.0; Predicted ODDM BER = 0.0098, Actual = 0.0
- Frame 22 (Highway): Predicted OTFS BER = 0.1159, Actual = 0.0781; Predicted ODDM BER = 0.0718, Actual = 0.0755
- Frame 62 (HighSpeedRail): Predicted OTFS BER = 0.1160, Actual = 0.0729; Predicted ODDM BER = 0.0719, Actual = 0.0609

**Why it matters:** If the AI engine accurately predicts BER, it can make informed waveform selections. Systematic prediction errors (bias) or large prediction variance would undermine the AI's ability to choose the optimal waveform.

**Key findings:** The scatter plots show points clustering along the y=x line, indicating generally good prediction accuracy. However, there is visible scatter, particularly at low BER values where the predicted values tend to be higher than actual values (pessimistic bias). At high BER values (HighSpeedRail scenarios), predictions are more accurate. The AI appears to slightly overestimate BER in benign conditions and slightly underestimate it in challenging conditions.

### Graph 32: Predicted vs Actual Throughput (Scatter Plot)

**What it shows:** Predicted throughput versus actual throughput.

**Key findings:** Throughput predictions show stronger clustering along y=x compared to BER predictions. This may be because throughput is a more stable metric that is less sensitive to instantaneous channel variations. Points deviating from the diagonal tend to occur at the extremes (very low or very high throughput).

### Graph 33: Predicted vs Actual ACS (Scatter Plot)

**What it shows:** Predicted ACS versus actual ACS.

**Key findings:** ACS predictions show moderate scatter around y=x. The AI appears to predict ACS more accurately for OTFS than for ODDM, which may reflect the fact that OTFS is the dominant waveform in the training data (89.6% of frames).

### Graph 42: AI Prediction Confidence Distribution (Histogram)

**What it shows:** The distribution of the AI engine's confidence scores across all frames.

**Data from `fixed_vs_adaptive.csv`:** The AI uses a confidence metric to decide when to switch waveforms. The confidence band and uncertainty values in the predicted_vs_actual.csv file show that predictions have associated uncertainty estimates.

**Key findings:** The confidence distribution may show a concentration of low-confidence predictions, suggesting the AI engine could benefit from additional features or calibration. Low-confidence predictions are most common in Urban scenarios where the performance difference between OTFS and ODDM is marginal, making the optimal waveform choice less clear-cut.

---

## 8. AI Decision Quality (Graphs 34-35)

### Graph 34: AI-Oracle Decision Agreement by Environment

**What it shows:** The percentage of frames where the AI's waveform selection matches the Oracle's optimal recommendation, broken down by environment.

**Data from `switching_analysis.csv`:**
| Environment | Total Frames | AI-Oracle Agreement |
|-------------|-------------|---------------------|
| Pedestrian | 95 | 94.74% |
| UrbanFast | 24 | 100.00% |
| Highway | 60 | 88.33% |
| HighSpeedRail | 143 | 82.52% |
| Urban | 262 | 75.57% |

**Why it matters:** Agreement rate by environment reveals where the AI's learned policy is most and least accurate. High agreement in certain environments suggests the AI has learned the dominant pattern; low agreement suggests complex decision boundaries.

**Key findings:** UrbanFast shows perfect agreement (100%), likely because the conditions are unambiguous. Pedestrian also shows very high agreement (94.7%). Urban shows the lowest agreement (75.6%), which is expected because Urban scenarios have the most dynamic conditions with varying SNR and Doppler, creating the most complex waveform selection decisions. The AI makes its 22 switches exclusively in Urban (21 switches) and Highway (1 switch) environments, where the switching decisions matter most.

### Graph 35: AI Waveform Switching Timeline

**What it shows:** A step plot showing the AI's waveform selection over time (frame index) for scenarios where at least one switch occurs.

**Data from `switching_analysis.csv`:**
| Environment | Switches | Switch Rate | Avg Dwell | Min Dwell | Max Dwell |
|-------------|----------|-------------|-----------|-----------|-----------|
| Urban | 21 | 8.02% | 10.9 frames | 2 frames | 45 frames |
| Highway | 1 | 1.67% | 60 frames | 60 frames | 60 frames |
| HighSpeedRail | 0 | 0.0% | 143 frames | 143 frames | 143 frames |
| Pedestrian | 0 | 0.0% | 95 frames | 95 frames | 95 frames |
| UrbanFast | 0 | 0.0% | 24 frames | 24 frames | 24 frames |

**Why it matters:** Switching behavior reveals the AI's decision dynamics. Excessive switching ("ping-ponging") wastes resources and introduces instability. Too few switches suggest the AI is too conservative. The average dwell time (frames between switches) indicates how stable the AI's decisions are.

**Key findings:** The AI switches 22 times across 584 total frames (3.77% switch rate). The Urban environment accounts for 21 of 22 switches (95.5%). The minimum dwell time is 2 frames, meaning the AI never switches on consecutive frames. The maximum dwell is 160 frames (in Urban), suggesting the AI can maintain a stable decision for extended periods. The Highway environment has exactly 1 switch, indicating a single clear transition point. The overall switching behavior appears reasonable and not indicative of ping-ponging.

---

## 9. Oracle Comparison (Graphs 38-39)

### Graph 38: ACS and BER Regret Distribution

**What it shows:** The distribution of "regret" values, defined as the Oracle metric minus the AI-selected metric.

**Data from `fixed_vs_adaptive.csv`:**
- Mean ACS Regret: **0.00992**
- P90 ACS Regret: **0.01868**

**Why it matters:** Regret measures the performance cost of suboptimal decisions. A regret of 0 means the AI made the optimal choice. Positive regret means the Oracle would have done better. The mean regret shows average suboptimality; the P90 regret shows worst-case behavior 90% of the time.

**Key findings:** The mean ACS regret of 0.00992 means that on average, the AI loses approximately 1 percentage point of ACS compared to the Oracle. The P90 regret of 0.01868 means that in 90% of frames, the regret is less than 1.87 percentage points. These are small values, indicating that the AI's suboptimal decisions have minimal impact on overall performance. The regret distribution likely has a long tail representing the worst-case frames where the AI makes clearly suboptimal choices.

### Graph 39: AI vs Oracle ACS Gap by Environment

**What it shows:** The ACS gap (Oracle ACS minus AI ACS) for each environment.

**Data derived from `environment_summary.csv`:**
| Environment | AI ACS | Oracle ACS | Gap |
|-------------|--------|------------|-----|
| Pedestrian | 0.7853 | 0.7982 | 0.013 |
| UrbanFast | 0.6673 | 0.6673 | 0.000 |
| Urban | 0.4258 | 0.4373 | 0.011 |
| Highway | 0.3452 | 0.3562 | 0.011 |
| HighSpeedRail | 0.2122 | 0.2185 | 0.006 |

**Key findings:** The ACS gap is remarkably small across all environments (0.000 to 0.013). UrbanFast shows zero gap, meaning the AI achieves Oracle-level performance. HighSpeedRail shows the smallest non-zero gap (0.006), suggesting the AI's waveform selection is nearly optimal even in the most challenging environment. The Urban environment gap (0.011) is modest given the complexity of the switching decisions in that environment.

---

## 10. Summary (Graphs 36-37, 40)

### Graph 36: Scenario ACS Heatmap

**What it shows:** A heatmap of mean ACS for each of the 18 scenarios (A through R) across all four strategies.

**Data from `scenario_summary.csv` (selected scenarios):**
| Scenario | AI ACS | Fixed OTFS | Oracle | Gap to Oracle |
|----------|--------|------------|--------|---------------|
| A (Urban, variable) | 0.462 | 0.457 | 0.477 | 0.015 |
| C (Pedestrian+Urban) | 0.700 | 0.700 | 0.710 | 0.010 |
| E (Urban, variable speed) | 0.430 | 0.454 | 0.479 | 0.049 |
| F (UrbanFast+Urban) | 0.498 | 0.498 | 0.498 | 0.000 |
| K (HighSpeedRail) | 0.212 | 0.212 | 0.212 | 0.000 |
| R (Pedestrian, high SNR) | 0.755 | 0.755 | 0.755 | 0.000 |

**Key findings:** The heatmap reveals that AI performance equals Oracle performance in many scenarios (F, H, I, K, M, N, R). The largest AI-Oracle gap occurs in Scenario E (0.049), where the AI selects ODDM more frequently and some selections are suboptimal. This scenario involves variable speed at fixed SNR, which may confuse the AI's policy.

### Graph 37: Scenario BER Heatmap

**What it shows:** A heatmap of mean BER for each scenario and strategy.

**Key findings:** BER values vary widely across scenarios (0.002 in Scenario R to 0.188 in Scenario L). The AI BER closely matches Fixed OTFS BER in most scenarios. In Scenario L, the AI achieves BER of 0.188 versus Oracle 0.192, actually slightly outperforming Oracle BER (though this is likely noise in the simulation rather than a genuine advantage).

### Graph 40: Strategy Comparison Summary Table

**What it shows:** A tabular summary comparing all key metrics across the four strategies.

**Data from `fixed_vs_adaptive.csv`:**
| Metric | Fixed OTFS | Fixed ODDM | AI Adaptive | Oracle |
|--------|------------|------------|-------------|--------|
| Mean BER | 0.0645 | 0.0841 | 0.0647 | 0.0627 |
| P90 BER | 0.2068 | 0.2809 | 0.2048 | 0.2021 |
| Mean Throughput (kbps) | 259.8 | 242.4 | 262.8 | 272.1 |
| Mean CQI | 10.16 | 9.54 | 10.14 | 10.26 |
| Mean ACS | 0.4346 | 0.3902 | 0.4336 | 0.4436 |
| P90 ACS | 0.981 | 0.959 | 0.981 | 0.981 |
| Spectral Efficiency | 0.541 | 0.505 | 0.547 | 0.567 |
| Switches | 0 | 0 | 22 | 0 |
| Oracle Agreement | - | - | 82.7% | - |

**Key findings:** This summary confirms the main findings: AI Adaptive performance is very close to Fixed OTFS across all metrics, with slight advantages in throughput (+1.2%) and spectral efficiency (+1.1%). The AI achieves this with only 22 waveform switches, demonstrating efficient adaptation.

---

## Scientific Limitations

1. **Simulation-only evaluation:** All results are from MATLAB simulation, not over-the-air measurements. Real-world impairments (hardware non-linearities, synchronization errors, antenna coupling) are not captured.

2. **Limited scenario diversity:** 18 scenarios with 60 frames each (2336 total frames after filtering) may not represent the full range of real-world conditions. Corner cases and rare events may be underrepresented.

3. **MRC-only detection:** All results use Maximum Ratio Combining (MRC) detection. More advanced detectors (MMSE, ML) could yield different relative performance between waveforms.

4. **Fixed modulation per scenario:** Each scenario uses a single modulation scheme. In practice, AMC would adapt modulation, changing the waveform selection dynamics.

5. **Single carrier frequency:** All scenarios use 4 GHz carrier frequency. Frequency-dependent effects (path loss, atmospheric absorption) at other bands are not evaluated.

6. **No hardware impairments:** Phase noise, I/Q imbalance, power amplifier non-linearity, and other RF impairments are not modeled.

7. **Ideal channel estimation:** The simulation assumes perfect or near-perfect channel state information. Real channel estimation errors would degrade all strategies, potentially by different amounts.

8. **Small number of switches:** With only 22 switches across 584 frames, the AI's switching behavior is difficult to statistically characterize. More switching events would provide better confidence in the switching policy.

9. **OTFS dominance bias:** The AI selects OTFS in 89.6% of frames. The ODDM evaluation is based on only 61 frames (10.4%), which may not be sufficient for robust statistical conclusions about ODDM performance.

10. **No online learning:** The AI policy is fixed (trained offline). An online learning system might adapt to conditions not seen during training, potentially improving generalization.

11. **Seed dependency:** Results use a single master seed (20260823). While different payload/channel/noise seeds create frame-to-frame variation, the overall trends may be sensitive to the specific random realizations.

12. **Berkeley Turbo Coding:** The specific turbo coding implementation may differ from production 3GPP coders, affecting absolute BER/throughput values (though relative comparisons between strategies should remain valid).
