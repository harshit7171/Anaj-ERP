import { useEffect, useState } from "react";

type ApiResult = { ok: boolean; error?: string; preview_text?: string };

type FieldFlags = Record<string, boolean>;

type LetterApi = {
  get_letterhead_print_options?(): Promise<
    ApiResult & { options?: Record<string, unknown>; profile?: Record<string, string> }
  >;
  save_letterhead_print_options?(options: Record<string, unknown>): Promise<ApiResult>;
  print_company_letterhead?(): Promise<ApiResult & { preview_text?: string }>;
};

const LEFT_FIELDS = [
  ["gst_no", "GST No"],
  ["pan_no", "PAN No"],
  ["market_license_no", "Market License No"],
  ["fssai_license_no", "FSSAI License No"],
  ["iso_no", "ISO No"],
  ["iec_no", "IEC No"],
  ["msme", "MSME"],
] as const;

const RIGHT_FIELDS = [
  ["mobile_no", "Mobile No"],
  ["phone_no", "Phone No"],
  ["email", "E-Mail"],
  ["tan_no", "TAN No"],
  ["cin_no", "CIN No"],
  ["kums_no", "KUMS No"],
  ["rtal_no", "RTAL No"],
] as const;

function bridge(): LetterApi | undefined {
  return window.pywebview?.api as unknown as LetterApi | undefined;
}

export default function LetterHeadPrintScreen({ onExit }: { onExit(): void }) {
  const [nameSource, setNameSource] = useState<"company_name" | "print_name">("company_name");
  const [showAddress, setShowAddress] = useState(true);
  const [fields, setFields] = useState<FieldFlags>({});
  const [preview, setPreview] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  function applyOptions(options: Record<string, unknown>) {
    setNameSource((options.name_source as "company_name" | "print_name") ?? "company_name");
    setShowAddress(Boolean(options.show_address ?? true));
    if (options.fields && typeof options.fields === "object") {
      setFields(options.fields as FieldFlags);
    }
  }

  useEffect(() => {
    void bridge()?.get_letterhead_print_options?.().then((response) => {
      if (response?.ok && response.options) applyOptions(response.options);
    });
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        void printHead();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function persist() {
    await bridge()?.save_letterhead_print_options?.({
      name_source: nameSource,
      show_address: showAddress,
      fields,
    });
  }

  async function printHead() {
    setError("");
    await persist();
    const response = await bridge()?.print_company_letterhead?.();
    if (!response?.ok) {
      setError(response?.error ?? "Print failed.");
      return;
    }
    if (response.preview_text) setPreview(response.preview_text);
    setStatus("Sent to printer.");
  }

  function toggleField(key: string, checked: boolean) {
    setFields((prev) => ({ ...prev, [key]: checked }));
  }

  return (
    <section className="accounts-entry-screen letter-head-screen">
      <header className="accounts-entry-title">Letter Head Print</header>
      <div className="letter-head-layout">
        <div className="letter-head-left">
          <label>
            <input
              type="radio"
              checked={nameSource === "company_name"}
              onChange={() => setNameSource("company_name")}
            />
            Company Name
          </label>
          <label>
            <input
              type="radio"
              checked={nameSource === "print_name"}
              onChange={() => setNameSource("print_name")}
            />
            Company Print Name
          </label>
          <label>
            <input type="checkbox" checked={showAddress} onChange={(e) => setShowAddress(e.target.checked)} />
            Show Address
          </label>
          <div className="letter-field-columns">
            <div>
              {LEFT_FIELDS.map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={fields[key] ?? true}
                    onChange={(e) => toggleField(key, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <div>
              {RIGHT_FIELDS.map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={fields[key] ?? true}
                    onChange={(e) => toggleField(key, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="letter-head-actions">
          <button type="button" disabled title="Font dialog coming soon">
            Set Company Font
          </button>
          <button type="button" disabled title="Font dialog coming soon">
            Set Company Address Font
          </button>
          <button type="button" onClick={() => void printHead()}>
            Print F3
          </button>
          <button type="button" onClick={onExit}>
            Close F4
          </button>
        </div>
      </div>
      {preview && <pre className="letter-head-preview">{preview}</pre>}
      {status && <p className="accounts-entry-status">{status}</p>}
      {error && <p className="accounts-entry-error">{error}</p>}
    </section>
  );
}
