export default function Overview() {
  return (
    <div className="p-6 max-w-5xl space-y-5">
      {/* Title bar */}
      <div className="flex items-baseline justify-between border-b border-border pb-3">
        <h1 className="text-lg font-semibold text-black tracking-tight">Overview</h1>
        <span className="text-xs text-text-muted font-mono">SYSTEM STATUS BOARD</span>
      </div>

      {/* System status table */}
      <section>
        <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">System Status</h2>
        <div className="border border-border bg-surface">
          <table className="w-full text-[13px]">
            <tbody>
              {[
                { component: "Simulation Engine", status: "READY" },
                { component: "Phase 6 Dataset", status: "LOADED" },
                { component: "Phase 3 Models", status: "READY" },
                { component: "MATLAB Bridge", status: "STANDBY" },
                { component: "WebSocket", status: "LISTENING" },
                { component: "Custom Evaluation", status: "READY" },
              ].map((item) => (
                <tr key={item.component} className="border-b border-border-subtle last:border-b-0">
                  <td className="px-3 py-1.5 text-text-secondary">{item.component}</td>
                  <td className="px-3 py-1.5 text-right">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-gold" />
                      <span className="text-black font-medium text-xs font-mono">{item.status}</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Operating conditions reference */}
      <section>
        <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Reference Evaluation</h2>
        <div className="grid grid-cols-2 gap-3">
          <div className="border border-border bg-surface p-3">
            <h3 className="text-[11px] text-text-muted uppercase tracking-wide mb-2">Phase 6 Final Evaluation</h3>
            <table className="w-full text-[13px]">
              <tbody>
                {[
                  ["Scenarios", "18 (A-R)"],
                  ["Strategies", "4 (fixed OTFS, fixed ODDM, AI adaptive, oracle)"],
                  ["Total Frames", "2,336 rows"],
                  ["AI Switches", "22"],
                  ["Oracle Agreement", "82.7%"],
                  ["Mean ACS Regret", "0.0099"],
                ].map(([label, value]) => (
                  <tr key={label} className="border-b border-border-subtle last:border-b-0">
                    <td className="py-1 text-text-muted">{label}</td>
                    <td className="py-1 text-right text-black font-medium">{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border border-border bg-surface p-3">
            <h3 className="text-[11px] text-text-muted uppercase tracking-wide mb-2">Key Metrics</h3>
            <table className="w-full text-[13px]">
              <tbody>
                {[
                  ["BER", "Bit Error Rate — fraction of received bits in error"],
                  ["ACS", "Adaptive Communication Score — composite quality metric"],
                  ["CQI", "Channel Quality Indicator — integer 0-15"],
                  ["Oracle Agreement", "Fraction of frames where AI selected the oracle-optimal waveform"],
                ].map(([label, desc]) => (
                  <tr key={label} className="border-b border-border-subtle last:border-b-0">
                    <td className="py-1 text-black font-medium whitespace-nowrap pr-3">{label}</td>
                    <td className="py-1 text-text-muted text-xs">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section>
        <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Signal Path</h2>
        <div className="border border-border bg-surface p-3 font-mono text-[12px] text-text-secondary leading-relaxed">
          <pre>{`TRANSMITTER ──→ WAVEFORM (OTFS / ODDM) ──→ CHANNEL ──→ RECEIVER ──→ DETECTOR (MRC / LMMSE) ──→ METRICS`}</pre>
        </div>
      </section>

      {/* Footer note */}
      <div className="border-t border-border pt-3">
        <p className="text-[11px] text-text-muted">
          Phase 3 AI policy is canonical. Phase 4 is experimental. Phase 6 dataset is the single source of truth.
          Custom operating points are model-based estimates unless an exact validated operating point exists.
        </p>
      </div>
    </div>
  );
}
