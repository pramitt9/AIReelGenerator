
import json
from openai import OpenAI
from flask import current_app


def generate_script(topic: str) -> dict:
    """
    Generate a structured reel script and scene-by-scene storyboard.
    """

    api_key = current_app.config.get("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OpenAI API key is not configured.")

    client = OpenAI(api_key=api_key)

    system_prompt = """
    You are an expert short-form video scriptwriter and creative director.

    Create engaging, visually interesting scripts for Instagram Reels
    and YouTube Shorts.

    Return ONLY valid JSON with this structure:

    {
        "title": "Video title",
        "hook": "Attention-grabbing opening",
        "scenes": [
            {
                "scene_number": 1,
                "narration": "What the narrator says",
                "visual_description": "Detailed description of what viewers should see",
                "visual_type": "stock_video",
                "duration": 5
            }
        ],
        "ending": "Closing narration"
    }

    Requirements:
    - Create 5-8 scenes.
    - Total narration should be approximately 100-150 words.
    - Each scene should last 3-8 seconds.
    - Visual descriptions must be specific and searchable.
    - Use stock_video as the default visual_type.
    - Use ai_generated only when a suitable real-world visual is unlikely.
    - Make the opening hook compelling.
    - Ensure narration flows naturally between scenes.
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

    if not isinstance(result.get("scenes"), list) or not result["scenes"]:
        raise ValueError("Generated storyboard contains no scenes.")

    return result
