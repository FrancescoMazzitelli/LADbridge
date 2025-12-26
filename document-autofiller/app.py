from flask import Flask
from flask_restx import Api
from controller import autofillerController
from cheroot.wsgi import Server

app = Flask(__name__)
app.config['BUNDLE_ERRORS'] = True

api = Api(app, 
          title="Document AutoFiller", 
          version="1.0", 
          description="API documentation for Document AutoFiller",
          doc="/swagger")

BASE_PATH = "/api"

api.add_namespace(autofillerController.api, path=f"{BASE_PATH}/filler")

if __name__ == "__main__":
    server = Server(("0.0.0.0", 5700), app)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
