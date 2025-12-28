import os
import pandas as pd
import requests
from flask import request, jsonify, send_file
from flask_restx import Namespace, Resource, reqparse
import json
import shutil

from service.splitterService import SplitterService
from service.composerService import ComposerService

api = Namespace("filler", description="Document filling operations")

file_upload_parser = api.parser()
file_upload_parser.add_argument(
    'file', 
    location='files',
    type='FileStorage', 
    required=True, 
    help='File to upload (PDF)'
)

SERVICE_ID = os.environ.get("SERVICE_ID", 0)
SERVICE_HOST = os.environ.get("SERVICE_HOST", "localhost")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", 5700))
GATEWAY_HOST = os.environ.get("GATEWAY_HOST", "localhost")
GATEWAY_PORT = os.environ.get("GATEWAY_PORT", 5000)
CONSUL_HOST = os.environ.get("CONSUL_HOST", "localhost")
CONSUL_PORT = os.environ.get("CONSUL_PORT", 8500)

model_name = "phi4-reasoning:14b"
datadoc = None
tofilldoc = None

@api.route('/convert')
class ConvertDocs(Resource):
    @api.expect(file_upload_parser)
    def post(self):
        toConvert = request.files.get('file')

        if not toConvert:
            return {"error": "File not provided"}, 400

        os.makedirs("uploads", exist_ok=True)
        save_path = os.path.join("uploads", toConvert.filename)
        toConvert.save(save_path)

        service = SplitterService()
        output_path = service.generate_fields(f"uploads/{toConvert.filename}", "converted.pdf")
        return {"message": f"Output file path: {output_path}"}, 200


@api.route('/datadoc')
class DataDocument(Resource):
    @api.expect(file_upload_parser)
    def post(self):
        """Data document upload endpoint."""
        global datadoc
        uploaded_file = request.files.get('file')

        if not uploaded_file:
            return {"error": "File not provided"}, 400

        os.makedirs("uploads", exist_ok=True)
        save_path = os.path.join("uploads", uploaded_file.filename)
        uploaded_file.save(save_path)

        datadoc = save_path
        return {"message": f"Document containing data set to {datadoc}"}, 200


@api.route('/tofilldoc')
class FillDocument(Resource):
    @api.expect(file_upload_parser)
    def post(self):
        """Document to fill upload endpoint."""
        global tofilldoc
        uploaded_file = request.files.get('file')

        if not uploaded_file:
            return {"error": "File not provided"}, 400

        os.makedirs("uploads", exist_ok=True)
        save_path = os.path.join("uploads", uploaded_file.filename)
        uploaded_file.save(save_path)

        tofilldoc = save_path
        return {"message": f"Document to fill set to {tofilldoc}"}, 200


@api.route('/fill')
class Fill(Resource):
    def post(self):
        """Fill the document using the provided data and return the filled PDF."""
        global datadoc, tofilldoc

        if not datadoc or not tofilldoc:
            return {"error": "Both datadoc and tofilldoc must be uploaded first."}, 400

        splitter = SplitterService()
        composer = ComposerService()
        filleddoc = f"{tofilldoc}_FILLED.pdf"
        iter_counter = 0

        data_df = pd.read_csv(datadoc)
        information = data_df.to_string()

        tofilldoc, fields = splitter.split(tofilldoc)
        populated_chunks = []

        for field in fields:
            prompt = f"""
            <|system|>
            You are an AI agent that returns exactly one value to fill a document field.

            RULES:
            - You MUST output exactly and only one <FIELD>...</FIELD> tag.
            - NO text before the tag, NO text after the tag, NO blank lines.
            - NO reasoning, NO explanations, NO comments.
            - Use ONLY the information inside "INFORMATION". 
            - Do NOT invent or infer new data.
            - If no suitable value exists, output exactly: <FIELD>--</FIELD>
            - Never output more than ONE <FIELD>...</FIELD> tag.

            Your entire reply must match this regex pattern exactly:
            <FIELD>\s*([^<]*)\s*<\/FIELD>
            If your reply does not match this format, it will be rejected.
            <|end|>

            <|user|>
            Using this INFORMATION:
            {information}

            Return the best value for the document field below.
            FIELD NAME: {field['field_name']}
            FIELD NEARBY TEXT: {field['label_text']}
            <|end|>
            <|assistant|>
            """

            response = query_ollama(prompt)
            print(response)

            ordered_values = composer.extract_filled_field(response)
            if ordered_values is None or len(ordered_values) == 0:
                ordered_values = ["--"]

            if iter_counter == 0:
                composer.fill_pdf_form(tofilldoc, filleddoc, ordered_values)
            else:
                composer.fill_pdf_form(filleddoc, filleddoc, ordered_values)

            iter_counter += 1
            populated_chunks.append(response)

        response = send_file(
            filleddoc,
            as_attachment=True,
            download_name=os.path.basename(filleddoc),
            mimetype="application/pdf"
        )
        if response:
            try:
                uploads_dir = "uploads"
                if os.path.exists(uploads_dir):
                    shutil.rmtree(uploads_dir)
                    print("🧹 Directory 'uploads/' cleaned.")
            except Exception as e:
                print(f"⚠️ Errors during 'uploads/' directory cleaning: {e}")

        return response
    

@api.route("/register")
class Registration(Resource):
    @api.doc(summary="", description="Register the service to the registry for discovery (catalog + consul).")
    def post(self):
        swagger_url = f"http://{SERVICE_HOST}:{SERVICE_PORT}/swagger.json"
        try:
            spec = requests.get(swagger_url).json()
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
                "Http": f"http://{SERVICE_HOST}:{SERVICE_PORT}/api/filler/health",
                "Interval": "10s",
                "Timeout": "5s",
                "DeregisterCriticalServiceAfter": "30s"
            }
        }

        try:
            consul_response = requests.put(
                f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/agent/service/register",
                json=consul_payload
            )
        except Exception as e:
            return {"error": f"Cannot register service on Consul: {str(e)}"}, 500

        try:
            gateway_response = requests.post(
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


def query_ollama(prompt):
    url = os.environ.get("OLLAMA_API_URL", "http://192.168.250.40:15888")
    try:
        response = requests.post(
            f"{url}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "options": {
                    "temperature": 0.0,
                    "max_tokens": 4096,
                    "num_ctx": 8192,
                },
                "stream": False
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"[HTTP ERROR] Errore nella richiesta a Ollama: {e}")
    except ValueError:
        raise RuntimeError(f"[PARSE ERROR] Risposta non JSON valida da Ollama: {response.text}")
