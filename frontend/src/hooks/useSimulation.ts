import { useState, useEffect, useRef, useCallback } from "react";
import type {
  SimulationStatus,
  SimulationState,
  CurrentMetricsResponse,
  FrameResult,
  ScenarioInfo,
  StrategyInfo,
  PolicyInfo,
  ConfigResponse,
} from "../types/api";
import { api } from "../services/api";
import { wsService } from "../services/websocket";

export type ConnectionStatus = "connected" | "disconnected" | "connecting";

export interface SimulationState2 {
  connectionStatus: ConnectionStatus;
  simStatus: SimulationStatus | null;
  simState: SimulationState | null;
  currentMetrics: CurrentMetricsResponse | null;
  frameHistory: FrameResult[];
  scenarios: ScenarioInfo[];
  strategies: StrategyInfo[];
  policies: PolicyInfo[];
  config: ConfigResponse | null;
  error: string | null;
  loading: boolean;
}

export function useSimulation() {
  const [state, setState] = useState<SimulationState2>({
    connectionStatus: "connecting",
    simStatus: null,
    simState: null,
    currentMetrics: null,
    frameHistory: [],
    scenarios: [],
    strategies: [],
    policies: [],
    config: null,
    error: null,
    loading: true,
  });

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const pollStatus = useCallback(async () => {
    try {
      const status = await api.getSimulationStatus();
      setState((prev) => ({ ...prev, simStatus: status, error: null }));

      if (status.status === "RUNNING" || status.status === "PAUSED") {
        const [simState, metrics, history] = await Promise.all([
          api.getSimulationState(),
          api.getCurrentMetrics(),
          api.getHistory(200),
        ]);
        setState((prev) => ({
          ...prev,
          simState: "status" in simState && simState.status === "simulation_not_running"
            ? prev.simState
            : (simState as SimulationState),
          currentMetrics: "status" in metrics ? prev.currentMetrics : (metrics as CurrentMetricsResponse),
          frameHistory: history,
        }));
      }
    } catch {
      setState((prev) => ({ ...prev, error: "Failed to fetch simulation status" }));
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = setInterval(pollStatus, 2000);
  }, [pollStatus]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    wsService.connect();

    const unsub = wsService.subscribe((event) => {
      if (event.type === "frame_update" && event.result) {
        setState((prev) => ({
          ...prev,
          frameHistory: [...prev.frameHistory, event.result!].slice(-200),
        }));
      }
      if (event.type === "simulation_started") {
        startPolling();
      }
      if (
        event.type === "simulation_completed" ||
        event.type === "simulation_stopped" ||
        event.type === "simulation_error"
      ) {
        stopPolling();
        pollStatus();
      }
      if (event.type === "simulation_paused" || event.type === "simulation_resumed") {
        pollStatus();
      }
    });

    const checkConnection = setInterval(() => {
      setState((prev) => ({
        ...prev,
        connectionStatus: wsService.isConnected() ? "connected" : "disconnected",
      }));
    }, 3000);

    Promise.all([
      api.getScenarios(),
      api.getStrategies(),
      api.getPolicies(),
      api.getConfig(),
      api.getSimulationStatus(),
    ])
      .then(([scenarios, strategies, policies, config, simStatus]) => {
        setState((prev) => ({
          ...prev,
          scenarios,
          strategies,
          policies,
          config,
          simStatus,
          loading: false,
          connectionStatus: wsService.isConnected() ? "connected" : "disconnected",
        }));
        if (simStatus.status === "RUNNING" || simStatus.status === "PAUSED") {
          startPolling();
        }
      })
      .catch(() => {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: "Failed to connect to backend",
          connectionStatus: "disconnected",
        }));
      });

    return () => {
      unsub();
      stopPolling();
      clearInterval(checkConnection);
      wsService.disconnect();
    };
  }, [startPolling, stopPolling, pollStatus]);

  const startSimulation = useCallback(
    async (req: {
      mode: string;
      scenario: string;
      strategy: string;
      policy: string;
      seed0?: number;
    }) => {
      setState((prev) => ({ ...prev, error: null }));
      try {
        const result = await api.startSimulation(req);
        setState((prev) => ({ ...prev, simStatus: result, frameHistory: [] }));
        startPolling();
        return result;
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Start failed";
        setState((prev) => ({ ...prev, error: msg }));
        return null;
      }
    },
    [startPolling]
  );

  const stopSimulation = useCallback(async () => {
    try {
      await api.stopSimulation();
      stopPolling();
      await pollStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Stop failed";
      setState((prev) => ({ ...prev, error: msg }));
    }
  }, [stopPolling, pollStatus]);

  const pauseSimulation = useCallback(async () => {
    try {
      await api.pauseSimulation();
      await pollStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Pause failed";
      setState((prev) => ({ ...prev, error: msg }));
    }
  }, [pollStatus]);

  const resumeSimulation = useCallback(async () => {
    try {
      await api.resumeSimulation();
      startPolling();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Resume failed";
      setState((prev) => ({ ...prev, error: msg }));
    }
  }, [startPolling]);

  const resetSimulation = useCallback(async () => {
    try {
      stopPolling();
      await api.resetSimulation();
      setState((prev) => ({
        ...prev,
        simStatus: null,
        simState: null,
        currentMetrics: null,
        frameHistory: [],
        error: null,
      }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Reset failed";
      setState((prev) => ({ ...prev, error: msg }));
    }
  }, [stopPolling]);

  return {
    ...state,
    startSimulation,
    stopSimulation,
    pauseSimulation,
    resumeSimulation,
    resetSimulation,
  };
}
