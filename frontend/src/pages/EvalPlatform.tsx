import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "../services/api";
import type {
  GoldenDatasetManifest,
  EvalSuiteInfo,
  EvalRunSummaryData,
  EvalRunFullData,
  EvalGraphData,
  WSEvalEvent,
  CaseType,
  CaseResultStatus,
  RegressionComparisonData,
} from "../types/api";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  Legend,
} from "recharts";

/* ── Color / style constants ─────────────────────────────────────────────── */
const PASS = "#1a1a1a";
const FAIL = "#8a7340";
const OOD_COLOR = "#6b5c3e";

const selectCls =
  "border border-border bg-surface text-black text-[13px] px-2 py-1.5 focus:outline-none focus:border-gold";

/* ── Subcomponents ────────────────────────────────────────────────────────── */

function SuiteCard({
  suite,
  disabled,
  onRun,
}: {
  suite: EvalSuiteInfo;
  disabled: boolean;
  onRun: (id: string) => void;
}) {
  return (
    <button
      onClick={() => onRun(suite.id)}
      disabled={disabled}
      className="border border-border bg-surface p-3 text-left hover:border-gold transition-colors disabled:opacity-40 disabled:cursor-not-allowed group"
    >
      <div className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-1 group-hover:text-black">
        {suite.name}
      </div>
      <div className="text-[11px] text-text-muted">{suite.description}</div>
    </button>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full h-1.5 bg-surface-alt border border-border overflow-hidden">
      <div
        className="h-full bg-gold transition-all duration-200"
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

function StatBlock({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: boolean;
}) {
  return (
    <div className="text-center">
      <div
        className={`text-[20px] font-mono font-semibold ${
          accent ? "text-gold" : "text-black"
        }`}
      >
        {value}
      </div>
      <div className="text-[10px] text-text-muted uppercase tracking-widest mt-0.5">
        {label}
      </div>
    </div>
  );
}

function ResultBadge({ result }: { result: CaseResultStatus }) {
  const styles: Record<CaseResultStatus, string> = {
    PASS: "border-black text-black",
    FAIL: "border-gold text-gold",
    REJECTED: "border-gold text-gold",
    UNAVAILABLE: "border-text-muted text-text-muted",
  };
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-semibold border ${
        styles[result]
      }`}
    >
      {result}
    </span>
  );
}

function TypeBadge({ t }: { t: CaseType }) {
  const styles: Record<CaseType, string> = {
    EXACT: "border-black text-black",
    INTERIOR: "border-text-muted text-text-muted",
    BOUNDARY: "border-gold text-gold",
    OOD: "border-gold text-gold",
  };
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono font-semibold border ${
        styles[t]
      }`}
    >
      {t}
    </span>
  );
}

/* ── Charts ───────────────────────────────────────────────────────────────── */

