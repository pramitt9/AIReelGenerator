import json
import math

from openai import OpenAI
from flask import current_app


ALLOWED_MOTIONS = {"none", "zoom_in", "zoom_out", "pan"}
ALLOWED_VISUAL_TYPES = {"stock_video", "ai_generated"}


def _required_text(value, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Generated storyboard has an invalid '{field_name}'.")
    return value.strip()


def _validate_storyboard(result: dict) -> dict:
    """Validate and normalize the structured storyboard returned by the model."""

    if not isinstance(result, dict):
        raise ValueError("AI returned a storyboard that is not a JSON object.")

    result["title"] = _required_text(result.get("title"), "title")
    result["hook"] = _required_text(result.get("hook"), "hook")
    result["ending"] = _required_text(result.get("ending"), "ending")

    scenes = result.get("scenes")
    if not isinstance(scenes, list) or not 5 <= len(scenes) <= 8:
        raise ValueError("Generated storyboard must contain between 5 and 8 scenes.")

    normalized_scenes = []
    seen_numbers = set()

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} must be a JSON object.")

        narration = _required_text(scene.get("narration"), f"scene {index} narration")
        visual_description = _required_text(
            scene.get("visual_description"),
            f"scene {index} visual_description"
        )

        scene_number = scene.get("scene_number", index)
        if isinstance(scene_number, bool) or not isinstance(scene_number, int):
            raise ValueError(f"Scene {index} has an invalid scene_number.")
        if scene_number in seen_numbers:
            raise ValueError(f"Duplicate scene_number: {scene_number}.")
        seen_numbers.add(scene_number)

        duration = scene.get("duration")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValueError(f"Scene {index} has an invalid duration.")
        duration = float(duration)
        if not math.isfinite(duration) or not 3 <= duration <= 8:
            raise ValueError(f"Scene {index} duration must be between 3 and 8 seconds.")

        visual_type = scene.get("visual_type", "stock_video")
        if visual_type not in ALLOWED_VISUAL_TYPES:
            raise ValueError(
                f"Scene {index} has unsupported visual_type: {visual_type!r}."
            )

        camera_motion = scene.get("camera_motion", "none")
        if camera_motion not in ALLOWED_MOTIONS:
            camera_motion = "none"

        normalized_scenes.append({
            **scene,
            "scene_number": scene_number,
            "narration": narration,
            "visual_description": visual_description,
            "visual_type": visual_type,
            "duration": duration,
            "camera_motion": camera_motion,
        })

    normalized_scenes.sort(key=lambda item: item["scene_number"])
    expected_numbers = list(range(1, len(normalized_scenes) + 1))
    actual_numbers = [scene["scene_number"] for scene in normalized_scenes]
    if actual_numbers != expected_numbers:
        raise ValueError("Scene numbers must be consecutive, starting at 1.")

    result["scenes"] = normalized_scenes
    return result


def generate_script(topic: str) -> dict:
    """
    Generate and validate a structured reel script and scene-by-scene storyboard.
    """

    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("A non-empty topic is required.")

    topic = topic.strip()
    if len(topic) > 500:
        raise ValueError("Topic must be 500 characters or fewer.")

    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key is not configured.")

    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=2)

    system_prompt = """
You are an expert short-form video scriptwriter and creative director.

Create engaging, visually interesting scripts for Instagram Reels and YouTube Shorts.
Return only a valid JSON object with this exact structure:
{
  "title": "Video title",
  "hook": "Attention-grabbing opening",
  "scenes": [
    {
      "scene_number": 1,
      "narration": "What the narrator says",
      "visual_description": "Detailed, specific, searchable visual description",
      "visual_type": "stock_video",
      "duration": 5,
      "camera_motion": "zoom_in"
    }
  ],
  "ending": "Closing narration"
}

Requirements:
- Create 5 to 8 scenes, numbered consecutively from 1.
- Total narration should be approximately 100-150 words.
- Each scene must last between 3 and 8 seconds.
- Every scene needs non-empty narration and a specific visual_description.
- Use stock_video as the default visual_type.
- Use ai_generated only when a suitable real-world visual is unlikely.
- Use only these visual_type values: stock_video, ai_generated.
- Assign exactly one camera_motion to every scene.
- Allowed camera_motion values: none, zoom_in, zoom_out, pan.
- Use zoom_in for dramatic reveals, zoom_out for establishing shots,
  pan for landscapes and wide scenes, and none for fast action.
- Vary camera movement naturally rather than repeating it in every scene.
- Ensure narration flows naturally from the hook through the ending.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Create a short-form video script about: {topic}"
            }
        ],
        temperature=0.8,
        max_tokens=1800,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("AI returned an empty response.")

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("AI returned invalid JSON.") from exc

    return _validate_storyboard(result)
