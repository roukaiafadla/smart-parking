from flask import Blueprint, render_template, redirect, url_for, flash, Response, request, stream_with_context
from flask_login import login_required
from app import db
from bson import ObjectId
import json
import queue
import threading

alertes_bp = Blueprint('alertes', __name__, url_prefix='/alertes')

# File d'attente partagée pour les événements SSE
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()

def _broadcast(data: dict):
    """Envoie un événement à tous les clients SSE connectés."""
    payload = f"data: {json.dumps(data)}\n\n"
    dead = []
    with _sse_lock:
        for q in _sse_clients:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# ── ROUTES ──────────────────────────────────────────

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


@alertes_bp.route('/stream')
@login_required
def stream():
    """Endpoint SSE — le dashboard s'y connecte pour recevoir les alertes en temps réel."""
    q: queue.Queue = queue.Queue(maxsize=20)
    with _sse_lock:
        _sse_clients.append(q)

    @stream_with_context
    def generate():
        # Ping initial pour confirmer la connexion
        yield "data: {\"type\": \"connected\"}\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"   # évite que le proxy ferme la connexion
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',   # désactive le buffering nginx
        }
    )


@alertes_bp.route('/api/push', methods=['POST'])
def api_push():
    """Reçoit les événements depuis handler.py et les diffuse aux clients SSE."""
    data = request.get_json(silent=True) or {}
    _broadcast(data)
    return {'ok': True}