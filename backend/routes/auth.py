from flask import Blueprint
from controllers.auth_controller import redirect_to_login, handle_callback, query_local_fhir

auth_bp = Blueprint("auth", __name__)

# Route 1: Patient initiates connection to a hospital
auth_bp.route("/connect")(redirect_to_login)

# Route 2: Hospital redirects patient back after login
auth_bp.route("/callback")(handle_callback)

# Route 3: Query local HAPI FHIR server directly
auth_bp.route("/local")(query_local_fhir)