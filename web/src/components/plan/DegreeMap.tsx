"use client";

import { useId, useMemo, useState } from "react";
import type { Schemas } from "@/lib/api";
import { units } from "@/lib/format";
import { Heading } from "@/components/ui";

type DegreeMapData = Schemas["DegreeMapOut"];
type MapNode = Schemas["MapNodeOut"];
type Status = MapNode["status"];

const NODE_W = 136;
const NODE_H = 46;
const GAP_X = 46;
const GAP_Y = 10;
const HEADER_H = 34;
const PAD = 12;

// Status is shown three ways: outline colour, an icon, and the word in the accessible label.
const STATUS: Record<Status, { label: string; icon: string; color: string; dashed: boolean }> = {
  done: { label: "Done", icon: "✓", color: "var(--status-done)", dashed: false },
  in_progress: { label: "In progress", icon: "◐", color: "var(--status-in-progress)", dashed: false },
  planned: { label: "Planned", icon: "○", color: "var(--status-planned)", dashed: false },
  choice: { label: "Your choice", icon: "?", color: "var(--text-muted)", dashed: true },
  blocked: { label: "Not scheduled", icon: "✕", color: "var(--status-blocked)", dashed: true },
};

interface Placed extends MapNode {
  x: number;
  y: number;
}

/** F5: the student's whole degree as a map, by term, with prerequisite arrows. */
export function DegreeMap({ id, data }: { id: string; data: DegreeMapData }) {
  const titleId = useId();
  const [selected, setSelected] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const layout = useMemo(() => place(data), [data]);
  const related = useMemo(() => (selected ? connected(selected, data) : null), [selected, data]);
  const byKey = useMemo(() => new Map(layout.nodes.map((node) => [node.key, node])), [layout]);
  const counts = useMemo(() => {
    const found = new Map<Status, number>();
    for (const node of data.nodes) found.set(node.status, (found.get(node.status) ?? 0) + 1);
    return found;
  }, [data]);
  const chosen = selected ? byKey.get(selected) : undefined;

  return (
    <section id={id} aria-labelledby={titleId} className="space-y-3">
      <Heading>
        <span id={titleId}>Degree map</span>
      </Heading>
      <p className="text-sm text-text-muted">
        Every course on your path, by term. Arrows point from a prerequisite to the course that needs it. Select a
        course to highlight what it needs and what it opens.
      </p>
      <ul className="flex flex-wrap gap-3 text-xs" aria-label="Map legend">
        {(Object.keys(STATUS) as Status[])
          .filter((status) => counts.get(status))
          .map((status) => (
            <li key={status} className="flex items-center gap-1">
              <span
                aria-hidden
                className="inline-flex h-5 w-5 items-center justify-center rounded border-2 bg-surface text-[11px] font-bold"
                style={{ borderColor: STATUS[status].color, borderStyle: STATUS[status].dashed ? "dashed" : "solid", color: STATUS[status].color }}
              >
                {STATUS[status].icon}
              </span>
              {STATUS[status].label} ({counts.get(status)})
            </li>
          ))}
      </ul>
      <div className="relative overflow-x-auto rounded-card border border-border bg-surface">
        <svg
          width={layout.width}
          height={layout.height}
          role="group"
          aria-label={`Degree map with ${data.nodes.length} courses across ${data.columns.length} terms`}
          className="block"
        >
          <defs>
            <marker id={`${titleId}-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--text-muted)" />
            </marker>
            <marker id={`${titleId}-arrow-on`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--brand-primary)" />
            </marker>
          </defs>

          {data.columns.map((column, index) => {
            const x = PAD + index * (NODE_W + GAP_X) - GAP_X / 4;
            const current = column.kind === "current";
            return (
              <g key={column.label} aria-hidden>
                <rect
                  x={x}
                  y={4}
                  width={NODE_W + GAP_X / 2}
                  height={layout.height - 8}
                  rx={10}
                  fill={current ? "color-mix(in srgb, var(--status-in-progress) 8%, transparent)" : index % 2 ? "var(--background)" : "transparent"}
                  opacity={0.8}
                />
                <text
                  x={x + (NODE_W + GAP_X / 2) / 2}
                  y={HEADER_H - 12}
                  textAnchor="middle"
                  fontSize={12}
                  fontWeight={600}
                  fill={column.kind === "completed" ? "var(--text-muted)" : "var(--text)"}
                >
                  {column.label}
                </text>
              </g>
            );
          })}

          <g aria-hidden>
            {data.edges.map((edge) => {
              const source = byKey.get(edge.source);
              const target = byKey.get(edge.target);
              if (!source || !target) return null;
              const on = related ? related.has(edge.source) && related.has(edge.target) : false;
              const x1 = source.x + NODE_W;
              const y1 = source.y + NODE_H / 2;
              const x2 = target.x - 2;
              const y2 = target.y + NODE_H / 2;
              const bend = Math.max(18, (x2 - x1) / 2);
              return (
                <path
                  key={`${edge.source}>${edge.target}`}
                  d={`M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`}
                  fill="none"
                  stroke={on ? "var(--brand-primary)" : "var(--text-muted)"}
                  strokeWidth={on ? 2 : 1}
                  opacity={related ? (on ? 1 : 0.08) : 0.35}
                  markerEnd={`url(#${titleId}-arrow${on ? "-on" : ""})`}
                />
              );
            })}
          </g>

          {layout.nodes.map((node) => {
            const style = STATUS[node.status];
            const dimmed = related !== null && !related.has(node.key);
            const isSelected = node.key === selected;
            const label = `${node.code ?? ""} ${node.title}, ${style.label}, ${data.columns[node.column]?.label ?? ""}`;
            const toggle = () => setSelected(isSelected ? null : node.key);
            return (
              <g
                key={node.key}
                transform={`translate(${node.x},${node.y})`}
                role="button"
                tabIndex={0}
                aria-pressed={isSelected}
                aria-label={label.trim()}
                onClick={toggle}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggle();
                  }
                }}
                onFocus={() => setFocused(node.key)}
                onBlur={() => setFocused(null)}
                opacity={dimmed ? 0.25 : 1}
                className="cursor-pointer outline-none"
              >
                {focused === node.key && (
                  <rect x={-4} y={-4} width={NODE_W + 8} height={NODE_H + 8} rx={12} fill="none" stroke="var(--brand-primary)" strokeWidth={3} />
                )}
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={8}
                  fill={`color-mix(in srgb, ${style.color} 10%, var(--surface))`}
                  stroke={isSelected ? "var(--brand-primary)" : style.color}
                  strokeWidth={isSelected ? 3 : 1.5}
                  strokeDasharray={style.dashed ? "4 3" : undefined}
                />
                <text x={8} y={18} fontSize={12} fontWeight={700} fill="var(--text)">
                  <tspan fill={style.color}>{style.icon}</tspan> {node.code ?? "Choice"}
                </text>
                <text x={NODE_W - 8} y={18} fontSize={10} textAnchor="end" fill="var(--text-muted)">
                  {units(node.units)}u
                </text>
                <text x={8} y={35} fontSize={10.5} fill="var(--text-muted)">
                  {shorten(node.code ? node.title : node.group_label ?? node.title, 23)}
                </text>
                <title>{label}</title>
              </g>
            );
          })}
        </svg>
      </div>
      <Details node={chosen} data={data} />
    </section>
  );
}

