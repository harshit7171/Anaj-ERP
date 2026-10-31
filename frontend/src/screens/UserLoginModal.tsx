import { FormEvent, useState } from "react";

import type { Result } from "../api/types";
import type { UserSession } from "../app/access/menuAccess";

type LoginApi = {
  user_login(username: string, password: string): Promise<Result & { session?: UserSession }>;
};

export default function UserLoginModal({
  api,
  onLoggedIn,
}: {
  api: LoginApi;
  onLoggedIn(session: UserSession): void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const response = await api.user_login(username.trim(), password);
    setBusy(false);
    if (!response.ok || !response.session) {
      setError(response.error ?? "Login failed");
      return;
    }
    onLoggedIn(response.session);
  }

  return (
    <div className="blocking-modal user-login-modal" role="dialog" aria-modal="true">
      <form className="saved-dialog user-login-form" onSubmit={(event) => void submit(event)}>
        <header>
          <span>User Login</span>
        </header>
        <p className="status-message">
          Sign in with the credentials assigned by the owner. You will only see menus enabled for your user.
        </p>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="error-message">{error}</p>}
        <button className="primary-button" disabled={busy} type="submit">
          Login
        </button>
      </form>
    </div>
  );
}
