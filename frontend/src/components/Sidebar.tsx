const SECTIONS = [
  {
    label: "MONITOR",
    items: [
      { id: "overview", label: "Overview" },
      { id: "digital-twin", label: "Digital Twin" },
    ],
  },
  {
    label: "EVALUATION",
    items: [
      { id: "custom-eval", label: "Custom Eval" },
      { id: "evals-platform", label: "Evals Platform" },
    ],
  },
  {
    label: "ANALYSIS",
    items: [
      { id: "analysis", label: "Results" },
    ],
  },
  {
    label: "SYSTEM",
    items: [
      { id: "about", label: "About" },
    ],
  },
];

export default function Sidebar({
  active,
  onNavigate,
}: {
  active: string;
  onNavigate: (id: string) => void;
}) {
  return (
    <aside className="w-44 bg-surface border-r border-border flex-shrink-0 hidden md:flex flex-col">
      <nav className="flex-1 py-2">
        {SECTIONS.map((section) => (
          <div key={section.label} className="mb-1">
            <div className="px-4 pt-3 pb-1 text-[10px] font-semibold text-gold tracking-widest uppercase">
              {section.label}
            </div>
            {section.items.map((item) => {
              const isActive = active === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`w-full text-left px-4 py-1.5 text-[13px] transition-colors border-l-2 ${
                    isActive
                      ? "bg-surface text-black border-gold font-medium"
                      : "bg-transparent text-text-secondary border-transparent hover:text-black hover:bg-surface-alt"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="px-4 py-2 border-t border-border">
        <div className="text-[10px] text-text-muted font-mono">CONSOLE v11.1</div>
      </div>
    </aside>
  );
}
