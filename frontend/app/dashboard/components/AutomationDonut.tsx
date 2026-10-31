"use client";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

interface AutomationDonutProps {
  alreadyAutomated?: number;
  canAutomate?: number;
}


export default function AutomationDonut({ alreadyAutomated = 0, canAutomate = 0 }: AutomationDonutProps) {
  const manual = Math.max(0, 100 - alreadyAutomated - canAutomate);
  const actionable = parseFloat((alreadyAutomated + canAutomate).toFixed(1));

  const DATA = [
    { name: "Already Automated", value: parseFloat(alreadyAutomated.toFixed(1)), color: "#10B981" },
    { name: "Can Automate", value: parseFloat(canAutomate.toFixed(1)), color: "#4F46E5" },
    { name: "Manual Required", value: parseFloat(manual.toFixed(1)), color: "#EF4444" },
  ];
  return (
    <div className="donut-wrap">
      <div className="donut-chart-area">
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={DATA}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
              startAngle={90}
              endAngle={-270}
            >
              {DATA.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v) => [`${Number(v).toFixed(1)}%`, ""]}
              contentStyle={{
                background: "white",
                border: "1px solid #E5E7EB",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <div className="center-val">{actionable.toFixed(1)}%</div>
          <div className="center-label">Actionable</div>
        </div>
      </div>

      <div className="donut-legend">
        {DATA.map((d, i) => (
          <div key={i} className="legend-item">
            <div className="legend-dot" style={{ background: d.color }} />
            <span className="legend-name">{d.name}</span>
            <span className="legend-val">{d.value}%</span>
          </div>
        ))}
      </div>

      <style jsx>{`
        .donut-wrap { width: 100%; }
        .donut-chart-area {
          position: relative;
          height: 180px;
        }
        .donut-center {
          position: absolute;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          text-align: center;
          pointer-events: none;
        }
        .center-val {
          font-size: 20px;
          font-weight: 700;
          color: #111827;
          font-family: 'JetBrains Mono', monospace;
          line-height: 1;
        }
        .center-label {
          font-size: 9px;
          color: #6B7280;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-top: 2px;
        }
        .donut-legend {
          margin-top: 8px;
        }
        .legend-item {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 7px;
          font-size: 11px;
          color: #374151;
        }
        .legend-dot {
          width: 8px; height: 8px;
          border-radius: 50%;
          flex-shrink: 0;
        }
        .legend-name { flex: 1; }
        .legend-val {
          font-weight: 700;
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          color: #111827;
        }
      `}</style>
    </div>
  );
}
