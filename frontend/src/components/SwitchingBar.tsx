import type { FrameResult } from "../types/api";

export default function SwitchingBar({
  history,
  switches,
}: {
  history: FrameResult[];
  switches: number;
}) {
  if (history.length === 0) {
    return (
      <div className="border border-border bg-surface p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">Waveform Usage</span>
          <span className="text-[11px] text-text-muted font-mono">SW: {switches}</span>
        </div>
        <div className="h-2 bg-surface-alt" />
      </div>
    );
  }

  const segments: { waveform: string; start: number; end: number }[] = [];
  let segStart = 0;
  let curWaveform = history[0].waveform;

  for (let i = 1; i < history.length; i++) {
    if (history[i].waveform !== curWaveform) {
      segments.push({ waveform: curWaveform, start: segStart, end: i });
      segStart = i;
      curWaveform = history[i].waveform;
    }
  }
  segments.push({ waveform: curWaveform, start: segStart, end: history.length });

  const otfsFrames = history.filter((f) => f.waveform === "OTFS").length;
  const oddmFrames = history.filter((f) => f.waveform === "ODDM").length;

  return (
    <div className="border border-border bg-surface p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">Waveform Usage</span>
        <span className="text-[11px] text-text-muted font-mono">SW: {switches}</span>
      </div>

      <div className="h-2 bg-surface-alt overflow-hidden flex">
        {segments.map((seg, i) => {
          const width = ((seg.end - seg.start) / history.length) * 100;
          return (
            <div
              key={i}
              className={`h-full transition-all duration-300 ${
                seg.waveform === "OTFS" ? "bg-gold" : "bg-black"
              }`}
              style={{ width: `${width}%` }}
              title={`${seg.waveform}: frames ${history[seg.start]?.frame ?? seg.start}-${history[Math.min(seg.end - 1, history.length - 1)]?.frame ?? seg.end}`}
            />
          );
        })}
      </div>

      <div className="flex items-center gap-4 mt-1.5 text-[11px] text-text-muted">
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-1.5 bg-gold inline-block" />
          OTFS ({otfsFrames})
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-1.5 bg-black inline-block" />
          ODDM ({oddmFrames})
        </span>
      </div>
    </div>
  );
}
