import type { FrameResult } from "../types/api";

export default function OracleComparison({ latest }: { latest: FrameResult | null }) {
  if (!latest) {
    return (
      <div className="border border-border bg-surface p-3">
        <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Oracle Reference</h3>
        <p className="text-[11px] text-text-muted">No data</p>
      </div>
    );
  }

  const agree = latest.waveform === latest.oracle_waveform;

  return (
    <div className="border border-border bg-surface p-3">
      <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Oracle Reference</h3>
      <table className="w-full text-[12px]">
        <tbody>
          {[
            ["Selected", latest.waveform],
            ["Oracle", latest.oracle_waveform],
            ["Agreement", agree ? "YES" : "NO"],
            ["ACS Regret", latest.ACS_regret.toFixed(4)],
          ].map(([label, value]) => (
            <tr key={label} className="border-b border-border-subtle last:border-b-0">
              <td className="py-1 text-text-muted">{label}</td>
              <td className={`py-1 text-right font-mono ${
                label === "Agreement" ? (agree ? "text-black font-semibold" : "text-gold") : "text-black"
              }`}>
                {value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
