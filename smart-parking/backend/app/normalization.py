from __future__ import annotations


def normalize_uid(uid: str) -> str:
    uid_clean = uid.strip().upper().replace("-", "").replace(" ", "")
    return " ".join(uid_clean[index : index + 2] for index in range(0, len(uid_clean), 2))


def normalize_matricule(matricule: str) -> str:
    return "".join(character for character in matricule.upper() if character.isalnum())

