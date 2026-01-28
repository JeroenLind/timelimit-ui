import bcrypt

def generate_family_hashes(password):
    """Genereert BCrypt hashes conform de Android app logica (Cost factor 12)."""
    password_bytes = password.encode('utf-8')

    # Twee unieke salts voor maximale veiligheid
    salt1 = bcrypt.gensalt(rounds=12)
    salt2 = bcrypt.gensalt(rounds=12)

    # De hashes die de server verwacht
    hash1 = bcrypt.hashpw(password_bytes, salt1)
    hash2 = bcrypt.hashpw(password_bytes, salt2)

    return {
        "hash": hash1.decode('utf-8'),
        "secondHash": hash2.decode('utf-8'),
        "secondSalt": salt2.decode('utf-8')
    }