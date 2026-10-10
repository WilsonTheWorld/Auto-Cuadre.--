"""Auto-actualización de Auto Cuadre.

Cómo funciona
  1. Se lee un manifiesto `version.json` del origen configurado (update_manifest_url):
        {"version": "1.1.0", "url": "auto_cuadre_1.1.0.zip", "sha256": "<64 hex>", "notes": "..."}
     El origen puede ser una URL https:// o una carpeta compartida / ruta local (p. ej. \\\\SERVIDOR\\updates\\version.json).
  2. Si la versión es mayor que la instalada, se descarga el .zip con avance y se verifica su SHA-256.
  3. Los archivos nuevos se copian sobre el programa (con respaldo en .update_backup y reversión si algo falla).
     Nunca se tocan config.json ni la caché de estadísticas.
  4. La aplicación se reinicia sola.

Importante: el repositorio de GitHub es privado, así que NO se puede usar directamente como origen sin
incrustar una credencial en cada PC. Publique el manifiesto y el .zip en una carpeta compartida o en
un sitio público/propio (ver make_release.py).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

from utils import PROJECT_DIR
from version import __version__

PROTECTED = {"config.json", "stats_cache.json", "update_notice.json"}  # nunca se sobrescriben
UPDATABLE_SUFFIXES = {".py", ".ps1", ".bat", ".md", ".txt"}
BACKUP_DIR = PROJECT_DIR / ".update_backup"
NOTICE_PATH = PROJECT_DIR / "update_notice.json"
TIMEOUT_SECONDS = 8  # si no hay internet/servidor, el arranque no se queda esperando

Progress = Callable[[float, str], None]


class UpdateError(RuntimeError):
    pass


def parse_version(text: Any) -> tuple[int, int, int]:
    numbers = [int(n) for n in re.findall(r"\d+", str(text))]
    if not numbers:
        raise UpdateError(f"Versión no válida: {text!r}")
    return tuple((numbers + [0, 0, 0])[:3])  # type: ignore[return-value]


def _is_url(location: str) -> bool:
    return bool(re.match(r"^https?://", location, re.IGNORECASE))


def _open(location: str):
    if _is_url(location):
        if location.lower().startswith("http://"):
            raise UpdateError("El origen de actualizaciones debe usar HTTPS.")
        request = urllib.request.Request(location, headers={"User-Agent": "AutoCuadre-Updater"})
        return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
    return open(location, "rb")  # carpeta compartida / ruta local


def _size(source) -> int:
    try:
        return int(source.headers.get("Content-Length") or 0)
    except AttributeError:
        try:
            return os.fstat(source.fileno()).st_size
        except (AttributeError, OSError):
            return 0


def _resolve(manifest_location: str, package: str) -> str:
    if _is_url(manifest_location):
        return urllib.parse.urljoin(manifest_location, package)
    return str(Path(manifest_location).parent / package)


def check_for_update(manifest_location: str) -> dict[str, str] | None:
    """Devuelve los datos de la versión nueva, o None si ya se está al día / no hay origen configurado."""
    manifest_location = (manifest_location or "").strip()
    if not manifest_location:
        return None
    with _open(manifest_location) as handle:
        manifest = json.loads(handle.read().decode("utf-8-sig"))
    version = str(manifest.get("version", ""))
    if parse_version(version) <= parse_version(__version__):
        return None
    sha256 = str(manifest.get("sha256", "")).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise UpdateError("El manifiesto no incluye un SHA-256 válido; no se instalará la actualización.")
    package = str(manifest.get("url", "")).strip()
    if not package:
        raise UpdateError("El manifiesto no indica el paquete a descargar.")
    return {"version": version, "url": _resolve(manifest_location, package),
            "sha256": sha256, "notes": str(manifest.get("notes", ""))}


def download_package(info: dict[str, str], progress: Progress) -> Path:
    """Descarga el .zip con avance y verifica su SHA-256."""
    work_dir = Path(tempfile.mkdtemp(prefix="auto_cuadre_update_"))
    target = work_dir / "package.zip"
    digest, received = hashlib.sha256(), 0
    try:
        with _open(info["url"]) as source, target.open("wb") as output:
            total = _size(source)
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                progress(received / total if total else 0.0,
                         f"Descargando versión {info['version']}… {received // 1024} KB")
        if digest.hexdigest() != info["sha256"]:
            raise UpdateError("La descarga está dañada o fue alterada (el SHA-256 no coincide).")
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    progress(1.0, "Descarga verificada")
    return target


def _common_root(names: list[str]) -> str | None:
    firsts = {Path(name).parts[0] for name in names if len(Path(name).parts) > 1}
    if len(firsts) == 1 and all(len(Path(name).parts) > 1 for name in names):
        return firsts.pop()
    return None


def _extract_safely(package: Path, staging: Path) -> None:
    staging_root = staging.resolve()
    with zipfile.ZipFile(package) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        root = _common_root([m.filename for m in members])
        for member in members:
            relative = Path(member.filename)
            if relative.is_absolute() or ".." in relative.parts or ":" in member.filename:
                raise UpdateError("El paquete contiene rutas no permitidas.")
            if root:
                relative = relative.relative_to(root)
            destination = (staging / relative).resolve()
            if staging_root not in destination.parents:
                raise UpdateError("El paquete contiene rutas no permitidas.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def apply_package(package: Path, info: dict[str, str], target_dir: Path = PROJECT_DIR) -> list[str]:
    """Instala los archivos del paquete con respaldo; revierte todo si algo falla."""
    staging = package.parent / "staging"
    _extract_safely(package, staging)
    backup = BACKUP_DIR / __version__ if target_dir == PROJECT_DIR else target_dir / ".update_backup" / __version__
    changed: list[Path] = []
    try:
        for file in sorted(p for p in staging.rglob("*") if p.is_file()):
            relative = file.relative_to(staging)
            if relative.name in PROTECTED or file.suffix.lower() not in UPDATABLE_SUFFIXES:
                continue
            destination = target_dir / relative
            if destination.exists():
                (backup / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup / relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination)
            changed.append(relative)
    except Exception:
        for relative in changed:
            saved = backup / relative
            if saved.exists():
                shutil.copy2(saved, target_dir / relative)
            else:
                (target_dir / relative).unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(package.parent, ignore_errors=True)
    if target_dir == PROJECT_DIR:
        NOTICE_PATH.write_text(json.dumps({"version": info["version"], "previous": __version__,
                                           "notes": info.get("notes", "")}, ensure_ascii=False), encoding="utf-8")
    return [str(relative) for relative in changed]


def consume_update_notice() -> dict[str, str] | None:
    """Lee (y borra) el aviso que deja una actualización recién instalada."""
    try:
        notice = json.loads(NOTICE_PATH.read_text(encoding="utf-8"))
        NOTICE_PATH.unlink(missing_ok=True)
        return notice if isinstance(notice, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def restart_application() -> None:
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([sys.executable, str(PROJECT_DIR / "main.py")], cwd=str(PROJECT_DIR),
                     creationflags=flags, close_fds=True)
