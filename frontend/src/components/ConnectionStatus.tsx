import type { ConnectionStatus } from "../hooks/useSimulation";

export default function ConnectionStatus({ status }: { status: ConnectionStatus }) {
  const colors = {
    connected: "text-success",
    connecting: "text-warning",
    disconnected: "text-error",
  };

  return (
    <span className={`text-xs ${colors[status]}`}>
      {status === "connected" && "Backend Connected"}
      {status === "connecting" && "Connecting..."}
      {status === "disconnected" && "Backend Offline"}
    </span>
  );
}
