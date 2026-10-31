import { FormEvent, useEffect, useState } from "react";

import type { Result } from "../api/types";

type DesignApi = {
  get_print_design(): Promise<Result & { design?: Record<string, unknown> }>;
  save_print_design(design: Record<string, unknown>): Promise<Result>;
};

function PrintFormatDesigner({ api }: { api: DesignApi }) {
  const [mandiLicense, setMandiLicense] = useState("");
  const [bankQr, setBankQr] = useState("");
  const [customTerms, setCustomTerms] = useState("");
  const [headerLines, setHeaderLines] = useState("");
  const [footerLines, setFooterLines] = useState("");
  const [showQr, setShowQr] = useState(true);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    void api.get_print_design().then((response) => {
      if (!response.ok || !response.design) return;
      const design = response.design;
      setMandiLicense(String(design.mandi_license_no ?? ""));
      setBankQr(String(design.bank_qr_payload ?? ""));
      setCustomTerms(String(design.custom_terms ?? ""));
      setShowQr(Boolean(design.show_bank_qr ?? true));
      const headers = design.header_lines;
      const footers = design.footer_lines;
      if (Array.isArray(headers)) setHeaderLines(headers.join("\n"));
      if (Array.isArray(footers)) setFooterLines(footers.join("\n"));
    });
  }, [api]);

  async function save(event: FormEvent) {
    event.preventDefault();
    const response = await api.save_print_design({
      mandi_license_no: mandiLicense,
      bank_qr_payload: bankQr,
      custom_terms: customTerms,
      show_bank_qr: showQr,
      header_lines: headerLines.split("\n").map((line) => line.trim()).filter(Boolean),
      footer_lines: footerLines.split("\n").map((line) => line.trim()).filter(Boolean),
    });
    setResult(response);
  }

  return (
    <form className="entry-form p-2 text-xs" onSubmit={(event) => void save(event)}>
      <h2>Print Format Designer</h2>
      <p className="status-message mb-2">
        Customize mandi bill headers, footers, license line, and bank QR/UPI text. Placeholders:
        {" "}
        <code>{"{company_name}"}</code>, <code>{"{mandi_license_no}"}</code>, <code>{"{city}"}</code>,
        {" "}
        <code>{"{custom_terms}"}</code>.
      </p>
      <label>
        Mandi license number
        <input value={mandiLicense} onChange={(e) => setMandiLicense(e.target.value)} />
      </label>
      <label>
        Bank QR / UPI payload
        <input value={bankQr} onChange={(e) => setBankQr(e.target.value)} />
      </label>
      <label className="checkbox-label">
        <input checked={showQr} type="checkbox" onChange={(e) => setShowQr(e.target.checked)} />
        Print bank QR line on bills
      </label>
      <label>
        Custom terms
        <textarea rows={2} value={customTerms} onChange={(e) => setCustomTerms(e.target.value)} />
      </label>
      <label>
        Header lines (one per line)
        <textarea rows={4} value={headerLines} onChange={(e) => setHeaderLines(e.target.value)} />
      </label>
      <label>
        Footer lines (one per line)
        <textarea rows={3} value={footerLines} onChange={(e) => setFooterLines(e.target.value)} />
      </label>
      <button type="submit">Save print template</button>
      {result && (
        <p className={result.ok ? "text-green-800" : "text-red-700"}>
          {result.ok ? "Template saved." : result.error}
        </p>
      )}
    </form>
  );
}

export default PrintFormatDesigner;
