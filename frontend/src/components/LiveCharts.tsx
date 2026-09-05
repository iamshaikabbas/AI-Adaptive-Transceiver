import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { FrameResult } from "../types/api";

const CHART_MARGIN = { top: 4, right: 4, left: -20, bottom: 0 };

function MiniChart({
  title,
  data,
  dataKey,
  unit,
  fmt,
  highlight,
}: {
  title: string;
  data: FrameResult[];
  dataKey: keyof FrameResult;
  unit?: string;
  fmt?: (v: number) => string;
  highlight?: boolean;
}) {
  const chartData = data
    .filter((f) => typeof f[dataKey] === "number" && Number.isFinite(f[dataKey] as number))
    .map((f) => ({
      frame: f.frame,
      value: f[dataKey] as number,
    }));

  const lastVal = chartData.length > 0 ? chartData[chartData.length - 1].value : null;

  return (
    <div className="border border-border bg-surface p-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-text-muted uppercase tracking-wide">{title}</span>
        {lastVal !== null && (
          <span className={`text-[12px] font-mono ${highlight ? "text-gold font-semibold" : "text-black"}`}>
            {fmt ? fmt(lastVal) : lastVal.toFixed(4)}{unit ?? ""}
          </span>
        )}
      </div>
      <div className="h-14">
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={CHART_MARGIN}>
              <XAxis dataKey="frame" hide />
              <YAxis hide domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#FFFFFF",
                  border: "1px solid #D9D9D9",
                  borderRadius: 2,
                  fontSize: 11,
                }}
                labelStyle={{ color: "#666666" }}
                formatter={(v) => [typeof v === "number" ? v.toFixed(6) : String(v), title]}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={highlight ? "#C9A227" : "#111111"}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-[11px] text-text-muted">
            Awaiting data
          </div>
        )}
      </div>
    </div>
  );
}

export default function LiveCharts({ history }: { history: FrameResult[] }) {
  const recent = history.slice(-60);

  return (
    <div className="grid grid-cols-2 gap-2">
      <MiniChart title="BER" data={recent} dataKey="BER" fmt={(v) => v.toFixed(4)} highlight />
      <MiniChart title="Throughput" data={recent} dataKey="throughput_bps" unit=" bps" fmt={(v) => (v / 1000).toFixed(1)} />
      <MiniChart title="ACS" data={recent} dataKey="ACS" fmt={(v) => v.toFixed(4)} highlight />
      <MiniChart title="CQI" data={recent} dataKey="CQI" fmt={(v) => v.toFixed(0)} />
    </div>
  );
}
