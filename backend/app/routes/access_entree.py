from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required
from app import db
from datetime import datetime

access_entree_bp = Blueprint("access_entree", __name__, url_prefix="/access")


# --- AFFICHAGE WEB ---
@access_entree_bp.route("/")
@login_required
def index():
    logs = list(db.access_logs.find().sort("timestamp", -1).limit(50))
    return render_template("access.html", logs=logs)


# --- ROUTE RASPBERRY PI ENTRÉE ---
@access_entree_bp.route("/api/entree", methods=["POST"])
def check_entree():
    data = request.json

    if not data or not data.get("uid"):
        return jsonify({"status": "error", "message": "UID manquant"}), 400

    uid       = ' '.join(data.get("uid", "").strip().upper().split())
    matricule = data.get("matricule", "").strip().upper()

    # Vérifier le tag
    user = db.users.find_one({"id_tag": uid, "etat": "actif"})

    if not user:
        db.access_logs.insert_one({
            "id_tag":    uid,
            "user_id":   None,
            "nom":       "Inconnu",
            "matricule": matricule,
            "timestamp": datetime.now(),
            "statut":    "refusé",
            "type":      "entree"
        })
        return jsonify({"status": "error", "message": "Tag non reconnu"})

    # Vérifier le matricule
    if matricule:
        vehicule = db.vehicules.find_one({
            "user_id":   user.get("_id"),
            "matricule": matricule
        })
        if not vehicule:
            db.access_logs.insert_one({
                "id_tag":    uid,
                "user_id":   user.get("_id"),
                "nom":       f"{user['prenom']} {user['nom']}",
                "matricule": matricule,
                "timestamp": datetime.now(),
                "statut":    "refusé",
                "type":      "entree"
            })
            return jsonify({"status": "error", "message": "Matricule non reconnu"})

    nom = f"{user['prenom']} {user['nom']}"
    db.access_logs.insert_one({
        "id_tag":    uid,
        "user_id":   user.get("_id"),
        "nom":       nom,
        "matricule": matricule,
        "timestamp": datetime.now(),
        "statut":    "autorisé",
        "type":      "entree"
    })
    return jsonify({"status": "valid", "message": nom})