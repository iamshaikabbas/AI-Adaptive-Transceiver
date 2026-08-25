export default function MetricCard({
  label,
  value,
  unit,
}: {
  label: string;
  value: string | number;
  unit?: string;
}) {
  return (
    <div className="bg-surface border border-border rounded-md px-3 py-2">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="flex items-baseline gap-1 mt-0.5">
        <span className="text-sm font-semibold text-text-primary">{value}</span>
        {unit && <span className="text-xs text-text-muted">{unit}</span>}
      </div>
    </div>
  );
}
