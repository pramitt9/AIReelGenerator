
import os
import json
import secrets
from pathlib import Path

import streamlit as st

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="VidSnapAI | AI Video Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------
# SECRETS
# --------------------------------------------------

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

os.environ["FLASK_ENV"] = "production"

# --------------------------------------------------
# CUSTOM DESIGN SYSTEM
# --------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --bg: #09090f;
    --panel: #11111b;
    --panel2: #171725;
    --border: #29293b;
    --text: #f5f3ff;
    --muted: #9695aa;
    --purple: #9875ff;
    --pink: #d879ff;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: #0d0d16;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 2rem;
}

h1, h2, h3 {
    font-family: 'Space Grotesk', sans-serif !important;
    color: var(--text) !important;
}

p, label, span {
    font-family: 'DM Sans', sans-serif;
}

.hero {
    padding: 36px 38px;
    border-radius: 22px;
    background:
        radial-gradient(ellipse at 90% 10%, #6242a044, transparent 45%),
        linear-gradient(120deg, #19152b, #11111b 70%);
    border: 1px solid #40345f;
    margin-bottom: 28px;
}

.hero-tag {
    color: #c1a9ff;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-size: 11px;
    font-weight: 700;
}

.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(32px, 4vw, 48px);
    line-height: 1.15;
    font-weight: 700;
    margin: 14px 0;
    color: white;
}

.hero-description {
    color: #aaa6c0;
    font-size: 15px;
    max-width: 570px;
    line-height: 1.7;
}

.section-label {
    color: #bba5ff;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 18px;
}

.scene-card {
    background: linear-gradient(135deg, #171725, #11111b);
    border: 1px solid #303047;
    border-radius: 14px;
    padding: 19px 21px;
    margin-bottom: 12px;
}

.scene-number {
    color: #b99fff;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
}

.scene-heading {
    color: white;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 18px;
    font-weight: 600;
    margin: 8px 0;
}

.scene-description {
    color: #aaa8bc;
    font-size: 13px;
    line-height: 1.6;
}

.metric {
    background: #151522;
    border: 1px solid var(--border);
    padding: 17px;
    border-radius: 13px;
}

.metric-value {
    color: white;
    font-size: 25px;
    font-weight: 700;
    font-family: 'Space Grotesk', sans-serif;
}

.metric-label {
    color: var(--muted);
    font-size: 12px;
    margin-top: 4px;
}

div.stButton > button,
div.stFormSubmitButton > button {
    background: linear-gradient(110deg, #7855eb, #a06aff);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 11px 20px;
    font-weight: 700;
    transition: 0.2s ease;
}

div.stButton > button:hover,
div.stFormSubmitButton > button:hover {
    border: 1px solid #c5aaff;
    box-shadow: 0 0 22px #9875ff44;
    color: white;
}

div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
    background: #171725;
    color: white;
    border-color: #34344a;
    border-radius: 9px;
}

div[data-baseweb="select"] > div {
    background: #171725;
    border-color: #34344a;
}

[data-testid="stExpander"] {
    background: #151522;
    border: 1px solid var(--border);
    border-radius: 12px;
}

hr {
    border-color: var(--border);
}

footer {
    visibility: hidden;
}

#MainMenu {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# FLASK BACKEND
# --------------------------------------------------

from app import create_app
from app.extensions import db
from app.models import User, Project
from app.services.ai.script_generator import generate_script
from app.services.generation.generation_pipeline import (
    generate_project_video,
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
    st.error(f"Backend initialization failed: {error}")
    st.stop()


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "page" not in st.session_state:
    st.session_state.page = "Create"

if "project_id" not in st.session_state:
    st.session_state.project_id = None

if "storyboard" not in st.session_state:
    st.session_state.storyboard = None

if "video_bytes" not in st.session_state:
    st.session_state.video_bytes = None


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div style="padding: 0 5px 25px 5px;">
        <div style="font-size:29px;font-weight:800;color:white;
                    font-family:'Space Grotesk',sans-serif;">
            🎬 VidSnap<span style="color:#a98aff;">AI</span>
        </div>
        <div style="font-size:11px;color:#85839b;
                    letter-spacing:1.5px;margin-top:5px;">
            AI VIDEO PRODUCTION STUDIO
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-label">WORKSPACE</div>',
                unsafe_allow_html=True)

    if st.button("✦  Create a video", use_container_width=True):
        st.session_state.page = "Create"

    if st.button("▤  Storyboard", use_container_width=True):
        st.session_state.page = "Storyboard"

    if st.button("▶  Final video", use_container_width=True):
        st.session_state.page = "Video"

    st.divider()

    st.markdown("""
    <div style="padding:12px;color:#85839b;font-size:12px;">
        <b style="color:#c1a9ff;">VIDSNAPAI V2</b><br><br>
        Powered by OpenAI, Pixabay,<br>
        ElevenLabs and FFmpeg.
    </div>
    """, unsafe_allow_html=True)


# --------------------------------------------------
# TOP HEADER
# --------------------------------------------------

st.markdown("""
<div style="display:flex;justify-content:space-between;
            align-items:center;margin-bottom:25px;">
    <div>
        <div style="color:#8e8ba4;font-size:12px;
                    letter-spacing:1.5px;">YOUR CREATIVE WORKSPACE</div>
        <div style="font-size:14px;color:#d9d5e8;margin-top:5px;">
            Welcome to VidSnapAI
        </div>
    </div>
    <div style="background:#171725;border:1px solid #34344a;
                padding:8px 14px;border-radius:20px;
                font-size:11px;color:#c4afff;">
        ● SYSTEM ONLINE
    </div>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# CREATE PAGE
# --------------------------------------------------

if st.session_state.page == "Create":

    st.markdown("""
    <div class="hero">
        <div class="hero-tag">✦ AI-powered video creation</div>
        <div class="hero-title">
            Your next big idea.<br>
            <span style="color:#b79aff;">One reel away.</span>
        </div>
        <div class="hero-description">
            Turn a simple idea into a cinematic short-form video.
            Generate scripts, discover visuals, create narration
            and produce your final reel.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-label">01 / START CREATING</div>',
                unsafe_allow_html=True)
    st.header("What are we making today?")
    st.caption("Describe your idea. Let AI take care of the creative heavy lifting.")

    with st.form("project_form"):

        title = st.text_input(
            "PROJECT TITLE",
            placeholder="e.g. The Mystery of Black Holes",
        )

        topic = st.text_area(
            "YOUR VIDEO IDEA",
            placeholder=(
                "Describe the topic, story or concept you want "
                "to turn into a reel..."
            ),
            height=140,
        )

        st.markdown(
            "<div style='color:#85839b;font-size:11px;'>"
            "AI will create a storyboard with 5–8 scenes, "
            "narration and visual descriptions."
            "</div>",
            unsafe_allow_html=True,
        )

        submitted = st.form_submit_button(
            "✦  Generate my storyboard",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        if not title.strip() or not topic.strip():
            st.warning("Please enter a project title and video idea.")

        elif len(title.strip()) > 150:
            st.warning("Project title must be 150 characters or fewer.")

        elif len(topic.strip()) > 255:
            st.warning("Please shorten your topic to 255 characters or fewer.")

        else:
            with st.spinner("Creating your storyboard with AI..."):

                try:
                    with flask_app.app_context():

                        user = User.query.filter_by(
                            email="demo@vidsnapai.app"
                        ).first()

                        storyboard = generate_script(topic.strip())

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
                        st.session_state.video_bytes = None
                        st.session_state.page = "Storyboard"

                    st.success("Your storyboard is ready!")
                    st.rerun()

                except Exception as error:
                    st.error(f"Storyboard generation failed: {error}")


# --------------------------------------------------
# STORYBOARD PAGE
# --------------------------------------------------

if st.session_state.page == "Storyboard":

    storyboard = st.session_state.storyboard

    if not storyboard:
        st.info("Create a video first to see your storyboard.")
        if st.button("Create a video"):
            st.session_state.page = "Create"
            st.rerun()

    else:
        st.markdown(
            '<div class="section-label">02 / CREATIVE BLUEPRINT</div>',
            unsafe_allow_html=True,
        )

        st.title(storyboard["title"])
        st.caption("Your AI-generated storyboard is ready for production.")

        scenes = storyboard["scenes"]
        total_duration = sum(scene["duration"] for scene in scenes)

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown(
                f'<div class="metric"><div class="metric-value">'
                f'{len(scenes)}</div><div class="metric-label">'
                f'TOTAL SCENES</div></div>',
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(
                f'<div class="metric"><div class="metric-value">'
                f'{total_duration:.0f}s</div><div class="metric-label">'
                f'ESTIMATED SCENE DURATION</div></div>',
                unsafe_allow_html=True,
            )

        with c3:
            st.markdown(
                '<div class="metric"><div class="metric-value">'
                '9:16</div><div class="metric-label">'
                'VERTICAL VIDEO FORMAT</div></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        st.markdown("### Opening hook")

        st.markdown(
            f'<div class="panel" style="border-left:3px solid #a98aff;">'
            f'<div style="font-size:16px;color:white;">'
            f'{storyboard["hook"]}</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown("### Scene breakdown")

        for scene in scenes:

            with st.container():
                st.markdown(
                    f"""
                    <div class="scene-card">
                        <div class="scene-number">
                            SCENE {scene["scene_number"]:02d}
                            &nbsp; • &nbsp;
                            {scene["duration"]} SECONDS
                        </div>
                        <div class="scene-heading">
                            {scene["visual_description"]}
                        </div>
                        <div class="scene-description">
                            {scene["narration"]}
                        </div>
                        <div style="margin-top:12px;font-size:11px;
                                    color:#a88cff;">
                            CAMERA: {scene["camera_motion"].upper()}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("### Closing narration")

        st.markdown(
            f'<div class="panel">{storyboard["ending"]}</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        left, right = st.columns([1, 1])

        with left:
            if st.button("← Create another project", use_container_width=True):
                st.session_state.page = "Create"
                st.rerun()

        with right:
            if st.button(
                "▶  Generate final video",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.page = "Video"
                st.rerun()


# --------------------------------------------------
# VIDEO GENERATION PAGE
# --------------------------------------------------

if st.session_state.page == "Video":

    st.markdown(
        '<div class="section-label">03 / VIDEO PRODUCTION</div>',
        unsafe_allow_html=True,
    )

    st.title("Bring your story to life.")
    st.caption(
        "Your scenes, footage, narration and subtitles "
        "will be combined into a final MP4."
    )

    if not st.session_state.storyboard:
        st.info("Create a storyboard before generating a video.")

        if st.button("Create a video"):
            st.session_state.page = "Create"
            st.rerun()

    elif "video_bytes" not in st.session_state or st.session_state.video_bytes is None:

        st.markdown("""
        <div class="panel">
            <div style="font-size:20px;font-weight:700;color:white;">
                Ready for production
            </div>
            <div style="color:#9996ad;font-size:13px;margin-top:8px;">
                VidSnapAI will now retrieve footage, generate narration,
                transcribe the audio and render your final video.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "🎬  Start video production",
            type="primary",
            use_container_width=True,
        ):

            try:
                with st.status(
                    "Producing your video...",
                    expanded=True,
                ) as status:

                    st.write("Processing your storyboard and footage...")
                    st.write("Generating AI narration...")
                    st.write("Preparing subtitle transcription...")
                    st.write("Rendering the final video...")

                    with flask_app.app_context():
                        result = generate_project_video(
                            st.session_state.project_id
                        )

                    video_path = Path(result["output_video"])

                    if not video_path.is_file():
                        raise FileNotFoundError(
                            "The final video file was not found."
                        )

                    st.session_state.video_bytes = video_path.read_bytes()
                    st.session_state.video_name = "vidsnapai_reel.mp4"

                    status.update(
                        label="Video production completed!",
                        state="complete",
                        expanded=False,
                    )

                st.rerun()

            except Exception as error:
                st.error(f"Video generation failed: {error}")

    if st.session_state.video_bytes is not None:

        st.markdown("### Your finished reel")

        st.video(st.session_state.video_bytes)

        st.download_button(
            "⬇  Download your MP4",
            data=st.session_state.video_bytes,
            file_name=st.session_state.video_name,
            mime="video/mp4",
            type="primary",
            use_container_width=True,
        )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.markdown("""
<div style="text-align:center;padding:40px 0 15px 0;
            color:#656379;font-size:11px;">
    VID SNAP AI &nbsp; • &nbsp; BUILT FOR CREATORS
    <br><br>
    Powered by AI. Made for stories.
</div>
""", unsafe_allow_html=True)
