from flask import Flask
from pymongo import MongoClient
from flask_login import LoginManager
from .config import Config

db = None
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    global db
    client = MongoClient(app.config["MONGO_URI"])
    db = client["smart_parking"]

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter.'
    login_manager.login_message_category = 'error'

    from .routes.dashboard import dashboard_bp
    from .routes.users import users_bp
    from .routes.vehicles import vehicles_bp
    from .routes.tags import tags_bp
    from .routes.auth import auth_bp
    from .routes.alertes import alertes_bp
    from .routes.access import access_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(vehicles_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(alertes_bp)
    app.register_blueprint(access_bp)
    

    return app