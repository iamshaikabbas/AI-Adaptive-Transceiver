import type { AIInfo } from "../types/api";

export default function WaveformComparison({ ai }: { ai: AIInfo | null }) {
  const otfsACS = ai?.predicted_otfs_acs != null ? ai.predicted_otfs_acs.toFixed(4) : "---";
  const oddmACS = ai?.predicted_oddm_acs != null ? ai.predicted_oddm_acs.toFixed(4) : "---";
  const selected = ai?.selected_waveform;

  return (
    <div className="border border-border bg-surface p-3">
      <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">
        Waveform Comparison
      </h3>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-border text-text-muted">
            <th className="text-left py-1 font-medium">Metric</th>
            <th className="text-center py-1 font-medium">OTFS</th>
            <th className="text-center py-1 font-medium">ODDM</th>
          </tr>
        </thead>
        <tbody>
          <tr className={`border-b border-border-subtle ${selected === "OTFS" ? "bg-active-light" : ""}`}>
            <td className="py-1 text-text-muted">ACS</td>
            <td className="py-1 text-center font-mono">{otfsACS}</td>
            <td className="py-1 text-center font-mono">{oddmACS}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
