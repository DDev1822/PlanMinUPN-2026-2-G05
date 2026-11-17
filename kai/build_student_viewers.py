"""Deriva visores 3D legibles, manteniendo intacto el payload validado."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
GROUP = next(ROOT.glob("outputs/g??_products.json")).stem[:3].upper()
sys.path.insert(0, str(ROOT))
from src.missions.products import verified_product


def embedded(text):
    marker = f"window.{GROUP}_MODEL"
    start = text.index(marker)
    return text[start:text.index("</script>", start)]


def build():
    for stage in ("S11", "S12"):
        _, folder, _ = verified_product(ROOT, stage)
        source = folder / f"{stage.lower()}_model_3d.html"
        original = source.read_text(encoding="utf-8")
        text = original.replace("../../../assets/", "../../assets/")
        text = text.replace("../../../index.html", "../../index.html")
        text = text.replace("<html lang=\"es\"", f"<html lang=\"es\" data-group=\"{GROUP}\"", 1)
        pattern = r'<p><a href="../../index\.html#' + stage.lower() + r'".*?</p>'
        replacement = (f'<p><a href="../../index.html#{stage.lower()}" target="_top">Volver al proyecto</a> · '
                       f'<a href="RESULTADOS_{GROUP}.html#{stage.lower()}" target="_top">Consultar resultados y bloques</a></p>')
        text, changes = re.subn(pattern, replacement, text, count=1)
        assert changes == 1
        text = re.sub(r'<a\s+[^>]*href="[^"]+\.(?:json|csv|csv\.gz|md)"[^>]*>.*?</a>', '', text)
        text = text.replace("filas en el CSV completo", "bloques en el modelo completo")
        text = text.replace("por ejemplo G01-00000.", "por ejemplo un identificador de la consulta visual.")
        text = re.sub(r'por ejemplo [A-Z0-9_-]+\.', 'por ejemplo un identificador de la consulta visual.', text, count=1)
        text = text.replace('G01-ALLOC-01: cada bloque participa proporcionalmente',
                            'Regla de aula: cada bloque participa proporcionalmente')
        text = text.replace(f"{GROUP}-ALLOC-01: cada bloque participa proporcionalmente",
                            "Regla de aula: cada bloque participa proporcionalmente")
        old = '<script src="../../assets/quantitative.js"></script>'
        assert text.count(old) == 1
        text = text.replace(old, old + '<script src="visor_estudiantil.js"></script>')
        # El 3D dibuja una selección para rendimiento. La consulta cubre toda la malla.
        text = text.replace('<div class="metrics" id="metrics"></div>',
            f'<p class="muted">El 3D dibuja una selección de bloques para facilitar la exploración. '
            f'La <a href="RESULTADOS_{GROUP}.html#consulta">consulta visual</a> permite buscar toda la malla.</p>'
            '<div class="metrics" id="metrics"></div>', 1)
        assert embedded(original) == embedded(text)
        assert 'href="s11_summary.json"' not in text and 'href="s12_summary.json"' not in text
        target = ROOT / f"docs/learning/VISOR_{stage}_{GROUP}.html"
        target.write_text(text, encoding="utf-8", newline="\n")
        print(GROUP, stage, target.stat().st_size,
              hashlib.sha256(embedded(text).encode("utf-8")).hexdigest())


if __name__ == "__main__":
    build()
