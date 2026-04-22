from flask import Blueprint, render_template
from flask_login import login_required
from app import db

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # ── Stats ──────────────────────────────────────────
    total_users       = db.users.count_documents({})
    active_users      = db.users.count_documents({'etat': 'actif'})
    new_users_month   = 0  # à implémenter quand date_creation est ajouté

    total_tags        = db.tags.count_documents({})
    active_tags       = db.tags.count_documents({'etat': 'actif'})
    inactive_tags     = db.tags.count_documents({'etat': {'$in': ['perdu', 'désactivé']}})
    unassigned_tags   = db.tags.count_documents({'user_id': None})

    total_vehicles    = db.vehicules.count_documents({})

    stats = {
        'total_users':        total_users,
        'active_users':       active_users,
        'new_users_this_month': new_users_month,
        'total_tags':         total_tags,
        'active_tags':        active_tags,
        'inactive_tags':      inactive_tags,
        'unassigned_tags':    unassigned_tags,
        'total_vehicles':     total_vehicles,
    }

    # ── Recent users ───────────────────────────────────
    recent_users = list(db.users.find().limit(8))

    # ── Donut chart math ───────────────────────────────
    # SVG circle circumference for r=38: 2 * pi * 38 ≈ 238.76
    CIRC = 238.76
    if total_tags > 0:
        active_pct   = active_tags   / total_tags
        inactive_pct = inactive_tags / total_tags
    else:
        active_pct = inactive_pct = 0

    active_dash   = round(active_pct   * CIRC, 2)
    inactive_dash = round(inactive_pct * CIRC, 2)
    rest_dash     = round(CIRC - active_dash,   2)
    rest_dash2    = round(CIRC - inactive_dash, 2)
    # offset: push inactive segment to start right after active
    inactive_offset = round(25 - active_dash, 2)

    donut = {
        'active_dash':      active_dash,
        'inactive_dash':    inactive_dash,
        'rest_dash':        rest_dash,
        'rest_dash2':       rest_dash2,
        'inactive_offset':  inactive_offset,
    }

    return render_template(
        'dashboard.html',
        stats=stats,
        recent_users=recent_users,
        donut=donut,
    )
