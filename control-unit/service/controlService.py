from service.discoveryService import Discovery
import json
import requests
import re
import aiohttp
import asyncio
import os
import mimetypes
import shutil

class Controller:

    def __init__(self):
        self.model_name = "phi4-reasoning:14b"
        os.makedirs("Files", exist_ok=True)

    def analyze_files(self, files: list):
        analyzed = []

        if files:
            for f in files:
                filename = f.filename
                content_type = f.mimetype or mimetypes.guess_type(filename)[0]
                size = f.content_length
                path = os.path.join("Files", filename)
                f.save(path)

                file_info = {
                    "filename": filename,
                    "content_type": content_type,
                    "size": size,
                    "path": path
                }

                if content_type == "application/pdf":
                    file_info["category"] = "document"
                elif content_type and content_type.startswith("image/"):
                    file_info["category"] = "image"
                elif content_type in ["text/csv", "application/vnd.ms-excel"]:
                    file_info["category"] = "tabular"
                else:
                    file_info["category"] = "unknown"

                analyzed.append(file_info)

        return analyzed

     
    def query_ollama(self, prompt: str) -> str:
        url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
        try:
            response = requests.post(
                f"{url}/api/generate",
                json={
                    "model": self.model_name,
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


    def decompose_task(self, discovered_services, discovered_capabilities, discovered_endpoints, query, input_files=None):

        example = {
        "tasks": [
            {
            "task_name": "analyze text",
            "service_id": "svc-001",
            "endpoint": "service endpoint",
            "input": "[TEXT]text to analyze[/TEXT]",
            "operation": "POST"
            },
            {
            "task_name": "retrieve report",
            "service_id": "svc-002",
            "endpoint": "service endpoint",
            "input": "[FILE]filename[/FILE]",
            "operation": "GET"
            }
          ]
        }

        example_str = json.dumps(example)
        prompt = f"""
            <|system|>
            You have access to a list of services registered in a distributed system, each described by:
            - services
            - capabilities
            - endpoints
            - optional user-provided files

            You will receive a query in natural language and must:
            1. Decompose it into atomic tasks.
            2. Associate each task with one or more compatible services based on their capabilities, endpoints and file types.
            3. Return an execution plan.

            REPLY ONLY with a valid JSON, WITHOUT any introductory text or comments.

            Example of the JSON Response (Make sure to fille the fields with data provided by user):
            TEMPLATE:
            {example_str}

            RULES:
            - Use only the data provided. Do not make assumptions or invent services or invent endpoints.
            - Be careful with endpoints names and HTTP operations, they must match date provided in ENDPOINTS section.
            - Endpoints may contain path parameters placeholders in curly brackets
            - You MUST replace these placeholders with actual values extracted from the user query.
            - NEVER return an endpoint containing unresolved placeholders.
            - You have to understand, given the endpoint, if there is a path parameter or a query parameter.
            - Think about the best way to decompose the query and assign tasks to services. 
            - If files are images, prefer OCR / image-processing services
            - If files are PDFs or documents, prefer text-extraction or analysis services
            - If files are tabular (CSV, Excel), prefer data-processing services
            - If no service can handle the file type, do NOT invent one
            <|end|>
            <|user|>
            SERVICES:
            {discovered_services}

            CAPABILITIES:
            {discovered_capabilities}

            ENDPOINTS:
            {discovered_endpoints}

            FILES:
            {input_files}

            QUERY:
            {query}
            <|end|>
            <|assistant|>
        """

        response = self.query_ollama(prompt)
        print(f"[LLM RESPONSE] {response}")
        print("="*100)
        return response

    def extract_agents(self, agents_json):
        plan = {}
        json_str = ""
        try:
            think_close_match = re.search(r'</think>', agents_json, flags=re.IGNORECASE)

            if think_close_match:
                after_think = agents_json[think_close_match.end():].strip()
                start = after_think.find('{')
                end = after_think.rfind('}') + 1

                if start != -1 and end != -1 and start < end:
                    json_str = after_think[start:end].strip()
                    plan = json.loads(json_str)
                else:
                    print("[FORMAT ERROR] JSON delimited by { ... } not fount after </think>.")
            else:
                print("[FORMAT ERROR] No tag </think> found.")
        except json.JSONDecodeError as e:
            print(f"[DECODE ERROR] Errors in JSON parsing: {e}\nExtracted content:\n{json_str}")
        return plan


    # ========== Async version maintained for future works ==========
    async def call_agent(self, session, task, discovered_services):
        """Versione asincrona - mantenuta per compatibilità"""
        task_name = task.get("task_name")
        endpoint = task.get("endpoint")
        input_data = task.get("input", "")
        operation = task.get("operation", "").upper()

        response_result = {
            "task_name": task_name,
            "operation": operation
        }

        tag_pattern = r"\[(\w+)\](.*?)\[/\1\]"
        match = re.search(tag_pattern, input_data, re.DOTALL)

        payload = None
        is_file = False
        file_path = None
        filename = None

        if match:
            tag = match.group(1)
            content = match.group(2)

            if tag == "TEXT":
                payload = content

            elif tag == "FILE":
                filename = content
                file_path = os.path.join("Files", filename)

                if not os.path.exists(file_path):
                    response_result.update({
                        "status": "ERROR",
                        "status_code": 404,
                        "result": f"File '{filename}' non trovato"
                    })
                    return response_result

                is_file = True
        else:
            payload = input_data

        try:
            request_kwargs = {"timeout": 5}

            if is_file:
                form = aiohttp.FormData()
                form.add_field(
                    name="file",
                    value=open(file_path, "rb"),
                    filename=filename,
                    content_type="application/octet-stream"
                )
                request_kwargs["data"] = form
            else:
                request_kwargs["json"] = payload

            match operation:
                case "POST":
                    resp_ctx = session.post(endpoint, **request_kwargs)
                case "PUT":
                    resp_ctx = session.put(endpoint, **request_kwargs)
                case "GET":
                    resp_ctx = session.get(endpoint, timeout=5)
                case "DELETE":
                    resp_ctx = session.delete(endpoint, timeout=5)
                case _:
                    raise ValueError(f"Operazione HTTP non supportata: {operation}")

            async with resp_ctx as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "")

                if 200 <= status < 300:
                    if "application/json" in content_type:
                        result = await resp.json()
                    else:
                        result = await resp.text()

                    print(f"[SUCCESS] Task '{task_name}' completed")
                    response_result.update({
                        "status": "SUCCESS",
                        "status_code": status,
                        "result": result
                    })
                else:
                    error_text = await resp.text()
                    print(f"[ERROR] Task '{task_name}' failed: {error_text}")
                    response_result.update({
                        "status": "ERROR",
                        "status_code": status,
                        "result": error_text
                    })

        except Exception as e:
            print(f"[EXCEPTION] Task '{task_name}' → {e}")
            response_result.update({
                "status": "EXCEPTION",
                "status_code": 500,
                "result": str(e)
            })

        return response_result

    async def trigger_agents_async(self, agents: dict, discovered_services):
        """Versione asincrona - mantenuta per compatibilità"""
        tasks = agents.get("tasks", [])
        async with aiohttp.ClientSession() as session:
            futures = [asyncio.create_task(self.call_agent(session, task, discovered_services)) for task in tasks]
            results = await asyncio.gather(*futures)
        return results
    
    # ===============================================================

    def call_agent_sync(self, task, discovered_services):
        """Versione sincrona - esegue una singola task"""
        task_name = task.get("task_name")
        endpoint = task.get("endpoint")
        input_data = task.get("input", "")
        operation = task.get("operation", "").upper()

        response_result = {
            "task_name": task_name,
            "operation": operation
        }

        tag_pattern = r"\[(\w+)\](.*?)\[/\1\]"
        match = re.search(tag_pattern, input_data, re.DOTALL)

        payload = None
        is_file = False
        file_path = None
        filename = None

        if match:
            tag = match.group(1)
            content = match.group(2)

            if tag == "TEXT":
                payload = content

            elif tag == "FILE":
                filename = content
                file_path = os.path.join("Files", filename)

                if not os.path.exists(file_path):
                    response_result.update({
                        "status": "ERROR",
                        "status_code": 404,
                        "result": f"File '{filename}' non trovato"
                    })
                    return response_result

                is_file = True
        else:
            payload = input_data

        try:
            if is_file:
                # Upload file
                with open(file_path, "rb") as file:
                    files = {"file": (filename, file, "application/octet-stream")}
                    match operation:
                        case "POST":
                            resp = requests.post(endpoint, files=files, timeout=30)
                        case "PUT":
                            resp = requests.put(endpoint, files=files, timeout=30)
                        case _:
                            raise ValueError(f"Operazione HTTP non supportata per file: {operation}")
            else:
                # Wrappa il payload in {"input": ...} se è una stringa
                if isinstance(payload, str):
                    json_payload = {"input": payload}
                else:
                    json_payload = payload

                match operation:
                    case "POST":
                        resp = requests.post(endpoint, json=json_payload, timeout=30)
                    case "PUT":
                        resp = requests.put(endpoint, json=json_payload, timeout=30)
                    case "GET":
                        resp = requests.get(endpoint, timeout=30)
                    case "DELETE":
                        resp = requests.delete(endpoint, timeout=30)
                    case _:
                        raise ValueError(f"Operazione HTTP non supportata: {operation}")

            status = resp.status_code
            content_type = resp.headers.get("Content-Type", "")

            if 200 <= status < 300:
                if "application/json" in content_type:
                    try:
                        result = resp.json()
                    except:
                        result = resp.text()
                else:
                    result = resp.text()

                print(f"[SUCCESS] Task '{task_name}' completed")
                response_result.update({
                    "status": "SUCCESS",
                    "status_code": status,
                    "result": result
                })
            else:
                error_text = resp.text()
                print(f"[ERROR] Task '{task_name}' failed: {error_text}")
                response_result.update({
                    "status": "ERROR",
                    "status_code": status,
                    "result": error_text
                })

        except Exception as e:
            print(f"[EXCEPTION] Task '{task_name}' → {e}")
            response_result.update({
                "status": "EXCEPTION",
                "status_code": 500,
                "result": str(e)
            })

        return response_result

    def trigger_agents_sync(self, agents: dict, discovered_services):
        """Versione sincrona - esegue tutte le tasks in sequenza"""
        tasks = agents.get("tasks", [])
        results = []
        for task in tasks:
            result = self.call_agent_sync(task, discovered_services)
            results.append(result)
        return results

    def trigger_agents(self, agents: dict, discovered_services):
        """Wrapper - usa la versione sincrona"""
        return self.trigger_agents_sync(agents, discovered_services)

    def control(self, query, files=None):
        input_files = files or []
        analyzed_files = self.analyze_files(input_files)

        catalog_url = os.environ.get("CATALOG_URL")
        registry = Discovery(os.environ.get("REGISTRY_URL"))

        discovered_services = []
        discovered_capabilities = []
        discovered_endpoints = []

        services = registry.services()

        register_key = "POST /register"
        print("DISCOVERED SERVICES:")

        input = {
            "query": query
        }
        service_data = requests.post(f"{catalog_url}/index/search", json=input)
        service_data = service_data.json()
        service_list = service_data["results"]

        if not service_list:
            return {
                "execution_plan": {},
                "execution_results": [],
                "error": "No services matched the query"
            }
        
        registry_service_ids = set(s["id"] for s in services)
        filtered_service_list = [s for s in service_list if s["_id"] in registry_service_ids]
        orphaned_services = [s for s in service_list if s["_id"] not in registry_service_ids]
        if orphaned_services:
            print("[WARNING] Services found via semantic search but are no longer in the registry:")
            for s in orphaned_services:
                print(f"- {s.get('_id')} : {s.get('name')}")

        if not filtered_service_list:
            return {
                "execution_plan": {},
                "execution_results": [],
                "error": "None of the discovered services are currently available in the registry"
            }
        
        for service in filtered_service_list:
            if isinstance(service.get("capabilities"), dict):
                service["capabilities"].pop(register_key, None)

            if isinstance(service.get("endpoints"), dict):
                service["endpoints"].pop(register_key, None)

            print(service)
            print("="*100)

            service_preamble = {
                "_id": service.get("_id"),
                "name": service.get("name"),
                "description": service.get("description"),
            }
            discovered_services.append(service_preamble)
            discovered_capabilities.append(service.get("capabilities", {}))
            discovered_endpoints.append(service.get("endpoints", {}))
        
        plan_json = self.decompose_task(
            discovered_services=discovered_services,
            discovered_capabilities=discovered_capabilities,
            discovered_endpoints=discovered_endpoints,
            query=query,
            input_files=analyzed_files
        )
        plan = self.extract_agents(plan_json)

        results = self.trigger_agents(plan, discovered_services)

        for filename in os.listdir('Files'):
            file_path = os.path.join('Files', filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

        return {
            "execution_plan": plan,
            "execution_results": results
        }