#!/usr/bin/env python3
"""Split frontend/src/EntryWindow.tsx into feature modules (one-time maintainer tool)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src" / "EntryWindow.tsx"
OUT_ACCOUNTING = ROOT / "frontend" / "src" / "features" / "accounting" / "forms"
OUT_MANDI = ROOT / "frontend" / "src" / "features" / "mandi-vouchers" / "forms"
OUT_ADMIN = ROOT / "frontend" / "src" / "features" / "admin" / "forms"

ACCOUNTING = {
    "LedgerForm",
    "CommodityForm",
    "PartyForm",
    "JournalForm",
    "CashBookForm",
    "ReportView",
    "TaxRegister",
    "ChargeRuleForm",
    "InterestForm",
    "Configuration",
}
MANDI = {"FormJ", "SaleBill", "FormICredit", "DocumentForm", "MandiVoucherActions"}
SHARED_HELPERS = {"Message", "SavedModal"}

IMPORT_HEADER = '''import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import Autocomplete, { LookupItem } from "../../../shared/ui/Autocomplete";
import Button from "../../../shared/ui/components/Button";
import CreditLimitWarningModal from "../../../shared/ui/components/CreditLimitWarningModal";
import DataGrid from "../../../shared/ui/components/DataGrid";
import TransactionScreen, { InlineField } from "../../../shared/ui/components/TransactionScreen";
import useFieldFocusHandlers from "../../../shared/hooks/useFieldFocusHandlers";
import { useFormEnterFlow } from "../../../shared/hooks/useFormEnterFlow";
import { useGridEnterNavigation } from "../../../shared/hooks/useGridEnterNavigation";
import type { CreditEvaluation } from "../../../shared/api/types";
import {
  buildChargeOverrides,
  moveToNextField,
  rupeesToPaise,
  today,
  workflowApi,
} from "../../../shared/entry/workflow";
import type { Result } from "../../../shared/entry/types";
import { EntryMessage as Message, SavedModal } from "../../../shared/entry/EntryMessages";

'''


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    router_idx = next(i for i, line in enumerate(lines) if line.startswith("function EntryWindow"))
    body = lines[32:router_idx]

    chunks: dict[str, list[str]] = {}
    types_buf: list[str] = []
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current
        if current:
            chunks[current] = types_buf + buf
            types_buf = []
            buf = []
            current = None

    for line in body:
        fn = re.match(r"^function (\w+)", line)
        typ = re.match(r"^type (\w+)", line)
        if fn:
            flush()
            current = fn.group(1)
            buf = [line]
        elif typ and current is None:
            types_buf.append(line)
        elif current:
            buf.append(line)
        elif typ:
            types_buf.append(line)
    flush()

    OUT_ACCOUNTING.mkdir(parents=True, exist_ok=True)
    OUT_MANDI.mkdir(parents=True, exist_ok=True)
    OUT_ADMIN.mkdir(parents=True, exist_ok=True)

    for name, chunk in chunks.items():
        if name in SHARED_HELPERS:
            continue
        if name in ACCOUNTING:
            out_dir = OUT_ACCOUNTING
        elif name in MANDI:
            out_dir = OUT_MANDI
        else:
            continue
        out_path = out_dir / f"{name}.tsx"
        exports = f"\nexport {{ {name} }};\n"
        out_path.write_text(IMPORT_HEADER + "\n".join(chunk) + exports, encoding="utf-8")

    index_accounting = OUT_ACCOUNTING / "index.ts"
    index_accounting.write_text(
        "\n".join(f'export {{ {n} }} from "./{n}";' for n in sorted(ACCOUNTING & chunks.keys()))
        + "\n",
        encoding="utf-8",
    )
    index_mandi = OUT_MANDI / "index.ts"
    index_mandi.write_text(
        "\n".join(f'export {{ {n} }} from "./{n}";' for n in sorted(MANDI & chunks.keys()))
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(chunks)} chunks under features/")


if __name__ == "__main__":
    main()
