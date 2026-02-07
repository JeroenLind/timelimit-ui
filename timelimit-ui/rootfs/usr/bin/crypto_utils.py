import bcrypt
import hmac
import hashlib
import base64

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

def calculate_hmac_sha512(key_base64, message):
    """
    Berekent HMAC-SHA512 voor sync action signing.
    
    Args:
        key_base64: Base64-encoded key (secondSalt)
        message: String message (sequenceNumber|deviceId|encodedAction)
    
    Returns:
        Base64-encoded HMAC-SHA512 hash
    """
    try:
        # Decode de base64 key
        key_bytes = base64.b64decode(key_base64)
        
        # Bereken HMAC-SHA512
        message_bytes = message.encode('utf-8')
        hmac_obj = hmac.new(key_bytes, message_bytes, hashlib.sha512)
        
        # Return base64-encoded hash
        return base64.b64encode(hmac_obj.digest()).decode('utf-8')
    except Exception as e:
        raise ValueError(f"HMAC calculation failed: {str(e)}")