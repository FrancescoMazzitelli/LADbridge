import os
import re
import json
import requests
import service.knowledgeBase as kb

DOCUMENT_SOURCE_DIRECTORY = 'Documents'

class Qa:
    def __init__(self):
        self.model_name = "phi4-reasoning:14b"
        self.kb = kb.MyKnowledgeBase(DOCUMENT_SOURCE_DIRECTORY)
        self.kb.initiate_document_injetion_pipeline()
    
    def update_kb(self):
        self.kb.initiate_document_injetion_pipeline()

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
                        "max_tokens": 4096
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
        
    def query(self, query):

        context = self.kb.retriever.invoke(query)

        prompt = f"""
            <|system|>
            Using the information contained in the CONTEXT block

            provide a comprehensive answer to the question in the QUERY block
            
            CONTEXT:
            {context}

            QUERY:
            {query}

            RULES:
            Answer only the question asked; the response must be concise and relevant.
            If the answer cannot be deduced from the context, do not provide an answer.

            <|end|>
            <|assistant|>
            """

        response = self.query_ollama(prompt)
        print(f"[LLM RESPONSE] {response}")
        print("="*100)
        return response
    
    def clean_response(self, response):
        parsed = re.match(r'<\/think>\s*(.*)', response, flags=re.IGNORECASE)
        cleaned = parsed.group(1)
        return cleaned
    
    def invoke(self, query):
        response = self.query(query)
        cleaned_response = cleaned_response(response)
        return cleaned_response