import os
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import psutil

from app import create_app
from app.extensions import db
from app.models import User, Project, GenerationJob
from app.services.generation.generation_pipeline import recover_stale_generation


app = create_app({
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False
})


def test_stale_generation_recovery():
    with TemporaryDirectory() as temp_dir:
        with app.app_context():
            db.create_all()

            try:
                user = User(
                    username="recovery_test",
                    email="recovery_test@example.com"
                )
                user.set_password("testpassword123")
                db.session.add(user)
                db.session.commit()

                # TEST 1: Dead worker with an existing successful video.
                print("\n===== TEST 1: PRESERVE PREVIOUS VIDEO =====")

                video_path = Path(temp_dir) / "previous_video.mp4"
                video_path.write_bytes(b"previous successful video")

                project = Project(
                    title="Recovery Test 1",
                    topic="Testing",
                    user_id=user.id,
                    status="processing"
                )
                db.session.add(project)
                db.session.commit()

                job = GenerationJob(
                    project_id=project.id,
                    status="completed",
                    output_video=str(video_path)
                )
                db.session.add(job)

                stale_job = GenerationJob(
                    project_id=project.id,
                    status="processing",
                    worker_pid=99999999,
                    worker_host=socket.gethostname(),
                    worker_create_time=12345.0
                )
                db.session.add(stale_job)
                db.session.commit()

                assert recover_stale_generation(project.id) is True

                db.session.expire_all()
                assert db.session.get(GenerationJob, stale_job.id).status == "failed"
                assert db.session.get(Project, project.id).status == "completed"
                assert video_path.is_file()

                print("Stale job marked failed.")
                print("Project restored to completed.")
                print("Previous video preserved.")

                # TEST 2: Dead worker without a previous successful video.
                print("\n===== TEST 2: NO PREVIOUS VIDEO =====")

                project2 = Project(
                    title="Recovery Test 2",
                    topic="Testing",
                    user_id=user.id,
                    status="processing"
                )
                db.session.add(project2)
                db.session.commit()

                stale_job2 = GenerationJob(
                    project_id=project2.id,
                    status="processing",
                    worker_pid=99999999,
                    worker_host=socket.gethostname(),
                    worker_create_time=12345.0
                )
                db.session.add(stale_job2)
                db.session.commit()

                assert recover_stale_generation(project2.id) is True

                db.session.expire_all()
                assert db.session.get(GenerationJob, stale_job2.id).status == "failed"
                assert db.session.get(Project, project2.id).status == "failed"

                print("Stale job marked failed.")
                print("Project correctly marked failed.")

                # TEST 3: A live worker must never be recovered.
                print("\n===== TEST 3: LIVE WORKER PROTECTION =====")

                project3 = Project(
                    title="Recovery Test 3",
                    topic="Testing",
                    user_id=user.id,
                    status="processing"
                )
                db.session.add(project3)
                db.session.commit()

                current_process = psutil.Process(os.getpid())

                live_job = GenerationJob(
                    project_id=project3.id,
                    status="processing",
                    worker_pid=os.getpid(),
                    worker_host=socket.gethostname(),
                    worker_create_time=current_process.create_time()
                )
                db.session.add(live_job)
                db.session.commit()

                assert recover_stale_generation(project3.id) is False

                db.session.expire_all()
                assert db.session.get(GenerationJob, live_job.id).status == "processing"
                assert db.session.get(Project, project3.id).status == "processing"

                print("Live job was not recovered.")
                print("Project remains processing.")

                print("\nALL STALE GENERATION RECOVERY TESTS PASSED!")

            finally:
                db.session.rollback()
                db.drop_all()
                db.session.remove()

