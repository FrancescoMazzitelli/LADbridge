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
    help='File to upload (PDF, CSV, DOCX, ecc.)'
)

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
