import { FormEvent, useEffect, useMemo, useState } from "react";

import type { Result } from "../../api/types";

type CatalogRow = {
  menu: string;
  group: string;
  label: string;
  key: string;
};

type GrantRow = {
  permission_key: string;
  enabled: boolean;
  access_level: "read" | "write";
  valid_days: string;
};

type UserRow = {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  can_view_kachi: boolean;
  is_active: boolean;
  use_custom_menu: boolean;
  access_valid_until: string;
  permissions?: Record<string, string>;
};

type UserAccessApi = {
  list_lan_users(): Promise<Result & { users?: UserRow[] }>;
  save_lan_user(payload: Record<string, unknown>): Promise<Result>;
  delete_lan_user(userId: string): Promise<Result>;
  list_user_permission_catalog(): Promise<Result & { catalog?: CatalogRow[] }>;
  get_user_permissions(userId: string): Promise<Result & { permissions?: Record<string, string> }>;
  save_user_permissions(userId: string, grants: GrantRow[]): Promise<Result>;
};

const MAIN_MENUS = ["Master", "Daily", "Entry", "Search", "Reports", "Gst Reports", "Tools"];

export default function UserAccessScreen({ api }: { api: UserAccessApi }) {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [catalog, setCatalog] = useState<CatalogRow[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedMenu, setSelectedMenu] = useState("Master");
  const [grants, setGrants] = useState<Record<string, GrantRow>>({});
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("munim");
  const [canViewKachi, setCanViewKachi] = useState(true);
  const [useCustomMenu, setUseCustomMenu] = useState(true);
  const [accessDays, setAccessDays] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const selectedUser = users.find((row) => row.user_id === selectedUserId);

  const menuRows = useMemo(
    () => catalog.filter((row) => row.menu === selectedMenu),
    [catalog, selectedMenu],
  );

  async function refreshUsers() {
    const response = await api.list_lan_users();
    if (response.ok && response.users) {
      setUsers(response.users);
      if (!selectedUserId && response.users.length) {
        setSelectedUserId(response.users[0].user_id);
      }
    }
  }

  useEffect(() => {
    void refreshUsers();
    void api.list_user_permission_catalog().then((response) => {
      if (response.ok && response.catalog) setCatalog(response.catalog);
    });
  }, [api]);

  useEffect(() => {
    if (!selectedUserId) {
      setGrants({});
      return;
    }
    const user = users.find((row) => row.user_id === selectedUserId);
    if (user) {
      setUsername(user.username);
      setDisplayName(user.display_name);
      setRole(user.role);
      setCanViewKachi(user.can_view_kachi);
      setUseCustomMenu(user.use_custom_menu);
      setAccessDays("");
    }
    void api.get_user_permissions(selectedUserId).then((response) => {
      if (!response.ok || !response.permissions) return;
      const next: Record<string, GrantRow> = {};
      for (const row of catalog) {
        const level = response.permissions[row.key];
        next[row.key] = {
          permission_key: row.key,
          enabled: Boolean(level),
          access_level: level === "write" ? "write" : "read",
          valid_days: "",
        };
      }
      setGrants(next);
    });
  }, [selectedUserId, users, catalog, api]);

  function updateGrant(key: string, patch: Partial<GrantRow>) {
    setGrants((current) => ({
      ...current,
      [key]: { ...current[key], permission_key: key, ...patch },
    }));
  }

  function grantsPayload(): GrantRow[] {
    return Object.values(grants).map((row) => ({
      permission_key: row.permission_key,
      enabled: row.enabled,
      access_level: row.access_level,
      valid_days: row.valid_days,
    }));
  }

  async function saveUser(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    const response = await api.save_lan_user({
      user_id: selectedUserId || undefined,
      username,
      display_name: displayName || username,
      password: password || undefined,
      role,
      can_view_kachi: canViewKachi,
      use_custom_menu: useCustomMenu,
      is_active: true,
      access_days: accessDays || undefined,
      permissions: grantsPayload(),
    });
    if (!response.ok) {
      setError(response.error ?? "Could not save user");
      return;
    }
    setMessage("User saved.");
    setPassword("");
    await refreshUsers();
  }

  async function savePermissionsOnly() {
    if (!selectedUserId) return;
    setError("");
    const response = await api.save_user_permissions(selectedUserId, grantsPayload());
    if (!response.ok) {
      setError(response.error ?? "Could not save permissions");
      return;
    }
    setMessage("Page access saved.");
  }

  async function deleteUser() {
    if (!selectedUserId) return;
    if (!window.confirm("Delete this user?")) return;
    const response = await api.delete_lan_user(selectedUserId);
    if (!response.ok) {
      setError(response.error ?? "Could not delete user");
      return;
    }
    setSelectedUserId("");
    await refreshUsers();
  }

  function newUser() {
    setSelectedUserId("");
    setUsername("");
    setDisplayName("");
    setPassword("");
    setRole("munim");
    setUseCustomMenu(true);
    setAccessDays("");
    const next: Record<string, GrantRow> = {};
    for (const row of catalog) {
      next[row.key] = {
        permission_key: row.key,
        enabled: false,
        access_level: "read",
        valid_days: "",
      };
    }
    setGrants(next);
  }

  return (
    <section className="user-access-screen accounts-entry-screen">
      <header className="accounts-entry-title">Users — page access (Munim / staff)</header>
      <p className="accounts-entry-status">
        Owner (admin) sees all menus. Tick pages below for restricted users; choose Read or Read+Write.
        Optional days limit access for that page or set account days when saving the user.
      </p>
      <div className="user-access-layout">
        <aside className="user-access-sidebar">
          <h3>Users</h3>
          <ul className="user-access-list">
            {users.map((user) => (
              <li key={user.user_id}>
                <button
                  type="button"
                  className={user.user_id === selectedUserId ? "is-selected" : ""}
                  onClick={() => setSelectedUserId(user.user_id)}
                >
                  {user.username}
                </button>
              </li>
            ))}
          </ul>
          <h3>Main Menus</h3>
          <ul className="user-access-list">
            {MAIN_MENUS.map((menu) => (
              <li key={menu}>
                <button
                  type="button"
                  className={menu === selectedMenu ? "is-selected" : ""}
                  onClick={() => setSelectedMenu(menu)}
                >
                  {menu}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="user-access-main">
          <form className="user-access-form" onSubmit={(event) => void saveUser(event)}>
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
                <option value="admin">Owner / Admin (full access)</option>
                <option value="munim">Munim</option>
                <option value="operator">Operator</option>
                <option value="clerk">Clerk (read-only role)</option>
              </select>
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useCustomMenu}
                onChange={(e) => setUseCustomMenu(e.target.checked)}
              />
              Restrict menus to ticks below
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={canViewKachi}
                onChange={(e) => setCanViewKachi(e.target.checked)}
              />
              Can view Kachi company
            </label>
            <label>
              Account access (days from today)
              <input
                inputMode="numeric"
                placeholder="e.g. 3"
                value={accessDays}
                onChange={(e) => setAccessDays(e.target.value)}
              />
            </label>
            {selectedUser?.access_valid_until && (
              <p className="accounts-entry-status">Valid until: {selectedUser.access_valid_until}</p>
            )}
            <div className="user-access-toolbar">
              <button type="submit">Save User</button>
              <button type="button" onClick={() => void savePermissionsOnly()}>
                Save access grid
              </button>
              <button type="button" onClick={newUser}>
                New User
              </button>
              <button type="button" className="danger-btn" onClick={() => void deleteUser()}>
                Delete User
              </button>
            </div>
          </form>

          <table className="accounts-entry-grid user-access-grid">
            <thead>
              <tr>
                <th>Option 1</th>
                <th>Option 2</th>
                <th>Option 3</th>
                <th>Enabled</th>
                <th>Access</th>
                <th>Days</th>
              </tr>
            </thead>
            <tbody>
              {menuRows.map((row) => {
                const grant = grants[row.key] ?? {
                  permission_key: row.key,
                  enabled: false,
                  access_level: "read" as const,
                  valid_days: "",
                };
                return (
                  <tr key={row.key}>
                    <td>{row.menu}</td>
                    <td>{row.group || "—"}</td>
                    <td>{row.label}</td>
                    <td>
                      <input
                        type="checkbox"
                        checked={grant.enabled}
                        onChange={(e) => updateGrant(row.key, { enabled: e.target.checked })}
                      />
                    </td>
                    <td>
                      <select
                        value={grant.access_level}
                        disabled={!grant.enabled}
                        onChange={(e) =>
                          updateGrant(row.key, {
                            access_level: e.target.value as "read" | "write",
                          })
                        }
                      >
                        <option value="read">Read only</option>
                        <option value="write">Read + Write</option>
                      </select>
                    </td>
                    <td>
                      <input
                        className="picker-field"
                        inputMode="numeric"
                        placeholder="—"
                        disabled={!grant.enabled}
                        value={grant.valid_days}
                        onChange={(e) => updateGrant(row.key, { valid_days: e.target.value })}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {message && <p className="accounts-entry-status">{message}</p>}
          {error && <p className="accounts-entry-error">{error}</p>}
        </div>
      </div>
    </section>
  );
}
