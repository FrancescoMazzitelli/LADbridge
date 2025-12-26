from flask import request, jsonify
from extras.flask_restx import Namespace, Resource, reqparse, inputs
from werkzeug.datastructures import FileStorage, ImmutableDict
from service.controlService import Controller
import json

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
        data = args['input']
        file_input = args['file']
        json_input = json.loads(data)
        print(f"String input: {json_input['input']}")
        print(f"File ricevuti: {file_input}")

        #controller = Controller()
        #results = controller.control(user_input, file_input)

        return jsonify("results")
