import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import current_app


def _validate_ids(project_id: int, scene_id: int | None = None) -> None:
    if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id <= 0:
        raise ValueError("project_id must be a positive integer.")

    if scene_id is not None:
        if isinstance(scene_id, bool) or not isinstance(scene_id, int) or scene_id <= 0:
            raise ValueError("scene_id must be a positive integer.")


def get_project_storage_path(project_id: int) -> str:
    """Return the absolute media directory for a project."""
    _validate_ids(project_id)

    storage_root = (
        Path(current_app.root_path).resolve()
        .parent / "storage" / "media" / "projects"
    )
    return str(storage_root / f"project_{project_id}")


def _get_safe_project_directory(project_id: int) -> Path:
    """Resolve a project directory and ensure it cannot escape its storage root."""
    _validate_ids(project_id)

    storage_root = (
        Path(current_app.root_path).resolve()
        .parent / "storage" / "media" / "projects"
    ).resolve()
    project_dir = (storage_root / f"project_{project_id}").resolve()

    if project_dir.parent != storage_root or project_dir.name != f"project_{project_id}":
        raise ValueError("Invalid project storage path.")

    return project_dir


def delete_video(asset_path: str, project_id: int) -> bool:
    """
    Delete a video only if it belongs directly to the specified project.

    Returns True if a file was deleted, False if it did not exist.
    """
    if not asset_path:
        return False

    project_dir = _get_safe_project_directory(project_id)
    target_path = Path(asset_path).resolve()

    if target_path.parent != project_dir:
        raise ValueError("Asset path is outside project storage.")

    if not target_path.is_file():
        return False

    target_path.unlink()
    return True


def delete_project_storage(project_id: int) -> bool:
    """
    Delete all downloaded media for one project.

    The resolved directory must be the exact project_<id> child of the
    application's media/projects storage directory. This prevents a bad
    project ID or symlink from deleting unrelated files.
    """
    project_dir = _get_safe_project_directory(project_id)

    if not project_dir.exists():
        return False

    if project_dir.is_symlink() or not project_dir.is_dir():
        raise ValueError("Project storage path is not a valid directory.")

    shutil.rmtree(project_dir)
    return True


def download_video(url: str, project_id: int, scene_id: int) -> str:
    """
    Download a selected Pixabay video to a temporary file, then atomically
    promote it to its stable scene filename.
    """
    _validate_ids(project_id, scene_id)

    parsed_url = urlparse(url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "cdn.pixabay.com"
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise ValueError("Untrusted video download URL.")

    storage_root = Path(_get_safe_project_directory(project_id))
    storage_root.mkdir(parents=True, exist_ok=True)

    filename = f"scene_{scene_id}.mp4"
    file_path = storage_root / filename
    temp_path = storage_root / f"{filename}.{os.urandom(8).hex()}.part"

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(10, 60),
            allow_redirects=False,
        ) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("video/"):
                raise ValueError("Downloaded resource is not a video.")

            with temp_path.open("wb") as video_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        video_file.write(chunk)

        if not temp_path.is_file() or temp_path.stat().st_size == 0:
            raise RuntimeError("Downloaded video is empty.")

        os.replace(temp_path, file_path)

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    return str(file_path)
