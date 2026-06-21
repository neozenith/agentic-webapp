/** A single big-number KPI: the value rendered large with a label beneath. `unit` (when
 * given) is appended after the formatted number (e.g. "$", "%", " orders"). */
export interface KpiCardProps {
  label: string;
  value: number | null;
  unit?: string;
}

const formatValue = (value: number | null, unit?: string): string => {
  if (value === null) return "—";
  const num = Number.isInteger(value)
    ? value.toLocaleString()
    : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (!unit) return num;
  // Currency-style units sit in front; everything else trails the number.
  return unit === "$" || unit === "£" || unit === "€"
    ? `${unit}${num}`
    : `${num}${unit.startsWith("%") ? "" : " "}${unit}`;
};

export function KpiCard({ label, value, unit }: KpiCardProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 py-6 text-center">
      <span className="text-4xl font-semibold tabular-nums">{formatValue(value, unit)}</span>
      <span className="text-sm text-muted-foreground">{label}</span>
    </div>
  );
}
