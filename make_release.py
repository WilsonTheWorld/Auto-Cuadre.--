"""Genera un paquete de actualización para Auto Cuadre.

Uso:
    python make_release.py 1.1.0 "Qué cambia en esta versión" [carpeta_salida]

Crea en la carpeta de salida (por defecto ./release):
    auto_cuadre_1.1.0.zip   archivos del programa (.py .ps1 .bat .md .txt), sin config.json ni caché
    version.json            manifiesto con versión, nombre del zip, SHA-256 y notas

Publique ambos archivos en la misma carpeta compartida (\\\\SERVIDOR\\updates) o sitio HTTPS y escriba la ruta
de version.json en Configuración > Origen de actualizaciones.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
INCLUDE = {".py", ".ps1", ".bat", ".md", ".txt"}
SKIP_NAMES = {"config.json", "stats_cache.json", "update_notice.json"}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not re.fullmatch(r"\d+(\.\d+){0,2}", argv[1]):
        print(__doc__)
        return 1
    version = argv[1]
    notes = argv[2] if len(argv) > 2 else ""
    out_dir = Path(argv[3]) if len(argv) > 3 else PROJECT_DIR / "release"
    out_dir.mkdir(parents=True, exist_ok=True)

    (PROJECT_DIR / "version.py").write_text(
        f'"""Versión instalada de Auto Cuadre. make_release.py la actualiza al publicar."""\n\n__version__ = "{version}"\n',
        encoding="utf-8")

    package = out_dir / f"auto_cuadre_{version}.zip"
    files = sorted(
        path for path in PROJECT_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in INCLUDE and path.name not in SKIP_NAMES
        and not any(part.startswith(".") or part in {"release", "__pycache__"} for part in path.relative_to(PROJECT_DIR).parts))
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(PROJECT_DIR).as_posix())

    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    manifest = {"version": version, "url": package.name, "sha256": digest, "notes": notes}
    (out_dir / "version.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Paquete: {package}  ({len(files)} archivos)\nSHA-256: {digest}\nManifiesto: {out_dir / 'version.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
