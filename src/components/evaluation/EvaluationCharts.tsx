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
}

export function MetricCard({
  label,
  value,
  ci,
  icon,
  format = "percent",
}: MetricCardProps) {
  const formattedValue =
    format === "percent"
      ? `${(value * 100).toFixed(1)}%`
      : format === "count"
      ? String(value)
      : value.toFixed(3);

  const getColorClass = (v: number) => {
    if (v >= 0.8) return "text-emerald-600 dark:text-emerald-400";
    if (v >= 0.6) return "text-amber-600 dark:text-amber-400";
    return "text-red-600 dark:text-red-400";
  };

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-muted-foreground mb-1">
          {icon}
          <span className="text-sm">{label}</span>
        </div>
        <div className={cn("text-2xl font-bold", getColorClass(value))}>
          {formattedValue}
        </div>
        {ci && format === "percent" && (
          <div className="text-xs text-muted-foreground mt-1">
            IC 95%: [{(ci[0] * 100).toFixed(1)}%, {(ci[1] * 100).toFixed(1)}%]
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
