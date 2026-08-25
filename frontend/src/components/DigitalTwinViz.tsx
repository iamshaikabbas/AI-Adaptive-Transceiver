import type { SimulationState } from "../types/api";

const ENV_LABELS: Record<string, string> = {
  Pedestrian: "Pedestrian",
  Urban: "Urban",
  UrbanFast: "Urban Fast",
  Highway: "Highway",
  HighSpeedRail: "High-Speed Rail",
};

export default function DigitalTwinViz({ state }: { state: SimulationState | null }) {
  const env = state?.environment ?? "---";
  const speed = state?.speed_kmph ?? 0;
  const snr = state?.snr_db ?? 0;
  const waveform = state?.waveform ?? "---";
  const snrBars = Math.max(1, Math.min(5, Math.round(snr / 6)));

  return (
    <div className="border border-border bg-surface p-3">
      <h3 className="text-[11px] font-semibold text-gold uppercase tracking-widest mb-2">
        Signal Path
      </h3>

      <svg viewBox="0 0 600 130" className="w-full" style={{ maxHeight: 140 }}>
        {/* TX block */}
        <rect x="30" y="25" width="90" height="70" fill="#F7F7F5" stroke="#D9D9D9" strokeWidth="1" />
        <text x="75" y="52" textAnchor="middle" fill="#111111" fontSize="11" fontWeight="600">TX</text>
        <text x="75" y="68" textAnchor="middle" fill="#666666" fontSize="9">Transmitter</text>

        {/* Signal path TX → Channel */}
        <line x1="120" y1="60" x2="195" y2="60" stroke="#111111" strokeWidth="1" strokeDasharray="4 2" />

        {/* Channel block */}
        <rect x="195" y="10" width="210" height="100" fill="#F7F7F5" stroke="#D9D9D9" strokeWidth="1" />
        <text x="300" y="32" textAnchor="middle" fill="#111111" fontSize="11" fontWeight="600">
          {ENV_LABELS[env] ?? env}
        </text>
        <text x="300" y="48" textAnchor="middle" fill="#666666" fontSize="9">
          {state?.channel_profile ?? "---"} | {state?.modulation ?? "-"} QAM
        </text>
        <text x="300" y="64" textAnchor="middle" fill="#999999" fontSize="9">
          Speed {speed.toFixed(0)} km/h · Doppler {(state?.doppler_hz ?? 0).toFixed(1)} Hz
        </text>
        <text x="300" y="80" textAnchor="middle" fill="#999999" fontSize="9">
          SNR {snr.toFixed(1)} dB
        </text>

        {/* SNR indicator */}
        {[0, 1, 2, 3, 4].map((i) => (
          <rect
            key={`snr${i}`}
            x={262 + i * 14}
            y={90}
            width={10}
            height={6}
            fill={i < snrBars ? "#111111" : "#D9D9D9"}
          />
        ))}

        {/* Signal path Channel → RX */}
        <line x1="405" y1="60" x2="480" y2="60" stroke="#111111" strokeWidth="1" strokeDasharray="4 2" />

        {/* RX block */}
        <rect x="480" y="25" width="90" height="70" fill="#F7F7F5" stroke="#D9D9D9" strokeWidth="1" />
        <text x="525" y="52" textAnchor="middle" fill="#111111" fontSize="11" fontWeight="600">RX</text>
        <text x="525" y="68" textAnchor="middle" fill="#666666" fontSize="9">Receiver</text>

        {/* Active waveform label */}
        <text x="300" y="125" textAnchor="middle" fill="#C9A227" fontSize="10" fontWeight="600">
          Active: {waveform}
        </text>
      </svg>
    </div>
  );
}
