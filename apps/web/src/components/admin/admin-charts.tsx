"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney } from "@/lib/format";
import type { AdminSeriesPoint } from "@/types/admin";

function shortMoney(value: number) {
  if (value >= 1_000_000) {
    return `${new Intl.NumberFormat("fr-FR", {
      maximumFractionDigits: 1,
    }).format(value / 1_000_000)} M`;
  }
  if (value >= 1_000) {
    return `${Math.round(value / 1_000)} k`;
  }
  return String(value);
}

const tooltipStyle = {
  background: "#ffffff",
  border: "1px solid #e5dfdc",
  borderRadius: 10,
  boxShadow: "0 12px 30px rgba(18, 16, 18, 0.10)",
  fontSize: 12,
};

export function AdminSeriesChart({
  data,
  dataKey,
  color = "#d4342b",
  money = false,
  label,
  height = 240,
}: {
  data: AdminSeriesPoint[];
  dataKey: "count" | "total";
  color?: string;
  money?: boolean;
  label: string;
  height?: number;
}) {
  if (!data.length) {
    return (
      <div className="grid h-60 place-items-center text-sm text-muted">
        Aucune donnée sur cette période.
      </div>
    );
  }
  return (
    <div aria-label={label} className="w-full" role="img">
      <ResponsiveContainer height={height} width="100%">
        <BarChart data={data} margin={{ bottom: 0, left: -14, right: 4, top: 8 }}>
          <CartesianGrid stroke="#eee9e6" strokeDasharray="3 4" vertical={false} />
          <XAxis
            axisLine={false}
            dataKey="date"
            fontSize={10}
            interval="preserveStartEnd"
            minTickGap={18}
            tick={{ fill: "#696562" }}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            axisLine={false}
            fontSize={11}
            tick={{ fill: "#696562" }}
            tickFormatter={money ? shortMoney : String}
            tickLine={false}
            width={54}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            cursor={{ fill: "#f9f6f5" }}
            formatter={(value: unknown) =>
              money ? formatMoney(Number(value ?? 0)) : String(value ?? 0)
            }
            labelFormatter={(value: unknown) => String(value)}
          />
          <Bar
            dataKey={dataKey}
            fill={color}
            maxBarSize={28}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const PLAN_COLORS: Record<string, string> = {
  free: "#d8d1cd",
  essential: "#d08b27",
  pro: "#d4342b",
};

export function AdminPlanSplitChart({
  breakdown,
}: {
  breakdown: Record<string, number>;
}) {
  const data = Object.entries(breakdown)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  if (!data.length) {
    return (
      <div className="grid h-60 place-items-center text-sm text-muted">
        Aucun abonnement enregistré.
      </div>
    );
  }

  return (
    <div>
      <div
        aria-label="Répartition des abonnements par plan"
        className="h-60 w-full"
        role="img"
      >
        <ResponsiveContainer height="100%" width="100%">
          <PieChart>
            <Pie
              cx="50%"
              cy="50%"
              data={data}
              dataKey="value"
              innerRadius={58}
              labelLine={false}
              nameKey="name"
              outerRadius={86}
              paddingAngle={2}
            >
              {data.map((entry) => (
                <Cell
                  fill={PLAN_COLORS[entry.name] ?? "#d8d1cd"}
                  key={entry.name}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value: unknown, name: unknown) => [
                String(value),
                String(name),
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 space-y-1.5 text-xs text-muted">
        {data.map((entry) => (
          <li className="flex items-center justify-between gap-3" key={entry.name}>
            <span className="flex items-center gap-2">
              <span
                className="size-2.5 rounded-sm"
                style={{ background: PLAN_COLORS[entry.name] ?? "#d8d1cd" }}
              />
              {entry.name}
            </span>
            <span className="font-semibold text-ink">{entry.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
