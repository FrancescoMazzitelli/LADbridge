from flask import Flask
from flask_restx import Api
from controller import qaController
from cheroot.wsgi import Server

app = Flask(__name__)
app.config['BUNDLE_ERRORS'] = True

api = Api(app, 
          title="Question Answering service", 
          version="1.0", 
          description="API documentation for Question Answering service",
          doc="/swagger")

BASE_PATH = "/api"

api.add_namespace(qaController.api, path=f"{BASE_PATH}/qa")

if __name__ == "__main__":
    server = Server(("0.0.0.0", 5600), app)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
