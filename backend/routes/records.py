from flask import Blueprint
from controllers.records_controller import add_record, edit_record, remove_record

records_bp = Blueprint("records", __name__)

records_bp.route("/session/<session_id>/<table>", methods=["POST"])(add_record)
records_bp.route("/session/<session_id>/<table>/<int:row_id>", methods=["PUT"])(edit_record)
records_bp.route("/session/<session_id>/<table>/<int:row_id>", methods=["DELETE"])(remove_record)
