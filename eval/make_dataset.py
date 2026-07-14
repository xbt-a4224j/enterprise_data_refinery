"""Generate a labeled evaluation dataset: synthetic building-permit documents in varied
formats, each with ground-truth field values. Deterministic (no randomness)."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE / "dataset"

JUR = ["Springfield", "Delaware County", "Cary", "Lakewood", "Media", "Riverside",
       "Franklin", "Auburn", "Kingsport", "Bristol", "Salem", "Dover"]
TYPES = ["Residential Alteration", "Commercial New Construction", "Residential Solar",
         "Demolition", "Electrical", "Plumbing", "Roofing", "Mechanical"]
STATUS = ["Issued", "Under Review", "Finaled", "Expired", "Approved"]
APPL = ["Rivera Construction LLC", "Keystone Developers Inc", "SunFair Energy",
        "Clearway Demolition", "Homefront Builders", "Apex Mechanical", "Blue Ridge Roofing"]

# Three label templates to test format robustness.
TEMPLATES = [
    ("t1", "CITY OF {jur_up} - BUILDING PERMIT\nPermit No: {pid}\nSite Address: {addr}\n"
           "Type: {ptype}\nStatus: {status}\nDate Issued: {date}\n"
           "Estimated Valuation: ${val:,}\nApplicant: {appl}\n"),
    ("t2", "{jur_up} COUNTY PERMIT RECORD\nPermit ID: {pid}\nAddress: {addr}\n"
           "Permit Type: {ptype}\nCurrent Status: {status}\nIssued: {date}\n"
           "Valuation: ${val:,}\nApplicant Name: {appl}\n"),
    ("t3", "TOWN OF {jur_up} - PERMIT\nNo. {pid}\nLocation: {addr}\nCategory: {ptype}\n"
           "Status: {status}\nIssue Date: {date}\nJob Value: ${val:,}\nApplicant: {appl}\n"),
]


def _rows():
    rows = []
    for i in range(24):
        jur = JUR[i % len(JUR)]
        ptype = TYPES[i % len(TYPES)]
        status = STATUS[i % len(STATUS)]
        appl = APPL[i % len(APPL)]
        pid = f"BP-2026-{4000 + i * 37:05d}"
        val = 15000 + (i * 41000) % 1_400_000
        month = 1 + (i % 9)
        day = 1 + (i * 3) % 27
        date = f"2026-{month:02d}-{day:02d}"
        addr = f"{10 + i * 7} {['Maple','Oak','Birch','Dogwood','Elm'][i % 5]} St, {jur}"
        rows.append(dict(pid=pid, jur=jur, ptype=ptype, status=status, appl=appl,
                         val=val, date=date, addr=addr))
    return rows


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    for f in DOCS.glob("*.txt"):
        f.unlink()
    labels = {}
    for i, r in enumerate(_rows()):
        tname, tmpl = TEMPLATES[i % len(TEMPLATES)]
        text = tmpl.format(jur_up=r["jur"].upper(), addr=r["addr"], pid=r["pid"],
                           ptype=r["ptype"], status=r["status"], date=r["date"],
                           val=r["val"], appl=r["appl"])
        name = f"permit_{i:02d}.txt"
        (DOCS / name).write_text(text)
        labels[name] = {
            "permit_id": r["pid"], "jurisdiction": r["jur"], "permit_type": r["ptype"],
            "status": r["status"], "issued_date": r["date"],
            "valuation_usd": float(r["val"]), "applicant": r["appl"],
        }
    (HERE / "labels.json").write_text(json.dumps(labels, indent=2))
    print(f"wrote {len(labels)} labeled docs to {DOCS} + labels.json")


if __name__ == "__main__":
    main()