function LiveCharts({ graphData }: { graphData: EvalGraphData }) {
  const hasData = graphData.case_index.length > 0;
  if (!hasData) return null;

  const chartData = graphData.case_index.map((ci, i) => ({
    case: ci,
    passRate: graphData.pass_rate[i] ?? 0,
    oodReject: graphData.ood_rejection_rate[i] ?? 0,
    berErr: graphData.ber_error[i],
    tpErr: graphData.throughput_error[i],
    acsErr: graphData.acs_error[i],
    conf: graphData.confidence[i],
    berPred: graphData.ber_pred[i],
    berGt: graphData.ber_gt[i],
    pass: graphData.pass_cumulative[i],
    fail: graphData.fail_cumulative[i],
    rej: graphData.rejected_cumulative[i],
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Pass Rate */}
        <div className="border border-border bg-surface p-3">
          <h4 className="text-[10px] font-semibold text-gold uppercase tracking-widest mb-2">
            Pass Rate (cumulative)
          </h4>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e5e0" />
              <XAxis dataKey="case" tick={{ fontSize: 9 }} stroke="#999" />
              <YAxis
                domain={[0, 1]}
                tick={{ fontSize: 9 }}
                stroke="#999"
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  background: "#fff",
                  border: "1px solid #e8e5e0",
                }}
                formatter={(value) => `${(Number(value) * 100).toFixed(1)}%`}
              />
              <Area
                type="monotone"
                dataKey="passRate"
                stroke={PASS}
                fill={PASS}
                fillOpacity={0.05}
                name="Pass Rate"
              />
              <Area
                type="monotone"
                dataKey="oodReject"
                stroke={OOD_COLOR}
                fill={OOD_COLOR}
                fillOpacity={0.05}
                name="OOD Reject Rate"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Cumulative Results */}
        <div className="border border-border bg-surface p-3">
          <h4 className="text-[10px] font-semibold text-gold uppercase tracking-widest mb-2">
            Cumulative Results
          </h4>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e5e0" />
              <XAxis dataKey="case" tick={{ fontSize: 9 }} stroke="#999" />
              <YAxis tick={{ fontSize: 9 }} stroke="#999" />
              <Tooltip
                contentStyle={{
                  fontSize: 11,
                  background: "#fff",
                  border: "1px solid #e8e5e0",
                }}
              />
              <Area
                type="monotone"
                dataKey="pass"
                stackId="1"
                stroke={PASS}
                fill={PASS}
                fillOpacity={0.1}
                name="PASS"
              />
              <Area
                type="monotone"
                dataKey="fail"
                stackId="1"
                stroke={FAIL}
                fill={FAIL}
                fillOpacity={0.1}
                name="FAIL"
              />
              <Area
                type="monotone"
                dataKey="rej"
                stackId="1"
                stroke={OOD_COLOR}
                fill={OOD_COLOR}
                fillOpacity={0.1}
                name="REJECTED"
              />
              <Legend
                iconType="square"
                iconSize={8}
                wrapperStyle={{ fontSize: 10 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* BER Prediction vs Ground Truth scatter */}
      <div className="border border-border bg-surface p-3">
        <h4 className="text-[10px] font-semibold text-gold uppercase tracking-widest mb-2">
          BER: Prediction vs Ground Truth (log₁₀)
        </h4>
        <ResponsiveContainer width="100%" height={160}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e5e0" />
            <XAxis
              type="number"
              dataKey="berGt"
              name="GT"
              tick={{ fontSize: 9 }}
              stroke="#999"
              label={{
                value: "Ground Truth (log₁₀)",
                position: "bottom",
                fontSize: 9,
                offset: -5,
              }}
            />
            <YAxis
              type="number"
              dataKey="berPred"
              name="Pred"
              tick={{ fontSize: 9 }}
              stroke="#999"
              label={{
                value: "Prediction",
                angle: -90,
                position: "insideLeft",
                fontSize: 9,
              }}
            />
            <Tooltip
              contentStyle={{
                fontSize: 11,
                background: "#fff",
                border: "1px solid #e8e5e0",
              }}
            />
            <Scatter
              data={chartData.filter(
                (d) => d.berGt != null && d.berPred != null
              )}
              fill={PASS}
              name="Cases"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ── Case Table ───────────────────────────────────────────────────────────── */

function CaseTable({ cases }: { cases: EvalRunFullData["cases"] }) {
  const [page, setPage] = useState(0);
  const perPage = 20;
  const total = cases.length;
  const totalPages = Math.ceil(total / perPage);
  const slice = cases.slice(page * perPage, (page + 1) * perPage);

  return (
    <div className="border border-border bg-surface">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <h4 className="text-[11px] font-semibold text-gold uppercase tracking-widest">
          Case Results ({total})
        </h4>
        <div className="flex items-center gap-2 text-[11px] text-text-muted">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-1.5 py-0.5 border border-border hover:border-gold disabled:opacity-30"
          >
            &lt;
          </button>
          <span className="font-mono">
            {page + 1}/{totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-1.5 py-0.5 border border-border hover:border-gold disabled:opacity-30"
          >
            &gt;
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-border text-text-muted">
              <th className="text-left px-3 py-1.5 font-medium">Case</th>
              <th className="text-left px-3 py-1.5 font-medium">Type</th>
              <th className="text-left px-3 py-1.5 font-medium">Env</th>
              <th className="text-right px-3 py-1.5 font-medium">Speed</th>
              <th className="text-right px-3 py-1.5 font-medium">SNR</th>
              <th className="text-left px-3 py-1.5 font-medium">Channel</th>
              <th className="text-left px-3 py-1.5 font-medium">Result</th>
              <th className="text-right px-3 py-1.5 font-medium">BER Pred</th>
              <th className="text-right px-3 py-1.5 font-medium">BER GT</th>
              <th className="text-right px-3 py-1.5 font-medium">ACS</th>
              <th className="text-right px-3 py-1.5 font-medium">Conf</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((c) => {
              const predRaw = c.prediction as Record<string, unknown> | null;
              const selected = (predRaw?.selected_waveform as string) ?? "OTFS";
              const predWf = (predRaw != null ? predRaw[selected] : null) as Record<string, number> | null;
              return (
                <tr
                  key={c.case_id}
                  className="border-b border-border-subtle last:border-b-0"
                >
                  <td className="px-3 py-1.5 font-mono">{c.case_id}</td>
                  <td className="px-3 py-1.5">
                    <TypeBadge t={c.case_type} />
                  </td>
                  <td className="px-3 py-1.5">
                    {c.input_conditions.environment}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">
                    {c.input_conditions.speed_kmph.toFixed(0)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">
                    {c.input_conditions.snr_db.toFixed(1)}
                  </td>
                  <td className="px-3 py-1.5">
                    {c.input_conditions.channel_profile}
                  </td>
                  <td className="px-3 py-1.5">
                    <ResultBadge result={c.result} />
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">
                    {predWf?.BER != null ? predWf.BER.toFixed(4) : "N/A"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">
                    {c.ground_truth?.BER != null
                      ? (c.ground_truth.BER as number).toFixed(4)
                      : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">
                    {predWf?.ACS != null ? predWf.ACS.toFixed(4) : "N/A"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">
                    {c.confidence != null ? c.confidence.toFixed(3) : "N/A"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Run History ──────────────────────────────────────────────────────────── */

function RunHistory({
  runs,
  onSelect,
}: {
  runs: EvalRunSummaryData[];
  onSelect: (id: string) => void;
}) {
  return (
    <div className="border border-border bg-surface">
      <div className="px-3 py-2 border-b border-border">
        <h4 className="text-[11px] font-semibold text-gold uppercase tracking-widest">
          Run History
        </h4>
      </div>
      {runs.length === 0 ? (
        <div className="px-3 py-4 text-[11px] text-text-muted">
          No runs yet. Select a suite above to start an evaluation.
        </div>
      ) : (
        <div className="divide-y divide-border-subtle">
          {runs.map((r) => (
            <button
              key={r.run_id}
              onClick={() => onSelect(r.run_id)}
              className="w-full text-left px-3 py-2 hover:bg-surface-alt transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-medium">
                  {r.run_id}
                </span>
                <span
                  className={`text-[10px] font-mono font-semibold ${
                    r.status === "COMPLETED"
                      ? "text-black"
                      : r.status === "FAILED"
                      ? "text-gold"
                      : "text-text-muted"
                  }`}
                >
                  {r.status}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1 text-[10px] text-text-muted">
                <span>{r.suite}</span>
                <span>{r.total_cases} cases</span>
                <span>
                  {r.passed}P / {r.failed}F / {r.rejected}R
                </span>
                <span>{r.elapsed_seconds.toFixed(1)}s</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Comparison View ──────────────────────────────────────────────────────── */

function ComparisonView({
  runAId,
  runBId,
}: {
  runAId: string;
  runBId: string;
}) {
  const [data, setData] = useState<RegressionComparisonData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .evalsCompare(runAId, runBId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"));
  }, [runAId, runBId]);

  if (error) return <div className="text-[12px] text-gold">{error}</div>;
  if (!data) return <div className="text-[11px] text-text-muted">Loading...</div>;

  return (
    <div className="space-y-3">
      <div className="text-[12px] text-text-muted border border-border bg-surface p-3">
        {data.interpretation}
      </div>
      <div className="border border-border bg-surface overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="border-b border-border text-text-muted">
              <th className="text-left px-3 py-1.5 font-medium">Metric</th>
              <th className="text-right px-3 py-1.5 font-medium">Run A</th>
              <th className="text-right px-3 py-1.5 font-medium">Run B</th>
              <th className="text-right px-3 py-1.5 font-medium">Delta</th>
              <th className="text-right px-3 py-1.5 font-medium">% Change</th>
              <th className="text-left px-3 py-1.5 font-medium">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.metric_comparison.map((mc) => (
              <tr
                key={mc.metric}
                className="border-b border-border-subtle last:border-b-0"
              >
                <td className="px-3 py-1.5 font-mono">{mc.metric}</td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {mc.run_a.toFixed(4)}
                </td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {mc.run_b.toFixed(4)}
                </td>
                <td
                  className={`px-3 py-1.5 text-right font-mono ${
                    mc.interpretation === "IMPROVED"
                      ? "text-black font-semibold"
                      : mc.interpretation === "DEGRADED"
                      ? "text-gold font-semibold"
                      : ""
                  }`}
                >
                  {mc.delta >= 0 ? "+" : ""}
                  {mc.delta.toFixed(4)}
                </td>
                <td className="px-3 py-1.5 text-right font-mono">
                  {mc.pct_change >= 0 ? "+" : ""}
                  {mc.pct_change.toFixed(1)}%
                </td>
                <td className="px-3 py-1.5">
                  <span
                    className={`text-[10px] font-mono font-semibold ${
                      mc.interpretation === "IMPROVED"
                        ? "text-black"
                        : mc.interpretation === "DEGRADED"
                        ? "text-gold"
                        : "text-text-muted"
                    }`}
                  >
                    {mc.interpretation}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Main Page ────────────────────────────────────────────────────────────── */

export default function EvalPlatform() {
  const [manifest, setManifest] = useState<GoldenDatasetManifest | null>(null);
  const [suites, setSuites] = useState<EvalSuiteInfo[]>([]);
  const [runs, setRuns] = useState<EvalRunSummaryData[]>([]);
  const [activeRun, setActiveRun] = useState<EvalRunSummaryData | null>(null);
  const [selectedRunData, setSelectedRunData] =
    useState<EvalRunFullData | null>(null);
  const [graphData, setGraphData] = useState<EvalGraphData>({
    elapsed_seconds: [],
    case_index: [],
    case_types: [],
    ber_error: [],
    throughput_error: [],
    cqi_error: [],
    acs_error: [],
    confidence: [],
    regret_ber: [],
    pass_cumulative: [],
    fail_cumulative: [],
    rejected_cumulative: [],
    pass_rate: [],
    ood_rejection_rate: [],
    ber_pred: [],
    ber_gt: [],
    tp_pred: [],
    tp_gt: [],
    cqi_pred: [],
    cqi_gt: [],
  });
  const [view, setView] = useState<
    "dashboard" | "history" | "compare"
  >("dashboard");
  const [compareA, setCompareA] = useState<string>("");
  const [compareB, setCompareB] = useState<string>("");

  const wsRef = useRef<WebSocket | null>(null);

  /* Load initial data */
  useEffect(() => {
    api.evalsGoldenDataset().then(setManifest).catch(() => {});
    api.evalsSuites().then(setSuites).catch(() => {});
    api.evalsListRuns().then(setRuns).catch(() => {});
    api.evalsStatus().then((s) => {
      if (s.running && s.active_run_id) {
        api.evalsGetRun(s.active_run_id).then((rd) => {
          if (rd.summary) setActiveRun(rd.summary);
        }).catch(() => {});
      }
    }).catch(() => {});
  }, []);

  /* WebSocket for live eval progress */
  const connectWs = useCallback(() => {
    if (wsRef.current) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws/evals`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg: WSEvalEvent = JSON.parse(event.data);
        if (msg.type !== "eval_progress") return;

        setActiveRun((prev) => {
          if (!prev || prev.run_id !== msg.run_id) return prev;
          return {
            ...prev,
            status: msg.status,
            progress_pct: msg.progress_pct,
            completed_cases: msg.completed_cases,
            elapsed_seconds: msg.elapsed_seconds,
            current_case_id: msg.current_case_id,
            current_case_type: msg.current_case_type,
            passed: msg.passed,
            failed: msg.failed,
            rejected: msg.rejected,
            unavailable: msg.unavailable,
          };
        });

        if (msg.graph_data_full) {
          setGraphData(msg.graph_data_full);
        }

        if (msg.status === "COMPLETED" || msg.status === "FAILED") {
          api.evalsListRuns().then(setRuns).catch(() => {});
        }
      } catch {
        /* ignore parse errors */
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  }, []);

  useEffect(() => {
    connectWs();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connectWs]);

  /* Start run */
  const handleStartRun = useCallback(
    async (suiteId: string) => {
      if (activeRun) return;
      try {
        const summary = await api.evalsStartRun(suiteId);
        setActiveRun(summary);
        setGraphData({
          elapsed_seconds: [],
          case_index: [],
          case_types: [],
          ber_error: [],
          throughput_error: [],
          cqi_error: [],
          acs_error: [],
          confidence: [],
          regret_ber: [],
          pass_cumulative: [],
          fail_cumulative: [],
          rejected_cumulative: [],
          pass_rate: [],
          ood_rejection_rate: [],
          ber_pred: [],
          ber_gt: [],
          tp_pred: [],
          tp_gt: [],
          cqi_pred: [],
          cqi_gt: [],
        });
        connectWs();
      } catch (e) {
        alert(e instanceof Error ? e.message : "Failed to start run");
      }
    },
    [activeRun, connectWs]
  );

  /* Stop run */
  const handleStopRun = useCallback(async () => {
    try {
      await api.evalsStopRun();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to stop run");
    }
  }, []);

  /* View a specific run */
  const handleViewRun = useCallback(async (runId: string) => {
    setView("history");
    try {
      const data = await api.evalsGetRun(runId);
      setSelectedRunData(data);
      if (data.graph_data) {
        setGraphData(data.graph_data);
      }
    } catch (e) {
      console.error("Failed to load run:", e);
    }
  }, []);

  const isRunning = activeRun?.status === "RUNNING";

  return (
    <div className="p-6 max-w-7xl space-y-5">
      {/* Header */}
      <div className="flex items-baseline justify-between border-b border-border pb-3">
        <h1 className="text-lg font-semibold text-black tracking-tight">
          Evals Platform
        </h1>
        <span className="text-[11px] text-text-muted font-mono">
          EVALUATION FRAMEWORK
        </span>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-border">
        {(
          [
            ["dashboard", "Dashboard"],
            ["history", "Run History"],
            ["compare", "Regression Compare"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={`px-3 py-1.5 text-[11px] font-medium border-b-2 transition-colors ${
              view === key
                ? "border-gold text-black"
                : "border-transparent text-text-muted hover:text-black"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── DASHBOARD ────────────────────────────────────────────────────── */}
      {view === "dashboard" && (
        <div className="space-y-5">
          {/* Golden Dataset */}
          {manifest && (
            <div className="border border-border bg-surface p-4">
              <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">
                Golden Dataset
              </h2>
              <div className="grid grid-cols-6 gap-4">
                <StatBlock
                  label="Rows"
                  value={manifest.total_rows.toLocaleString()}
                />
                <StatBlock
                  label="Scenarios"
                  value={manifest.scenario_count}
                />
                <StatBlock
                  label="Fixed OTFS"
                  value={manifest.fixed_otfs_count}
                />
                <StatBlock
                  label="Oracle"
                  value={manifest.oracle_count}
                />
                <StatBlock label="SNR Range" value={`${manifest.snr_range[0]}–${manifest.snr_range[1]}`} />
                <StatBlock label="Speed Range" value={`${manifest.speed_range[0]}–${manifest.speed_range[1]}`} />
              </div>
              <div className="mt-2 flex items-center gap-3 text-[10px] text-text-muted font-mono">
                <span>
                  Checksum:{" "}
                  <span className={manifest.checksum_verified ? "text-black" : "text-gold"}>
                    {manifest.checksum_verified ? "VERIFIED" : "MISMATCH"}
                  </span>
                </span>
                <span>{manifest.checksum_md5}</span>
              </div>
            </div>
          )}

          {/* Suites */}
          <div className="border border-border bg-surface p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest">
                Run Evaluation Suite
              </h2>
              {isRunning && (
                <button
                  onClick={handleStopRun}
                  className="px-3 py-1 text-[11px] font-semibold tracking-wide border border-gold text-gold hover:bg-gold hover:text-white transition-colors"
                >
                  STOP
                </button>
              )}
            </div>
            <div className="grid grid-cols-4 gap-3">
              {suites.map((s) => (
                <SuiteCard
                  key={s.id}
                  suite={s}
                  disabled={isRunning}
                  onRun={handleStartRun}
                />
              ))}
            </div>
          </div>

          {/* Active Run Progress */}
          {activeRun && (
            <div className="border border-border bg-surface p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-[11px] font-semibold text-gold uppercase tracking-widest">
                  Active Run: {activeRun.run_id}
                </h2>
                <span
                  className={`text-[10px] font-mono font-semibold ${
                    activeRun.status === "RUNNING"
                      ? "text-gold"
                      : activeRun.status === "COMPLETED"
                      ? "text-black"
                      : "text-gold"
                  }`}
                >
                  {activeRun.status}
                </span>
              </div>

              <ProgressBar pct={activeRun.progress_pct} />

              <div className="grid grid-cols-7 gap-3">
                <StatBlock
                  label="Cases"
                  value={`${activeRun.completed_cases}/${activeRun.total_cases}`}
                />
                <StatBlock
                  label="Passed"
                  value={activeRun.passed}
                  accent
                />
                <StatBlock label="Failed" value={activeRun.failed} />
                <StatBlock label="Rejected" value={activeRun.rejected} />
                <StatBlock label="Unavail" value={activeRun.unavailable} />
                <StatBlock
                  label="Elapsed"
                  value={`${activeRun.elapsed_seconds.toFixed(1)}s`}
                />
                <StatBlock
                  label="Current"
                  value={activeRun.current_case_id ?? "—"}
                />
              </div>
            </div>
          )}

          {/* Live Charts */}
          <LiveCharts graphData={graphData} />
        </div>
      )}

      {/* ── RUN HISTORY ──────────────────────────────────────────────────── */}
      {view === "history" && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-1">
              <RunHistory runs={runs} onSelect={handleViewRun} />
            </div>
            <div className="col-span-2 space-y-4">
              {selectedRunData ? (
                <>
                  {/* Report */}
                  {selectedRunData.report && (
                    <div className="border border-border bg-surface p-4">
                      <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">
                        Report — {selectedRunData.report.run_id}
                      </h3>

                      {/* New nested report structure (EXACT/INTERIOR/BOUNDARY/OOD) */}
                      {selectedRunData.report.exact !== undefined ? (
                        <div className="space-y-3">
                          {/* Prediction Accuracy — EXACT */}
                          <div className="border border-border-subtle p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">
                                Prediction Accuracy
                              </span>
                              <span className="text-[10px] text-text-muted">
                                {selectedRunData.report.exact.pass}/{selectedRunData.report.exact.completed} pass ·{" "}
                                {(selectedRunData.report.exact.pass_rate * 100).toFixed(1)}%
                              </span>
                            </div>
                            <p className="text-[10px] text-text-muted mb-2">
                              EXACT — genuine prediction vs. MATLAB-validated ground truth
                            </p>
                            <div className="flex gap-2 text-[11px]">
                              <span className="text-black font-semibold">
                                {selectedRunData.report.exact.pass} pass
                              </span>
                              <span className="text-text-muted">
                                {selectedRunData.report.exact.fail} fail · total {selectedRunData.report.exact.total}
                              </span>
                            </div>
                          </div>

                          {/* Generalization — INTERIOR */}
                          <div className="border border-border-subtle p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">
                                Generalization
                              </span>
                              <span className="text-[10px] text-text-muted">
                                {selectedRunData.report.interior?.model_estimates ?? 0} model estimates
                              </span>
                            </div>
                            <p className="text-[10px] text-text-muted">
                              MODEL ESTIMATE — No ground truth available. Not counted as prediction accuracy.
                            </p>
                          </div>

                          {/* Boundary Robustness — BOUNDARY */}
                          <div className="border border-border-subtle p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">
                                Boundary Robustness
                              </span>
                              <span className="text-[10px] text-text-muted">
                                {selectedRunData.report.boundary?.model_estimates ?? 0} model estimates
                              </span>
                            </div>
                            <p className="text-[10px] text-text-muted">
                              BOUNDARY — no fabricated ground truth. {" "}
                              {selectedRunData.report.boundary?.rejected ?? 0} rejected as out-of-domain.
                            </p>
                          </div>

                          {/* Safety — OOD */}
                          <div className="border border-border-subtle p-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">
                                Safety
                              </span>
                              <span className="text-[10px] text-text-muted">
                                {selectedRunData.report.ood?.total ?? 0} OOD inputs
                              </span>
                            </div>
                            <div className="text-[12px] font-mono">
                              {selectedRunData.report.ood?.rejected ?? 0} / {selectedRunData.report.ood?.total ?? 0} rejected
                            </div>
                            <div className="text-[12px] font-mono">
                              OOD rejection rate: {((selectedRunData.report.ood?.rejection_rate ?? 0) * 100).toFixed(0)}%
                            </div>
                            <p className="text-[10px] text-text-muted mt-1">
                              Fabricated predictions: {selectedRunData.report.ood?.fabricated_predictions ?? 0} (must be 0)
                            </p>
                          </div>

                          {/* Flight metrics for EXACT */}
                          {selectedRunData.report.aggregated_metrics &&
                            Object.keys(selectedRunData.report.aggregated_metrics).length > 0 && (
                              <div className="border border-border-subtle p-3">
                                <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">
                                  Prediction Accuracy Metrics (EXACT)
                                </span>
                                <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-[11px]">
                                  {Object.entries(selectedRunData.report.aggregated_metrics).map(
                                    ([k, v]) => (
                                      <div key={k} className="flex justify-between">
                                        <span className="text-text-muted">{k}</span>
                                        <span className="font-mono">
                                          {typeof v === "number" ? v.toFixed(6) : v}
                                        </span>
                                      </div>
                                    )
                                  )}
                                </div>
                              </div>
                            )}
                        </div>
                      ) : (
                        <>
                          {/* Legacy flat report structure */}
                          <div className="grid grid-cols-6 gap-3">
                            <StatBlock label="Total" value={selectedRunData.report.total_cases} />
                            <StatBlock label="Pass" value={selectedRunData.report.passed} accent />
                            <StatBlock label="Fail" value={selectedRunData.report.failed} />
                            <StatBlock label="Rejected" value={selectedRunData.report.rejected} />
                            <StatBlock label="Unavail" value={selectedRunData.report.unavailable} />
                            <StatBlock label="Time" value={`${selectedRunData.report.elapsed_seconds.toFixed(1)}s`} />
                          </div>
                          {/* By Case Type breakdown */}
                          <div className="mt-3 overflow-x-auto">
                            <table className="w-full text-[11px]">
                              <thead>
                                <tr className="border-b border-border text-text-muted">
                                  <th className="text-left px-2 py-1 font-medium">Type</th>
                                  <th className="text-right px-2 py-1 font-medium">Count</th>
                                  <th className="text-right px-2 py-1 font-medium">Pass</th>
                                  <th className="text-right px-2 py-1 font-medium">Fail</th>
                                  <th className="text-right px-2 py-1 font-medium">Rejected</th>
                                </tr>
                              </thead>
                              <tbody>
                                {Object.entries(selectedRunData.report.by_case_type).map(
                                  ([ct, stats]) => (
                                    <tr
                                      key={ct}
                                      className="border-b border-border-subtle last:border-b-0"
                                    >
                                      <td className="px-2 py-1">
                                        <TypeBadge t={ct as CaseType} />
                                      </td>
                                      <td className="px-2 py-1 text-right font-mono">{stats.count}</td>
                                      <td className="px-2 py-1 text-right font-mono">{stats.pass}</td>
                                      <td className="px-2 py-1 text-right font-mono">{stats.fail}</td>
                                      <td className="px-2 py-1 text-right font-mono">{stats.rejected}</td>
                                    </tr>
                                  )
                                )}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* Charts */}
                  {selectedRunData.graph_data && (
                    <LiveCharts graphData={selectedRunData.graph_data} />
                  )}

                  {/* Cases table */}
                  {selectedRunData.cases && selectedRunData.cases.length > 0 && (
                    <CaseTable cases={selectedRunData.cases} />
                  )}
                </>
              ) : (
                <div className="border border-border bg-surface p-8 text-center text-[12px] text-text-muted">
                  Select a run from the list to view details
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── COMPARE ──────────────────────────────────────────────────────── */}
      {view === "compare" && (
        <div className="space-y-4">
          <div className="border border-border bg-surface p-4">
            <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-3">
              Regression Comparison
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-0.5">
                <span className="text-[11px] text-text-muted">Run A (baseline)</span>
                <select
                  value={compareA}
                  onChange={(e) => setCompareA(e.target.value)}
                  className={selectCls}
                >
                  <option value="">Select run...</option>
                  {runs.map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.run_id} ({r.status})
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-[11px] text-text-muted">Run B (comparison)</span>
                <select
                  value={compareB}
                  onChange={(e) => setCompareB(e.target.value)}
                  className={selectCls}
                >
                  <option value="">Select run...</option>
                  {runs.map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.run_id} ({r.status})
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          {compareA && compareB && compareA !== compareB && (
            <ComparisonView runAId={compareA} runBId={compareB} />
          )}
          {compareA && compareB && compareA === compareB && (
            <div className="text-[12px] text-text-muted border border-border bg-surface p-4">
              Select two different runs to compare.
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="border-t border-border pt-3">
        <p className="text-[10px] text-text-muted">
          Evals Platform — compares AI prediction pipeline output against
          MATLAB-validated Golden Dataset. No ground truth is fabricated from
          AI predictions. Out-of-domain inputs are rejected, never predicted.
        </p>
      </div>
    </div>
  );
}
