import type {
  HealthResponse,
  ConfigResponse,
  ScenarioInfo,
  SimulationStartRequest,
  SimulationStatus,
  SimulationState,
  FrameResult,
  MetricsSummary,
  CurrentMetricsResponse,
  StrategyInfo,
  PolicyInfo,
  CustomEvaluationRequest,
  CustomEvaluationResponse,
  CustomSchemaResponse,
} from "../types/api";

const BASE = "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body != null ? { "Content-Type": "application/json" } : undefined,
    body: body != null ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<HealthResponse>("/api/health"),
  getConfig: () => get<ConfigResponse>("/api/config"),
  getScenarios: () => get<ScenarioInfo[]>("/api/scenarios"),
  getScenarioDetail: (id: string) => get<ScenarioInfo>(`/api/scenarios/${id}`),
  startSimulation: (req: SimulationStartRequest) =>
    post<SimulationStatus>("/api/simulation/start", req),
  stopSimulation: () => post<{ status: string; run_id: string }>("/api/simulation/stop"),
  pauseSimulation: () => post<{ status: string; run_id: string }>("/api/simulation/pause"),
  resumeSimulation: () => post<{ status: string; run_id: string }>("/api/simulation/resume"),
  resetSimulation: () => post<{ status: string }>("/api/simulation/reset"),
  stepSimulation: () => post<SimulationStatus>("/api/simulation/step"),
  getSimulationStatus: () => get<SimulationStatus>("/api/simulation/status"),
  getSimulationState: () =>
    get<SimulationState | { status: string }>("/api/simulation/state"),
  getSimulationResult: () =>
    get<FrameResult | { status: string }>("/api/simulation/result"),
  getHistory: (limit = 100) =>
    get<FrameResult[]>(`/api/simulation/history?limit=${limit}`),
  getMetricsSummary: () => get<MetricsSummary>("/api/metrics/summary"),
  getCurrentMetrics: () =>
    get<CurrentMetricsResponse | { status: string }>("/api/metrics/current"),
  getStrategies: () => get<StrategyInfo[]>("/api/strategies"),
  getPolicies: () => get<PolicyInfo[]>("/api/policies"),
  getCustomSchema: () => get<CustomSchemaResponse>("/api/custom/schema"),
  evaluateCustom: (req: CustomEvaluationRequest) =>
    post<CustomEvaluationResponse>("/api/custom/evaluate", req),
};
