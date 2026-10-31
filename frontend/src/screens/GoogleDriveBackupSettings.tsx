import { FormEvent, useEffect, useState } from "react";

import type { Result } from "../api/types";

type SettingsApi = {
  get_company_settings(): Promise<Result & { settings?: Record<string, unknown> }>;
  save_company_settings(settings: Record<string, unknown>): Promise<Result>;
  create_backup?(destination: string): Promise<Result & { mirrored?: boolean; uploaded?: boolean; sync_path?: string }>;
};

export default function GoogleDriveBackupSettings({ api }: { api: SettingsApi }) {
  const [enabled, setEnabled] = useState(false);
  const [googleEmail, setGoogleEmail] = useState("");
  const [syncFolder, setSyncFolder] = useState("");
  const [serviceAccountPath, setServiceAccountPath] = useState("");
  const [driveFolderId, setDriveFolderId] = useState("");
  const [backupPath, setBackupPath] = useState("C:\\AnajERP\\backup");
  const [baseSettings, setBaseSettings] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    void api.get_company_settings().then((response) => {
      if (!response.ok || !response.settings) return;
      const settings = response.settings;
      setBaseSettings(settings);
      setEnabled(Boolean(settings.google_drive_enabled));
      setGoogleEmail(String(settings.google_email ?? ""));
      setSyncFolder(String(settings.google_drive_sync_folder ?? ""));
      setServiceAccountPath(String(settings.google_service_account_json_path ?? ""));
      setDriveFolderId(String(settings.google_drive_folder_id ?? ""));
      const path = settings.default_backup_path;
      if (path) setBackupPath(String(path));
    });
  }, [api]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const response = await api.save_company_settings({
      ...baseSettings,
      google_drive_enabled: enabled,
      google_email: googleEmail,
      google_drive_sync_folder: syncFolder,
      google_service_account_json_path: serviceAccountPath,
      google_drive_folder_id: driveFolderId,
      default_backup_path: backupPath,
    });
    setResult(response);
  }

  async function testBackup() {
    if (!api.create_backup) return;
    const response = await api.create_backup(backupPath);
    setResult(response);
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void save(event)}>
      <h2>Google Drive Backup (optional)</h2>
      <p className="status-message mb-2">
        Easiest: set sync folder to your Google Drive desktop folder — every local backup is copied there automatically.
        Advanced: service account JSON + Drive folder ID uploads via API (requires pip install anaj-erp[integrations]).
      </p>
      <label className="checkbox-label">
        <input checked={enabled} type="checkbox" onChange={(e) => setEnabled(e.target.checked)} />
        Enable Google Drive backup steps after Create Backup
      </label>
      <label>
        Gmail / Google account (for your reference)
        <input value={googleEmail} onChange={(e) => setGoogleEmail(e.target.value)} placeholder="mandi@example.com" />
      </label>
      <label>
        Google Drive sync folder (local path)
        <input value={syncFolder} onChange={(e) => setSyncFolder(e.target.value)} placeholder="C:\\Users\\You\\Google Drive\\AnajERP" />
      </label>
      <label>
        Service account JSON path (optional API upload)
        <input value={serviceAccountPath} onChange={(e) => setServiceAccountPath(e.target.value)} />
      </label>
      <label>
        Drive folder ID (share folder with service account email)
        <input value={driveFolderId} onChange={(e) => setDriveFolderId(e.target.value)} />
      </label>
      <label>
        Local backup file path
        <input value={backupPath} onChange={(e) => setBackupPath(e.target.value)} />
      </label>
      <div className="flex gap-2 mt-2">
        <button type="submit">Save</button>
        <button type="button" onClick={() => void testBackup()}>Test backup now</button>
      </div>
      {result && (
        <p className={result.ok ? "text-green-800" : "text-red-700"}>
          {result.ok
            ? `Backup OK${result.sync_path ? ` · synced to ${String(result.sync_path)}` : ""}${result.uploaded ? " · uploaded to Drive" : ""}`
            : result.error}
        </p>
      )}
    </form>
  );
}
