import type { FrameResult } from "../types/api";

export default function Timeline({
  history,
  totalFrames,
  currentFrame,
}: {
  history: FrameResult[];
  totalFrames: number;
  currentFrame: number;
}) {
  const switches = history.filter((f) => f.switched).map((f) => f.frame);

  return (
    <div className="border border-border bg-surface p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-gold uppercase tracking-widest">Timeline</span>
        <span className="text-[11px] text-text-muted font-mono">
          {currentFrame}/{totalFrames}
        </span>
      </div>

      <div className="relative h-2 bg-surface-alt overflow-hidden">
        {totalFrames > 0 && (
          <div
            className="absolute inset-y-0 left-0 bg-black transition-all duration-300"
            style={{ width: `${(currentFrame / totalFrames) * 100}%` }}
          />
        )}

        {switches.map((frame) => (
          <div
            key={frame}
            className="absolute top-0 w-0.5 h-2 bg-gold"
            style={{ left: `${(frame / Math.max(totalFrames, 1)) * 100}%` }}
            title={`Switch at frame ${frame}`}
          />
        ))}
      </div>

      <div className="flex items-center gap-3 mt-1.5 text-[11px] text-text-muted">
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 bg-gold inline-block" />
          Switch
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-0.5 bg-black inline-block" />
          Progress
        </span>
      </div>
    </div>
  );
}
