import { useEffect, useState } from "react";

import type { DashboardSummary, DesktopApi } from "../api/types";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";

function BentoDashboard({ api }: { api: DesktopApi }) {
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    void api.dashboard_summary().then((response) => {
      if (response.ok) setDashboard(response.dashboard ?? null);
    });
  }, [api]);

  const trends = dashboard?.inward_trends ?? [];
  const maxBags = Math.max(...trends.map((row) => row.bags_scaled), 1);
  const compliance = dashboard?.compliance;
  const executive = dashboard?.executive as
    | {
        today_arrivals_bags?: number;
        today_arrivals_quantity_scaled?: number;
        cash_in_hand_paise?: number;
        bank_balances?: { name: string; balance_paise: number }[];
        top_outstanding_dues?: {
          name: string;
          balance_paise: number;
          document_number: string;
        }[];
        today_sales_paise?: number;
        today_sales_count?: number;
        receivables_paise?: number;
        payables_paise?: number;
      }
    | undefined;
  const alerts = (dashboard?.threshold_alerts ?? []) as { message?: string }[];

  return (
    <div className="retro-dashboard">
      <section className="retro-dashboard-hero">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em]">Financial control center</p>
          <h1>Business Overview</h1>
          <p>Mandi activity, farmer exposure, and statutory readiness at a glance.</p>
        </div>
        <div className="inline-flex items-center gap-2 border border-white/30 bg-white/10 px-3 py-1.5 text-[11px] font-semibold">
          <span className="h-2 w-2 bg-[#398d49]" />
          Local books active
        </div>
      </section>

      <div className="retro-dashboard-grid">
        <Card title="Today's Mandi Pulse" className="min-h-0 retro-dash-top-left">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-[10px] uppercase text-[#37687a]">Arrivals (bags)</div>
              <strong className="text-lg tabular-nums">{executive?.today_arrivals_bags ?? 0}</strong>
            </div>
            <div>
              <div className="text-[10px] uppercase text-[#37687a]">Cash in hand</div>
              <strong className="text-lg tabular-nums">
                ₹{((executive?.cash_in_hand_paise ?? 0) / 100).toFixed(2)}
              </strong>
            </div>
            <div>
              <div className="text-[10px] uppercase text-[#37687a]">Today&apos;s sales</div>
              <strong className="text-lg tabular-nums">
                ₹{((executive?.today_sales_paise ?? 0) / 100).toFixed(2)}
              </strong>
              <div className="text-[10px] text-[#37687a]">{executive?.today_sales_count ?? 0} bills</div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-[#37687a]">Recv. vs Pay.</div>
              <strong className="block tabular-nums text-sm">
                ₹{((executive?.receivables_paise ?? 0) / 100).toFixed(2)}
              </strong>
              <strong className="block tabular-nums text-sm text-[#37687a]">
                ₹{((executive?.payables_paise ?? 0) / 100).toFixed(2)}
              </strong>
            </div>
          </div>
        </Card>

        <Card title="Top Outstanding Dues" className="min-h-0 retro-dash-top-mid">
          <div className="space-y-1 overflow-y-auto text-xs">
            {(executive?.top_outstanding_dues ?? []).map((row) => (
              <div className="retro-stat-row" key={row.document_number}>
                <span className="truncate">{row.name}</span>
                <strong className="tabular-nums">₹{(row.balance_paise / 100).toFixed(2)}</strong>
              </div>
            ))}
            {executive && !executive.top_outstanding_dues?.length && (
              <p className="text-[10px] text-[#37687a]">No outstanding balances.</p>
            )}
          </div>
        </Card>

        <Card title="Bank Balances" className="min-h-0 retro-dash-top-right">
          <div className="space-y-1 text-xs">
            {(executive?.bank_balances ?? []).map((row) => (
              <div className="retro-stat-row" key={row.name}>
                <span>{row.name}</span>
                <strong className="tabular-nums">₹{(row.balance_paise / 100).toFixed(2)}</strong>
              </div>
            ))}
          </div>
        </Card>

        {alerts.length > 0 && (
          <Card title="Tax Threshold Alerts" className="retro-dash-alerts">
            <ul className="list-disc pl-4 text-xs">
              {alerts.map((alert, index) => (
                <li key={index}>{alert.message}</li>
              ))}
            </ul>
          </Card>
        )}

        <Card title="Mandi Inward Analytics" className="min-h-0 retro-dash-chart">
          <div className="retro-bar-chart">
            {!dashboard && (
              <div className="grid h-full w-full grid-cols-6 items-end gap-2">
                {[42, 70, 48, 88, 62, 78].map((height, index) => (
                  <div key={index} className="retro-bar animate-pulse opacity-50" style={{ height: `${height}%` }} />
                ))}
              </div>
            )}
            {dashboard && trends.length === 0 && (
              <div className="m-auto text-center">
                <p className="text-xs font-semibold">No inward activity yet</p>
                <p className="text-[10px] text-[#37687a]">Posted inward documents will appear here.</p>
              </div>
            )}
            {trends.map((row) => (
              <div key={row.month} className="flex h-full flex-1 flex-col items-center justify-end">
                <div
                  className="retro-bar"
                  style={{ height: `${Math.max(12, (row.bags_scaled / maxBags) * 120)}px` }}
                  title={`${row.bags_scaled} bags`}
                />
                <span className="retro-bar-label">{row.month}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Farmer Risk Watchlist" className="min-h-0 retro-dash-risk">
          <div className="h-full space-y-1 overflow-y-auto">
            {(dashboard?.farmer_risk_watchlist ?? []).map((row) => (
              <div key={row.party_id} className="retro-stat-row">
                <div className="min-w-0">
                  <strong className="block truncate text-xs">{row.farmer_name}</strong>
                  <div className="mt-0.5 text-[10px] text-[#37687a]">{row.group_name}</div>
                </div>
                <StatusBadge status={row.status === "exceeded" ? "exceeded" : "approaching"} />
              </div>
            ))}
            {dashboard && !dashboard.farmer_risk_watchlist.length && (
              <div className="grid h-full place-items-center text-center">
                <div>
                  <p className="text-xs font-semibold">Credit exposure is healthy</p>
                  <p className="text-[10px] text-[#37687a]">No farmers are near their limits.</p>
                </div>
              </div>
            )}
          </div>
        </Card>

        <Card title="Statutory Compliance" className="retro-dash-compliance">
          <div className="retro-compliance-grid text-xs">
            {[
              {
                label: `TDS Liability${compliance?.month_label ? ` · ${compliance.month_label}` : ""}`,
                value: `₹${((compliance?.tds_liability_paise ?? 0) / 100).toFixed(2)}`,
                icon: "₹",
              },
              {
                label: "Pending TDS Rows",
                value: String(compliance?.tds_pending_count ?? 0),
                icon: "T",
              },
              {
                label: "Open E-Way Bills",
                value: String(compliance?.open_eway_bills ?? 0),
                icon: "E",
              },
            ].map((item) => (
              <div key={item.label} className="retro-compliance-item">
                <span className="retro-compliance-icon">{item.icon}</span>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-[#37687a]">{item.label}</div>
                  <strong className="tabular-money mt-0.5 block text-lg">{item.value}</strong>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default BentoDashboard;
