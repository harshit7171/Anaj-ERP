import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import Autocomplete, { LookupItem } from "./Autocomplete";
import AnimatedAmount from "./components/AnimatedAmount";
import CreditLimitWarningModal from "./components/CreditLimitWarningModal";
import FormToast from "./components/FormToast";
import MessageDialog from "./components/MessageDialog";
import ModifyRecordSearchBar, { type ModifySearchRow } from "./components/ModifyRecordSearchBar";
import PrintOptionsPanel, {
  defaultPrintOptions,
  type PrintOptions,
} from "./components/PrintOptionsPanel";
import TransactionScreen, { InlineField } from "./components/TransactionScreen";
import type { CreditEvaluation } from "./api/types";
import { useGridEnterNavigation } from "./hooks/useGridEnterNavigation";
import { validateDenseDocument } from "./utils/mandiValidation";

type Result = {
  ok: boolean;
  error?: string;
  error_type?: string;
  document?: Record<string, unknown>;
  calculation?: Record<string, unknown>;
  document_number?: string;
};

type WorkflowApi = {
  calculate_document(payload: Record<string, unknown>): Promise<Result>;
  check_credit_limit(payload: Record<string, unknown>): Promise<Result & { evaluation?: CreditEvaluation }>;
  next_document_number(documentType: string): Promise<Result>;
  post_document(payload: Record<string, unknown>): Promise<Result>;
  print_document(documentId: string): Promise<Result>;
  print_mandi_bill?(payload: Record<string, unknown>): Promise<Result & { paths?: string[] }>;
  whatsapp_for_document?(documentId: string): Promise<Result & { url?: string }>;
  open_whatsapp_url?(url: string): Promise<Result>;
  attach_document_file?(documentId: string, source: string): Promise<Result>;
  list_document_attachments?(
    documentId: string,
  ): Promise<Result & { attachments?: { attachment_id: string; file_name: string }[] }>;
  search_documents?(
    documentType: string,
    query: string,
    limit?: number,
  ): Promise<Result & { rows?: ModifySearchRow[] }>;
  get_document?(
    documentId: string,
  ): Promise<
    Result & {
      document?: { header?: Record<string, unknown>; lines?: Record<string, unknown>[] };
      audit_trail?: { action: string; occurred_at: string; reason?: string }[];
    }
  >;
};

type HeaderField = {
  key: string;
  label: string;
  type?: "text" | "time" | "select" | "party" | "readonly";
  options?: string[];
  primaryParty?: boolean;
  derivedFrom?: string;
  derivedProperty?: "gstin" | "address" | "phone";
};

type DenseRow = {
  rowId: number;
  commodity: LookupItem | null;
  values: Record<string, string>;
};

type Column = {
  key: string;
  label: string;
  type?: "text" | "number" | "select" | "commodity" | "output";
  options?: string[];
  defaultValue?: string;
  integer?: boolean;
  value?(row: DenseRow): number;
};

type GridSection = {
  key: string;
  title: string;
  inventoryDirection?: "in" | "out";
  columns: Column[];
  quantity(row: DenseRow): number;
  bags?(row: DenseRow): number;
  pack?(row: DenseRow): number;
  rate?(row: DenseRow): number;
  hsn?(row: DenseRow): string;
  reference?(row: DenseRow): string;
};

type PageConfig = {
  documentType: string;
  numberLabel: string;
  headerFields: HeaderField[];
  sections: GridSection[];
  financial?: boolean;
  expenses?: boolean;
};

const decimal = (value: string | undefined) => {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
};

const qtlFromBags = (row: DenseRow) =>
  ((decimal(row.values.bags) * decimal(row.values.pack)) + decimal(row.values.extra)) / 100;

const grossFor = (quantity: number, rate: number) => quantity * rate;

const gateColumns: Column[] = [
  { key: "commodity", label: "Commodity", type: "commodity" },
  { key: "packaging", label: "Packaging Type", type: "select", options: ["Bardana", "Jute"] },
  { key: "bags", label: "Declared Bag Count", type: "number", integer: true },
  { key: "grossWeight", label: "Gross Weight", type: "number" },
  { key: "tareWeight", label: "Tare Weight", type: "number" },
  {
    key: "netWeight",
    label: "Net Weight",
    type: "output",
    value: (row) => Math.max(0, decimal(row.values.grossWeight) - decimal(row.values.tareWeight)),
  },
  { key: "moistureCode", label: "Moisture Code" },
];

