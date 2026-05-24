from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
from app.normalization import normalize_matricule
from bson import ObjectId

vehicles_bp = Blueprint('vehicles', __name__, url_prefix='/vehicles')


@vehicles_bp.route('/')
@login_required
def index():
    vehicles = list(db.vehicules.find())
    for v in vehicles:
        if v.get('user_id'):
            user = db.users.find_one({'_id': ObjectId(v['user_id'])})
            v['owner'] = f"{user['prenom']} {user['nom']}" if user else 'Inconnu'
        else:
            v['owner'] = '—'
    return render_template('vehicles.html', vehicles=vehicles)


@vehicles_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    users = list(db.users.find({'etat': 'actif'}))
    if request.method == 'POST':
        matricule = normalize_matricule(request.form.get('matricule', ''))
        user_id   = request.form.get('user_id', '').strip()
        marque    = request.form.get('marque', '').strip()
        modele    = request.form.get('modele', '').strip()
        couleur   = request.form.get('couleur', '').strip()

        if not matricule:
            flash('Le matricule est obligatoire.', 'error')
            return render_template('vehicle_form.html', action='create', data=request.form, users=users)

        if db.vehicules.find_one({'matricule': matricule}):
            flash('Ce matricule existe déjà.', 'error')
            return render_template('vehicle_form.html', action='create', data=request.form, users=users)

        # Vérifier que le user_id est valide
        if user_id and not db.users.find_one({'_id': ObjectId(user_id)}):
            flash('Client introuvable.', 'error')
            return render_template('vehicle_form.html', action='create', data=request.form, users=users)

        db.vehicules.insert_one({
            'matricule': matricule,
            'user_id':   ObjectId(user_id) if user_id else None,
            'marque':    marque,
            'modele':    modele,
            'couleur':   couleur,
        })
        flash('Véhicule ajouté avec succès.', 'success')
        return redirect(url_for('vehicles.index'))

    return render_template('vehicle_form.html', action='create', data={}, users=users)


@vehicles_bp.route('/edit/<id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    vehicle = db.vehicules.find_one({'_id': ObjectId(id)})
    if not vehicle:
        flash('Véhicule introuvable.', 'error')
        return redirect(url_for('vehicles.index'))

    users = list(db.users.find({'etat': 'actif'}))

    if request.method == 'POST':
        matricule = normalize_matricule(request.form.get('matricule', ''))
        user_id   = request.form.get('user_id', '').strip()
        marque    = request.form.get('marque', '').strip()
        modele    = request.form.get('modele', '').strip()
        couleur   = request.form.get('couleur', '').strip()

        if not matricule:
            flash('Le matricule est obligatoire.', 'error')
            return render_template('vehicle_form.html', action='edit', data=request.form, vehicle=vehicle, users=users)

        existing = db.vehicules.find_one({'matricule': matricule, '_id': {'$ne': ObjectId(id)}})
        if existing:
            flash('Ce matricule est déjà utilisé.', 'error')
            return render_template('vehicle_form.html', action='edit', data=request.form, vehicle=vehicle, users=users)

        # Mettre à jour le véhicule
        db.vehicules.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'matricule': matricule,
                'user_id':   ObjectId(user_id) if user_id else None,
                'marque':    marque,
                'modele':    modele,
                'couleur':   couleur,
            }}
        )

        # Sync — mettre à jour id_tag du user si le propriétaire a changé
        # (rien à faire ici — le véhicule pointe vers le user, pas l'inverse)

        flash('Véhicule modifié avec succès.', 'success')
        return redirect(url_for('vehicles.index'))

    return render_template('vehicle_form.html', action='edit', data=vehicle, vehicle=vehicle, users=users)


@vehicles_bp.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
    vehicle = db.vehicules.find_one({'_id': ObjectId(id)})
    if not vehicle:
        flash('Véhicule introuvable.', 'error')
        return redirect(url_for('vehicles.index'))

    db.vehicules.delete_one({'_id': ObjectId(id)})
    flash('Véhicule supprimé.', 'success')
    return redirect(url_for('vehicles.index'))