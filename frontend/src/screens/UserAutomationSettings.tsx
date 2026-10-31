import { FormEvent, useEffect, useState } from "react";

import type { Result } from "../api/types";

type SettingsApi = {
  get_company_settings(): Promise<Result & { settings?: Record<string, unknown> }>;
  save_company_settings(settings: Record<string, unknown>): Promise<Result>;
};

type AutomationSettings = {
  tds_popup_on_save: boolean;
  tcs_threshold_popup: boolean;
  tds_194q_popup: boolean;
  rcm_freight_popup: boolean;
  whatsapp_after_invoice: boolean;
  whatsapp_after_form_j: boolean;
  whatsapp_after_form_i: boolean;
  whatsapp_pending_balance: boolean;
  credit_limit_popup: boolean;
};

const defaults: AutomationSettings = {
  tds_popup_on_save: true,
  tcs_threshold_popup: true,
  tds_194q_popup: true,
  rcm_freight_popup: true,
  whatsapp_after_invoice: false,
  whatsapp_after_form_j: true,
  whatsapp_after_form_i: false,
  whatsapp_pending_balance: true,
  credit_limit_popup: true,
};

function readAutomation(settings: Record<string, unknown> | undefined): AutomationSettings {
  const block = settings?.automation;
  if (!block || typeof block !== "object") return defaults;
  const raw = block as Record<string, unknown>;
  return {
    tds_popup_on_save: Boolean(raw.tds_popup_on_save ?? defaults.tds_popup_on_save),
    tcs_threshold_popup: Boolean(raw.tcs_threshold_popup ?? defaults.tcs_threshold_popup),
    tds_194q_popup: Boolean(raw.tds_194q_popup ?? defaults.tds_194q_popup),
    rcm_freight_popup: Boolean(raw.rcm_freight_popup ?? defaults.rcm_freight_popup),
    whatsapp_after_invoice: Boolean(raw.whatsapp_after_invoice ?? defaults.whatsapp_after_invoice),
    whatsapp_after_form_j: Boolean(raw.whatsapp_after_form_j ?? defaults.whatsapp_after_form_j),
    whatsapp_after_form_i: Boolean(raw.whatsapp_after_form_i ?? defaults.whatsapp_after_form_i),
    whatsapp_pending_balance: Boolean(raw.whatsapp_pending_balance ?? defaults.whatsapp_pending_balance),
    credit_limit_popup: Boolean(raw.credit_limit_popup ?? defaults.credit_limit_popup),
  };
}

export default function UserAutomationSettings({ api }: { api: SettingsApi }) {
  const [automation, setAutomation] = useState<AutomationSettings>(defaults);
  const [result, setResult] = useState<Result | null>(null);
  const [baseSettings, setBaseSettings] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void api.get_company_settings().then((response) => {
      if (!response.ok || !response.settings) return;
      setBaseSettings(response.settings);
      setAutomation(readAutomation(response.settings));
    });
  }, [api]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const response = await api.save_company_settings({
      ...baseSettings,
      automation,
    });
    setResult(response);
    if (response.ok) {
      setBaseSettings((current) => ({ ...current, automation }));
    }
  }

  function toggle(key: keyof AutomationSettings) {
    setAutomation((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void save(event)}>
      <h2>User Alerts &amp; WhatsApp</h2>
      <p className="status-message mb-2">
        Turn reminders on or off per company. WhatsApp opens wa.me with farmer/buyer mobile from the account master.
      </p>
      <label className="checkbox-label">
        <input checked={automation.tds_popup_on_save} type="checkbox" onChange={() => toggle("tds_popup_on_save")} />
        Show TDS checklist popup after saving vouchers with TDS
      </label>
      <label className="checkbox-label">
        <input checked={automation.tcs_threshold_popup} type="checkbox" onChange={() => toggle("tcs_threshold_popup")} />
        Dashboard alert when party nears ₹50L TCS threshold (206C(1H))
      </label>
      <label className="checkbox-label">
        <input checked={automation.tds_194q_popup} type="checkbox" onChange={() => toggle("tds_194q_popup")} />
        Alert when purchase turnover crosses ₹50L (TDS 194Q)
      </label>
      <label className="checkbox-label">
        <input checked={automation.rcm_freight_popup} type="checkbox" onChange={() => toggle("rcm_freight_popup")} />
        RCM reminder on GTA / commercial freight services
      </label>
      <label className="checkbox-label">
        <input checked={automation.credit_limit_popup} type="checkbox" onChange={() => toggle("credit_limit_popup")} />
        Credit limit warning on purchase / lifting save
      </label>
      <h3 className="mt-3 font-semibold">WhatsApp (one-click share)</h3>
      <label className="checkbox-label">
        <input checked={automation.whatsapp_after_invoice} type="checkbox" onChange={() => toggle("whatsapp_after_invoice")} />
        Offer WhatsApp after Sale Invoice save
      </label>
      <label className="checkbox-label">
        <input checked={automation.whatsapp_after_form_j} type="checkbox" onChange={() => toggle("whatsapp_after_form_j")} />
        Offer WhatsApp after J-Form (Parchi) save
      </label>
      <label className="checkbox-label">
        <input checked={automation.whatsapp_after_form_i} type="checkbox" onChange={() => toggle("whatsapp_after_form_i")} />
        Offer WhatsApp after I-Form save
      </label>
      <label className="checkbox-label">
        <input checked={automation.whatsapp_pending_balance} type="checkbox" onChange={() => toggle("whatsapp_pending_balance")} />
        Show WhatsApp reminder on Find Account / pending balance rows
      </label>
      <button className="mt-3" type="submit">Save preferences</button>
      {result && (
        <p className={result.ok ? "text-green-800" : "text-red-700"}>
          {result.ok ? "Preferences saved." : result.error}
        </p>
      )}
    </form>
  );
}

export function readAutomationFromSettings(settings: Record<string, unknown> | undefined): AutomationSettings {
  return readAutomation(settings);
}
