
import os
import requests

from flask import current_app


def get_project_storage_path(project_id: int) -> str:
    """Return the absolute media directory for a project."""

    return os.path.abspath(
        os.path.join(
            current_app.root_path,
            "..",
            "storage",
            "media",
            "projects",
            f"project_{project_id}"
        )
    )


def delete_video(asset_path: str, project_id: int) -> bool:
    """
    Delete a video only if it belongs to the specified project.

    Returns True if a file was deleted, False if it did not exist.
    """

    if not asset_path:
        return False

    project_dir = os.path.realpath(
        get_project_storage_path(project_id)
    )
    target_path = os.path.realpath(asset_path)

    try:
        if os.path.commonpath(
            [project_dir, target_path]
        ) != project_dir:
            raise ValueError("Asset path is outside project storage.")

    except ValueError:
        raise ValueError("Invalid asset path.")

    if not os.path.isfile(target_path):
        return False

    os.remove(target_path)
    return True


def download_video(url: str, project_id: int, scene_id: int) -> str:
    """
    Download a selected video using a stable scene ID filename.
    Returns the saved absolute file path.
    """

    if not url.startswith("https://cdn.pixabay.com/"):
        raise ValueError("Untrusted video download URL.")

    storage_root = get_project_storage_path(project_id)
    os.makedirs(storage_root, exist_ok=True)

    filename = f"scene_{scene_id}.mp4"
    file_path = os.path.join(storage_root, filename)
    temp_path = file_path + ".part"

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(10, 60)
        ) as response:

            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("video/"):
                raise ValueError("Downloaded resource is not a video.")

            with open(temp_path, "wb") as video_file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        video_file.write(chunk)

        if not os.path.isfile(temp_path) or os.path.getsize(temp_path) == 0:
            raise RuntimeError("Downloaded video is empty.")

        os.replace(temp_path, file_path)

    except Exception:
        for path in (temp_path,):
            if os.path.exists(path):
                os.remove(path)
        raise

    return file_path