function Details({ node, data }: { node: MapNode | undefined; data: DegreeMapData }) {
  if (!node) {
    return <p className="text-xs text-text-muted">Tip: on a phone, scroll the map sideways and tap a course.</p>;
  }
  const titles = new Map(data.nodes.map((n) => [n.key, n.code ? `${n.code} ${n.title}` : n.title]));
  const needs = data.edges.filter((edge) => edge.target === node.key).map((edge) => titles.get(edge.source));
  const opens = data.edges.filter((edge) => edge.source === node.key).map((edge) => titles.get(edge.target));
  return (
    <div role="status" className="rounded-card border border-primary bg-surface p-3 text-sm">
      <p className="font-semibold">
        {node.code ? `${node.code} ${node.title}` : node.title}
        <span className="font-normal text-text-muted">
          {" "}
          · {STATUS[node.status].label}, {data.columns[node.column]?.label}
        </span>
      </p>
      {node.group_label && <p className="text-text-muted">Counts toward {node.group_label}</p>}
      <p className="mt-1">Needs first: {needs.length ? needs.join(", ") : "nothing on this map"}</p>
      <p>Opens: {opens.length ? opens.join(", ") : "nothing later on this map"}</p>
    </div>
  );
}

/** Columns by term; within a column, courses sit near the prerequisites they come from. */
function place(data: DegreeMapData): { nodes: Placed[]; width: number; height: number } {
  const sources = new Map<string, string[]>();
  for (const edge of data.edges) sources.set(edge.target, [...(sources.get(edge.target) ?? []), edge.source]);
  const row = new Map<string, number>();
  const placed: Placed[] = [];
  let tallest = 0;
  data.columns.forEach((_column, index) => {
    const inColumn = data.nodes.filter((node) => node.column === index);
    const weight = (node: MapNode) => {
      const rows = (sources.get(node.key) ?? []).map((key) => row.get(key)).filter((r): r is number => r !== undefined);
      if (node.status === "choice") return 10_000;
      return rows.length ? rows.reduce((a, b) => a + b, 0) / rows.length : 5_000;
    };
    const ordered = [...inColumn].sort((a, b) => weight(a) - weight(b));
    ordered.forEach((node, position) => {
      row.set(node.key, position);
      placed.push({
        ...node,
        x: PAD + index * (NODE_W + GAP_X),
        y: HEADER_H + position * (NODE_H + GAP_Y),
      });
    });
    tallest = Math.max(tallest, ordered.length);
  });
  return {
    nodes: placed,
    width: PAD * 2 + data.columns.length * (NODE_W + GAP_X) - GAP_X / 2,
    height: HEADER_H + tallest * (NODE_H + GAP_Y) + PAD,
  };
}

/** Everything upstream (prerequisites, transitively) and downstream (what it opens) of a course. */
function connected(key: string, data: DegreeMapData): Set<string> {
  const found = new Set([key]);
  const walk = (start: string, forward: boolean) => {
    const stack = [start];
    while (stack.length) {
      const current = stack.pop()!;
      for (const edge of data.edges) {
        const [from, to] = forward ? [edge.source, edge.target] : [edge.target, edge.source];
        if (from === current && !found.has(to)) {
          found.add(to);
          stack.push(to);
        }
      }
    }
  };
  walk(key, true);
  walk(key, false);
  return found;
}

function shorten(text: string, length: number): string {
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}
