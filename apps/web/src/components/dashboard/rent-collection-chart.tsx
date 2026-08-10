"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney, monthLabel } from "@/lib/format";
import type { MonthlyCollection } from "@/types/domain";

type ChartItem = {
  period: string;
  label: string;
  expected: number;
  collected: number;
};

function chartData(data: MonthlyCollection[]): ChartItem[] {
  return data.map((item) => ({
    period: item.period,
    label: monthLabel(item.period).slice(0, 3),
    expected: Number(item.expected),
    collected: Number(item.collected),
  }));
}

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

export function RentCollectionChart({
  data: monthlyCollection,
}: {
  data: MonthlyCollection[];
}) {
  const data = chartData(monthlyCollection);

  if (!data.length) {
    return (
      <div className="grid h-64 place-items-center text-sm text-muted">
        Le graphique apparaîtra après la génération des premières échéances.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap gap-x-5 gap-y-2 text-xs font-medium text-muted">
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm bg-[#d8d1cd]" />
          Montant attendu
        </span>
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm bg-brand" />
          Montant encaissé
        </span>
      </div>
      <div
        aria-label="Comparaison mensuelle des loyers attendus et encaissés"
        className="h-64 w-full"
        role="img"
      >
        <ResponsiveContainer height="100%" width="100%">
          <BarChart
            barCategoryGap="28%"
            data={data}
            margin={{ bottom: 0, left: -14, right: 4, top: 8 }}
          >
            <CartesianGrid stroke="#eee9e6" strokeDasharray="3 4" vertical={false} />
            <XAxis
              axisLine={false}
              dataKey="label"
              fontSize={11}
              tick={{ fill: "#696562" }}
              tickLine={false}
            />
            <YAxis
              axisLine={false}
              fontSize={11}
              tick={{ fill: "#696562" }}
              tickFormatter={shortMoney}
              tickLine={false}
              width={54}
            />
            <Tooltip
              contentStyle={{
                background: "#ffffff",
                border: "1px solid #e5dfdc",
                borderRadius: 10,
                boxShadow: "0 12px 30px rgba(18, 16, 18, 0.10)",
                fontSize: 12,
              }}
              cursor={{ fill: "#f9f6f5" }}
              formatter={(value: unknown, name: unknown) => [
                formatMoney(Number(value ?? 0)),
                name === "expected" ? "Attendu" : "Encaissé",
              ]}
              labelFormatter={(
                _: unknown,
                payload: ReadonlyArray<{ payload?: unknown }>,
              ) => {
                const point = payload[0]?.payload as
                  | { period?: string }
                  | undefined;
                return point?.period ? monthLabel(point.period) : "";
              }}
            />
            <Bar
              dataKey="expected"
              fill="#d8d1cd"
              maxBarSize={34}
              radius={[4, 4, 0, 0]}
            />
            <Bar
              dataKey="collected"
              fill="#d4342b"
              maxBarSize={34}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>Loyers attendus et encaissés sur les six derniers mois</caption>
        <thead>
          <tr>
            <th scope="col">Mois</th>
            <th scope="col">Attendu</th>
            <th scope="col">Encaissé</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={item.period}>
              <th scope="row">{monthLabel(item.period)}</th>
              <td>{formatMoney(item.expected)}</td>
              <td>{formatMoney(item.collected)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs leading-5 text-muted">
        Les montants sont calculés à partir des échéances, après exclusion des
        éléments annulés.
      </p>
    </div>
  );
}
