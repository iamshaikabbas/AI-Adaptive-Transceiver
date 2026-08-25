import { useState, useEffect, useCallback } from "react";
import type { SimulationStatus, AIInfo, FrameResult } from "../types/api";
import { api } from "../services/api";
import SimulationControls from "../components/SimulationControls";
import DigitalTwinViz from "../components/DigitalTwinViz";
import AIDecisionPanel from "../components/AIDecisionPanel";
import WaveformComparison from "../components/WaveformComparison";
import OracleComparison from "../components/OracleComparison";
import LiveCharts from "../components/LiveCharts";
import Timeline from "../components/Timeline";
import SwitchingBar from "../components/SwitchingBar";
import type { SimulationState2 } from "../hooks/useSimulation";

function EnvironmentPanel({ state }: { state: SimulationState2["simState"] }) {
  if (!state) {
    return (
      <div className="border border-border bg-surface p-3">
        <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Operating Conditions</h3>
        <p className="text-[11px] text-text-muted">No active simulation</p>
      </div>
    );
  }

  return (
    <div className="border border-border bg-surface p-3">
      <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Operating Conditions</h3>
      <table className="w-full text-[12px]">
        <tbody>
          {[
            ["Environment", state.environment],
            ["Speed", `${state.speed_kmph.toFixed(1)} km/h`],
            ["SNR", `${state.snr_db.toFixed(1)} dB`],
            ["Doppler", `${state.doppler_hz.toFixed(1)} Hz`],
            ["Channel", state.channel_profile],
            ["Modulation", `${state.modulation} QAM`],
            ["Frame", `${state.frame}`],
          ].map(([label, value]) => (
            <tr key={label} className="border-b border-border-subtle last:border-b-0">
              <td className="py-1 text-text-muted">{label}</td>
              <td className="py-1 text-right text-black font-mono font-medium">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LiveMetrics({ latest }: { latest: FrameResult | null }) {
  if (!latest) {
    return (
      <div className="border border-border bg-surface p-3">
        <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Current Metrics</h3>
        <p className="text-[11px] text-text-muted">No data</p>
      </div>
    );
  }

  return (
    <div className="border border-border bg-surface p-3">
      <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Current Metrics</h3>
      <table className="w-full text-[12px]">
        <tbody>
          {[
            ["BER", latest.BER.toFixed(6)],
            ["Throughput", `${(latest.throughput_bps / 1000).toFixed(1)} kbps`],
            ["CQI", `${latest.CQI}`],
            ["ACS", latest.ACS.toFixed(4)],
            ["Waveform", latest.waveform],
            ["Oracle", latest.oracle_waveform],
          ].map(([label, value]) => (
            <tr key={label} className="border-b border-border-subtle last:border-b-0">
              <td className="py-1 text-text-muted">{label}</td>
              <td className="py-1 text-right text-black font-mono font-medium">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DigitalTwinPage() {
  const [simStatus, setSimStatus] = useState<SimulationStatus | null>(null);
  const [simState, setSimState] = useState<SimulationState2["simState"]>(null);
  const [currentAI, setCurrentAI] = useState<AIInfo | null>(null);
  const [frameHistory, setFrameHistory] = useState<FrameResult[]>([]);
  const [scenarios, setScenarios] = useState<SimulationState2["scenarios"]>([]);
  const [strategies, setStrategies] = useState<SimulationState2["strategies"]>([]);
  const [policies, setPolicies] = useState<SimulationState2["policies"]>([]);
  const [error, setError] = useState<string | null>(null);

  const [selectedScenario, setSelectedScenario] = useState("A");
  const [selectedMode, setSelectedMode] = useState("FAST");
  const [selectedStrategy, setSelectedStrategy] = useState("ai_adaptive");
  const [selectedPolicy, setSelectedPolicy] = useState("phase3");

  const fetchAll = useCallback(async () => {
    try {
      const [sc, st, po, status] = await Promise.all([
        api.getScenarios(),
        api.getStrategies(),
        api.getPolicies(),
        api.getSimulationStatus(),
      ]);
      setScenarios(sc);
      setStrategies(st);
      setPolicies(po);
      setSimStatus(status);
      if (sc.length > 0 && !scenarios.length) setSelectedScenario(sc[0].id);
      if (po.length > 0 && !policies.length) {
        const def = po.find((p) => p.default);
        if (def) setSelectedPolicy(def.id);
      }
    } catch {
      setError("Cannot connect to backend");
    }
  }, [scenarios.length, policies.length]);

  const refreshState = useCallback(async () => {
    try {
      const status = await api.getSimulationStatus();
      setSimStatus(status);
      if (status.status === "RUNNING" || status.status === "PAUSED") {
        const [state, metrics, hist] = await Promise.all([
          api.getSimulationState(),
          api.getCurrentMetrics(),
          api.getHistory(200),
        ]);
        if (!("status" in state)) setSimState(state);
        if (!("status" in metrics)) setCurrentAI(metrics.ai);
        setFrameHistory(hist);
      }
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    if (!simStatus) return;
    if (simStatus.status !== "RUNNING" && simStatus.status !== "PAUSED") return;
    const id = setInterval(refreshState, 2000);
    return () => clearInterval(id);
  }, [simStatus?.status, refreshState]);

  const onStart = async () => {
    try {
      setError(null);
      const result = await api.startSimulation({ mode: selectedMode, scenario: selectedScenario, strategy: selectedStrategy, policy: selectedPolicy });
      setSimStatus(result);
      setFrameHistory([]);
    } catch (e) { setError(e instanceof Error ? e.message : "Start failed"); }
  };
  const onPause = async () => { try { await api.pauseSimulation(); await refreshState(); } catch (e) { setError(e instanceof Error ? e.message : "Pause failed"); } };
  const onResume = async () => { try { await api.resumeSimulation(); } catch (e) { setError(e instanceof Error ? e.message : "Resume failed"); } };
  const onStop = async () => { try { await api.stopSimulation(); await refreshState(); } catch (e) { setError(e instanceof Error ? e.message : "Stop failed"); } };
  const onReset = async () => {
    try {
      await api.resetSimulation();
      setSimStatus(null); setSimState(null); setCurrentAI(null); setFrameHistory([]);
    } catch (e) { setError(e instanceof Error ? e.message : "Reset failed"); }
  };

  const switches = frameHistory.filter((f) => f.switched).length;
  const latest = frameHistory.length > 0 ? frameHistory[frameHistory.length - 1] : null;

  return (
    <div className="p-4 space-y-3 max-w-[1400px] mx-auto">
      <div className="flex items-baseline justify-between border-b border-border pb-2">
        <h1 className="text-lg font-semibold text-black tracking-tight">Digital Twin</h1>
        <span className="text-[11px] text-text-muted font-mono">
          {simStatus?.status ?? "IDLE"} · SCN {selectedScenario}
        </span>
      </div>

      {error && (
        <div className="border border-gold bg-active-light px-3 py-2 text-[12px] text-black font-mono">
          {error}
        </div>
      )}

      <div className="grid grid-cols-12 gap-3">
        {/* Left column */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-2">
          <SimulationControls
            scenarios={scenarios} strategies={strategies} policies={policies} simStatus={simStatus}
            selectedScenario={selectedScenario} selectedMode={selectedMode}
            selectedStrategy={selectedStrategy} selectedPolicy={selectedPolicy}
            onSelectScenario={setSelectedScenario} onSelectMode={setSelectedMode}
            onSelectStrategy={setSelectedStrategy} onSelectPolicy={setSelectedPolicy}
            onStart={onStart} onPause={onPause} onResume={onResume} onStop={onStop} onReset={onReset}
          />
          <EnvironmentPanel state={simState} />
          <LiveMetrics latest={latest} />
        </div>

        {/* Center column */}
        <div className="col-span-12 lg:col-span-6 flex flex-col gap-2">
          <DigitalTwinViz state={simState} />
          <AIDecisionPanel ai={currentAI} state={simState} switched={latest?.switched} />
          <WaveformComparison ai={currentAI} />
          <OracleComparison latest={latest} />
          <Timeline history={frameHistory} totalFrames={simStatus?.total_frames ?? 0} currentFrame={simStatus?.current_frame ?? 0} />
          <SwitchingBar history={frameHistory} switches={switches} />
        </div>

        {/* Right column: Charts */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-2">
          <LiveCharts history={frameHistory} />
        </div>
      </div>
    </div>
  );
}
