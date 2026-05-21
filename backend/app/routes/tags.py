from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
from app.normalization import normalize_uid
from bson import ObjectId

tags_bp = Blueprint('tags', __name__, url_prefix='/tags')


@tags_bp.route('/')
@login_required
def index():
    tags = list(db.tags.find())
    for t in tags:
        if t.get('user_id'):
            user = db.users.find_one({'_id': ObjectId(t['user_id'])})
            t['owner'] = f"{user['prenom']} {user['nom']}" if user else 'Inconnu'
        else:
            t['owner'] = '—'
    return render_template('tags.html', tags=tags)


@tags_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    users = list(db.users.find({'etat': 'actif'}))
    if request.method == 'POST':
        id_tag  = normalize_uid(request.form.get('id_tag', ''))
        user_id = request.form.get('user_id', '').strip()
        etat    = request.form.get('etat', 'actif')

        if not id_tag:
            flash('L\'identifiant du tag est obligatoire.', 'error')
            return render_template('tag_form.html', action='create', data=request.form, users=users)

        if db.tags.find_one({'id_tag': id_tag}):
            flash('Ce tag existe déjà.', 'error')
            return render_template('tag_form.html', action='create', data=request.form, users=users)

        db.tags.insert_one({
            'id_tag':  id_tag,
            'user_id': ObjectId(user_id) if user_id else None,
            'etat':    etat,
        })
        flash('Tag RFID créé avec succès.', 'success')
        return redirect(url_for('tags.index'))

    return render_template('tag_form.html', action='create', data={}, users=users)


@tags_bp.route('/edit/<id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    tag = db.tags.find_one({'_id': ObjectId(id)})
    if not tag:
        flash('Tag introuvable.', 'error')
        return redirect(url_for('tags.index'))

    users = list(db.users.find({'etat': 'actif'}))

    if request.method == 'POST':
        id_tag  = normalize_uid(request.form.get('id_tag', ''))
        user_id = request.form.get('user_id', '').strip()
        etat    = request.form.get('etat', 'actif')

        if not id_tag:
            flash('L\'identifiant du tag est obligatoire.', 'error')
            return render_template('tag_form.html', action='edit', data=request.form, tag=tag, users=users)

        existing = db.tags.find_one({'id_tag': id_tag, '_id': {'$ne': ObjectId(id)}})
        if existing:
            flash('Ce tag est déjà utilisé.', 'error')
            return render_template('tag_form.html', action='edit', data=request.form, tag=tag, users=users)

        db.tags.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'id_tag':  id_tag,
                'user_id': ObjectId(user_id) if user_id else None,
                'etat':    etat,
            }}
        )
        flash('Tag modifié avec succès.', 'success')
        return redirect(url_for('tags.index'))

    return render_template('tag_form.html', action='edit', data=tag, tag=tag, users=users)


@tags_bp.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
    tag = db.tags.find_one({'_id': ObjectId(id)})
    if not tag:
        flash('Tag introuvable.', 'error')
        return redirect(url_for('tags.index'))

    db.tags.delete_one({'_id': ObjectId(id)})
    flash('Tag supprimé.', 'success')
    return redirect(url_for('tags.index'))
