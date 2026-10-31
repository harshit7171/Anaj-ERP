import { FormEvent, useEffect, useState } from "react";

import type { Result } from "../api/types";

type CloudApi = {
  get_company_settings(): Promise<Result & { settings?: Record<string, unknown> }>;
  save_company_settings(settings: Record<string, unknown>): Promise<Result>;
  create_backup?(destination: string): Promise<Result>;
  start_cloud_oauth?(provider: string): Promise<
    Result & {
      user_code?: string;
      verification_url?: string;
      device_code?: string;
      interval?: number;
    }
  >;
  poll_cloud_oauth?(provider: string, deviceCode: string): Promise<Result & { pending?: boolean }>;
  run_encrypted_cloud_backup?(destination: string): Promise<Result & { encrypted_path?: string }>;
};

export default function CloudBackupSettings({ api }: { api: CloudApi }) {
  const [baseSettings, setBaseSettings] = useState<Record<string, unknown>>({});
  const [backupPath, setBackupPath] = useState("C:\\AnajERP\\backup");
  const [passphrase, setPassphrase] = useState("");
  const [onExit, setOnExit] = useState(false);
  const [googleOAuthClientId, setGoogleOAuthClientId] = useState("");
  const [googleOAuthSecret, setGoogleOAuthSecret] = useState("");
  const [microsoftOAuthClientId, setMicrosoftOAuthClientId] = useState("");
  const [googleSync, setGoogleSync] = useState("");
  const [onedriveSync, setOnedriveSync] = useState("");
  const [providers, setProviders] = useState<string[]>(["google"]);
  const [oauthHint, setOauthHint] = useState("");
  const [deviceCode, setDeviceCode] = useState("");
  const [oauthProvider, setOauthProvider] = useState<"google" | "onedrive">("google");
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    void api.get_company_settings().then((response) => {
      if (!response.ok || !response.settings) return;
      const settings = response.settings;
      setBaseSettings(settings);
      if (settings.default_backup_path) setBackupPath(String(settings.default_backup_path));
      setOnExit(Boolean(settings.cloud_backup_on_exit));
      setGoogleOAuthClientId(String(settings.google_oauth_client_id ?? ""));
      setGoogleOAuthSecret(String(settings.google_oauth_client_secret ?? ""));
      setMicrosoftOAuthClientId(String(settings.microsoft_oauth_client_id ?? ""));
      setGoogleSync(String(settings.google_drive_sync_folder ?? ""));
      setOnedriveSync(String(settings.onedrive_sync_folder ?? ""));
      const list = settings.cloud_backup_providers;
      if (Array.isArray(list)) setProviders(list.map(String));
    });
  }, [api]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const response = await api.save_company_settings({
      ...baseSettings,
      default_backup_path: backupPath,
      cloud_backup_on_exit: onExit,
      cloud_backup_passphrase: passphrase || baseSettings.cloud_backup_passphrase,
      cloud_backup_providers: providers,
      google_oauth_client_id: googleOAuthClientId,
      google_oauth_client_secret: googleOAuthSecret,
      microsoft_oauth_client_id: microsoftOAuthClientId,
      google_drive_sync_folder: googleSync,
      onedrive_sync_folder: onedriveSync,
      cloud_backup_google_enabled: providers.includes("google"),
      cloud_backup_onedrive_enabled: providers.includes("onedrive"),
    });
    setResult(response);
  }

  async function startOAuth(provider: "google" | "onedrive") {
    setOauthProvider(provider);
    const response = await api.start_cloud_oauth?.(provider);
    if (!response?.ok) {
      setResult(response ?? { ok: false, error: "OAuth start failed" });
      return;
    }
    setDeviceCode(String(response.device_code ?? ""));
    setOauthHint(
      `Open ${String(response.verification_url ?? "")} and enter code ${String(response.user_code ?? "")}`,
    );
  }

  async function completeOAuth() {
    if (!deviceCode) return;
    const response = await api.poll_cloud_oauth?.(oauthProvider, deviceCode);
    setResult(response ?? null);
    if (response?.ok) setOauthHint("Linked — tokens saved in company settings.");
  }

  async function testEncryptedBackup() {
    const response = await api.run_encrypted_cloud_backup?.(backupPath);
    setResult(response ?? null);
  }

  function toggleProvider(key: string) {
    setProviders((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  }

  return (
    <form className="entry-form p-2 text-xs cloud-backup-settings" onSubmit={(event) => void save(event)}>
      <h2>Encrypted Cloud Backup (Google Drive & OneDrive)</h2>
      <p className="status-message mb-2">
        Creates `.bak.enc` snapshots (AES via Fernet + your passphrase). OAuth2 device login uploads to your personal
        cloud; or mirror into Desktop sync folders. Optional automatic upload when you exit the app.
      </p>
      <label className="checkbox-label">
        <input checked={onExit} type="checkbox" onChange={(e) => setOnExit(e.target.checked)} />
        Run encrypted cloud backup on software exit
      </label>
      <label>
        Backup passphrase (8+ characters — required for encryption)
        <input type="password" value={passphrase} onChange={(e) => setPassphrase(e.target.value)} autoComplete="new-password" />
      </label>
      <label>
        Local backup folder
        <input value={backupPath} onChange={(e) => setBackupPath(e.target.value)} />
      </label>
      <fieldset>
        <legend>Providers</legend>
        <label className="checkbox-label">
          <input checked={providers.includes("google")} type="checkbox" onChange={() => toggleProvider("google")} />
          Google Drive
        </label>
        <label className="checkbox-label">
          <input checked={providers.includes("onedrive")} type="checkbox" onChange={() => toggleProvider("onedrive")} />
          Microsoft OneDrive
        </label>
      </fieldset>
      <label>
        Google OAuth client ID (device flow)
        <input value={googleOAuthClientId} onChange={(e) => setGoogleOAuthClientId(e.target.value)} />
      </label>
      <label>
        Google OAuth client secret (optional)
        <input value={googleOAuthSecret} onChange={(e) => setGoogleOAuthSecret(e.target.value)} />
      </label>
      <label>
        Microsoft OAuth client ID (OneDrive)
        <input value={microsoftOAuthClientId} onChange={(e) => setMicrosoftOAuthClientId(e.target.value)} />
      </label>
      <label>
        Google Drive desktop sync folder
        <input value={googleSync} onChange={(e) => setGoogleSync(e.target.value)} />
      </label>
      <label>
        OneDrive desktop sync folder
        <input value={onedriveSync} onChange={(e) => setOnedriveSync(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-2 mt-2">
        <button type="submit">Save</button>
        <button type="button" onClick={() => void startOAuth("google")}>
          Link Google (device code)
        </button>
        <button type="button" onClick={() => void startOAuth("onedrive")}>
          Link OneDrive (device code)
        </button>
        <button type="button" onClick={() => void completeOAuth()}>
          Complete OAuth login
        </button>
        <button type="button" onClick={() => void testEncryptedBackup()}>
          Test encrypted backup now
        </button>
      </div>
      {oauthHint && <p className="status-message mt-2">{oauthHint}</p>}
      {result && (
        <p className={result.ok ? "text-green-800" : "text-red-700"}>
          {result.ok
            ? `OK${result.encrypted_path ? ` · ${String(result.encrypted_path)}` : ""}`
            : result.error}
        </p>
      )}
    </form>
  );
}
