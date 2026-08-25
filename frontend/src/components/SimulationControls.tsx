import type { SimulationStatus, ScenarioInfo, StrategyInfo, PolicyInfo } from "../types/api";

type Status = SimulationStatus["status"];

export default function SimulationControls({
  scenarios,
  strategies,
  policies,
  simStatus,
  selectedScenario,
  selectedMode,
  selectedStrategy,
  selectedPolicy,
  onSelectScenario,
  onSelectMode,
  onSelectStrategy,
  onSelectPolicy,
  onStart,
  onPause,
  onResume,
  onStop,
  onReset,
}: {
  scenarios: ScenarioInfo[];
  strategies: StrategyInfo[];
  policies: PolicyInfo[];
  simStatus: SimulationStatus | null;
  selectedScenario: string;
  selectedMode: string;
  selectedStrategy: string;
  selectedPolicy: string;
  onSelectScenario: (v: string) => void;
  onSelectMode: (v: string) => void;
  onSelectStrategy: (v: string) => void;
  onSelectPolicy: (v: string) => void;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onReset: () => void;
}) {
  const s: Status = simStatus?.status ?? "STOPPED";
  const running = s === "RUNNING";
  const paused = s === "PAUSED";
  const idle = s === "STOPPED" || s === "COMPLETED" || s === "ERROR" || s === "CREATED";

  const selectCls = "bg-surface border border-border text-black text-[13px] px-2 py-1.5 disabled:opacity-40 focus:outline-none focus:border-gold";

  return (
    <div className="border border-border bg-surface p-3">
      <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">
        Simulation Control
      </h3>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <label className="flex flex-col gap-0.5">
          <span className="text-[11px] text-text-muted">Scenario</span>
          <select value={selectedScenario} onChange={(e) => onSelectScenario(e.target.value)} disabled={!idle} className={selectCls}>
            {scenarios.map((sc) => (<option key={sc.id} value={sc.id}>{sc.name}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[11px] text-text-muted">Mode</span>
          <select value={selectedMode} onChange={(e) => onSelectMode(e.target.value)} disabled={!idle} className={selectCls}>
            <option value="FAST">FAST</option>
            <option value="FULL">FULL</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[11px] text-text-muted">Strategy</span>
          <select value={selectedStrategy} onChange={(e) => onSelectStrategy(e.target.value)} disabled={!idle} className={selectCls}>
            {strategies.map((st) => (<option key={st.id} value={st.id}>{st.name}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[11px] text-text-muted">Policy</span>
          <select value={selectedPolicy} onChange={(e) => onSelectPolicy(e.target.value)} disabled={!idle} className={selectCls}>
            {policies.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
          </select>
        </label>
      </div>

      <div className="flex gap-1.5">
        {[
          { label: "START", onClick: onStart, disabled: !idle, active: idle },
          { label: "PAUSE", onClick: onPause, disabled: !running, active: running },
          { label: "RESUME", onClick: onResume, disabled: !paused, active: paused },
          { label: "STOP", onClick: onStop, disabled: !running && !paused, active: running || paused },
          { label: "RESET", onClick: onReset, disabled: running || paused, active: false },
        ].map((btn) => (
          <button
            key={btn.label}
            onClick={btn.onClick}
            disabled={btn.disabled}
            className={`px-2.5 py-1 text-[11px] font-semibold tracking-wide border transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${
              btn.active
                ? "bg-black text-white border-black hover:bg-dark-black"
                : "bg-surface text-black border-border hover:border-gold hover:text-gold"
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>

      {simStatus && (
        <div className="text-[11px] text-text-muted mt-2 font-mono">
          FRM <span className="text-black">{simStatus.current_frame}</span>/{simStatus.total_frames}
          {simStatus.elapsed_seconds > 0 && (
            <span className="ml-2">{simStatus.elapsed_seconds.toFixed(1)}s</span>
          )}
        </div>
      )}
    </div>
  );
}
