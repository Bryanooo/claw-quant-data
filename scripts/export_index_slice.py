"""Export an atomic research slice to a new, immutable Parquet bundle."""

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZipInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.research.index_slice import build_slice, canonical, content_hash, MODES
from hashlib import sha256


def export(payload, destination):
    import duckdb  # CLI-only dependency; no change to worker or API images.

    manifest = payload["manifest"]
    if payload["slice_id"] != content_hash(manifest) or manifest[
        "rows_sha256"
    ] != content_hash(payload["rows"]):
        raise ValueError("slice digest mismatch")
    flat = [
        (
            date.fromisoformat(manifest["trade_date"]),
            r["ts_code"],
            n,
            c["value"],
            c["available"],
            c["reason"],
        )
        for r in payload["rows"]
        for n in manifest["factors"]
        for c in (r["factors"][n],)
    ]
    with TemporaryDirectory(dir=destination.parent) as temp:
        table = Path(temp) / "factors.parquet"
        with duckdb.connect() as db:
            db.execute("SET threads=1")
            db.execute("""CREATE TABLE factors(trade_date DATE,ts_code VARCHAR,factor VARCHAR,
                          value DOUBLE,available BOOLEAN,reason VARCHAR)""")
            db.executemany("INSERT INTO factors VALUES (?,?,?,?,?,?)", flat)
            db.execute(
                "COPY (SELECT * FROM factors ORDER BY ts_code,factor) TO ? (FORMAT parquet)",
                [str(table)],
            )
            if db.execute(
                "SELECT * FROM read_parquet(?) ORDER BY ts_code,factor", [str(table)]
            ).fetchall() != sorted(flat, key=lambda x: (x[1], x[2])):
                raise ValueError("Parquet round trip changed data")
        data = table.read_bytes()
        metadata = dict(
            **manifest,
            slice_id=payload["slice_id"],
            parquet_sha256=sha256(data).hexdigest(),
            duckdb_version=duckdb.__version__,
            parquet_rows=len(flat),
        )
        bundle = Path(temp) / "bundle.zip"
        with ZipFile(bundle, "w") as archive:
            for name, content in (
                ("manifest.json", canonical(metadata)),
                ("rows.json", canonical(payload["rows"])),
                ("factors.parquet", data),
            ):
                archive.writestr(ZipInfo(name), content)
        os.link(bundle, destination)  # atomic no-clobber, same filesystem
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--factor", action="append", required=True)
    parser.add_argument("--knowledge", choices=MODES, default="known_then")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            export(build_slice(args.day, args.factor, args.knowledge), args.output),
            ensure_ascii=False,
        )
    )
