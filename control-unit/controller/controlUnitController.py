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

        execution_metadata = {
            "execution_plan": getattr(controller, "last_execution_plan", None),
            "execution_results": getattr(controller, "last_execution_results", None),
            "note": "PDF generated successfully"
        }

        boundary = f"BOUNDARY_{uuid.uuid4().hex}"

        json_part = (
            f"--{boundary}\r\n"
            "Content-Type: application/json\r\n\r\n"
            f"{json.dumps(execution_metadata)}\r\n"
        ).encode("utf-8")

        file_part = (
            f"--{boundary}\r\n"
            "Content-Type: application/pdf\r\n"
            f"Content-Disposition: {content_disposition}\r\n\r\n"
        ).encode("utf-8") + pdf_bytes + b"\r\n"

        closing = f"--{boundary}--".encode("utf-8")

        body = json_part + file_part + closing

        return Response(
            body,
            status=200,
            headers={
                "Content-Type": f"multipart/mixed; boundary={boundary}"
            }
        )
