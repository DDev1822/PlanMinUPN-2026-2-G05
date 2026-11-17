"""Regresión de la consulta visual contra las 26 observaciones de este grupo."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
GROUP = next(ROOT.glob("outputs/g??_products.json")).stem[:3].upper()
sys.path.insert(0, str(ROOT / "kai"))
application = importlib.import_module(f"aplicacion_{GROUP.lower()}")
controller = importlib.import_module(f"recorrido_{GROUP.lower()}")
VIEW = ROOT / "docs/learning"


def student_data():
    text = (VIEW / f"{GROUP.lower()}_student_results.js").read_text(encoding="utf-8")
    assert text.startswith("window.PLANMIN_STUDENT_RESULTS=")
    return json.loads(text.split("=", 1)[1].rstrip(";\n"))


def test_26_values_and_full_block_index():
    fields, s11, s12 = application.catalog(ROOT)
    data = student_data()
    assert (data["group"], data["s11_run_id"], data["s12_run_id"]) == (GROUP, s11, s12)
    assert len(fields) == len(data["fields"]) == 26
    for source, shown in zip(fields, data["fields"]):
        assert (shown["id"], shown["label"], shown["unit"], shown["value"], shown["block"]) == (
            source["id"], source["label"], source["unit"], source["expected"], source["block"])
    assert len(data["blocks"]) == data["block_count"]
    assert len({row[0] for row in data["blocks"]}) == data["block_count"]
    assert data["example_block"] in {row[0] for row in data["blocks"]}
    if data["sharded"]:
        assert GROUP == "G02"
        assert (VIEW / "g02_student_blocks").is_dir()


def test_kai_link_and_derived_viewer_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, "DATA", tmp_path)
    monkeypatch.setattr(controller.theory, "DATA", tmp_path)
    pending = controller.process({"operacion": "estado_aplicacion", "alumno": "QA_Consulta"})["pending"]
    assert pending["dato_verificado"]["modelo"] == "S11"
    assert f"RESULTADOS_{GROUP}.html#campo-" in pending["consulta_estudiantil"]
    assert (ROOT / pending["consulta_estudiantil"].split("#", 1)[0]).is_file()
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    assert f"RESULTADOS_{GROUP}.html#s11" in home
    assert f"RESULTADOS_{GROUP}.html#s12" in home
    page = (VIEW / f"RESULTADOS_{GROUP}.html").read_text(encoding="utf-8")
    assert "consulta_resultados.js" in page
    assert ".json\"" not in page and ".csv\"" not in page
    data = student_data()
    for stage in ("S11", "S12"):
        current = data[f"{stage.lower()}_run_id"]
        original = (ROOT / "outputs" / f"{GROUP.lower()}_{stage.lower()}" /
                    current / f"{stage.lower()}_model_3d.html").read_text(encoding="utf-8")
        derived = (VIEW / f"VISOR_{stage}_{GROUP}.html").read_text(encoding="utf-8")
        marker = f"window.{GROUP}_MODEL"
        payload = lambda text: text[text.index(marker):text.index("</script>", text.index(marker))]
        assert payload(derived) == payload(original)
        assert "href=\"block_model_" not in derived
        assert "visor_estudiantil.js" in derived
