"""Genera consulta estudiantil desde S11/S12 verificados del grupo local."""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
GROUP = next(ROOT.glob("outputs/g??_products.json")).stem[:3].upper()
sys.path.insert(0, str(ROOT / "kai"))
sys.path.insert(0, str(ROOT))
application = importlib.import_module(f"aplicacion_{GROUP.lower()}")
from src.missions.products import verified_product

TARGET = ROOT / f"docs/learning/{GROUP.lower()}_student_results.js"
SHARDS = ROOT / f"docs/learning/{GROUP.lower()}_student_blocks"
S11_COLS = ["cu_pct_est", "density_t_m3_est", "rock_volume_m3", "tonnage_t",
            "cu_pct_holes", "mo_pct_est", "au_gt_est"]
S12_COLS = ["allocated_moved_t", "total_opex_usd"]
COLS = ["block_id", "i", "j", "k", *S11_COLS, *S12_COLS]
FIELD_COL = {"S11.B.CU": "cu_pct_est", "S11.B.RHO": "density_t_m3_est",
             "S11.B.V": "rock_volume_m3", "S11.B.T": "tonnage_t",
             "S11.B.H": "cu_pct_holes", "S11.B.MO": "mo_pct_est",
             "S11.B.AU": "au_gt_est", "S12.B.ALLOC": "allocated_moved_t",
             "S12.B.OPEX": "total_opex_usd"}


def read_rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def num(value):
    return None if value in (None, "") else float(value)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_file(folder, name):
    direct = folder / name
    zipped = folder / (name + ".gz")
    if direct.is_file() == zipped.is_file():
        raise ValueError(f"Se esperaba exactamente una fuente para {name}")
    return direct if direct.is_file() else zipped


def build():
    s11, s11_folder, s11_summary = verified_product(ROOT, "S11")
    s12, s12_folder, _ = verified_product(ROOT, "S12")
    fields, s11_id, s12_id = application.catalog(ROOT)
    assert len(fields) == 26 and s11_id == s11["run_id"] and s12_id == s12["run_id"]
    s11_path = data_file(s11_folder, "block_model_s11.csv")
    s12_path = data_file(s12_folder, "block_scenario_s12.csv")
    example = next(f["block"] for f in fields if f["id"] == "S11.B.CU")
    sharded = GROUP == "G02"

    relation = {}
    for item in read_rows(s12_path):
        if item["scenario"] != "A":
            continue
        block = item["block_id"]
        assert block not in relation
        relation[block] = [num(item[key]) for key in S12_COLS]
    blocks = []
    shards = {}
    ids = set()
    example_row = None
    for item in read_rows(s11_path):
        block = item["block_id"]
        assert block not in ids and block in relation
        ids.add(block)
        row = [block, int(item["i"]), int(item["j"]), int(item["k"]),
               *(num(item[key]) for key in S11_COLS), *relation.pop(block)]
        if block == example:
            example_row = row
        if sharded:
            blocks.append(row[:4])
            shards.setdefault(row[1], []).append(row)
        else:
            blocks.append(row)
    assert not relation and len(blocks) == s11_summary["total_blocks"]
    assert example_row is not None
    pos = {key: i for i, key in enumerate(COLS)}
    for field in fields:
        if field["id"] in FIELD_COL:
            value = example_row[pos[FIELD_COL[field["id"]]]]
            assert value is not None and abs(value - float(field["expected"])) < 1e-6, field["id"]

    if sharded:
        SHARDS.mkdir(exist_ok=True)
        expected_names = set()
        for i, rows in shards.items():
            name = f"i_{i:03d}.js"
            expected_names.add(name)
            (SHARDS / name).write_text(
                f"window.PLANMIN_STUDENT_SHARDS[{i}]=" +
                json.dumps(rows, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + ";\n",
                encoding="utf-8")
        for old in SHARDS.glob("i_*.js"):
            if old.name not in expected_names:
                old.unlink()
    payload = {
        "group": GROUP, "s11_run_id": s11_id, "s12_run_id": s12_id,
        "source_sha256": {"s11_blocks": file_hash(s11_path), "s12_scenarios": file_hash(s12_path)},
        "block_count": len(blocks), "sharded": sharded,
        "example_block": example,
        "fields": [{"id": f["id"], "label": f["label"], "unit": f["unit"],
                    "stage": f["stage"], "block": f["block"], "places": f["places"],
                    "value": f["expected"]} for f in fields],
        "block_columns": COLS, "blocks": blocks,
    }
    TARGET.write_text("window.PLANMIN_STUDENT_RESULTS=" + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + ";\n", encoding="utf-8")
    print(json.dumps({"group": GROUP, "blocks": len(blocks), "fields": len(fields),
                      "index_bytes": TARGET.stat().st_size, "shards": len(shards),
                      "s11": s11_id, "s12": s12_id}, ensure_ascii=False))


if __name__ == "__main__":
    build()
