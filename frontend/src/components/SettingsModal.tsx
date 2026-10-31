import { useEffect, useState } from "react";

import type { ChargeRule, DesktopApi, Result } from "../api/types";
import Button from "./Button";
import Card from "./Card";
import Modal from "./Modal";

function SettingsModal({ api, onClose }: { api: DesktopApi; onClose(): void }) {
  const [rules, setRules] = useState<ChargeRule[]>([]);
  const [message, setMessage] = useState<Result | null>(null);
  const [draftRates, setDraftRates] = useState<Record<string, string>>({});

  useEffect(() => {
    void api.list_charge_rules().then((response) => {
      if (response.ok) {
        const loaded = response.charge_rules ?? [];
        setRules(loaded);
        setDraftRates(Object.fromEntries(loaded.map((rule) => [rule.charge_rule_id, rule.rate_decimal])));
      }
    });
  }, [api]);

  async function saveRule(rule: ChargeRule) {
    const response = await api.revise_charge_rule(rule.charge_rule_id, {
      rate_decimal: draftRates[rule.charge_rule_id],
      label: rule.label,
      effective_from: new Date().toISOString().slice(0, 10),
    });
    setMessage(response);
    if (response.ok) {
      const refreshed = await api.list_charge_rules();
      if (refreshed.ok) {
        const loaded = refreshed.charge_rules ?? [];
        setRules(loaded);
        setDraftRates(Object.fromEntries(loaded.map((item) => [item.charge_rule_id, item.rate_decimal])));
      }
    }
  }

  const grouped = rules.reduce<Record<string, ChargeRule[]>>((acc, rule) => {
    const bucket = rule.is_tax ? "GST / Tax" : rule.code.includes("TDS") ? "TDS" : "Mandi / Market";
    acc[bucket] = [...(acc[bucket] ?? []), rule];
    return acc;
  }, {});

  return (
    <Modal
      title="Administration / Charge Settings"
      onClose={onClose}
      size="large"
      footer={<Button variant="primary" onClick={onClose}>Close</Button>}
    >
      <p className="mb-3 text-xs text-[#37687a]">
        Updating a rule creates a new effective-dated version. Posted documents keep their original charge snapshots.
      </p>
      {Object.entries(grouped).map(([group, items]) => (
        <Card key={group} title={group} className="mb-3">
          <div className="grid gap-2 md:grid-cols-2">
            {items.map((rule) => (
              <div
                key={rule.charge_rule_id}
                className="grid min-w-0 grid-cols-[minmax(0,1fr)_90px_auto] items-center gap-2 border border-[#8aa7b2] bg-white p-2"
              >
                <div className="min-w-0">
                  <strong>{rule.label}</strong>
                  <div className="truncate text-[10px] text-[#37687a]">{rule.transaction_type} · {rule.code}</div>
                </div>
                <input
                  className="px-2 py-1 text-xs"
                  value={draftRates[rule.charge_rule_id] ?? rule.rate_decimal}
                  onChange={(event) => setDraftRates((current) => ({
                    ...current,
                    [rule.charge_rule_id]: event.target.value,
                  }))}
                />
                <Button onClick={() => void saveRule(rule)}>Revise</Button>
              </div>
            ))}
          </div>
        </Card>
      ))}
      {message && !message.ok && <p className="text-xs text-red-700">{message.error}</p>}
    </Modal>
  );
}

export default SettingsModal;
