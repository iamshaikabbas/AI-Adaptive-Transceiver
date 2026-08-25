import type { AIInfo, SimulationState } from "../types/api";

export default function AIDecisionPanel({
  ai,
  state,
  switched,
}: {
  ai: AIInfo | null;
  state: SimulationState | null;
  switched?: boolean;
}) {
  const waveform = ai?.selected_waveform ?? state?.waveform ?? "---";
  const otfsACS = ai?.predicted_otfs_acs != null ? ai.predicted_otfs_acs.toFixed(4) : "---";
  const oddmACS = ai?.predicted_oddm_acs != null ? ai.predicted_oddm_acs.toFixed(4) : "---";
  const confidence = ai?.confidence != null ? (ai.confidence * 100).toFixed(1) + "%" : "---";

  return (
    <div className="border border-border bg-surface p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest">
          Waveform Selection
        </h3>
        {switched && (
          <span className="text-[10px] font-mono text-gold border border-gold px-1.5 py-0.5">SWITCH</span>
        )}
      </div>

      <table className="w-full text-[12px] mb-2">
        <tbody>
          <tr className="border-b border-border-subtle">
            <td className="py-1 text-text-muted">Selected</td>
            <td className="py-1 text-right text-black font-semibold font-mono">{waveform}</td>
          </tr>
          <tr className="border-b border-border-subtle">
            <td className="py-1 text-text-muted">Policy</td>
            <td className="py-1 text-right text-black font-mono">Phase 3</td>
          </tr>
          <tr className="border-b border-border-subtle">
            <td className="py-1 text-text-muted">Confidence</td>
            <td className="py-1 text-right text-black font-mono">{confidence}</td>
          </tr>
          <tr className="border-b border-border-subtle">
            <td className="py-1 text-text-muted">ACS (OTFS)</td>
            <td className="py-1 text-right font-mono">{otfsACS}</td>
          </tr>
          <tr>
            <td className="py-1 text-text-muted">ACS (ODDM)</td>
            <td className="py-1 text-right font-mono">{oddmACS}</td>
          </tr>
        </tbody>
      </table>

      {ai?.reason && (
        <div className="text-[11px] text-text-muted bg-surface-alt border border-border-subtle px-2 py-1.5 font-mono leading-relaxed">
          {ai.reason}
        </div>
      )}
    </div>
  );
}
