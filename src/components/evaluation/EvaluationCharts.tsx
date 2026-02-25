"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/* ─── RadarChart ─── */

interface RadarChartProps {
  metrics: number[];
  labels: string[];
  secondaryMetrics?: number[];
  secondaryLabel?: string;
  size?: number;
}

export function RadarChart({
  metrics,
  labels,
  secondaryMetrics,
  secondaryLabel,
  size = 300,
}: RadarChartProps) {
  const n = metrics.length;
  const cx = size / 2;
  const cy = size / 2;
  const r = (size / 2) - 50;

  const getPoint = (index: number, value: number) => {
    const angle = (2 * Math.PI * index) / n - Math.PI / 2;
    return {
      x: cx + r * value * Math.cos(angle),
      y: cy + r * value * Math.sin(angle),
    };
  };

  const polygon = (values: number[]) =>
    values.map((v, i) => getPoint(i, v)).map((p) => `${p.x},${p.y}`).join(" ");

  const gridLevels = [0.2, 0.4, 0.6, 0.8, 1.0];

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Grid */}
        {gridLevels.map((level) => (
          <polygon
            key={level}
            points={Array.from({ length: n }, (_, i) => getPoint(i, level))
              .map((p) => `${p.x},${p.y}`)
              .join(" ")}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="1"
            className="dark:stroke-gray-700"
          />
        ))}

        {/* Axes */}
        {Array.from({ length: n }, (_, i) => {
          const p = getPoint(i, 1);
          return (
            <line
              key={i}
              x1={cx}
              y1={cy}
              x2={p.x}
              y2={p.y}
              stroke="#e5e7eb"
              strokeWidth="1"
              className="dark:stroke-gray-700"
            />
          );
        })}

        {/* Secondary data polygon */}
        {secondaryMetrics && (
          <polygon
            points={polygon(secondaryMetrics)}
            fill="rgba(234, 179, 8, 0.15)"
            stroke="#eab308"
            strokeWidth="2"
            strokeDasharray="6 3"
          />
        )}

        {/* Primary data polygon */}
        <polygon
          points={polygon(metrics)}
          fill="rgba(59, 130, 246, 0.2)"
          stroke="#3b82f6"
          strokeWidth="2.5"
        />

        {/* Data points */}
        {metrics.map((v, i) => {
          const p = getPoint(i, v);
          return (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r="4"
              fill="#3b82f6"
              stroke="white"
              strokeWidth="2"
            />
          );
        })}

        {/* Labels */}
        {labels.map((label, i) => {
          const p = getPoint(i, 1.25);
          return (
            <text
              key={i}
              x={p.x}
              y={p.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-gray-600 dark:fill-gray-400 text-[11px]"
            >
              {label}
            </text>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-6 mt-2 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-0.5 bg-blue-500 rounded" />
          <span className="text-gray-600 dark:text-gray-400">Automatiche</span>
        </div>
        {secondaryMetrics && (
          <div className="flex items-center gap-2">
            <div className="w-4 h-0.5 bg-yellow-500 rounded border-dashed" />
            <span className="text-gray-600 dark:text-gray-400">
              {secondaryLabel || "Umane"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── HorizontalBarChart ─── */

interface BarItem {
  label: string;
  value: number;
  max?: number;
  ci?: [number, number];
}

interface HorizontalBarChartProps {
  items: BarItem[];
  colorClass?: string;
}

export function HorizontalBarChart({
  items,
  colorClass = "from-blue-500 to-indigo-500",
}: HorizontalBarChartProps) {
  return (
    <div className="space-y-4">
      {items.map((item) => {
        const max = item.max ?? 1;
        const pct = (item.value / max) * 100;
        return (
          <div key={item.label} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-700 dark:text-gray-300 font-medium">
                {item.label}
              </span>
              <span className="font-mono text-gray-600 dark:text-gray-400">
                {(item.value * 100).toFixed(1)}%
              </span>
            </div>
            <div className="relative h-6 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full bg-gradient-to-r transition-all duration-500",
                  colorClass
                )}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
              {/* CI markers */}
              {item.ci && (
                <>
                  <div
                    className="absolute top-0 h-full w-0.5 bg-gray-400 dark:bg-gray-500"
                    style={{ left: `${(item.ci[0] / max) * 100}%` }}
                  />
                  <div
                    className="absolute top-0 h-full w-0.5 bg-gray-400 dark:bg-gray-500"
                    style={{ left: `${(item.ci[1] / max) * 100}%` }}
                  />
                </>
              )}
            </div>
            {item.ci && (
              <div className="text-xs text-gray-500 dark:text-gray-500">
                IC 95%: [{(item.ci[0] * 100).toFixed(1)}%, {(item.ci[1] * 100).toFixed(1)}%]
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── ScoreDistribution ─── */

interface ScoreDistributionProps {
  label: string;
  distribution: Record<number, number>;
  average?: number;
}

const SCORE_COLORS = [
  "bg-red-400",
  "bg-orange-400",
  "bg-amber-400",
  "bg-lime-400",
  "bg-emerald-400",
];

const SCORE_LABELS = ["1", "2", "3", "4", "5"];

export function ScoreDistribution({
  label,
  distribution,
  average,
}: ScoreDistributionProps) {
  const maxCount = Math.max(...Object.values(distribution), 1);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {label}
        </span>
        {average !== undefined && (
          <span className="text-sm font-mono text-gray-600 dark:text-gray-400">
            {average.toFixed(2)} / 5
          </span>
        )}
      </div>
      <div className="space-y-1">
        {SCORE_LABELS.map((scoreLabel, idx) => {
          const score = idx + 1;
          const count = distribution[score] || 0;
          const pct = (count / maxCount) * 100;
          return (
            <div key={score} className="flex items-center gap-2">
              <span className="w-4 text-xs text-gray-500 text-right">
                {scoreLabel}
              </span>
              <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded transition-all duration-300",
                    SCORE_COLORS[idx]
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="w-6 text-xs text-gray-500 text-right">
                {count}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── MetricCard ─── */

interface MetricCardProps {
  label: string;
  value: number;
  ci?: [number, number];
  icon: React.ReactNode;
  format?: "percent" | "decimal" | "count";
  description?: string;
  baselineValue?: number;
  baselineCi?: [number, number];
  /** Use a neutral blue color scheme — for metrics where higher/lower isn't inherently good or bad */
  isNeutral?: boolean;
}

export function MetricCard({
  label,
  value,
  ci,
  icon,
  format = "percent",
  description,
  baselineValue,
  baselineCi,
  isNeutral = false,
}: MetricCardProps) {
  const formattedValue =
    format === "percent"
      ? `${(value * 100).toFixed(1)}%`
      : format === "count"
      ? String(value)
      : value.toFixed(3);

  const getColorClass = (v: number) => {
    if (isNeutral) return "text-blue-600 dark:text-blue-400";
    if (v >= 0.8) return "text-emerald-600 dark:text-emerald-400";
    if (v >= 0.6) return "text-amber-600 dark:text-amber-400";
    return "text-red-600 dark:text-red-400";
  };

  const getBarColor = (v: number) => {
    if (isNeutral) return "bg-blue-500";
    if (v >= 0.8) return "bg-emerald-500";
    if (v >= 0.6) return "bg-amber-500";
    return "bg-red-500";
  };

  const isDegenerate = ci && ci[0] === ci[1];
  const hasBaseline = baselineValue != null;
  const delta = hasBaseline ? value - baselineValue! : 0;

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-muted-foreground mb-2">
          {icon}
          <span className="text-sm font-medium">{label}</span>
        </div>
        <div className={cn("text-2xl font-bold mb-1", getColorClass(value))}>
          {formattedValue}
        </div>
        {hasBaseline && (
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-xs text-muted-foreground">Baseline:</span>
            <span className="text-xs font-mono text-amber-600 dark:text-amber-400">
              {format === "percent" ? `${(baselineValue! * 100).toFixed(1)}%` : baselineValue!.toFixed(3)}
            </span>
            <span className={cn(
              "text-xs font-semibold ml-0.5",
              delta > 0.005 ? "text-emerald-600 dark:text-emerald-400" :
              delta < -0.005 ? "text-red-500 dark:text-red-400" :
              "text-gray-400"
            )}>
              {delta > 0.005 ? "▲" : delta < -0.005 ? "▼" : "≈"}
              {format === "percent"
                ? ` ${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)}pp`
                : ` ${delta >= 0 ? "+" : ""}${delta.toFixed(3)}`}
            </span>
          </div>
        )}
        {format === "percent" && (
          <div className="space-y-1 mb-1">
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-blue-500 w-14 shrink-0">Sistema</span>
              <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-1.5">
                <div
                  className={cn("h-1.5 rounded-full transition-all", getBarColor(value))}
                  style={{ width: `${Math.min(value * 100, 100)}%` }}
                />
              </div>
            </div>
            {hasBaseline && (
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-amber-500 w-14 shrink-0">Baseline</span>
                <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-1.5">
                  <div
                    className="h-1.5 rounded-full bg-amber-400 transition-all"
                    style={{ width: `${Math.min(baselineValue! * 100, 100)}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
        {description && (
          <div className="text-xs text-muted-foreground mb-1">{description}</div>
        )}
        {ci && format === "percent" && (
          <div className="text-xs text-muted-foreground">
            IC 95%: [{(ci[0] * 100).toFixed(1)}%, {(ci[1] * 100).toFixed(1)}%]
            {isDegenerate && (
              <span className="ml-1 text-amber-500" title="Basato su un singolo campione">
                (n=1)
              </span>
            )}
          </div>
        )}
        {hasBaseline && baselineCi && format === "percent" && (
          <div className="text-xs text-muted-foreground">
            Baseline IC 95%: [{(baselineCi[0] * 100).toFixed(1)}%, {(baselineCi[1] * 100).toFixed(1)}%]
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ─── MiniMetricBars ─── */

interface MiniMetricBarsProps {
  values: { label: string; value: number; color: string }[];
}

export function MiniMetricBars({ values }: MiniMetricBarsProps) {
  return (
    <div className="flex items-center gap-1">
      {values.map((v) => (
        <div
          key={v.label}
          className="relative group"
          title={`${v.label}: ${(v.value * 100).toFixed(0)}%`}
        >
          <div className="w-8 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full", v.color)}
              style={{ width: `${v.value * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── ABComparisonChart ─── */

interface ABComparisonItem {
  label: string;
  systemValue: number;
  baselineValue: number;
}

interface ABComparisonChartProps {
  items: ABComparisonItem[];
  maxValue?: number;
}

export function ABComparisonChart({ items, maxValue = 5 }: ABComparisonChartProps) {
  return (
    <div className="space-y-4">
      {items.map((item) => {
        const sysPct = (item.systemValue / maxValue) * 100;
        const basePct = (item.baselineValue / maxValue) * 100;
        const delta = item.systemValue - item.baselineValue;
        return (
          <div key={item.label} className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-700 dark:text-gray-300 font-medium">
                {item.label}
              </span>
              <span className={cn(
                "text-xs font-semibold",
                delta > 0 ? "text-emerald-600" : delta < 0 ? "text-red-600" : "text-gray-500"
              )}>
                {delta > 0 ? "+" : ""}{delta.toFixed(2)}
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-20 text-xs text-blue-600 dark:text-blue-400">Sistema</span>
                <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-500"
                    style={{ width: `${Math.min(sysPct, 100)}%` }}
                  />
                </div>
                <span className="w-10 text-xs font-mono text-right text-gray-600 dark:text-gray-400">
                  {item.systemValue.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-20 text-xs text-amber-600 dark:text-amber-400">Baseline</span>
                <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-amber-400 to-amber-500 transition-all duration-500"
                    style={{ width: `${Math.min(basePct, 100)}%` }}
                  />
                </div>
                <span className="w-10 text-xs font-mono text-right text-gray-600 dark:text-gray-400">
                  {item.baselineValue.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-gradient-to-r from-blue-500 to-indigo-500" />
          ParliamentRAG
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-gradient-to-r from-amber-400 to-amber-500" />
          Baseline RAG
        </div>
      </div>
    </div>
  );
}

/* ─── WinRateChart ─── */

interface WinRateChartProps {
  systemWinRate: number;
  baselineWinRate: number;
  tieRate: number;
  totalEvaluations: number;
}

export function WinRateChart({ systemWinRate, baselineWinRate, tieRate, totalEvaluations }: WinRateChartProps) {
  const sysW = Math.round(systemWinRate * 100);
  const baseW = Math.round(baselineWinRate * 100);
  const tieW = Math.round(tieRate * 100);

  return (
    <div className="space-y-4">
      <div className="flex items-center h-10 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800">
        {sysW > 0 && (
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 flex items-center justify-center text-white text-xs font-bold"
            style={{ width: `${sysW}%` }}
          >
            {sysW > 8 ? `${sysW}%` : ""}
          </div>
        )}
        {tieW > 0 && (
          <div
            className="h-full bg-gray-300 dark:bg-gray-600 flex items-center justify-center text-gray-700 dark:text-gray-300 text-xs font-bold"
            style={{ width: `${tieW}%` }}
          >
            {tieW > 8 ? `${tieW}%` : ""}
          </div>
        )}
        {baseW > 0 && (
          <div
            className="h-full bg-gradient-to-r from-amber-400 to-amber-500 flex items-center justify-center text-white text-xs font-bold"
            style={{ width: `${baseW}%` }}
          >
            {baseW > 8 ? `${baseW}%` : ""}
          </div>
        )}
      </div>
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-gradient-to-r from-blue-500 to-indigo-500" />
          <span className="text-gray-600 dark:text-gray-400">
            ParliamentRAG preferito ({sysW}%)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-gray-300 dark:bg-gray-600" />
          <span className="text-gray-600 dark:text-gray-400">
            Pari ({tieW}%)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-gradient-to-r from-amber-400 to-amber-500" />
          <span className="text-gray-600 dark:text-gray-400">
            Baseline preferito ({baseW}%)
          </span>
        </div>
      </div>
      <p className="text-xs text-center text-muted-foreground">
        Basato su {totalEvaluations} valutazioni blind A/B
      </p>
    </div>
  );
}
