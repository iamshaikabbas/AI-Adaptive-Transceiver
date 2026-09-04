export interface HealthResponse {
  status: string;
  service: string;
  phase: number;
  policy: string;
  digital_twin: "available" | "unavailable";
  matlab: "available" | "unavailable";
  ai_engine: "available" | "unavailable";
}

export interface ConfigResponse {
  default_policy: string;
  available_policies: string[];
  available_strategies: string[];
  supported_environments: string[];
  supported_channels: string[];
  supported_modulations: number[];
  simulation_modes: string[];
}

export interface ScenarioInfo {
  id: string;
  name: string;
  environment: string;
  duration_frames: number;
}

export interface SimulationStartRequest {
  mode: string;
  scenario: string;
  strategy: string;
  policy: string;
  seed0?: number;
}

export interface SimulationStatus {
  run_id: string;
  status: string;
  scenario: string;
  strategy: string;
  policy: string;
  mode: string;
  current_frame: number;
  total_frames: number;
  elapsed_seconds: number;
}

export interface SimulationState {
  frame: number;
  scenario_id: string;
  environment: string;
  speed_kmph: number;
  snr_db: number;
  doppler_hz: number;
  channel_profile: string;
  modulation: number;
  waveform: string;
  strategy: string;
}

export interface AIInfo {
  selected_waveform?: string;
  confidence?: number;
  predicted_otfs_acs?: number;
  predicted_oddm_acs?: number;
  reason?: string;
  fallback_used: boolean;
}

export interface FrameResult {
  run_id: string;
  frame: number;
  scenario_id: string;
  environment: string;
  speed_kmph: number;
  snr_db: number;
  doppler_hz: number;
  channel_profile: string;
  modulation: number;
  waveform: string;
  strategy: string;
  switched: boolean;
  oracle_waveform: string;
  BER: number;
  throughput_bps: number;
  CQI: number;
  ACS: number;
  ACS_regret: number;
  decision_correct: number;
  actual_BER_OTFS?: number;
  actual_ACS_OTFS?: number;
  actual_BER_ODDM?: number;
  actual_ACS_ODDM?: number;
  actual_TP_OTFS?: number;
  actual_TP_ODDM?: number;
}

export interface BackendMetrics {
  ber: number | null;
  ser: number | null;
  per: number | null;
  throughput_bps: number | null;
  spectral_efficiency: number | null;
  cqi: number | null;
  acs: number | null;
  detector_time_ms: number | null;
  latency_ms_modeled: number | null;
}

export interface MetricsSummary {
  frames_processed: number;
  otfs_frames: number;
  oddm_frames: number;
  switches: number;
  mean_ber: number;
  mean_throughput: number;
  mean_cqi: number;
  mean_acs: number;
  oracle_agreement: number;
  mean_acs_regret: number;
}

export interface CurrentMetricsResponse {
  metrics: BackendMetrics;
  ai: AIInfo;
}

export interface StrategyInfo {
  id: string;
  name: string;
}

export interface PolicyInfo {
  id: string;
  name: string;
  description: string;
  default: boolean;
}

export interface WSFrameEvent {
  type: string;
  run_id: string;
  frame?: number;
  total_frames?: number;
  result?: FrameResult;
  error?: string;
  scenario?: string;
  strategy?: string;
}

// ── Phase 11: Custom Evaluation ──────────────────────────────────────────────

export interface PredictionUncertaintyModel {
  mean: number;
  std: number;
  p10: number | null;
  p90: number | null;
}

export interface WaveformPredictionModel {
  waveform: string;
  detector: string;
  BER: PredictionUncertaintyModel | null;
  throughput_bps: PredictionUncertaintyModel | null;
  CQI: PredictionUncertaintyModel | null;
  ACS: PredictionUncertaintyModel | null;
  PER: PredictionUncertaintyModel | null;
  spectral_efficiency: PredictionUncertaintyModel | null;
}

