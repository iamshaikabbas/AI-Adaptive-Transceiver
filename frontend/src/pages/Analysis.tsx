import { useState, useEffect } from "react";
import { api, type GraphEntry } from "../services/api";

const CATEGORY_LABELS: Record<string, string> = {
  "01_system_overview": "System Overview",
  "02_waveform_comparison": "Waveform Comparison",
  "03_snr_analysis": "SNR Analysis",
  "04_mobility_analysis": "Mobility Analysis",
  "05_channel_analysis": "Channel Profiles",
  "06_modulation_analysis": "Modulation Analysis",
  "07_ai_analysis": "AI Decision Analysis",
  "08_oracle_analysis": "Oracle Analysis",
  "09_digital_twin": "Digital Twin",
  "10_summary": "Summary",
};

export default function Analysis() {
  const [graphs, setGraphs] = useState<GraphEntry[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    api.graphsIndex()
      .then(setGraphs)
      .catch(() => {});
  }, []);

  const categories = [...new Set(graphs.map((g) => g.category))];

  const filtered = selectedCategory === "all"
    ? graphs
    : graphs.filter((g) => g.category === selectedCategory);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="border-b border-border pb-2">
        <h1 className="text-lg font-semibold text-black tracking-tight">Analysis</h1>
        <p className="text-[12px] text-text-muted mt-1">
          Phase 7 evaluation graphs — 2,336 operating points across 18 scenarios.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => setSelectedCategory("all")}
          className={`px-2.5 py-1 text-[11px] border transition-colors ${
            selectedCategory === "all"
              ? "bg-black text-white border-black"
              : "bg-surface border-border text-text-muted hover:border-gold hover:text-gold"
          }`}
        >
          ALL ({graphs.length})
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-2.5 py-1 text-[11px] border transition-colors ${
              selectedCategory === cat
                ? "bg-black text-white border-black"
                : "bg-surface border-border text-text-muted hover:border-gold hover:text-gold"
            }`}
          >
            {CATEGORY_LABELS[cat] ?? cat}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((g) => (
          <div
            key={g.graph_id}
            className="border border-border bg-surface overflow-hidden"
          >
            <div
              className="cursor-pointer"
              onClick={() => setExpanded(expanded === g.graph_id ? null : g.graph_id)}
            >
              {expanded === g.graph_id ? (
                <img
                  src={api.graphFileUrl(g.filename)}
                  alt={g.title}
                  className="w-full"
                  loading="lazy"
                />
              ) : (
                <div className="h-32 bg-surface-alt flex items-center justify-center">
                  <img
                    src={api.graphFileUrl(g.filename)}
                    alt={g.title}
                    className="max-h-full object-contain p-2"
                    loading="lazy"
                  />
                </div>
              )}
            </div>
            <div className="px-3 py-2.5">
              <h3 className="text-[13px] font-medium text-black">{g.title}</h3>
              <p className="text-[11px] text-text-muted mt-1 leading-relaxed">{g.description}</p>
              {expanded === g.graph_id && g.interpretation && (
                <p className="text-[11px] text-text-secondary mt-2 leading-relaxed bg-surface-alt border border-border-subtle p-2">
                  {g.interpretation}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
