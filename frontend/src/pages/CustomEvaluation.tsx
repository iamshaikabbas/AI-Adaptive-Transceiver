import { useEffect, useState, useCallback } from "react";
import { api } from "../services/api";
import type {
  CustomEvaluationRequest,
  CustomEvaluationResponse,
  CustomSchemaResponse,
  WaveformPredictionModel,
} from "../types/api";

function CoverageBadge({ coverage }: { coverage: string }) {
  const labels: Record<string, string> = {
    EXACT: "EXACT",
    COVERED: "COVERED",
    NEAR_BOUNDARY: "NEAR BOUNDARY",
    OOD: "OUTSIDE COVERAGE",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-mono font-semibold border ${
      coverage === "OOD" ? "border-gold text-gold" : "border-black text-black"
    }`}>
      {labels[coverage] ?? coverage}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[11px] font-mono font-semibold border ${
      confidence === "UNAVAILABLE" ? "border-gold text-gold" : "border-black text-black"
    }`}>
      {confidence}
    </span>
  );
}

function WaveformPanel({ title, pred }: { title: string; pred: WaveformPredictionModel | null }) {
  if (!pred) return <div className="text-[11px] text-text-muted">No prediction</div>;
  return (
    <div className="space-y-2">
      <h4 className="text-[11px] font-semibold text-gold uppercase tracking-widest">{title} ({pred.detector})</h4>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-border text-text-muted">
            <th className="text-left py-1 font-medium">Metric</th>
            <th className="text-right py-1 font-medium">Value</th>
            <th className="text-right py-1 font-medium">Uncertainty</th>
            <th className="text-right py-1 font-medium">p10-p90</th>
          </tr>
        </thead>
        <tbody>
          {[
            ["BER", pred.BER?.mean, pred.BER?.std, pred.BER?.p10, pred.BER?.p90, (v: number) => v.toFixed(6)],
            ["Throughput", pred.throughput_bps?.mean, pred.throughput_bps?.std, pred.throughput_bps?.p10, pred.throughput_bps?.p90, (v: number) => `${(v / 1000).toFixed(1)} kbps`],
            ["CQI", pred.CQI?.mean, pred.CQI?.std, pred.CQI?.p10, pred.CQI?.p90, (v: number) => v.toFixed(1)],
            ["ACS", pred.ACS?.mean, pred.ACS?.std, pred.ACS?.p10, pred.ACS?.p90, (v: number) => v.toFixed(4)],
            ["PER", pred.PER?.mean, pred.PER?.std, pred.PER?.p10, pred.PER?.p90, (v: number) => v.toFixed(4)],
            ["Spectral Eff.", pred.spectral_efficiency?.mean, pred.spectral_efficiency?.std, pred.spectral_efficiency?.p10, pred.spectral_efficiency?.p90, (v: number) => v.toFixed(2)],
          ].map(([label, mean, std, p10, p90, fmt]) => (
            <tr key={label as string} className="border-b border-border-subtle last:border-b-0">
              <td className="py-1 text-text-muted">{label as string}</td>
              <td className="py-1 text-right text-black font-mono font-medium">
                {mean != null ? (fmt as (v: number) => string)(mean as number) : "N/A"}
              </td>
              <td className="py-1 text-right font-mono text-text-muted">
                {std != null ? `±${(std as number).toFixed(4)}` : ""}
              </td>
              <td className="py-1 text-right font-mono text-text-muted text-[11px]">
                {p10 != null && p90 != null ? `[${(p10 as number).toFixed(3)}, ${(p90 as number).toFixed(3)}]` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CustomEvaluation() {
  const [schema, setSchema] = useState<CustomSchemaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CustomEvaluationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<CustomEvaluationRequest>({
    environment: "Urban",
    speed_kmph: 25.0,
    snr_db: 10.0,
    channel_profile: "EVA",
    modulation: 4,
    detector: "MRC",
  });

  useEffect(() => { api.getCustomSchema().then(setSchema).catch(() => {}); }, []);

  const handleSubmit = useCallback(async () => {
    setLoading(true); setError(null); setResult(null);
    try { setResult(await api.evaluateCustom(form)); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Evaluation failed"); }
    finally { setLoading(false); }
  }, [form]);

  const updateField = <K extends keyof CustomEvaluationRequest>(key: K, value: CustomEvaluationRequest[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const selectCls = "w-full border border-border bg-surface text-black text-[13px] px-2 py-1.5 focus:outline-none focus:border-gold";
  const inputCls = "w-full border border-border bg-surface text-black text-[13px] px-2 py-1.5 focus:outline-none focus:border-gold font-mono";

  return (
    <div className="p-6 max-w-5xl space-y-5">
      <div className="flex items-baseline justify-between border-b border-border pb-3">
        <h1 className="text-lg font-semibold text-black tracking-tight">Custom Operating Point</h1>
        <span className="text-[11px] text-text-muted font-mono">MODEL-BASED EVALUATION</span>
      </div>

      <p className="text-[12px] text-text-muted">
        Evaluate a user-defined operating condition using the validated dataset and Phase 3 regression models.
      </p>

      {/* Input Form */}
      <div className="border border-border bg-surface p-4">
        <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-3">Input Parameters</h2>
        <div className="grid grid-cols-3 gap-3">
          <label className="flex flex-col gap-0.5">
            <span className="text-[11px] text-text-muted">Environment</span>
            <select value={form.environment} onChange={(e) => updateField("environment", e.target.value)} className={selectCls}>
              {schema?.supported_environments.map((env) => (<option key={env} value={env}>{env}</option>))}
            </select>
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[11px] text-text-muted">Speed (km/h)</span>
            <input type="number" min={0} step={0.1} value={form.speed_kmph} onChange={(e) => updateField("speed_kmph", parseFloat(e.target.value) || 0)} className={inputCls} />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[11px] text-text-muted">SNR (dB)</span>
            <input type="number" step={0.1} value={form.snr_db} onChange={(e) => updateField("snr_db", parseFloat(e.target.value) || 0)} className={inputCls} />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[11px] text-text-muted">Channel Profile</span>
            <select value={form.channel_profile} onChange={(e) => updateField("channel_profile", e.target.value)} className={selectCls}>
              {schema?.supported_channel_profiles.map((ch) => (<option key={ch} value={ch}>{ch}</option>))}
            </select>
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[11px] text-text-muted">Modulation</span>
            <select value={form.modulation} onChange={(e) => updateField("modulation", parseInt(e.target.value))} className={selectCls}>
              {schema?.supported_modulations.map((mod) => (
                <option key={mod} value={mod}>{mod === 4 ? "QPSK (4)" : mod === 16 ? "16-QAM (16)" : `${mod}-QAM (${mod})`}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="text-[11px] text-text-muted">Detector</span>
            <select value={form.detector ?? ""} onChange={(e) => updateField("detector", e.target.value || undefined)} className={selectCls}>
              <option value="">Auto</option>
              {schema?.supported_detectors.map((det) => (<option key={det} value={det}>{det}</option>))}
            </select>
          </label>
        </div>
        <button onClick={handleSubmit} disabled={loading}
          className="mt-3 px-4 py-1.5 text-[12px] font-semibold tracking-wide border border-black bg-black text-white hover:bg-dark-black transition-colors disabled:opacity-40">
          {loading ? "EVALUATING..." : "EVALUATE"}
        </button>
      </div>

      {error && (
        <div className="border border-gold bg-active-light px-3 py-2 text-[12px] text-black font-mono">{error}</div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Coverage & Confidence */}
          <div className="border border-border bg-surface p-4">
            <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Model Coverage</h2>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-muted">Coverage:</span>
                <CoverageBadge coverage={result.coverage} />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-muted">Confidence:</span>
                <ConfidenceBadge confidence={result.confidence} />
              </div>
              <div className="text-[11px] text-text-muted font-mono ml-auto">
                Doppler: {result.input.doppler_hz.toFixed(1)} Hz
              </div>
            </div>
          </div>

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="space-y-1">
              {result.warnings.map((w, i) => (
                <div key={i} className="border border-gold bg-active-light px-3 py-2 text-[12px] text-black font-mono">{w}</div>
              ))}
            </div>
          )}

          {/* Predictions */}
          <div className="border border-border bg-surface p-4">
            <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-3">Predicted Performance</h2>
            <div className="grid grid-cols-2 gap-6">
              <WaveformPanel title="OTFS" pred={result.predictions.OTFS} />
              <WaveformPanel title="ODDM" pred={result.predictions.ODDM} />
            </div>
          </div>

          {/* Waveform Selection */}
          <div className="border border-border bg-surface p-4">
            <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Waveform Selection</h2>
            <table className="w-full text-[12px]">
              <tbody>
                {[
                  ["Policy", result.decision.policy_version],
                  ["Selected", result.decision.selected_waveform ?? "N/A"],
                  ["Objective", result.decision.objective],
                  ["OTFS ACS", result.decision.predicted_OTFS_ACS?.toFixed(4) ?? "N/A"],
                  ["ODDM ACS", result.decision.predicted_ODDM_ACS?.toFixed(4) ?? "N/A"],
                  ["Difference", result.decision.predicted_OTFS_ACS != null && result.decision.predicted_ODDM_ACS != null
                    ? `${(result.decision.predicted_OTFS_ACS - result.decision.predicted_ODDM_ACS) >= 0 ? "+" : ""}${(result.decision.predicted_OTFS_ACS - result.decision.predicted_ODDM_ACS).toFixed(4)}`
                    : "N/A"],
                ].map(([label, value]) => (
                  <tr key={label} className="border-b border-border-subtle last:border-b-0">
                    <td className="py-1 text-text-muted">{label}</td>
                    <td className="py-1 text-right text-black font-mono font-medium">{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.decision.reason && (
              <div className="mt-2 text-[11px] text-text-muted bg-surface-alt border border-border-subtle px-2 py-1.5 font-mono">
                {result.decision.reason}
              </div>
            )}
          </div>

          {/* Nearest Neighbors */}
          {result.nearest_neighbors.length > 0 && (
            <div className="border border-border bg-surface p-4">
              <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">Nearest Validated Operating Points</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-border text-text-muted">
                      <th className="text-left py-1 font-medium">#</th>
                      <th className="text-left py-1 font-medium">Distance</th>
                      <th className="text-left py-1 font-medium">Scenario</th>
                      <th className="text-left py-1 font-medium">Frame</th>
                      <th className="text-right py-1 font-medium">&Delta;Speed</th>
                      <th className="text-right py-1 font-medium">&Delta;SNR</th>
                      <th className="text-right py-1 font-medium">OTFS BER</th>
                      <th className="text-right py-1 font-medium">OTFS ACS</th>
                      <th className="text-right py-1 font-medium">ODDM ACS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.nearest_neighbors.map((n, i) => (
                      <tr key={i} className="border-b border-border-subtle last:border-b-0">
                        <td className="py-1 text-text-muted">{i + 1}</td>
                        <td className="py-1 font-mono font-medium">{n.distance.toFixed(4)}</td>
                        <td className="py-1">{n.source_scenario}</td>
                        <td className="py-1 font-mono">{n.source_frame}</td>
                        <td className="py-1 text-right font-mono">{n.speed_difference >= 0 ? "+" : ""}{n.speed_difference.toFixed(1)}</td>
                        <td className="py-1 text-right font-mono">{n.snr_difference >= 0 ? "+" : ""}{n.snr_difference.toFixed(2)}</td>
                        <td className="py-1 text-right font-mono">{n.otfs_ber?.toFixed(4) ?? "N/A"}</td>
                        <td className="py-1 text-right font-mono">{n.otfs_acs?.toFixed(4) ?? "N/A"}</td>
                        <td className="py-1 text-right font-mono">{n.oddm_acs?.toFixed(4) ?? "N/A"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Disclaimer */}
          <div className="border-t border-border pt-3">
            <p className="text-[11px] text-text-muted">
              Custom operating points are model-based estimates unless an exact validated operating point exists.
              The model is not a substitute for physical measurement or RF validation outside the training/model domain.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
