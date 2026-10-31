import { FormEvent, useEffect, useState } from "react";

import type { Company, Result } from "../api/types";

type AdminApi = {
  list_lan_users(): Promise<Result & { users?: Record<string, unknown>[] }>;
  save_lan_user(payload: Record<string, unknown>): Promise<Result & { user?: Record<string, unknown> }>;
  list_companies(): Promise<Result & { companies?: Company[] }>;
  set_company_profile(companyId: string, companyProfile: string): Promise<Result>;
};

export default function UserAdmin({ api }: { api: AdminApi }) {
  const [users, setUsers] = useState<Record<string, unknown>[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("munim");
  const [canViewKachi, setCanViewKachi] = useState(true);
  const [result, setResult] = useState<Result | null>(null);

  async function refresh() {
    const userResponse = await api.list_lan_users();
    if (userResponse.ok && userResponse.users) setUsers(userResponse.users);
    const companyResponse = await api.list_companies();
    if (companyResponse.ok && companyResponse.companies) setCompanies(companyResponse.companies);
  }

  useEffect(() => {
    void refresh();
  }, [api]);

  async function saveUser(event: FormEvent) {
    event.preventDefault();
    const response = await api.save_lan_user({
      username,
      display_name: displayName || username,
      password: password || undefined,
      role,
      can_view_kachi: canViewKachi,
      is_active: true,
    });
    setResult(response);
    if (response.ok) {
      setPassword("");
      void refresh();
    }
  }

  async function toggleProfile(company: Company & { company_profile?: string }) {
    const next = company.company_profile === "kachi" ? "standard" : "kachi";
    const response = await api.set_company_profile(company.company_id, next);
    setResult(response);
    if (response.ok) void refresh();
  }

  return (
    <section className="entry-form p-2 text-xs">
      <h2>Office Users (Administrator)</h2>
      <p className="status-message">
        Munim users can post vouchers. Clerks are read-only. Hide Kachi companies by clearing
        &quot;Can view Kachi&quot; or marking companies below.
      </p>
      <form className="mb-4 flex flex-wrap items-end gap-2" onSubmit={(event) => void saveUser(event)}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} required />
        </label>
        <label>
          Display name
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="admin">Admin</option>
            <option value="munim">Munim</option>
            <option value="operator">Operator</option>
            <option value="clerk">Clerk (read-only)</option>
            <option value="readonly">Read-only</option>
          </select>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={canViewKachi}
            onChange={(e) => setCanViewKachi(e.target.checked)}
          />
          Can view Kachi
        </label>
        <button type="submit">Add / Update User</button>
      </form>
      {result && !result.ok && <p className="text-red-700">{result.error}</p>}
      <h3>Users</h3>
      <table className="mb-4 w-full border-collapse">
        <thead>
          <tr>
            <th className="border px-1">Username</th>
            <th className="border px-1">Role</th>
            <th className="border px-1">Kachi</th>
            <th className="border px-1">Active</th>
          </tr>
        </thead>
        <tbody>
          {users.map((row) => (
            <tr key={String(row.user_id)}>
              <td className="border px-1">{String(row.username)}</td>
              <td className="border px-1">{String(row.role)}</td>
              <td className="border px-1">{Number(row.can_view_kachi) ? "Yes" : "No"}</td>
              <td className="border px-1">{Number(row.is_active) ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Company profile (Pakki vs Kachi)</h3>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className="border px-1">Company</th>
            <th className="border px-1">Profile</th>
            <th className="border px-1">Action</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((company) => (
            <tr key={company.company_id}>
              <td className="border px-1">{company.name}</td>
              <td className="border px-1">
                {(company as Company & { company_profile?: string }).company_profile ?? "standard"}
              </td>
              <td className="border px-1">
                <button type="button" onClick={() => void toggleProfile(company as never)}>
                  Toggle Kachi
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
