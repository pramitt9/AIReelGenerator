from flask import Blueprint

main = Blueprint("main",__name__)

@main.route("/")
def home():
    return "Reel Generator V2 is running"