const configs: Record<string, PageConfig> = {
  Inward: {
    documentType: "inward",
    numberLabel: "Gate Pass No",
    headerFields: [
      { key: "entryType", label: "Entry Type", type: "select", options: ["Inward", "Outward"] },
      { key: "time", label: "Time", type: "time" },
      { key: "vehicleNumber", label: "Vehicle No" },
      { key: "driverName", label: "Driver Name" },
      { key: "driverMobile", label: "Driver Mobile" },
      { key: "sourceLocation", label: "Source Location" },
      { key: "destinationHub", label: "Destination Hub" },
      { key: "weighbridgeSlip", label: "Weighbridge Slip No" },
    ],
    sections: [{
      key: "gate",
      title: "Gate Pass Commodity Details",
      inventoryDirection: "in",
      columns: gateColumns,
      quantity: (row) => Math.max(0, decimal(row.values.grossWeight) - decimal(row.values.tareWeight)),
      bags: (row) => decimal(row.values.bags),
    }],
  },
  Outward: {
    documentType: "outward",
    numberLabel: "Gate Pass No",
    headerFields: [
      { key: "entryType", label: "Entry Type", type: "select", options: ["Outward", "Inward"] },
      { key: "time", label: "Time", type: "time" },
      { key: "vehicleNumber", label: "Vehicle No" },
      { key: "driverName", label: "Driver Name" },
      { key: "driverMobile", label: "Driver Mobile" },
      { key: "sourceLocation", label: "Source Location" },
      { key: "destinationHub", label: "Destination Hub" },
      { key: "weighbridgeSlip", label: "Weighbridge Slip No" },
    ],
    sections: [{
      key: "gate",
      title: "Gate Pass Commodity Details",
      inventoryDirection: "out",
      columns: gateColumns,
      quantity: (row) => Math.max(0, decimal(row.values.grossWeight) - decimal(row.values.tareWeight)),
      bags: (row) => decimal(row.values.bags),
    }],
  },
  "Milling Inward": {
    documentType: "milling_inward",
    numberLabel: "Milling Job Slip No",
    headerFields: [
      { key: "processingUnit", label: "Processing Unit / Sheller ID" },
      { key: "batchReference", label: "Batch Reference" },
      { key: "supervisor", label: "Supervisor" },
    ],
    sections: [
      {
        key: "inbound",
        title: "Inbound Processing — Sourced Stock",
        inventoryDirection: "out",
        columns: [
          { key: "commodity", label: "Raw Grain Item", type: "commodity" },
          { key: "lotNumber", label: "From Lot Number" },
          { key: "bags", label: "Bags Released", type: "number", integer: true },
          { key: "weight", label: "Weight Quintals", type: "number" },
        ],
        quantity: (row) => decimal(row.values.weight),
        bags: (row) => decimal(row.values.bags),
        reference: (row) => row.values.lotNumber,
      },
      {
        key: "outbound",
        title: "Outbound Yield — Milled Outputs",
        inventoryDirection: "in",
        columns: [
          { key: "commodity", label: "Finished Item Produced", type: "commodity" },
          { key: "bags", label: "Bags Filled", type: "number", integer: true },
          { key: "pack", label: "Pack Scale", type: "number", defaultValue: "50" },
          { key: "netYield", label: "Net Yield Quantity", type: "number" },
          { key: "byproductCode", label: "Byproduct Code" },
        ],
        quantity: (row) => decimal(row.values.netYield),
        bags: (row) => decimal(row.values.bags),
        pack: (row) => decimal(row.values.pack),
      },
    ],
  },
  "Milling Outward": {
    documentType: "milling_outward",
    numberLabel: "Milling Job Slip No",
    headerFields: [
      { key: "processingUnit", label: "Processing Unit / Sheller ID" },
      { key: "batchReference", label: "Batch Reference" },
      { key: "supervisor", label: "Supervisor" },
    ],
    sections: [],
  },
  "Consignment (Dr.)": {
    documentType: "consignment_debit",
    numberLabel: "Consignment Dr No",
    financial: true,
    expenses: true,
    headerFields: [
      { key: "farmer", label: "Farmer Name", type: "party", primaryParty: true },
      { key: "village", label: "Village / Group Name" },
      { key: "broker", label: "Broker Name", type: "party" },
      { key: "arhatiaLicense", label: "Arhatia License ID" },
      { key: "marketEntryRef", label: "Market Entry Ref" },
    ],
    sections: [{
      key: "lots",
      title: "Debit Patti / Inbound Lots",
      inventoryDirection: "in",
      columns: [
        { key: "commodity", label: "Commodity / Variety", type: "commodity" },
        { key: "lotNumber", label: "Lot / Dheri No" },
        { key: "bags", label: "Bags", type: "number", integer: true },
        { key: "pack", label: "Pack Weight", type: "number", defaultValue: "50" },
        { key: "extra", label: "Extra (kg)", type: "number" },
        { key: "totalWeight", label: "Total Weight (Qtl)", type: "output", value: qtlFromBags },
        { key: "rate", label: "Auction Bid Rate", type: "number" },
        { key: "gross", label: "Gross Amount", type: "output", value: (row) => grossFor(qtlFromBags(row), decimal(row.values.rate)) },
      ],
      quantity: qtlFromBags,
      bags: (row) => decimal(row.values.bags),
      pack: (row) => decimal(row.values.pack),
      rate: (row) => decimal(row.values.rate),
      reference: (row) => row.values.lotNumber,
    }],
  },
  "Consignment (Cr.)": {
    documentType: "consignment_credit",
    numberLabel: "Consignment Cr No",
    financial: true,
    expenses: true,
    headerFields: [
      { key: "buyer", label: "Buyer / Mill Name", type: "party", primaryParty: true },
      { key: "gstin", label: "GSTIN", type: "readonly", derivedFrom: "buyer", derivedProperty: "gstin" },
      { key: "paymentTerms", label: "Payment Terms (Days)" },
      { key: "formJReference", label: "Form-J Cross Reference" },
    ],
    sections: [{
      key: "allocation",
      title: "Buyer Settlement Assignment",
      inventoryDirection: "out",
      columns: [
        { key: "lotNumber", label: "Lot / Dheri Reference" },
        { key: "commodity", label: "Allocated Commodity", type: "commodity" },
        { key: "bags", label: "Total Dispatched Bags", type: "number", integer: true },
        { key: "netWeight", label: "Net Weight (Qtl)", type: "number" },
        { key: "rate", label: "Final Sale Rate", type: "number" },
        { key: "gross", label: "Extended Amount", type: "output", value: (row) => grossFor(decimal(row.values.netWeight), decimal(row.values.rate)) },
      ],
      quantity: (row) => decimal(row.values.netWeight),
      bags: (row) => decimal(row.values.bags),
      rate: (row) => decimal(row.values.rate),
      reference: (row) => row.values.lotNumber,
    }],
  },
  "Delivery Challan": {
    documentType: "delivery_challan",
    numberLabel: "Challan No",
    headerFields: [
      { key: "consignor", label: "Consignor Name (Seller)", type: "party", primaryParty: true },
      { key: "consignorGstin", label: "Consignor GSTIN", type: "readonly", derivedFrom: "consignor", derivedProperty: "gstin" },
      { key: "consignee", label: "Consignee Name (Buyer)", type: "party" },
      { key: "consigneeGstin", label: "Consignee GSTIN", type: "readonly", derivedFrom: "consignee", derivedProperty: "gstin" },
      { key: "placeOfSupply", label: "Place of Supply" },
      { key: "ewayBill", label: "E-Way Bill Number" },
    ],
    sections: [{
      key: "goods",
      title: "Delivery Commodity Details",
      inventoryDirection: "out",
      columns: [
        { key: "commodity", label: "Commodity Name", type: "commodity" },
        { key: "hsn", label: "HSN Code" },
        { key: "bags", label: "Bags Count", type: "number", integer: true },
        { key: "pack", label: "Pack Base", type: "number", defaultValue: "50" },
        { key: "quantity", label: "Net Quantity", type: "number" },
        { key: "taxable", label: "Taxable Value (Reference Only)", type: "number" },
      ],
      quantity: (row) => decimal(row.values.quantity),
      bags: (row) => decimal(row.values.bags),
      pack: (row) => decimal(row.values.pack),
      rate: (row) => {
        const quantity = decimal(row.values.quantity);
        return quantity ? decimal(row.values.taxable) / quantity : 0;
      },
      hsn: (row) => row.values.hsn,
    }],
  },
  "Purchase Memo": {
    documentType: "purchase_memo",
    numberLabel: "Memo No",
    financial: true,
    headerFields: [
      { key: "party", label: "Party Name", type: "party", primaryParty: true },
      { key: "broker", label: "Broker / Dalal Name", type: "party" },
      { key: "bargainNumber", label: "Bargain Sauda No" },
      { key: "mandiYard", label: "Mandi Yard Location" },
    ],
    sections: [],
  },
  "Sale Memo": {
    documentType: "sale_memo",
    numberLabel: "Memo No",
    financial: true,
    headerFields: [
      { key: "party", label: "Party Name", type: "party", primaryParty: true },
      { key: "broker", label: "Broker / Dalal Name", type: "party" },
      { key: "bargainNumber", label: "Bargain Sauda No" },
      { key: "mandiYard", label: "Mandi Yard Location" },
    ],
    sections: [],
  },
  "Purchase Invoice": {
    documentType: "purchase_invoice",
    numberLabel: "Purchase Bill No",
    financial: true,
    expenses: true,
    headerFields: [
      { key: "supplier", label: "Supplier / Broker Name", type: "party", primaryParty: true },
      { key: "gstin", label: "GSTIN", type: "readonly", derivedFrom: "supplier", derivedProperty: "gstin" },
      { key: "stateCode", label: "State Code" },
      { key: "reverseCharge", label: "Reverse Charge Flag", type: "select", options: ["N", "Y"] },
    ],
    sections: [{
      key: "purchase",
      title: "Purchase Bill Commodity Details",
      columns: [
        { key: "commodity", label: "Commodity Profile", type: "commodity" },
        { key: "hsn", label: "HSN" },
        { key: "bags", label: "Total Bags", type: "number", integer: true },
        { key: "quantity", label: "Net Quantity (Qtl)", type: "number" },
        { key: "rate", label: "Purchase Price", type: "number" },
        { key: "taxable", label: "Taxable Value", type: "output", value: (row) => grossFor(decimal(row.values.quantity), decimal(row.values.rate)) },
        { key: "cgst", label: "CGST %", type: "number" },
        { key: "sgst", label: "SGST %", type: "number" },
        { key: "igst", label: "IGST %", type: "number" },
        {
          key: "net",
          label: "Net Value",
          type: "output",
          value: (row) => {
            const taxable = grossFor(decimal(row.values.quantity), decimal(row.values.rate));
            return taxable * (1 + (decimal(row.values.cgst) + decimal(row.values.sgst) + decimal(row.values.igst)) / 100);
          },
        },
      ],
      quantity: (row) => decimal(row.values.quantity),
      bags: (row) => decimal(row.values.bags),
      rate: (row) => decimal(row.values.rate),
      hsn: (row) => row.values.hsn,
    }],
  },
  "Kachi Purchase": {
    documentType: "kachi_purchase",
    numberLabel: "Kachi Bill No",
    financial: true,
    expenses: true,
    headerFields: [
      { key: "farmer", label: "Farmer A/c", type: "party", primaryParty: true },
      { key: "buyer", label: "Buyer / Aarthia A/c", type: "party" },
      { key: "mandi", label: "Mandi" },
      { key: "damiPct", label: "Dami %" },
      { key: "marketFeePct", label: "Market Fee %" },
      { key: "finalFlag", label: "Final Status", type: "select", options: ["Open", "Final"] },
    ],
    sections: [{
      key: "crop",
      title: "Kachi Purchase Lines",
      inventoryDirection: "in",
      columns: [
        { key: "commodity", label: "Crop / Item", type: "commodity" },
        { key: "bags", label: "Bags", type: "number", integer: true },
        { key: "gross", label: "Gross Wt", type: "number" },
        { key: "tare", label: "Tare Wt", type: "number" },
        { key: "net", label: "Net Wt (Qtl)", type: "output", value: (row) => Math.max(0, decimal(row.values.gross) - decimal(row.values.tare)) },
        { key: "rate", label: "Rate", type: "number" },
        { key: "amount", label: "Amount", type: "output", value: (row) => grossFor(Math.max(0, decimal(row.values.gross) - decimal(row.values.tare)), decimal(row.values.rate)) },
      ],
      quantity: (row) => Math.max(0, decimal(row.values.gross) - decimal(row.values.tare)),
      bags: (row) => decimal(row.values.bags),
      rate: (row) => decimal(row.values.rate),
    }],
  },
  "Mandi Purchase Entry": {
    documentType: "mandi_purchase",
    numberLabel: "Mandi Bill No",
    financial: true,
    expenses: true,
    headerFields: [
      { key: "party", label: "Party A/c", type: "party", primaryParty: true },
      { key: "mandi", label: "Mandi (City)" },
      { key: "billNo", label: "Bill No." },
      { key: "billDate", label: "Bill Date" },
    ],
    sections: [{
      key: "purchase",
      title: "Mandi Purchase",
      inventoryDirection: "in",
      columns: [
        { key: "commodity", label: "Crop / Item", type: "commodity" },
        { key: "bags", label: "Bags", type: "number", integer: true },
        { key: "gross", label: "Gross Wt", type: "number" },
        { key: "tare", label: "Tare Wt", type: "number" },
        { key: "net", label: "Net Wt", type: "output", value: (row) => Math.max(0, decimal(row.values.gross) - decimal(row.values.tare)) },
        { key: "rate", label: "Rate", type: "number" },
        { key: "amount", label: "Amount", type: "output", value: (row) => grossFor(Math.max(0, decimal(row.values.gross) - decimal(row.values.tare)), decimal(row.values.rate)) },
      ],
      quantity: (row) => Math.max(0, decimal(row.values.gross) - decimal(row.values.tare)),
      bags: (row) => decimal(row.values.bags),
      rate: (row) => decimal(row.values.rate),
    }],
  },
  "GST Purchase Entry": {
    documentType: "gst_purchase",
    numberLabel: "GST Purchase No",
    financial: true,
    expenses: true,
    headerFields: [
      { key: "supplier", label: "Party A/c", type: "party", primaryParty: true },
      { key: "gstin", label: "GSTIN", type: "readonly", derivedFrom: "supplier", derivedProperty: "gstin" },
      { key: "billNo", label: "Bill No." },
      { key: "reverseCharge", label: "Rev. Charges", type: "select", options: ["N", "Y"] },
      { key: "inputClaim", label: "Input Claim", type: "select", options: ["Y", "N"] },
    ],
    sections: [{
      key: "lines",
      title: "GST Purchase Lines",
      inventoryDirection: "in",
      columns: [
        { key: "commodity", label: "Item Desc", type: "commodity" },
        { key: "hsn", label: "HSN" },
        { key: "bags", label: "Bags", type: "number", integer: true },
        { key: "quantity", label: "Net Qty", type: "number" },
        { key: "rate", label: "Rate", type: "number" },
        { key: "taxable", label: "Taxable", type: "output", value: (row) => grossFor(decimal(row.values.quantity), decimal(row.values.rate)) },
        { key: "cgst", label: "CGST %", type: "number" },
        { key: "sgst", label: "SGST %", type: "number" },
        { key: "igst", label: "IGST %", type: "number" },
      ],
      quantity: (row) => decimal(row.values.quantity),
      bags: (row) => decimal(row.values.bags),
      rate: (row) => decimal(row.values.rate),
      hsn: (row) => row.values.hsn,
    }],
  },
  "Lifting Entry": {
    documentType: "lifting_entry",
    numberLabel: "Lifting ID",
    headerFields: [
      { key: "dispatchFrom", label: "Dispatch From" },
      { key: "crop", label: "Item / Crop" },
      { key: "challanNo", label: "Challan No." },
      { key: "vehicleNo", label: "Vehicle No." },
      { key: "driver", label: "Driver Name" },
      { key: "transporter", label: "Transporter", type: "party" },
    ],
    sections: [{
      key: "lift",
      title: "Lifting Lines",
      inventoryDirection: "out",
      columns: [
        { key: "commodity", label: "Item", type: "commodity" },
        { key: "date", label: "Date" },
        { key: "challan", label: "Challan No." },
        { key: "vehicle", label: "Vehicle No." },
        { key: "bags", label: "Bags", type: "number", integer: true },
        { key: "weight", label: "Weight", type: "number" },
        { key: "rate", label: "Rate", type: "number" },
        { key: "amount", label: "Amount", type: "output", value: (row) => grossFor(decimal(row.values.weight), decimal(row.values.rate)) },
      ],
      quantity: (row) => decimal(row.values.weight),
      bags: (row) => decimal(row.values.bags),
      rate: (row) => decimal(row.values.rate),
    }],
  },
  "Transfer Challan": {
    documentType: "transfer_challan",
    numberLabel: "Transfer No",
    headerFields: [
      { key: "fromGodown", label: "From Godown / Source Stock" },
      { key: "toGodown", label: "To Godown / Destination Stock" },
      { key: "transporter", label: "Transporter Name", type: "party" },
      { key: "vehicleNumber", label: "Vehicle Registration No" },
    ],
    sections: [{
      key: "transfer",
      title: "Stock Transfer Details",
      inventoryDirection: "out",
      columns: [
        { key: "commodity", label: "Commodity Item", type: "commodity" },
        { key: "bags", label: "Bags Transferred", type: "number", integer: true },
        { key: "pack", label: "Pack Weight Scale", type: "number", defaultValue: "50" },
        { key: "quantity", label: "Total Transferred Weight (Qtl)", type: "output", value: (row) => decimal(row.values.bags) * decimal(row.values.pack) / 100 },
      ],
      quantity: (row) => decimal(row.values.bags) * decimal(row.values.pack) / 100,
      bags: (row) => decimal(row.values.bags),
      pack: (row) => decimal(row.values.pack),
    }],
  },
};

