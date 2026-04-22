from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from bson import ObjectId

alertes_bp = Blueprint('alertes', __name__, url_prefix='/alertes')


@alertes_bp.route('/')
@login_required
def index():
    alertes = list(db.alertes.find().sort('timestamp', -1))
    actives = db.alertes.count_documents({'statut': 'active'})
    return render_template('alertes.html', alertes=alertes, actives=actives)


@alertes_bp.route('/resolve/<id>', methods=['POST'])
@login_required
def resolve(id):
    db.alertes.update_one(
        {'_id': ObjectId(id)},
        {'$set': {'statut': 'résolue'}}
    )
    flash('Alerte marquée comme résolue.', 'success')
    return redirect(url_for('alertes.index'))