export interface NeighborModel {
  distance: number;
  speed_difference: number;
  snr_difference: number;
  doppler_difference: number;
  source_scenario: string;
  source_frame: number;
  environment: string;
  channel_profile: string;
  modulation: number;
  otfs_ber: number | null;
  otfs_acs: number | null;
  oddm_ber: number | null;
  oddm_acs: number | null;
}

export interface NeighborhoodConsistencyModel {
  waveform: string;
  predicted_acs: number | null;
  neighbor_acs_mean: number | null;
  neighbor_acs_median: number | null;
  neighbor_acs_range: [number | null, number | null] | null;
  deviation: number | null;
  consistent: boolean | null;
}

export interface CustomEvaluationRequest {
  environment: string;
  speed_kmph: number;
  snr_db: number;
  channel_profile: string;
  modulation: number;
  detector?: string;
}

export interface CustomEvaluationResponse {
  status: string;
  coverage: string;
  confidence: string;
  input: {
    environment: string;
    speed_kmph: number;
    snr_db: number;
    doppler_hz: number;
    channel_profile: string;
    modulation: number;
    detector: string | null;
  };
  nearest_neighbors: NeighborModel[];
  predictions: {
    OTFS: WaveformPredictionModel | null;
    ODDM: WaveformPredictionModel | null;
  };
  consistency: {
    OTFS: NeighborhoodConsistencyModel | null;
    ODDM: NeighborhoodConsistencyModel | null;
  };
  decision: {
    selected_waveform: string | null;
    best_by_objective: string;
    detector: string;
    switched: boolean;
    reason: string;
    confidence: number;
    objective: string;
    predicted_OTFS_ACS: number | null;
    predicted_ODDM_ACS: number | null;
    predicted_OTFS_BER: number | null;
    predicted_ODDM_BER: number | null;
    policy_version: string;
  };
  warnings: string[];
}

export interface CustomSchemaResponse {
  supported_environments: string[];
  supported_channel_profiles: string[];
  supported_modulations: number[];
  supported_detectors: string[];
  model_targets: string[];
  target_columns: Record<string, string>;
  numerical_ranges: Record<string, { min: number; max: number }>;
  doppler_derivation: {
    method: string;
    formula: string;
    note: string;
  };
  coverage_rules: Record<string, string>;
  policy_version: string;
  model_version: string;
}

// ── Evals Platform ───────────────────────────────────────────────────────────

export type CaseType = "EXACT" | "INTERIOR" | "BOUNDARY" | "OOD";
export type RunStatus = "RUNNING" | "COMPLETED" | "FAILED" | "STOPPED";
export type CaseResultStatus = "PASS" | "FAIL" | "REJECTED" | "UNAVAILABLE";
export type EvalSuiteId = "FULL_REGRESSION" | "PREDICTION_ACCURACY" | "OOD_SAFETY" | "ROBUSTNESS";

export interface EvalSuiteInfo {
  id: EvalSuiteId;
  name: string;
  description: string;
}

export interface GoldenDatasetManifest {
  total_rows: number;
  total_columns: number;
  scenario_count: number;
  frame_count: number;
  checksum_md5: string;
  checksum_verified: boolean;
  expected_md5: string;
  column_names: string[];
  environments: string[];
  channel_profiles: string[];
  speed_range: [number, number];
  snr_range: [number, number];
  fixed_otfs_count: number;
  fixed_oddm_count: number;
  oracle_count: number;
}

export interface EvalInputConditions {
  environment: string;
  speed_kmph: number;
  snr_db: number;
  doppler_hz: number;
  channel_profile: string;
  modulation: number;
  detector?: string;
}

export interface EvalCaseResultData {
  case_id: string;
  case_type: CaseType;
  suite: EvalSuiteId;
  input_conditions: EvalInputConditions;
  ground_truth_available: boolean;
  ground_truth: Record<string, number | null> | null;
  prediction: Record<string, unknown> | null;
  prediction_source: string;
  confidence?: number;
  coverage?: string;
  ood: boolean;
  ood_decision?: string;
  ood_reason?: string;
  result: CaseResultStatus;
  result_reason?: string;
  metrics?: Record<string, number | null>;
  elapsed_seconds: number;
  timestamp: string;
}

