from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
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
        id_tag        = request.form.get('id_tag', '').strip().upper()
        id_tag        = ' '.join(id_tag.split())  # normalise les espaces
        etat          = request.form.get('etat', 'actif')

        if not all([nom, prenom, email, num_telephone, id_tag]):
            flash('Tous les champs sont obligatoires.', 'error')
            return render_template('user_form.html', action='create', data=request.form)

        if db.users.find_one({'email': email}):
            flash('Cet email existe déjà.', 'error')
            return render_template('user_form.html', action='create', data=request.form)

        if db.users.find_one({'id_tag': id_tag}):
            flash('Ce tag RFID est déjà assigné.', 'error')
            return render_template('user_form.html', action='create', data=request.form)

        db.users.insert_one({
            'nom': nom,
            'prenom': prenom,
            'email': email,
            'num_telephone': num_telephone,
            'id_tag': id_tag,
            'etat': etat,
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

    if request.method == 'POST':
        nom           = request.form.get('nom', '').strip()
        prenom        = request.form.get('prenom', '').strip()
        email         = request.form.get('email', '').strip()
        num_telephone = request.form.get('num_telephone', '').strip()
        id_tag        = request.form.get('id_tag', '').strip().upper()
        id_tag        = ' '.join(id_tag.split())  # normalise les espaces
        etat          = request.form.get('etat', 'actif')

        if not all([nom, prenom, email, num_telephone, id_tag]):
            flash('Tous les champs sont obligatoires.', 'error')
            return render_template('user_form.html', action='edit', data=request.form, user=user)

        existing_email = db.users.find_one({'email': email, '_id': {'$ne': ObjectId(id)}})
        if existing_email:
            flash('Cet email est déjà utilisé par un autre client.', 'error')
            return render_template('user_form.html', action='edit', data=request.form, user=user)

        existing_tag = db.users.find_one({'id_tag': id_tag, '_id': {'$ne': ObjectId(id)}})
        if existing_tag:
            flash('Ce tag RFID est déjà assigné à un autre client.', 'error')
            return render_template('user_form.html', action='edit', data=request.form, user=user)

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
        flash('Client modifié avec succès.', 'success')
        return redirect(url_for('users.index'))

    return render_template('user_form.html', action='edit', data=user, user=user)


@users_bp.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
    user = db.users.find_one({'_id': ObjectId(id)})
    if not user:
        flash('Client introuvable.', 'error')
        return redirect(url_for('users.index'))

    db.users.delete_one({'_id': ObjectId(id)})
    flash('Client supprimé.', 'success')
    return redirect(url_for('users.index'))