from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from app.models.admin import Admin
from app import login_manager

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Un seul admin — chargé depuis config
ADMIN_ID = 'admin-001'

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_ID:
        return Admin(ADMIN_ID, current_app.config['ADMIN_USERNAME'])
    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if (username == current_app.config['ADMIN_USERNAME'] and
                password == current_app.config['ADMIN_PASSWORD']):
            admin = Admin(ADMIN_ID, username)
            login_user(admin)
            return redirect(url_for('dashboard.index'))

        flash('Identifiants incorrects.', 'error')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))