import bcrypt

def generate_family_hashes(password):
    """
    Genereert de hashes precies zoals de TimeLimit app dat doet:
    - hash: wachtwoord met salt 1
    - secondHash: wachtwoord met salt 2
    - secondSalt: de salt gebruikt voor de tweede hash
    """
    password_bytes = password.encode('utf-8')

    # Genereer twee unieke salts (cost factor 12 zoals in de app)
    salt1 = bcrypt.gensalt(rounds=12)
    salt2 = bcrypt.gensalt(rounds=12)

    # Bereken de hashes
    hash1 = bcrypt.hashpw(password_bytes, salt1)
    hash2 = bcrypt.hashpw(password_bytes, salt2)

    return {
        "hash": hash1.decode('utf-8'),
        "secondHash": hash2.decode('utf-8'),
        "secondSalt": salt2.decode('utf-8')
    }