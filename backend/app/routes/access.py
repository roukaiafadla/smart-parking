from flask import Blueprint, render_template
from flask_login import login_required
from app import db

access_bp = Blueprint('access', __name__, url_prefix='/access')


@access_bp.route('/')
@login_required
def index():
    logs = list(db.access_logs.find().sort('timestamp', -1).limit(50))
    return render_template('access.html', logs=logs)