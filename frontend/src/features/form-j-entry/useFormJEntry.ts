import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type { LookupItem } from "../../Autocomplete";
import {
  buildChargeOverrides,
  documentWorkflowApi,
  rupeesToPaise,
  type DocumentWorkflowResult,
} from "../shared/mandiDocumentUtils";
import { DheriRow, defaultDueDateIso, formJQuantity, isoToday, newDheriRow } from "./constants";

export function useFormJEntry({ onExit }: { onExit(): void }) {
  const [farmer, setFarmer] = useState<LookupItem | null>(null);
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(isoToday());
  const [dueDate, setDueDate] = useState(defaultDueDateIso);
  const [rows, setRows] = useState<DheriRow[]>([newDheriRow(1)]);
  const [purchaseAccount, setPurchaseAccount] = useState<LookupItem | null>(null);
  const [farmerAccount, setFarmerAccount] = useState<LookupItem | null>(null);
  const [commodityTransfer, setCommodityTransfer] = useState<LookupItem | null>(null);
  const [gatePassRequired, setGatePassRequired] = useState(false);
  const [selfPurchase, setSelfPurchase] = useState(false);
  const [bonus, setBonus] = useState("");
  const [excludedCharges, setExcludedCharges] = useState<string[]>([]);
  const [rateOverrides, setRateOverrides] = useState<Record<string, string>>({});
  const [showExpenses, setShowExpenses] = useState(true);
  const [calculation, setCalculation] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<DocumentWorkflowResult | null>(null);
  const [postedId, setPostedId] = useState("");
  const [showSavedModal, setShowSavedModal] = useState(false);

  useEffect(() => {
    void documentWorkflowApi()?.next_document_number("form_j").then((response) => {
      if (response?.ok && response.document_number) setNumber(response.document_number);
    });
  }, []);

  useEffect(() => {
    const shortcut = (event: globalThis.KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === "f") {
        event.preventDefault();
        setSelfPurchase((value) => !value);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  const updateRow = useCallback((rowId: number, values: Partial<DheriRow>) => {
    setRows((current) => current.map((row) => (row.rowId === rowId ? { ...row, ...values } : row)));
  }, []);

  const appendDheri = useCallback(() => {
    setRows((current) => [...current, newDheriRow(Math.max(...current.map((row) => row.rowId)) + 1)]);
    window.setTimeout(() => {
      document.querySelector<HTMLElement>(".dheri-panel [data-grid-row]:last-of-type input")?.focus();
    }, 0);
  }, []);

  const documentLines = useMemo(
    () =>
      rows
        .filter((row) => row.commodity && Number(row.rate) >= 0 && formJQuantity(row) > 0)
        .map((row) => ({
          commodity_id: row.commodity?.id,
          purchaser_party_id: selfPurchase ? null : row.purchaser?.id ?? null,
          gate_pass_number: row.gpNo,
          description: row.commodity?.label ?? "Commodity",
          bags_scaled: Math.round(Number(row.bags || 0)),
          bag_scale: 0,
          packing_weight_scaled: Math.round(Number(row.pack || 0) * 1000),
          loose_quantity_scaled: Math.round(Number(row.extra || 0) * 1000),
          quantity_scaled: Math.round(formJQuantity(row) * 1000),
          quantity_scale: 3,
          rate_paise: rupeesToPaise(row.rate),
          rate_unit: "quintal",
        })),
    [rows, selfPurchase],
  );

  const payload = useMemo(
    () => ({
      document_type: "form_j",
      document_number: number,
      document_date: date,
      party_id: farmer?.id ?? null,
      main_account_id: purchaseAccount?.id ?? commodityTransfer?.id ?? null,
      party_account_id: farmerAccount?.id ?? null,
      excluded_charge_codes: excludedCharges,
      overrides: buildChargeOverrides(calculation, rateOverrides),
      bonus_paise: rupeesToPaise(bonus),
      lines: documentLines,
      header: {
        due_date: dueDate,
        commodity_transfer_account_id: commodityTransfer?.id ?? null,
        gate_pass_required: gatePassRequired,
        self_purchase: selfPurchase,
      },
    }),
    [
      bonus,
      calculation,
      commodityTransfer?.id,
      date,
      documentLines,
      dueDate,
      excludedCharges,
      farmer?.id,
      farmerAccount?.id,
      gatePassRequired,
      number,
      purchaseAccount?.id,
      rateOverrides,
      selfPurchase,
    ],
  );

  const calculate = useCallback(async () => {
    const response = await documentWorkflowApi()?.calculate_document(payload);
    if (response) {
      setResult(response);
      setCalculation(response.calculation ?? null);
    }
  }, [payload]);

  useEffect(() => {
    if (!documentLines.length) {
      setCalculation(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void documentWorkflowApi()?.calculate_document(payload).then((response) => {
        if (response?.ok) setCalculation(response.calculation ?? null);
      });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [documentLines.length, payload]);

  const submit = useCallback(
    async (event?: FormEvent) => {
      event?.preventDefault();
      if (!farmer || !farmerAccount || !purchaseAccount || !documentLines.length) {
        setResult({
          ok: false,
          error: "Select the farmer, posting accounts and at least one complete dheri.",
        });
        return;
      }
      if (!selfPurchase && rows.some((row) => row.commodity && !row.purchaser)) {
        setResult({ ok: false, error: "Select a purchaser for every dheri." });
        return;
      }
      const response = await documentWorkflowApi()?.post_document(payload);
      if (response) {
        setResult(response);
        if (response.ok) {
          const document = response.document as { document_id?: string } | undefined;
          if (document?.document_id) setPostedId(document.document_id);
          setShowSavedModal(true);
          const next = await documentWorkflowApi()?.next_document_number("form_j");
          if (next?.document_number) setNumber(next.document_number);
        }
      }
    },
    [documentLines.length, farmer, farmerAccount, payload, purchaseAccount, rows, selfPurchase],
  );

  const printDocument = useCallback(async () => {
    if (!postedId) return;
    const api = documentWorkflowApi();
    const response = await (api?.print_mandi_bill?.({
      document_id: postedId,
      copies: 3,
      format: "auto",
      silent: true,
      html_columns: 80,
      escpos_columns: 80,
    }) ?? api?.print_document(postedId));
    if (response) {
      setResult(response);
      if (response.ok) setShowSavedModal(true);
    }
  }, [postedId]);

  const charges = (calculation?.charges ?? []) as Record<string, unknown>[];

  return {
    onExit,
    farmer,
    setFarmer,
    number,
    setNumber,
    date,
    setDate,
    dueDate,
    setDueDate,
    rows,
    updateRow,
    appendDheri,
    setRows,
    purchaseAccount,
    setPurchaseAccount,
    farmerAccount,
    setFarmerAccount,
    commodityTransfer,
    setCommodityTransfer,
    gatePassRequired,
    setGatePassRequired,
    selfPurchase,
    setSelfPurchase,
    bonus,
    setBonus,
    excludedCharges,
    setExcludedCharges,
    rateOverrides,
    setRateOverrides,
    showExpenses,
    setShowExpenses,
    calculation,
    result,
    postedId,
    showSavedModal,
    setShowSavedModal,
    charges,
    calculate,
    submit,
    printDocument,
    formJQuantity,
  };
}

export type FormJEntryViewModel = ReturnType<typeof useFormJEntry>;
