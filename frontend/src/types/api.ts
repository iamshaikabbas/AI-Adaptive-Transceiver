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
