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
    
    def update_kb(self):
        flag = self.kb.initiate_document_injetion_pipeline()
        return flag 

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

        if self.kb.retriever is None:
            return "Nessun documento disponibile nella knowledge base."
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
        if not response:
            return ""
        
        think_match = re.search(r'</think>\s*(.*)', response, flags=re.IGNORECASE | re.DOTALL)
    
        if think_match:
            cleaned = think_match.group(1).strip()
            return cleaned if cleaned else response.strip()
        
        return response.strip()
    
    def invoke(self, query):
        response = self.query(query)
        cleaned_response = self.clean_response(response)
        return cleaned_response