const memoColumns: Column[] = [
  { key: "commodity", label: "Commodity Classification", type: "commodity" },
  { key: "lotNumber", label: "Dheri Batch" },
  { key: "bags", label: "Bags Quantity", type: "number", integer: true },
  { key: "weight", label: "Weight Base", type: "number" },
  { key: "rate", label: "Agreed Rate", type: "number" },
  { key: "gross", label: "Gross Memo Total", type: "output", value: (row) => grossFor(decimal(row.values.weight), decimal(row.values.rate)) },
];

const memoSection: GridSection = {
  key: "memo",
  title: "Memo Commodity Details",
  columns: memoColumns,
  quantity: (row) => decimal(row.values.weight),
  bags: (row) => decimal(row.values.bags),
  rate: (row) => decimal(row.values.rate),
  reference: (row) => row.values.lotNumber,
};

configs["Purchase Memo"].sections = [memoSection];
configs["Sale Memo"].sections = [memoSection];
configs["Milling Outward"].sections = configs["Milling Inward"].sections;
configs["Gate Pass"] = { ...configs.Inward, documentType: "gate_pass" };

function api(): WorkflowApi | undefined {
  return window.pywebview?.api as unknown as WorkflowApi | undefined;
}

function blankRow(rowId: number, section: GridSection): DenseRow {
  return {
    rowId,
    commodity: null,
    values: Object.fromEntries(
      section.columns
        .filter((column) => column.key !== "commodity")
        .map((column) => [column.key, column.defaultValue ?? ""]),
    ),
  };
}

