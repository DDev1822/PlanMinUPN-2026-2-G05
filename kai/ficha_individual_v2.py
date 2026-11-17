"""Ficha E1 V2: contexto verificado por el sistema y evidencia E1 separada.

La ficha V1, su SQLite y su Excel permanecen intactos. Los valores de esta
versión nunca se presentan como respuestas del alumno.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
import xml.etree.ElementTree as ET
import zipfile

import ficha_individual as legacy

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "kai/ficha_e1_v2.json"
DATA = ROOT / ".kai_local"


def _sources():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    raw = (ROOT / contract["source_catalog"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != contract["source_catalog_sha256"]:
        raise ValueError("El catálogo fuente de la ficha V2 cambió")
    catalog, summary = legacy._fuentes()
    if catalog["resumen_sha256"] != contract["source_summary_sha256"]:
        raise ValueError("El resumen fuente de la ficha V2 cambió")
    fields = {f["id"]: f for f in catalog["campos"]}
    mapped = contract["fields"]
    if len(fields) != 21 or len(mapped) != 21 or set(fields) != {f["id"] for f in mapped}:
        raise ValueError("El contrato V2 debe cubrir los 21 campos originales exactamente")
    if len(contract["student_evidence"]) != 8:
        raise ValueError("Las competencias E1 del contrato V2 no coinciden")
    for item in mapped:
        if item["role"] not in {"METADATA", "OBSERVABLE"}:
            raise ValueError("Clasificación de campo no permitida")
        if item["role"] == "OBSERVABLE" and item.get("activity") not in contract["student_evidence"]:
            raise ValueError("Un dato observable carece de actividad E1")
        if item["role"] == "METADATA" and item.get("activity") is not None:
            raise ValueError("Un metadato no requiere evidencia del estudiante")
    return contract, catalog, summary, fields


def _demonstrated(folder):
    path = folder / "teoria_v2.sqlite"
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT id,actividad FROM eventos_v2 WHERE etapa='E1' "
                          "AND estado='DEMOSTRADO' ORDER BY rowid").fetchall()
    events = {}
    for event_id, activity in rows:
        events.setdefault(activity, event_id)
    return events


def _open(folder, contract, catalog):
    path = folder / "ficha_individual_v2.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS metadata_v2 (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
    db.execute("""CREATE TABLE IF NOT EXISTS campos_v2 (
        field_id TEXT PRIMARY KEY, value_json TEXT NOT NULL,
        origin TEXT NOT NULL CHECK(origin='SYSTEM_VERIFIED'),
        source_sha256 TEXT NOT NULL, source_commit TEXT NOT NULL,
        activity_id TEXT, evidence_event_id TEXT, verified_utc TEXT NOT NULL)""")
    expected = {"ficha_id": contract["ficha_id"], "version": str(contract["version"]),
                "contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
                "source_catalog_sha256": contract["source_catalog_sha256"],
                "source_summary_sha256": contract["source_summary_sha256"],
                "source_commit": catalog["source_commit"]}
    for key, value in expected.items():
        found = db.execute("SELECT valor FROM metadata_v2 WHERE clave=?", (key,)).fetchone()
        if found and found[0] != value:
            db.close()
            raise ValueError("La ficha V2 guardada pertenece a otra versión; conservar y revisar")
        db.execute("INSERT OR IGNORE INTO metadata_v2 VALUES (?,?)", (key, value))
    db.commit()
    return db


def _export(folder, alias, contract, catalog, fields, recorded, demonstrated):
    target = folder / "Ficha_Individual_G05_V2.xlsx"
    with zipfile.ZipFile(legacy.TEMPLATE) as source:
        sheet = ET.fromstring(source.read("xl/worksheets/sheet1.xml"))
        legacy._excel_cell(sheet, "C3", alias)
        legacy._excel_cell(sheet, "C4", len(recorded))
        legacy._excel_cell(sheet, "F4", "Contexto completo" if len(recorded) == 21 else "En curso")
        legacy._excel_cell(sheet, "B6", "Dato del proyecto")
        legacy._excel_cell(sheet, "C6", "Valor verificado")
        legacy._excel_cell(sheet, "F6", "Procedencia")
        for row, item in enumerate(contract["fields"], start=7):
            fid = item["id"]
            if fid in recorded:
                value = json.loads(recorded[fid][0])
                legacy._excel_cell(sheet, f"C{row}", legacy._display(fields[fid], value))
                legacy._excel_cell(sheet, f"F{row}", "SYSTEM_VERIFIED")
        legacy._excel_cell(sheet, "A28", "Competencias E1")
        legacy._excel_cell(sheet, "C28", len(demonstrated))
        legacy._excel_cell(sheet, "F28", "Evidencia separada")
        legacy._excel_cell(sheet, "B29", "Resumen verificado")
        legacy._excel_cell(sheet, "C29", contract["source_summary_sha256"])
        legacy._excel_cell(sheet, "C30", "Ficha V2")
        pending = folder / (".ficha_v2_" + uuid.uuid4().hex + ".xlsx")
        try:
            with zipfile.ZipFile(pending, "w") as dest:
                for info in source.infolist():
                    payload = (ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
                               if info.filename == "xl/worksheets/sheet1.xml" else source.read(info))
                    dest.writestr(info, payload)
            os.replace(pending, target)
        finally:
            pending.unlink(missing_ok=True)
    return target


def sync(alias, data=DATA):
    if not legacy.ALIAS.fullmatch(str(alias)):
        raise ValueError("Alias inválido para la ficha V2")
    contract, catalog, summary, fields = _sources()
    folder = data / alias
    folder.mkdir(parents=True, exist_ok=True)
    demonstrated = _demonstrated(folder)
    with closing(_open(folder, contract, catalog)) as db:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for item in contract["fields"]:
            activity = item.get("activity")
            if activity and activity not in demonstrated:
                continue
            field = fields[item["id"]]
            value = legacy._source_value(summary, field)
            expected = (json.dumps(value, ensure_ascii=False), "SYSTEM_VERIFIED",
                        contract["source_summary_sha256"], catalog["source_commit"],
                        activity, demonstrated.get(activity))
            previous = db.execute("SELECT value_json,origin,source_sha256,source_commit,activity_id,"
                                  "evidence_event_id FROM campos_v2 WHERE field_id=?", (item["id"],)).fetchone()
            if previous and tuple(previous) != expected:
                raise ValueError("Un campo V2 cambió de valor o procedencia: " + item["id"])
            db.execute("INSERT OR IGNORE INTO campos_v2 VALUES (?,?,?,?,?,?,?,?)",
                       (item["id"], *expected, now))
        db.commit()
        recorded = {row[0]: row[1:] for row in db.execute(
            "SELECT field_id,value_json,origin,source_sha256,source_commit,activity_id,evidence_event_id FROM campos_v2")}
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError("La ficha V2 falló la integridad SQLite")
    excel_ok = True
    try:
        xlsx = _export(folder, alias, contract, catalog, fields, recorded, demonstrated)
    except PermissionError:
        excel_ok = False
        xlsx = folder / "Ficha_Individual_G05_V2.xlsx"
    metadata = sum(fid in recorded for fid in ("PROYECTO.NOMBRE", "PROYECTO.DATASET", "PROYECTO.RELEASE"))
    complete = len(recorded) == 21 and all(a in demonstrated for a in contract["student_evidence"])
    return {"version": 2, "ficha_id": contract["ficha_id"], "verified_fields": len(recorded),
            "total_fields": 21, "metadata_verified": metadata, "observables_verified": len(recorded)-metadata,
            "competencies_demonstrated": sum(a in demonstrated for a in contract["student_evidence"]),
            "competencies_total": 8, "origin": "SYSTEM_VERIFIED", "pending": None,
            "complete": complete, "xlsx": str(xlsx), "excel_actualizado": excel_ok,
            "source_summary_sha256": contract["source_summary_sha256"],
            "legacy_v1_present": (folder / "ficha_individual.sqlite").is_file()}


def context_for(activity_id):
    """Datos comprobados para enseñar una actividad, no preguntas de memoria."""
    contract, _, summary, fields = _sources()
    return [{"id": item["id"], "etiqueta": fields[item["id"]]["etiqueta"],
             "valor": legacy._source_value(summary, fields[item["id"]]),
             "unidad": fields[item["id"]]["unidad"],
             "procedencia": "SYSTEM_VERIFIED",
             "source_sha256": contract["source_summary_sha256"]}
            for item in contract["fields"] if item.get("activity") == activity_id]
