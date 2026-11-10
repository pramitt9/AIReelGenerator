from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()

    user = User(
        username="testuser",
        email="test@example.com"
    )

    user.set_password("testpassword123")

    db.session.add(user)
    db.session.commit()

    saved_user = User.query.filter_by(
        email="test@example.com"
    ).first()

    print("User:", saved_user)
    print("Correct password:", saved_user.check_password("testpassword123"))
    print("Wrong password:", saved_user.check_password("wrongpassword"))