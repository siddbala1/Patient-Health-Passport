import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

PORT = int(os.getenv("PORT", 3000))

# Register routes
from routes.auth import auth_bp
from routes.records import records_bp
from routes.notes import notes_bp
app.register_blueprint(auth_bp)
app.register_blueprint(records_bp)
app.register_blueprint(notes_bp)

# Basic health check endpoint
@app.route("/health")
def health():
    return jsonify({
        "status": "running",
        "message": "Health Passport HIN Backend is live"
    })

# Start server
if __name__ == "__main__":
    print(f"Health Passport backend running on http://localhost:{PORT}")
    app.run(port=PORT, debug=True)