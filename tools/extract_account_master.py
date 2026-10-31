from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
masters = (ROOT / "backend/anaj_erp/masters.py").read_text(encoding="utf-8")
start = masters.index("_ACCOUNT_METADATA_KEYS")
end = masters.index("    def save_opening_stock")
body = masters[start:end]
header = '''"""Account Master persistence and record shaping."""

from __future__ import annotations

import json
from typing import Any

from ...accounting import AccountingService
from ...database import DatabaseManager
from ...database import utc_now
from ...errors import ValidationError


'''
body = body.replace(
    "    def save_account_master",
    "    def save",
).replace(
    "    def delete_account_master",
    "    def delete",
).replace(
    "    def get_account_master",
    "    def get_by_account_id",
).replace(
    "    def get_party_master",
    "    def get_by_party_id",
)
klass = f"class AccountMasterOps:\n    \"\"\"Account / party master CRUD for one company database.\"\"\"\n\n    def __init__(self, databases: DatabaseManager, database_path: str, accounting: AccountingService) -> None:\n        self.databases = databases\n        self.database_path = database_path\n        self.accounting = accounting\n\n"
# drop nothing - body includes module-level helpers then methods at wrong indent
lines = body.splitlines()
methods_start = next(i for i, line in enumerate(lines) if line.strip().startswith("def save_account_master") or line.strip().startswith("def save("))
helpers = "\n".join(lines[:methods_start])
methods = "\n".join(lines[methods_start:])
out = header + helpers + "\n\n" + klass + methods
(ROOT / "backend/anaj_erp/domains/masters/account_master.py").write_text(out, encoding="utf-8")
print("OK", len(out))
