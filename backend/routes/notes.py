from flask import Blueprint
from controllers.notes_controller import get_notes

notes_bp = Blueprint("notes", __name__)

notes_bp.route("/session/<session_id>/notes", methods=["GET"])(get_notes)
