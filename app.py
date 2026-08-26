import os

from dotenv import load_dotenv
from flask import Flask, render_template

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev")

    from routes.detection import detection_bp
    from routes.evidence import evidence_bp
    from routes.analysis import analysis_bp
    from routes.result import result_bp

    app.register_blueprint(detection_bp)
    app.register_blueprint(evidence_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(result_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
