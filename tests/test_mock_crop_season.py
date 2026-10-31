"""Mock crop-season volume generator."""

from __future__ import annotations

from pathlib import Path

from anaj_erp.database import DatabaseManager
from anaj_erp.mock_crop_season import generate_crop_season


def test_generate_crop_season_posts_documents(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "season")
    databases.initialize()
    company = databases.create_company("Season Co", 2026)
    company_id = str(company["company_id"])
    fy_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    stats = generate_crop_season(databases, company_id, fy_id, target_count=12)
    assert stats["posted"] == 12

    db_path = databases.company_path(company_id)
    with databases.connect(db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS c FROM document WHERE financial_year_id = ? AND status = 'posted'",
            (fy_id,),
        ).fetchone()
    assert int(row["c"]) >= 12
