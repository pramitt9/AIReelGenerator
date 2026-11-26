
import os
import json
import secrets
from pathlib import Path

import streamlit as st

# Load Streamlit secrets before importing Flask configuration.
for key in [
    "SECRET_KEY",
    "OPENAI_API_KEY",
    "ELEVENLABS_API_KEY",
    "PIXABAY_API_KEY",
    "DATABASE_URL",
]:
    try:
        if key in st.secrets:
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass

if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = secrets.token_hex(32)

os.environ["FLASK_ENV"] = "production"

from app import create_app
from app.extensions import db
from app.models import User, Project
from app.services.ai.script_generator import generate_script
from app.services.generation.generation_pipeline import (
    generate_project_video,
)

st.set_page_config(
    page_title="VidSnapAI",
    page_icon="🎬",
    layout="wide",
)

@st.cache_resource
def initialize_app():
    flask_app = create_app()

    with flask_app.app_context():
        db.create_all()

        user = User.query.filter_by(
            email="demo@vidsnapai.app"
        ).first()

        if not user:
            user = User(
                username="VidSnapAI Demo",
                email="demo@vidsnapai.app",
            )
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)
            db.session.commit()

    return flask_app


try:
    flask_app = initialize_app()
except Exception as error:
    st.error(f"Application initialization failed: {error}")
    st.stop()


st.title("🎬 VidSnapAI")
st.subheader("Turn your ideas into engaging short-form videos.")
st.caption("AI-powered storyboarding, stock footage, narration and subtitles.")

with st.form("project_form"):
    title = st.text_input("Video title", placeholder="My first reel")
    topic = st.text_area(
        "What should your reel be about?",
        placeholder="Explain the topic or idea for your video...",
        height=120,
    )
    submitted = st.form_submit_button(
        "Generate storyboard",
        type="primary",
    )

if submitted:
    if not title.strip() or not topic.strip():
        st.warning("Please enter both a title and a topic.")
    else:
        with st.spinner("Creating your AI storyboard..."):
            try:
                with flask_app.app_context():
                    user = User.query.filter_by(
                        email="demo@vidsnapai.app"
                    ).first()

                    storyboard = generate_script(topic)

                    project = Project(
                        title=title.strip(),
                        topic=topic.strip(),
                        user_id=user.id,
                        script=json.dumps(storyboard),
                        status="draft",
                    )

                    db.session.add(project)
                    db.session.commit()

                    st.session_state.project_id = project.id
                    st.session_state.storyboard = storyboard

                st.success("Storyboard generated successfully!")

            except Exception as error:
                st.error(f"Storyboard generation failed: {error}")


if "storyboard" in st.session_state:
    storyboard = st.session_state.storyboard

    st.divider()
    st.header(storyboard["title"])

    st.markdown("### Opening hook")
    st.write(storyboard["hook"])

    st.markdown("### Scenes")

    for scene in storyboard["scenes"]:
        with st.expander(
            f"Scene {scene['scene_number']} · {scene['duration']} seconds"
        ):
            st.write("**Narration:**", scene["narration"])
            st.write("**Visual:**", scene["visual_description"])
            st.write("**Camera movement:**", scene["camera_motion"])

    st.markdown("### Ending")
    st.write(storyboard["ending"])

    if st.button("🎥 Generate final video", type="primary"):
        with st.spinner(
            "Generating footage, narration, subtitles and final video. "
            "Please keep this page open..."
        ):
            try:
                with flask_app.app_context():
                    result = generate_project_video(
                        st.session_state.project_id
                    )

                video_path = Path(result["output_video"])

                if not video_path.is_file():
                    raise FileNotFoundError("Generated video was not found.")

                video_bytes = video_path.read_bytes()

                st.session_state.video_bytes = video_bytes
                st.session_state.video_name = "vidsnapai_reel.mp4"

                st.success("Your video is ready!")

            except Exception as error:
                st.error(f"Video generation failed: {error}")


if "video_bytes" in st.session_state:
    st.divider()
    st.header("Your generated reel")
    st.video(st.session_state.video_bytes)

    st.download_button(
        "⬇️ Download MP4",
        data=st.session_state.video_bytes,
        file_name=st.session_state.video_name,
        mime="video/mp4",
        type="primary",
    )