export interface EvalRunSummaryData {
  run_id: string;
  suite: EvalSuiteId;
  status: RunStatus;
  created_at: string;
  started_at: string;
  completed_at?: string;
  elapsed_seconds: number;
  total_cases: number;
  completed_cases: number;
  progress_pct: number;
  current_case_id?: string;
  current_case_type?: CaseType;
  passed: number;
  failed: number;
  rejected: number;
  unavailable: number;
  dataset_checksum: string;
  model_version: string;
  policy_version: string;
}

export interface EvalGraphData {
  elapsed_seconds: number[];
  case_index: number[];
  case_types: string[];
  ber_error: (number | null)[];
  throughput_error: (number | null)[];
  cqi_error: (number | null)[];
  acs_error: (number | null)[];
  confidence: (number | null)[];
  regret_ber: (number | null)[];
  pass_cumulative: number[];
  fail_cumulative: number[];
  rejected_cumulative: number[];
  pass_rate: number[];
  ood_rejection_rate: number[];
  ber_pred: (number | null)[];
  ber_gt: (number | null)[];
  tp_pred: (number | null)[];
  tp_gt: (number | null)[];
  cqi_pred: (number | null)[];
  cqi_gt: (number | null)[];
}

export interface EvalReport {
  run_id: string;
  suite: EvalSuiteId;
  status: RunStatus;
  total_cases: number;
  completed_cases: number;
  passed: number;
  failed: number;
  rejected: number;
  unavailable: number;
  elapsed_seconds: number;
  dataset_checksum: string;
  model_version: string;
  policy_version: string;
  aggregated_metrics: Record<string, number>;
  by_case_type: Record<string, { count: number; pass: number; fail: number; rejected: number; unavailable: number }>;
  overall?: {
    total: number;
    completed: number;
    passed: number;
    failed: number;
    rejected: number;
    unavailable: number;
  };
  exact?: {
    total: number;
    completed: number;
    pass: number;
    fail: number;
    pass_rate: number;
  };
  interior?: {
    total: number;
    completed: number;
    model_estimates: number;
    note?: string;
  };
  boundary?: {
    total: number;
    completed: number;
    model_estimates: number;
    rejected?: number;
    note?: string;
  };
  ood?: {
    total: number;
    rejected: number;
    fabricated_predictions: number;
    rejection_rate: number;
    false_prediction_rate: number;
  };
}

export interface EvalRunFullData {
  summary: EvalRunSummaryData;
  config: Record<string, unknown>;
  cases: EvalCaseResultData[];
  report: EvalReport;
  graph_data: EvalGraphData;
}

export interface WSEvalEvent {
  type: string;
  run_id: string;
  timestamp: string;
  progress_pct: number;
  completed_cases: number;
  total_cases: number;
  elapsed_seconds: number;
  current_case_id?: string;
  current_case_type?: CaseType;
  status: RunStatus;
  passed: number;
  failed: number;
  rejected: number;
  unavailable: number;
  case_result?: EvalCaseResultData;
  graph_data?: Partial<EvalGraphData>;
  graph_data_full?: EvalGraphData;
}

export interface MetricComparison {
  metric: string;
  run_a: number;
  run_b: number;
  delta: number;
  pct_change: number;
  direction_preference: "lower" | "higher";
  interpretation: "IMPROVED" | "DEGRADED" | "STABLE";
}

export interface RegressionComparisonData {
  run_a_id: string;
  run_b_id: string;
  run_a_summary: EvalRunSummaryData;
  run_b_summary: EvalRunSummaryData;
  metric_comparison: MetricComparison[];
  interpretation: string;
  improved: string[];
  degraded: string[];
  unchanged: string[];
}
