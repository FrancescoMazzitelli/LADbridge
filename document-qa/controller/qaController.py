from flask import request, jsonify
import requests as http
from flask_restx import Namespace, Resource, reqparse, fields
from werkzeug.datastructures import FileStorage
from service.qaService import Qa
from service.knowledgeBase import MyKnowledgeBase as kb
import os
import json
import time

api = Namespace(
    "qa",
    description="""
    Service for question-answering based on documents stored in a knowledge base.
    If needed, it is possible to upload additional documents and expand the knowledge of the conversational agent.
    """
    )

file_upload_parser = api.parser()
file_upload_parser.add_argument(
    'file',
    location='files',
    type=FileStorage,
    required=True,
    help='File to upload (PDF)'
)

CategorySchema = api.model(
    "CategorySchema",
    {
        "input": fields.String(required=True, description="The input text/question")
    }
)

SERVICE_ID = os.environ.get("SERVICE_ID", 0)
SERVICE_HOST = os.environ.get("SERVICE_HOST", "localhost")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", 5600))
GATEWAY_HOST = os.environ.get("GATEWAY_HOST", "localhost")
GATEWAY_PORT = os.environ.get("GATEWAY_PORT", 5000)
CONSUL_HOST = os.environ.get("CONSUL_HOST", "localhost")
CONSUL_PORT = os.environ.get("CONSUL_PORT", 8500)

qa = Qa()

@api.route("/invoke")
class ConversationalAgent(Resource):
    @api.expect(CategorySchema)
    @api.doc(summary="", description="""
    Given a question, this endpoint returns an answer based on contents of
    documents chunks embeddings stored in the knowledge base.
    """)
    def post(self):
        data = request.get_json(force=True)

        if isinstance(data, str):
            user_input = {"input": data}
        else:
            user_input = data.get('input', data)
        
        if not user_input:
            return {"error": "Missing input"}, 400
        
        results = qa.invoke(user_input)
        return jsonify({"response": results})

@api.route("/upload")
class DocumentUploader(Resource):
    @api.expect(file_upload_parser)
    @api.doc(summary="", description="""
    Upload a document, parse it, perform a paragraph-based chunking, embed the 
    chunks, and store them in the knowledge base.
    """)
    def post(self):
        uploaded_file = request.files.get('file')
        if not uploaded_file:
            return {"error": "File not provided"}, 400

        os.makedirs("Documents", exist_ok=True)
        save_path = os.path.join("Documents", uploaded_file.filename)
        uploaded_file.save(save_path)
        flag = qa.update_kb()

        time.sleep(10)
        
        if flag is True:
            return {"message": f"Document saved to {save_path}"}, 200
        else:
            return {"message": f"Document not processed"}, 500

@api.route("/register")
class Registration(Resource):
    @api.doc(summary="", description="Register the service to the registry for discovery (catalog + consul).")
    def post(self):
        swagger_url = f"http://{SERVICE_HOST}:{SERVICE_PORT}/swagger.json"
        try:
            spec = http.get(swagger_url).json()
        except Exception as e:
            return {"error": f"Cannot fetch swagger spec: {str(e)}"}, 500

        service_name = spec.get("info", {}).get("title", "unknown-service")
        service_id = SERVICE_ID
        description = spec.get("info", {}).get("description", "No description")
        paths = spec.get("paths", {})

        host_url = f"{SERVICE_HOST}:{SERVICE_PORT}"
        base_path = spec.get("basePath", "")

        capabilities = {}
        endpoints = {}
        for path, methods in paths.items():
            for method, details in methods.items():
                endpoint_key = f"{method.upper()} {path}"
                desc = details.get("description") or details.get("summary") or details.get("operationId") or method
                capabilities[endpoint_key] = desc
                endpoints[endpoint_key] = f"http://{host_url}{path}"

        catalog_payload = {
            "id": service_id,
            "name": service_name,
            "description": description,
            "capabilities": capabilities,
            "endpoints": endpoints
        }

        consul_payload = {
            "Name": service_name,
            "Id": service_id,
            "Meta": {
                "service_doc_id": service_id
            },
            "Check": {
                "TlsSkipVerify": True,
                "Method": "GET",
                "Http": f"http://{SERVICE_HOST}:{SERVICE_PORT}/api/qa/health",
                "Interval": "10s",
                "Timeout": "5s",
                "DeregisterCriticalServiceAfter": "30s"
            }
        }

        try:
            consul_response = http.put(
                f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/agent/service/register",
                json=consul_payload
            )
        except Exception as e:
            return {"error": f"Cannot register service on Consul: {str(e)}"}, 500

        try:
            gateway_response = http.post(
                f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/service",
                json=catalog_payload
            )
        except Exception as e:
            return {"error": f"Cannot register service on Gateway: {str(e)}"}, 500

        return {
            "status": "success",
            "consul_code": consul_response.status_code,
            "gateway_code": gateway_response.status_code,
            "catalog_payload": catalog_payload
        }


@api.route("/health")
class Healthcheck(Resource):
    @api.doc(summary="Health check", description="Return HTTP 200 if the service is running")
    def get(self):
        return {}, 200
