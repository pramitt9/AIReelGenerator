
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db


app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("scenes")
    }

    if "camera_motion" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE scenes "
                "ADD COLUMN camera_motion "
                "VARCHAR(20) NOT NULL DEFAULT 'none'"
            )
        )
        db.session.commit()
        print("Added camera_motion column.")
    else:
        print("camera_motion column already exists.")