function DenseDocumentForm({
  title,
  onExit,
  fastEntry = false,
  entryMode,
}: {
  title: string;
  onExit(): void;
  fastEntry?: boolean;
  entryMode?: "add" | "modify";
}) {
  const mode = entryMode ?? "add";
  const config = configs[title];
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [header, setHeader] = useState<Record<string, string>>({});
  const [lookups, setLookups] = useState<Record<string, LookupItem | null>>({});
  const [mainAccount, setMainAccount] = useState<LookupItem | null>(null);
  const [partyAccount, setPartyAccount] = useState<LookupItem | null>(null);
  const [rows, setRows] = useState<Record<string, DenseRow[]>>(() =>
    Object.fromEntries(config.sections.map((section) => [section.key, [blankRow(1, section)]])),
  );
  const [calculation, setCalculation] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [postedId, setPostedId] = useState("");
  const [showSaved, setShowSaved] = useState(false);
  const [attachPath, setAttachPath] = useState("");
  const [attachments, setAttachments] = useState<{ attachment_id: string; file_name: string }[]>([]);
  const [printBlockedOpen, setPrintBlockedOpen] = useState(false);
  const [rateOverrides, setRateOverrides] = useState<Record<string, string>>({});
  const [creditWarning, setCreditWarning] = useState<CreditEvaluation | null>(null);
  const [creditOverride, setCreditOverride] = useState(false);
  const [managerOverridePin, setManagerOverridePin] = useState("");
  const [searchRows, setSearchRows] = useState<ModifySearchRow[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [auditTrail, setAuditTrail] = useState<{ action: string; occurred_at: string; reason?: string }[]>([]);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [toast, setToast] = useState("");
  const [printOptions, setPrintOptions] = useState<PrintOptions>(defaultPrintOptions);
  const handleEnter = useGridEnterNavigation(() => {
    const active = document.activeElement?.closest<HTMLElement>("[data-grid-row]");
    if (active?.dataset.section) appendRow(active.dataset.section);
  });

  useEffect(() => {
    if (mode !== "add") return;
    void api()?.next_document_number(config.documentType).then((response) => {
      if (response.document_number) setNumber(response.document_number);
    });
    setDate(new Date().toISOString().slice(0, 10));
    setHeader({});
    setLookups({});
    setPostedId("");
    setAuditTrail([]);
    setRows(Object.fromEntries(config.sections.map((section) => [section.key, [blankRow(1, section)]])));
  }, [config.documentType, config.sections, mode]);

  const runSearch = useCallback((query: string) => {
    if (mode !== "modify") return;
    setSearchLoading(true);
    void api()
      ?.search_documents?.(config.documentType, query, 40)
      .then((response) => {
        if (response?.ok && response.rows) setSearchRows(response.rows);
      })
      .finally(() => setSearchLoading(false));
  }, [config.documentType, mode]);

  useEffect(() => {
    if (mode === "modify") runSearch("");
  }, [mode, runSearch]);

  async function loadDocument(row: ModifySearchRow) {
    const response = await api()?.get_document?.(row.document_id);
    if (!response?.ok || !response.document) {
      setToast(response?.error ?? "Could not load record.");
      return;
    }
    const headerPayload = response.document.header as Record<string, unknown>;
    setNumber(String(headerPayload.document_number ?? row.document_number));
    setDate(String(headerPayload.document_date ?? row.document_date));
    setPostedId(String(headerPayload.document_id ?? row.document_id));
    setAuditTrail(response.audit_trail ?? []);
    const metadata = headerPayload.metadata as {
      fields?: Record<string, string>;
      lookups?: Record<string, { id: string; label: string } | null>;
    } | undefined;
    if (metadata?.fields) setHeader(metadata.fields);
    if (metadata?.lookups) {
      setLookups(
        Object.fromEntries(
          Object.entries(metadata.lookups).map(([key, value]) => [key, value ?? null]),
        ),
      );
    }
    setToast(`Loaded ${row.document_number} — adjust and save as a new posting or use reversal workflow.`);
  }

  useEffect(() => {
    if (!postedId) {
      setAttachments([]);
      return;
    }
    void api()?.list_document_attachments?.(postedId).then((response) => {
      if (response?.ok && response.attachments) setAttachments(response.attachments);
    });
  }, [postedId]);

  const documentLines = useMemo(() => config.sections.flatMap((section) =>
    (rows[section.key] ?? [])
      .filter((row) => row.commodity && section.quantity(row) > 0)
      .map((row) => ({
        commodity_id: row.commodity?.id,
        description: row.commodity?.label ?? "Commodity",
        source_reference_number: section.reference?.(row) ?? null,
        hsn_code: section.hsn?.(row) ?? "",
        bags_scaled: Math.round(section.bags?.(row) ?? 0),
        bag_scale: 0,
        packing_weight_scaled: Math.round((section.pack?.(row) ?? 0) * 1000),
        loose_quantity_scaled: Math.round(decimal(row.values.extra) * 1000),
        quantity_scaled: Math.round(section.quantity(row) * 1000),
        quantity_scale: 3,
        rate_paise: Math.round((section.rate?.(row) ?? 0) * 100),
        rate_unit: "quintal",
        metadata: {
          section: section.key,
          inventory_direction: header.entryType
            ? header.entryType.toLocaleLowerCase().startsWith("in") ? "in" : "out"
            : section.inventoryDirection,
          values: row.values,
        },
      }))),
  [config.sections, header.entryType, rows]);

  const primaryField = config.headerFields.find((field) => field.primaryParty);
  const primaryParty = primaryField ? lookups[primaryField.key] : null;
  const charges = (calculation?.charges ?? []) as Record<string, unknown>[];
  const overrides = Object.fromEntries(charges.flatMap((charge) => {
    const code = String(charge.code);
    const entered = rateOverrides[code];
    const original = Number(charge.rate_decimal);
    if (entered === undefined || Number(entered) === original || original === 0) return [];
    const automatic = Math.abs(Number(charge.automatic_amount_paise));
    return [[code, {
      amount_paise: Math.round(automatic * Number(entered || 0) / original),
      reason: "Operator adjusted rate before posting",
    }]];
  }));

  const payload = useMemo(() => ({
    document_type: config.documentType,
    document_number: number,
    document_date: date,
    party_id: primaryParty?.id ?? null,
    main_account_id: mainAccount?.id ?? null,
    party_account_id: partyAccount?.id ?? null,
    lines: documentLines,
    overrides,
    header: {
      vehicle_number: header.vehicleNumber ?? "",
      driver_name: header.driverName ?? "",
      eway_bill_number: header.ewayBill ?? "",
      from_place: header.sourceLocation ?? header.fromGodown ?? "",
      to_place: header.destinationHub ?? header.toGodown ?? header.placeOfSupply ?? "",
      dispatch_time: header.time ?? "",
      reference_number: header.marketEntryRef ?? header.formJReference ?? header.bargainNumber ?? "",
      metadata: {
        fields: header,
        lookups: Object.fromEntries(
          Object.entries(lookups).map(([key, value]) => [key, value ? { id: value.id, label: value.label } : null]),
        ),
      },
    },
  }), [config.documentType, date, documentLines, header, lookups, mainAccount, number, overrides, partyAccount, primaryParty?.id]);

  useEffect(() => {
    if (!documentLines.length) {
      setCalculation(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void api()?.calculate_document(payload).then((response) => {
        if (response.ok) setCalculation(response.calculation ?? null);
      });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [JSON.stringify(payload), documentLines.length]);

  function updateRow(sectionKey: string, rowId: number, values: Partial<DenseRow>) {
    setRows((current) => ({
      ...current,
      [sectionKey]: current[sectionKey].map((row) =>
        row.rowId === rowId ? { ...row, ...values } : row
      ),
    }));
  }

  function updateValue(sectionKey: string, row: DenseRow, key: string, value: string) {
    updateRow(sectionKey, row.rowId, { values: { ...row.values, [key]: value } });
  }

  function appendRow(sectionKey: string) {
    const section = config.sections.find((candidate) => candidate.key === sectionKey);
    if (!section) return;
    setRows((current) => {
      const sectionRows = current[sectionKey];
      return {
        ...current,
        [sectionKey]: [
          ...sectionRows,
          blankRow(Math.max(...sectionRows.map((row) => row.rowId)) + 1, section),
        ],
      };
    });
    window.setTimeout(() => {
      document.querySelector<HTMLElement>(
        `.dense-section[data-section="${sectionKey}"] [data-grid-row]:last-of-type input`,
      )?.focus();
    }, 0);
  }

  async function save(event: FormEvent, forceOverride = false) {
    event.preventDefault();
    const issues = validateDenseDocument({
      documentNumber: number,
      partyLabel: primaryField?.label,
      hasParty: Boolean(primaryParty?.id),
      lineCount: documentLines.length,
      hasCommodityLine: documentLines.length > 0,
    });
    if (config.financial && (!mainAccount || !partyAccount)) {
      issues.push({ field: "accounts", message: "Main and party accounts are required." });
    }
    if (issues.length) {
      const mapped = Object.fromEntries(issues.map((issue) => [issue.field, issue.message]));
      setFieldErrors(mapped);
      setToast(issues[0].message);
      return;
    }
    setFieldErrors({});
    if (primaryParty?.id && !forceOverride && !creditOverride) {
      const preview = await api()?.check_credit_limit({
        party_id: primaryParty.id,
        additional_debit_paise: Number(calculation?.grand_total_paise ?? 0),
      });
      if (preview?.evaluation?.breached) {
        setCreditWarning(preview.evaluation);
        return;
      }
    }
    const response = await api()?.post_document({
      ...payload,
      credit_override_confirmed: forceOverride || creditOverride,
      manager_override_pin: managerOverridePin,
    });
    if (!response) return;
    setResult(response);
    if (response.ok) {
      const posted = response.document as { document_id?: string } | undefined;
      const newId = posted?.document_id ?? "";
      setPostedId(newId);
      setShowSaved(true);
      if (printOptions.auto_print_on_save && newId) {
        await printDocument(newId);
      }
    }
  }

  async function printDocument(documentId: string) {
    const payload = {
      document_id: documentId,
      copies: printOptions.copies,
      use_escpos: printOptions.use_escpos,
      escpos_columns: printOptions.escpos_columns,
      visible_columns: printOptions.visible_columns,
      format: printOptions.use_escpos ? "auto" : "html",
      silent: printOptions.use_escpos,
      html_columns: printOptions.escpos_columns,
    };
    const response = await (api()?.print_mandi_bill?.(payload) ?? api()?.print_document(documentId));
    if (response) setResult(response);
  }

  async function print() {
    if (!postedId) {
      setPrintBlockedOpen(true);
      return;
    }
    await printDocument(postedId);
  }

  async function shareWhatsApp() {
    if (!postedId) {
      setPrintBlockedOpen(true);
      return;
    }
    const response = await api()?.whatsapp_for_document?.(postedId);
    if (response?.ok && response.url) {
      await api()?.open_whatsapp_url?.(response.url);
    } else if (response) {
      setResult(response);
    }
  }

  async function attachScan() {
    if (!postedId || !attachPath.trim()) return;
    const response = await api()?.attach_document_file?.(postedId, attachPath.trim());
    if (response) setResult(response);
    if (response?.ok) {
      setAttachPath("");
      const listed = await api()?.list_document_attachments?.(postedId);
      if (listed?.ok && listed.attachments) setAttachments(listed.attachments);
    }
  }

  function renderHeaderField(field: HeaderField) {
    if (field.type === "party") {
      return (
        <Autocomplete
          entityType="party"
          label={field.primaryParty ? `${field.label} *` : field.label}
          value={lookups[field.key] ?? null}
          onSelect={(value) => {
            setLookups((current) => ({ ...current, [field.key]: value }));
            if (field.primaryParty && value?.account_id && value.account_name) {
              setPartyAccount({ id: value.account_id, label: value.account_name });
            }
          }}
        />
      );
    }
    if (field.type === "readonly") {
      const source = lookups[field.derivedFrom ?? ""];
      return (
        <label><span>{field.label}</span><input readOnly value={String(source?.[field.derivedProperty ?? "gstin"] ?? "")} /></label>
      );
    }
    if (field.type === "select") {
      return (
        <label><span>{field.label}</span><select value={header[field.key] ?? field.options?.[0] ?? ""} onChange={(event) => setHeader((current) => ({ ...current, [field.key]: event.target.value }))}>
          {field.options?.map((option) => <option key={option}>{option}</option>)}
        </select></label>
      );
    }
    return (
      <label><span>{field.label}</span><input type={field.type === "time" ? "time" : "text"} value={header[field.key] ?? ""} onChange={(event) => setHeader((current) => ({ ...current, [field.key]: event.target.value }))} /></label>
    );
  }

  return (
    <>
      <div onKeyDown={handleEnter}>
        <TransactionScreen
          entryMode={mode}
          title={`${title} (${mode === "add" ? "Add" : "Modify"})`}
          auditTrail={
            auditTrail.length ? (
              <ul className="audit-trail-list">
                {auditTrail.map((event) => (
                  <li key={`${event.occurred_at}-${event.action}`}>
                    <strong>{event.action}</strong> · {event.occurred_at}
                    {event.reason ? ` — ${event.reason}` : ""}
                  </li>
                ))}
              </ul>
            ) : undefined
          }
          modifySearch={
            mode === "modify" ? (
              <ModifyRecordSearchBar
                loading={searchLoading}
                rows={searchRows}
                onQueryChange={runSearch}
                onSelect={(row) => void loadDocument(row)}
              />
            ) : undefined
          }
          onDelete={
            mode === "modify"
              ? () => setToast("Posted mandi records must be reversed via voucher — delete is audit-only here.")
              : undefined
          }
          header={(
            <>
              <InlineField label={config.numberLabel} required>
                <input
                  required
                  className={`w-full rounded border px-1 py-0.5 mandi-numeric ${fieldErrors.document_number ? "field-invalid" : ""}`}
                  data-enter-order={1}
                  value={number}
                  onChange={(event) => setNumber(event.target.value)}
                />
              </InlineField>
              <InlineField label="Date" required>
                <input
                  required
                  type="date"
                  className="w-full rounded border px-1 py-0.5"
                  data-enter-order={2}
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                />
              </InlineField>
              {config.headerFields.map((field) => (
                <div className="dense-field min-w-[180px]" key={field.key}>{renderHeaderField(field)}</div>
              ))}
            </>
          )}
          grid={(
            <div className="space-y-3">
              {config.sections.map((section) => (
                <section className="dense-section" data-section={section.key} key={section.key}>
                  <h3 className="mb-1 font-semibold">{section.title}</h3>
                  <div
                    className="dense-grid-row dense-grid-heading"
                    style={{
                      gridTemplateColumns: `repeat(${section.columns.length}, minmax(0, 1fr)) 26px`,
                      minWidth: `${section.columns.length * 82 + 26}px`,
                    }}
                  >
                    {section.columns.map((column) => <span key={column.key}>{column.label}</span>)}<span />
                  </div>
                  {(rows[section.key] ?? []).map((row) => (
                    <div
                      className="dense-grid-row"
                      data-grid-row
                      data-section={section.key}
                      key={row.rowId}
                      style={{
                        gridTemplateColumns: `repeat(${section.columns.length}, minmax(0, 1fr)) 26px`,
                        minWidth: `${section.columns.length * 82 + 26}px`,
                      }}
                    >
                      {section.columns.map((column) => {
                        if (column.type === "commodity") {
                          return <Autocomplete key={column.key} entityType="commodity" label="" value={row.commodity} onSelect={(value) => updateRow(section.key, row.rowId, { commodity: value })} />;
                        }
                        if (column.type === "output") {
                          return <output key={column.key}>{(column.value?.(row) ?? 0).toFixed(3)}</output>;
                        }
                        if (column.type === "select") {
                          return <select key={column.key} value={row.values[column.key] ?? column.options?.[0] ?? ""} onChange={(event) => updateValue(section.key, row, column.key, event.target.value)}>{column.options?.map((option) => <option key={option}>{option}</option>)}</select>;
                        }
                        return <input key={column.key} inputMode={column.type === "number" ? "decimal" : undefined} step={column.integer ? "1" : undefined} type={column.integer ? "number" : "text"} value={row.values[column.key] ?? ""} onChange={(event) => updateValue(section.key, row, column.key, event.target.value)} />;
                      })}
                      {mode === "modify" && (
                        <button aria-label="Remove row" disabled={(rows[section.key] ?? []).length === 1} type="button" onClick={() => setRows((current) => ({ ...current, [section.key]: current[section.key].filter((item) => item.rowId !== row.rowId) }))}>×</button>
                      )}
                      {mode === "add" && <span />}
                    </div>
                  ))}
                  <button className="dense-add-row mt-1" type="button" onClick={() => appendRow(section.key)}>Add Row</button>
                </section>
              ))}
            </div>
          )}
          sidebar={!fastEntry && config.expenses ? (
            <div className="dense-expenses">
              <PrintOptionsPanel value={printOptions} onChange={setPrintOptions} />
              <h3 className="mb-1 font-semibold">Expense Details</h3>
              <div className="dense-expense-heading"><span>Expense Head</span><span>% / Unit</span><span>Amount</span></div>
              {charges.filter((charge) => charge.code !== "BONUS").map((charge) => (
                <div className="dense-expense-row" key={String(charge.code)}>
                  <span>{String(charge.label)}</span>
                  <input value={rateOverrides[String(charge.code)] ?? String(charge.rate_decimal)} onChange={(event) => setRateOverrides((current) => ({ ...current, [String(charge.code)]: event.target.value }))} />
                  <output>₹{(Number(charge.final_amount_paise) / 100).toFixed(2)}</output>
                </div>
              ))}
              {!charges.length && <small>Add a complete row to calculate configured expenses.</small>}
              <div className="dense-net-block">
                <span>Gross Amount</span><AnimatedAmount valuePaise={Number(calculation?.subtotal_paise ?? 0)} />
                <span>Total Expenses</span><AnimatedAmount valuePaise={Number(calculation?.total_charges_paise ?? 0)} />
                <strong>NET AMOUNT</strong><AnimatedAmount valuePaise={Number(calculation?.grand_total_paise ?? 0)} />
              </div>
              {config.financial && (
                <div className="mt-3 space-y-2">
                  <Autocomplete entityType="account" label="Main Account" required value={mainAccount} onSelect={setMainAccount} />
                  <Autocomplete entityType="account" label="Party Account" required value={partyAccount} onSelect={setPartyAccount} />
                </div>
              )}
            </div>
          ) : undefined}
          footerMessage={(
            <>
              {result && !result.ok ? <p className="error-message">{result.error}</p> : null}
              {postedId && (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <button type="button" onClick={() => void shareWhatsApp()}>WhatsApp</button>
                  </div>
                  <div className="flex flex-wrap items-end gap-2">
                    <label className="flex-1 min-w-[12rem]">
                      <span>Attach scan (full path)</span>
                      <input
                        value={attachPath}
                        onChange={(event) => setAttachPath(event.target.value)}
                        placeholder="C:\Scans\kanda-parchi.jpg"
                      />
                    </label>
                    <button type="button" onClick={() => void attachScan()}>Attach</button>
                  </div>
                  {attachments.length > 0 && (
                    <ul className="text-[11px] opacity-80">
                      {attachments.map((item) => (
                        <li key={item.attachment_id}>{item.file_name}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </>
          )}
          onSave={(event) => void save(event)}
          onPrint={() => void print()}
          onExit={onExit}
        />
      </div>
      {toast && <FormToast message={toast} onDismiss={() => setToast("")} />}
      {Object.keys(fieldErrors).length > 0 && (
        <div className="field-error-badges" aria-live="polite">
          {Object.entries(fieldErrors).map(([key, message]) => (
            <span className="field-error-badge" key={key}>{message}</span>
          ))}
        </div>
      )}
      {printBlockedOpen && (
        <MessageDialog
          message="Save the document before printing."
          onConfirm={() => setPrintBlockedOpen(false)}
        />
      )}
      {creditWarning && (
        <CreditLimitWarningModal
          evaluation={creditWarning}
          onCancel={() => setCreditWarning(null)}
          onProceed={(pin) => {
            setCreditOverride(true);
            setManagerOverridePin(pin);
            setCreditWarning(null);
            void save({ preventDefault() {} } as FormEvent, true);
          }}
        />
      )}
      {showSaved && (
        <div className="blocking-modal" role="dialog" aria-modal="true">
          <div className="saved-dialog"><header><span>Anaj Accounting ERP</span></header><p>Data has been Successfully Saved</p><button autoFocus type="button" onClick={() => setShowSaved(false)}>Close</button></div>
        </div>
      )}
    </>
  );
}

function supportsDenseDocument(title: string): boolean {
  return title in configs;
}

export { supportsDenseDocument };
export default DenseDocumentForm;
