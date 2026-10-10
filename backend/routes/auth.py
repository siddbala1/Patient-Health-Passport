from flask import Blueprint
from controllers.auth_controller import redirect_to_login, handle_callback, get_session
auth_bp = Blueprint("auth", __name__)

auth_bp.route("/connect")(redirect_to_login)
auth_bp.route("/callback")(handle_callback)
auth_bp.route("/session/<session_id>")(get_session)
