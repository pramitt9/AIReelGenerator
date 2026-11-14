# VidSnapAI

VidSnapAI is an AI-powered short-form video generation application built with Python and Flask.

## Features
- User registration, login, and session management.
- Project creation, editing, and deletion.
- AI storyboard generation using OpenAI.
- Editing hooks, endings, narration, and scenes.
- Adding, deleting, and reordering scenes.
- Stock footage search using Pixabay.
- Narration generation using ElevenLabs.
- Subtitle generation using faster-whisper.
- Video processing and rendering using FFmpeg.
- Preview and download completed MP4 videos.
- Generation job tracking and stale-job recovery.

## Technology Stack
- Python 3.13
- Flask and Flask-SQLAlchemy
- SQLAlchemy and SQLite
- Flask-Login
- OpenAI API
- ElevenLabs API
- Pixabay API
- faster-whisper
- FFmpeg and FFprobe

## Installation

1. Clone the repository:
   `git clone -b v2-refactor https://github.com/pramitt9/AIReelGenerator.git`

2. Enter the project directory:
   `cd AIReelGenerator`

3. Create a virtual environment:
   `py -3.13 -m venv .venv`

4. Install dependencies:
   `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`

5. Copy the example environment file:
   `Copy-Item .env.example .env`

6. Add your API keys and a secure SECRET_KEY to `.env`.

7. Install FFmpeg and FFprobe and ensure they are available on PATH.

8. Start the application:
   `.\.venv\Scripts\python.exe run.py`

## Application Workflow

1. Register or log in.
2. Create a project using a topic.
3. Generate an AI storyboard.
4. Review and edit the storyboard.
5. Generate the video.
6. Preview or download the completed MP4.

## Environment Variables

- SECRET_KEY: Flask session security.
- FLASK_ENV: Application environment.
- FLASK_DEBUG: Debug mode.
- OPENAI_API_KEY: AI storyboard generation.
- ELEVENLABS_API_KEY: Narration generation.
- PIXABAY_API_KEY: Stock footage search.
- DATABASE_URL: Optional database connection string.

SQLite is used by default.

## Notes

- API usage may incur provider costs.
- FFmpeg is an external system dependency.
- Generated videos, uploads, databases, and environment files are excluded from version control.
- Video generation currently runs inside the Flask request. This is intended for local development and demonstration, not high-concurrency production deployment.

## License

Add a license before distributing this project publicly.
