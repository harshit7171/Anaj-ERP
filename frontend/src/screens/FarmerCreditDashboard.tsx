import { useEffect, useMemo, useState } from "react";

import type { DesktopApi, FarmerCreditRow } from "../api/types";
import StatusBadge, { type Status } from "../components/StatusBadge";
import { debounce, fuzzyMatch } from "../utils/fuzzyFilter";

function formatRupees(paise: number): string {
  return `₹${(paise / 100).toFixed(2)}`;
}

function FarmerCreditDashboard({ api }: { api: DesktopApi }) {
  const [rows, setRows] = useState<FarmerCreditRow[]>([]);
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("");
  const [groups, setGroups] = useState<string[]>([]);

  const loadRows = useMemo(
    () => debounce((nextGroup: string, nextQuery: string) => {
      void api.farmer_credit_dashboard(nextGroup, nextQuery).then((response) => {
        if (response.ok) setRows(response.rows ?? []);
      });
    }, 150),
    [api],
  );

  useEffect(() => {
    void api.list_agricultural_groups().then((response) => {
      if (response.ok) setGroups(response.groups ?? []);
    });
    loadRows("", "");
  }, [api, loadRows]);

  useEffect(() => {
    loadRows(group, query);
  }, [group, query, loadRows]);

  const filtered = rows.filter((row) => fuzzyMatch(query, `${row.farmer_name} ${row.father_name} ${row.group_name}`));

  return (
    <div className="retro-dashboard">
      <header className="retro-toolbar">
        <div className="mr-auto">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#397f98]">Exposure monitoring</p>
          <h2>Farmer Credit &amp; Group Limits</h2>
        </div>
        <label className="relative min-w-[260px]">
          <input
            placeholder="Search farmer, father, or group..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <select
          className="min-w-[170px]"
          value={group}
          onChange={(event) => setGroup(event.target.value)}
        >
          <option value="">All Agricultural Groups</option>
          {groups.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </header>
      <div className="retro-table-shell">
        <table>
          <thead>
            <tr>
              {["Group", "Farmer", "Father", "Balance", "Limit", "Available", "Status"].map((heading) => (
                <th key={heading}>{heading}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.party_id}>
                <td>{row.group_name}</td>
                <td className="font-sans font-semibold">{row.farmer_name}</td>
                <td className="font-sans">{row.father_name}</td>
                <td>{formatRupees(row.current_balance_paise)}</td>
                <td>
                  {row.limit_assigned ? formatRupees(row.credit_limit_paise) : "Not set"}
                </td>
                <td>
                  {row.available_credit_paise == null ? "—" : formatRupees(row.available_credit_paise)}
                </td>
                <td className="font-sans">
                  <StatusBadge status={row.status as Status} />
                </td>
              </tr>
            ))}
            {!filtered.length && (
              <tr>
                <td className="px-4 py-12 text-center font-sans text-[#37687a]" colSpan={7}>
                  No farmer credit records match the selected filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default FarmerCreditDashboard;
