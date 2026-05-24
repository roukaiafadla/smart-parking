from flask import Blueprint, request, jsonify, render_template
from app import db
from app.normalization import normalize_uid
from datetime import datetime
from flask_login import login_required

access_api = Blueprint("access_api", __name__, url_prefix="/access")


# --- ROUTE POUR L'AFFICHAGE WEB ---
@access_api.route("/")
@login_required
def index():
    logs = list(db.access_logs.find().sort("timestamp", -1).limit(50))
    return render_template("access.html", logs=logs)


# --- ROUTE POUR LE RASPBERRY PI ---
@access_api.route("/api/open_barrier", methods=["POST"])
@login_required
def open_barrier():
    try:
        # Write command to a file that the bridge reads
        with open("barrier_command.txt", "w") as f:
            f.write("OPEN_BARRIER")
        return jsonify({"status": "ok", "message": "Commande envoyée"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    

    
@access_api.route("/api/access", methods=["POST"])
def check_access():
    data = request.json

    if not data or not data.get("uid"):
        return jsonify({"status": "error", "message": "UID manquant"}), 400

    uid = normalize_uid(data.get("uid", ""))

    # Chercher directement dans users par id_tag
    user = db.users.find_one({"id_tag": uid, "etat": "actif"})

    if user:
        nom = f"{user['prenom']} {user['nom']}"
        db.access_logs.insert_one({
            "id_tag": uid,
            "user_id": user.get("_id"),
            "nom": nom,
            "timestamp": datetime.now(),
            "statut": "autorisé",
            "type": "sortie"
        })
        return jsonify({"status": "valid", "message": f"Accès autorisé — {nom}"})

    else:
        db.access_logs.insert_one({
            "id_tag": uid,
            "user_id": None,
            "nom": "Inconnu",
            "timestamp": datetime.now(),
            "statut": "refusé",
            "type": "sortie"
        })
        return jsonify({"status": "error", "message": "Accès refusé"})
