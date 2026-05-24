from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
from app.normalization import normalize_matricule, normalize_uid
from bson import ObjectId

users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/')
@login_required
def index():
    users = list(db.users.find())
    return render_template('users.html', users=users)


@users_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        nom           = request.form.get('nom', '').strip()
        prenom        = request.form.get('prenom', '').strip()
        email         = request.form.get('email', '').strip()
        num_telephone = request.form.get('num_telephone', '').strip()
        id_tag        = normalize_uid(request.form.get('id_tag', ''))
        etat          = request.form.get('etat', 'actif')
        matricule     = normalize_matricule(request.form.get('matricule', ''))

        if not all([nom, prenom, email, num_telephone, id_tag, etat]):
            flash('Tous les champs sont obligatoires.', 'error')
            return render_template('user_form.html', action='create', data=request.form)

        if db.users.find_one({'email': email}):
            flash('Cet email existe déjà.', 'error')
            return render_template('user_form.html', action='create', data=request.form)

        if db.users.find_one({'id_tag': id_tag}):
            flash('Ce tag RFID est déjà assigné.', 'error')
            return render_template('user_form.html', action='create', data=request.form)

        # Vérifier unicité matricule dans vehicules (si fourni)
        if matricule and db.vehicules.find_one({'matricule': matricule}):
            flash('Ce matricule est déjà enregistré.', 'error')
            return render_template('user_form.html', action='create', data=request.form)

        # Créer le client — sans matricule dans users
        result = db.users.insert_one({
            'nom': nom,
            'prenom': prenom,
            'email': email,
            'num_telephone': num_telephone,
            'id_tag': id_tag,
            'etat': etat,
        })

        # Ajouter automatiquement le tag dans tags
        if not db.tags.find_one({'id_tag': id_tag}):
            db.tags.insert_one({
                'id_tag': id_tag,
                'user_id': result.inserted_id,
                'etat': etat,
            })

        # Ajouter automatiquement le véhicule dans vehicules (si matricule fourni)
        if matricule:
            db.vehicules.insert_one({
                'matricule': matricule,
                'user_id': result.inserted_id,
                'marque': '',
                'modele': '',
                'couleur': '',
            })

        flash('Client créé avec succès.', 'success')
        return redirect(url_for('users.index'))

    return render_template('user_form.html', action='create', data={})


@users_bp.route('/edit/<id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    user = db.users.find_one({'_id': ObjectId(id)})
    if not user:
        flash('Client introuvable.', 'error')
        return redirect(url_for('users.index'))

    # Récupérer le premier véhicule du client pour pré-remplir
    vehicule = db.vehicules.find_one({'user_id': ObjectId(id)})

    if request.method == 'POST':
        nom           = request.form.get('nom', '').strip()
        prenom        = request.form.get('prenom', '').strip()
        email         = request.form.get('email', '').strip()
        num_telephone = request.form.get('num_telephone', '').strip()
        id_tag        = normalize_uid(request.form.get('id_tag', ''))
        etat          = request.form.get('etat', 'actif')
        matricule     = normalize_matricule(request.form.get('matricule', ''))

        if not all([nom, prenom, email, num_telephone, id_tag, etat]):
            flash('Tous les champs sont obligatoires.', 'error')
            return render_template('user_form.html', action='edit', data=request.form, user=user, vehicule=vehicule)

        existing_email = db.users.find_one({'email': email, '_id': {'$ne': ObjectId(id)}})
        if existing_email:
            flash('Cet email est déjà utilisé par un autre client.', 'error')
            return render_template('user_form.html', action='edit', data=request.form, user=user, vehicule=vehicule)

        existing_tag = db.users.find_one({'id_tag': id_tag, '_id': {'$ne': ObjectId(id)}})
        if existing_tag:
            flash('Ce tag RFID est déjà assigné à un autre client.', 'error')
            return render_template('user_form.html', action='edit', data=request.form, user=user, vehicule=vehicule)

        # Vérifier unicité matricule dans vehicules (exclure celui du client actuel)
        if matricule:
            existing_matricule = db.vehicules.find_one({
                'matricule': matricule,
                'user_id': {'$ne': ObjectId(id)}
            })
            if existing_matricule:
                flash('Ce matricule est déjà utilisé par un autre client.', 'error')
                return render_template('user_form.html', action='edit', data=request.form, user=user, vehicule=vehicule)

        # Mettre à jour le client
        db.users.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'nom': nom,
                'prenom': prenom,
                'email': email,
                'num_telephone': num_telephone,
                'id_tag': id_tag,
                'etat': etat,
            }}
        )

        # Mettre à jour le tag dans tags
        db.tags.update_one(
            {'user_id': ObjectId(id)},
            {'$set': {'id_tag': id_tag, 'etat': etat}},
            upsert=True
        )

        # Mettre à jour ou créer le véhicule
        if matricule:
            if vehicule:
                db.vehicules.update_one(
                    {'_id': vehicule['_id']},
                    {'$set': {'matricule': matricule}}
                )
            else:
                db.vehicules.insert_one({
                    'matricule': matricule,
                    'user_id': ObjectId(id),
                    'marque': '',
                    'modele': '',
                    'couleur': '',
                })

        flash('Client modifié avec succès.', 'success')
        return redirect(url_for('users.index'))

    return render_template('user_form.html', action='edit', data=user, user=user, vehicule=vehicule)


@users_bp.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
    user = db.users.find_one({'_id': ObjectId(id)})
    if not user:
        flash('Client introuvable.', 'error')
        return redirect(url_for('users.index'))

    # Supprimer tag, tous les véhicules, et le client
    db.tags.delete_one({'user_id': ObjectId(id)})
    db.vehicules.delete_many({'user_id': ObjectId(id)})
    db.users.delete_one({'_id': ObjectId(id)})

    flash('Client, tag et véhicules associés supprimés.', 'success')
    return redirect(url_for('users.index'))