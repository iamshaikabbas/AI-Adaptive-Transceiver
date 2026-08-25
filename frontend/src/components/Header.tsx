import type { SimulationStatus } from "../types/api";
import type { ConnectionStatus } from "../hooks/useSimulation";

const STATUS_LABELS: Record<string, string> = {
  CREATED: "READY",
  RUNNING: "RUNNING",
  PAUSED: "PAUSED",
  STOPPED: "STOPPED",
  COMPLETED: "COMPLETE",
  ERROR: "ERROR",
};

export default function Header({
  connection,
  simStatus,
}: {
  connection: ConnectionStatus;
  simStatus: SimulationStatus | null;
}) {
  const statusLabel = simStatus ? STATUS_LABELS[simStatus.status] ?? simStatus.status : "IDLE";
  const isConnected = connection === "connected";

  return (
    <header className="h-14 bg-dark-black flex items-center px-4 gap-6 flex-shrink-0 border-b border-dark-black">
      {/* Left: Title */}
      <div className="flex items-baseline gap-3 min-w-0">
        <h1 className="text-white text-sm font-semibold tracking-wide whitespace-nowrap">
          AI-Adaptive Transceiver
        </h1>
        <span className="text-gold-light text-xs whitespace-nowrap hidden sm:inline">
          Digital Twin &amp; Performance Console
        </span>
      </div>

      {/* Right: Status */}
      <div className="ml-auto flex items-center gap-5 text-xs text-white/70 font-mono whitespace-nowrap">
        {simStatus && simStatus.scenario && (
          <span>
            <span className="text-white/40 mr-1">SCN</span>
            <span className="text-white">{simStatus.scenario}</span>
          </span>
        )}
        {simStatus && (
          <span>
            <span className="text-white/40 mr-1">FRM</span>
            <span className="text-white">{simStatus.current_frame}/{simStatus.total_frames}</span>
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-gold" : "bg-white/30"}`} />
          <span className={isConnected ? "text-white" : "text-white/50"}>
            {isConnected ? "CONNECTED" : "OFFLINE"}
          </span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${
            statusLabel === "RUNNING" ? "bg-gold" :
            statusLabel === "PAUSED" ? "bg-gold-light" :
            "bg-white/30"
          }`} />
          <span className="text-white">{statusLabel}</span>
        </span>
      </div>
    </header>
  );
}
