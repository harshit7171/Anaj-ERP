"""Typed structures for GSTR-1 JSON (GSTN upload shape)."""

from __future__ import annotations

from typing import Any
from typing import NotRequired
from typing import TypedDict


class Gstr1ItemDetail(TypedDict):
    txval: float
    rt: float
    iamt: float
    camt: float
    samt: float
    csamt: float


class Gstr1InvoiceItem(TypedDict):
    num: int
    itm_det: Gstr1ItemDetail


class Gstr1B2BInvoice(TypedDict):
    inum: str
    idt: str
    val: float
    pos: str
    rchrg: str
    inv_typ: str
    itms: list[Gstr1InvoiceItem]


class Gstr1B2BParty(TypedDict):
    ctin: str
    inv: list[Gstr1B2BInvoice]


class Gstr1B2CLInvoice(TypedDict):
    inum: str
    idt: str
    val: float
    itms: list[Gstr1InvoiceItem]


class Gstr1B2CLState(TypedDict):
    pos: str
    inv: list[Gstr1B2CLInvoice]


class Gstr1B2CSRow(TypedDict):
    sply_ty: str
    pos: str
    typ: str
    rt: float
    txval: float
    iamt: float
    camt: float
    samt: float
    csamt: float


class Gstr1Note(TypedDict):
    ntty: str
    nt_num: str
    nt_dt: str
    p_gst: str
    inum: str
    idt: str
    val: float
    itms: list[Gstr1InvoiceItem]


class Gstr1CdnrParty(TypedDict):
    ctin: str
    nt: list[Gstr1Note]


class Gstr1CdnurNote(TypedDict):
    typ: str
    ntty: str
    nt_num: str
    nt_dt: str
    p_gst: str
    inum: str
    idt: str
    val: float
    itms: list[Gstr1InvoiceItem]


class Gstr1HsnRow(TypedDict):
    num: int
    hsn_sc: str
    desc: str
    uqc: str
    qty: float
    rt: float
    txval: float
    iamt: float
    camt: float
    samt: float
    csamt: float


class Gstr1HsnSection(TypedDict):
    data: list[Gstr1HsnRow]


class Gstr1DocIssueDetail(TypedDict):
    num: int
    from_: str
    to: str
    totnum: int
    cancel: int
    net_issue: int


class Gstr1DocIssueType(TypedDict):
    doc_num: int
    doc_typ: str
    docs: list[Gstr1DocIssueDetail]


class Gstr1DocIssueSection(TypedDict):
    doc_det: list[Gstr1DocIssueType]


class Gstr1ExportPayload(TypedDict):
    version: str
    gstin: str
    fp: str
    gt: float
    b2b: list[Gstr1B2BParty]
    b2cl: list[Gstr1B2CLState]
    b2cs: list[Gstr1B2CSRow]
    cdnr: list[Gstr1CdnrParty]
    cdnur: list[Gstr1CdnurNote]
    exp: list[Any]
    hsn: Gstr1HsnSection
    doc_issue: Gstr1DocIssueSection


def empty_gstr1_payload(gstin: str, fp: str) -> dict[str, Any]:
    """Return an empty GSTR-1 root object with required arrays."""
    return {
        "version": "GST3.1.4",
        "gstin": gstin,
        "fp": fp,
        "gt": 0.0,
        "b2b": [],
        "b2cl": [],
        "b2cs": [],
        "cdnr": [],
        "cdnur": [],
        "exp": [],
        "hsn": {"data": []},
        "doc_issue": {"doc_det": []},
    }
