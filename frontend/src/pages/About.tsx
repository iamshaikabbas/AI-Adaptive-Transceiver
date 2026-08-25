export default function About() {
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="border-b border-border pb-2">
        <h1 className="text-lg font-semibold text-black tracking-tight">About</h1>
        <p className="text-[12px] text-text-muted mt-1">Project overview and technical details</p>
      </div>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Project</h2>
        <p className="text-[12px] text-text-secondary leading-relaxed">
          Adaptive wireless transceiver system that dynamically switches between OTFS and ODDM
          waveforms based on real-time channel conditions. The system learns an optimal switching
          policy validated against an oracle (genie-aided) benchmark.
        </p>
      </section>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Digital Twin</h2>
        <p className="text-[12px] text-text-secondary leading-relaxed">
          Software-only simulation environment modeling channel conditions across 5 mobility
          scenarios (Pedestrian, Urban, UrbanFast, Highway, HighSpeedRail) with 3 channel
          profiles (EPA, EVA, ETU) and modulations from 4-QAM to 64-QAM.
        </p>
        <p className="text-[11px] text-text-muted mt-2">
          No RF hardware. No SDR. No physical wireless channel.
        </p>
      </section>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Waveforms</h2>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-surface border border-border p-3">
            <div className="text-[12px] font-semibold text-black mb-1">OTFS</div>
            <p className="text-[11px] text-text-secondary leading-relaxed">
              Orthogonal Time Frequency Space. Operates in the delay-Doppler domain.
              Resilient to high-mobility channel conditions.
            </p>
          </div>
          <div className="bg-surface border border-border p-3">
            <div className="text-[12px] font-semibold text-black mb-1">ODDM</div>
            <p className="text-[11px] text-text-secondary leading-relaxed">
              Orthogonal Delay Doppler Modulation. Alternative waveform with different
              delay-Doppler domain characteristics.
            </p>
          </div>
        </div>
      </section>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Phase 3 AI Policy</h2>
        <p className="text-[12px] text-text-secondary leading-relaxed">
          Observes channel state information (SNR, Doppler, speed, channel profile) and makes
          frame-by-frame waveform switching decisions. Trained to approximate the oracle
          benchmark while maintaining low switching overhead. 82.7% oracle agreement across
          18 scenarios with only 22 switches.
        </p>
      </section>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Evaluation Metrics</h2>
        <div className="grid grid-cols-2 gap-2 text-[12px]">
          <div className="flex gap-2">
            <span className="font-medium text-black w-20 shrink-0">BER</span>
            <span className="text-text-secondary">Bit Error Rate — signal integrity</span>
          </div>
          <div className="flex gap-2">
            <span className="font-medium text-black w-20 shrink-0">ACS</span>
            <span className="text-text-secondary">Adaptive Criterion Score — waveform quality</span>
          </div>
          <div className="flex gap-2">
            <span className="font-medium text-black w-20 shrink-0">CQI</span>
            <span className="text-text-secondary">Channel Quality Indicator</span>
          </div>
          <div className="flex gap-2">
            <span className="font-medium text-black w-20 shrink-0">Throughput</span>
            <span className="text-text-secondary">Effective data rate in kbps</span>
          </div>
        </div>
      </section>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Architecture</h2>
        <pre className="text-[11px] text-text-secondary font-mono leading-relaxed bg-surface border border-border p-4 overflow-x-auto">
{`Environment
    |
    v
Digital Twin (MATLAB dt_step_frame.m)
    |
    v
Phase 3 AI Policy (ai_engine_v2.py)
    |
    v
OTFS / ODDM Selection
    |
    v
Channel Model (EPA / EVA / ETU)
    |
    v
Receiver (MRC Detection)
    |
    v
Metrics (BER, ACS, CQI, Throughput)`}
        </pre>
      </section>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Limitations</h2>
        <ul className="text-[12px] text-text-secondary space-y-1.5 list-disc list-inside">
          <li>Simplified channel models; real-world propagation may differ.</li>
          <li>Phase 3 policy trained on specific scenario distributions.</li>
          <li>Switching overhead is modeled but may vary in practice.</li>
          <li>No hardware impairments or RF front-end non-linearities.</li>
          <li>Oracle represents an upper bound achievable only with perfect channel knowledge.</li>
        </ul>
      </section>

      <section className="border-t border-border pt-5">
        <h2 className="text-[13px] font-semibold text-black mb-2">Technology</h2>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          {["MATLAB", "Python", "FastAPI", "React", "TypeScript", "Tailwind CSS", "Recharts", "Vite", "WebSocket"].map((t) => (
            <span key={t} className="bg-surface border border-border text-text-secondary px-2 py-1">
              {t}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
