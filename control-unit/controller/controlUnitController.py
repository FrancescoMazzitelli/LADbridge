from flask import request, jsonify, Response
from extras.flask_restx import Namespace, Resource, reqparse, inputs
from werkzeug.datastructures import FileStorage, ImmutableDict
from service.controlService import Controller
import json
import uuid
import os

api = Namespace("control", description="Services management and orchestration")

control_parser = api.parser()

control_parser.add_argument(
    'file',
    location='files',
    type=FileStorage,
    required=False,
    action='append',
    help='Files to upload'
)

control_parser.add_argument(
    'input',
    type=str,
    location='form',
    required=True,
    help='User input text'
)

@api.route("/invoke")
class ConversationalAgent(Resource):
    @api.expect(control_parser)
    def post(self):
        args = control_parser.parse_args()
        user_input = args['input']
        file_input = args['file']

        controller = Controller()
        results = controller.control(user_input, file_input)

        if not isinstance(results, Response):
            return jsonify(results)

        pdf_bytes = results.get_data()
        content_disposition = results.headers.get(
            "Content-Disposition",
            'attachment; filename="output.pdf"'
        )

        execution_results_sanitized = self.sanitize_execution_results(controller.execution_results)

        execution_metadata = {
            "execution_plan": getattr(controller, "execution_plan", None),
            "execution_results": execution_results_sanitized,
            "note": "PDF generated successfully"
        }

        response = Response(
            pdf_bytes,
            status=200,
            mimetype="application/pdf"
        )

        response.headers["Content-Disposition"] = content_disposition
        response.headers["X-Execution-Metadata"] = json.dumps(execution_metadata)

        return response

    def sanitize_execution_results(self, results):
        if isinstance(results, list):
            sanitized = []
            for r in results:
                if isinstance(r, dict):
                    r_copy = r.copy()
                    if r_copy.get("status") == "FILE" and "body" in r_copy:
                        r_copy["body"] = f"<{len(r_copy['body'])} bytes>"
                    sanitized.append(r_copy)
                else:
                    sanitized.append(r)
            return sanitized
        elif isinstance(results, dict):
            r_copy = results.copy()
            if r_copy.get("status") == "FILE" and "body" in r_copy:
                r_copy["body"] = f"<{len(r_copy['body'])} bytes>"
            return r_copy
        return results
