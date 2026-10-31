import { FormEvent, useEffect, useState } from "react";

import TransactionScreen, { InlineField } from "../components/TransactionScreen";
import type { Result } from "../api/types";

type GstSlab = {
  hsn_sac: string;
  description: string;
  cgst: string;
  sgst: string;
  igst: string;
  effective_from: string;
};

type SettingsApi = {
  get_company_settings(): Promise<Result & { settings?: Record<string, unknown> }>;
  save_company_settings(settings: Record<string, unknown>): Promise<Result>;
};

const emptySlab = (): GstSlab => ({
  hsn_sac: "",
  description: "",
  cgst: "",
  sgst: "",
  igst: "",
  effective_from: new Date().toISOString().slice(0, 10),
});

export default function GstRatesScreen({
  api,
  mode = "add",
  onExit,
}: {
  api: SettingsApi;
  mode?: "add" | "modify";
  onExit(): void;
}) {
  const [baseSettings, setBaseSettings] = useState<Record<string, unknown>>({});
  const [slab, setSlab] = useState<GstSlab>(emptySlab);
  const [slabs, setSlabs] = useState<GstSlab[]>([]);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    void api.get_company_settings().then((response) => {
      if (!response.ok || !response.settings) return;
      setBaseSettings(response.settings);
      const stored = response.settings.gst_rate_slabs;
      if (Array.isArray(stored)) {
        setSlabs(
          stored.map((row) => ({
            hsn_sac: String((row as GstSlab).hsn_sac ?? ""),
            description: String((row as GstSlab).description ?? ""),
            cgst: String((row as GstSlab).cgst ?? ""),
            sgst: String((row as GstSlab).sgst ?? ""),
            igst: String((row as GstSlab).igst ?? ""),
            effective_from: String((row as GstSlab).effective_from ?? ""),
          })),
        );
      }
    });
  }, [api]);

  function update(key: keyof GstSlab, value: string) {
    setSlab((current) => ({ ...current, [key]: value }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!slab.hsn_sac.trim()) {
      setResult({ ok: false, error: "HSN/SAC is required." });
      return;
    }
    const next =
      mode === "modify"
        ? slabs.map((row) => (row.hsn_sac === slab.hsn_sac ? slab : row))
        : [...slabs.filter((row) => row.hsn_sac !== slab.hsn_sac), slab];
    const response = await api.save_company_settings({
      ...baseSettings,
      gst_rate_slabs: next,
    });
    setResult(response);
    if (response.ok) {
      setSlabs(next);
      if (mode === "add") setSlab(emptySlab());
    }
  }

  return (
    <TransactionScreen
      title={mode === "modify" ? "Gst Rates Modify" : "Gst Rates Add"}
      footerMessage={result && !result.ok ? result.error : result?.ok ? "GST rate saved." : undefined}
      header={(
        <>
          <InlineField label="HSN / SAC">
            <input
              className="w-full rounded border px-1 py-0.5"
              data-enter-order={1}
              value={slab.hsn_sac}
              onChange={(e) => update("hsn_sac", e.target.value.toUpperCase())}
            />
          </InlineField>
          <InlineField label="Description">
            <input
              className="w-full rounded border px-1 py-0.5"
              data-enter-order={2}
              value={slab.description}
              onChange={(e) => update("description", e.target.value)}
            />
          </InlineField>
          <InlineField label="CGST %">
            <input
              className="w-full rounded border px-1 py-0.5 mandi-numeric"
              data-enter-order={3}
              inputMode="decimal"
              value={slab.cgst}
              onChange={(e) => update("cgst", e.target.value)}
            />
          </InlineField>
          <InlineField label="SGST %">
            <input
              className="w-full rounded border px-1 py-0.5 mandi-numeric"
              data-enter-order={4}
              inputMode="decimal"
              value={slab.sgst}
              onChange={(e) => update("sgst", e.target.value)}
            />
          </InlineField>
          <InlineField label="IGST %">
            <input
              className="w-full rounded border px-1 py-0.5 mandi-numeric"
              data-enter-order={5}
              inputMode="decimal"
              value={slab.igst}
              onChange={(e) => update("igst", e.target.value)}
            />
          </InlineField>
          <InlineField label="Effective From">
            <input
              className="w-full rounded border px-1 py-0.5"
              data-enter-order={6}
              type="date"
              value={slab.effective_from}
              onChange={(e) => update("effective_from", e.target.value)}
            />
          </InlineField>
        </>
      )}
      grid={(
        <table className="sortable-table text-xs">
          <thead>
            <tr>
              <th>HSN/SAC</th>
              <th>Description</th>
              <th>CGST</th>
              <th>SGST</th>
              <th>IGST</th>
              <th>From</th>
            </tr>
          </thead>
          <tbody>
            {slabs.map((row) => (
              <tr
                key={row.hsn_sac}
                className={mode === "modify" && row.hsn_sac === slab.hsn_sac ? "selected" : ""}
                onClick={() => mode === "modify" && setSlab(row)}
              >
                <td>{row.hsn_sac}</td>
                <td>{row.description}</td>
                <td>{row.cgst}</td>
                <td>{row.sgst}</td>
                <td>{row.igst}</td>
                <td>{row.effective_from}</td>
              </tr>
            ))}
            {!slabs.length && (
              <tr>
                <td colSpan={6}>No GST slabs configured yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
      onSave={(event) => void save(event)}
      onExit={onExit}
    />
  );
}
