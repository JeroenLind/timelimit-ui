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

def regenerate_second_hash(password, second_salt):
    """
    Regenereert de secondHash met een bestaande salt.
    Dit is nodig omdat de server alleen de salt terugstuurt, niet de hash zelf.
    
    Args:
        password: Het plaintext wachtwoord
        second_salt: De bcrypt salt string (bijv. "$2a$10$...")
    
    Returns:
        De bcrypt hash string
    """
    password_bytes = password.encode('utf-8')
    salt_bytes = second_salt.encode('utf-8')
    
    # Gebruik de bestaande salt om dezelfde hash te regenereren
    hash_result = bcrypt.hashpw(password_bytes, salt_bytes)
    
    return hash_result.decode('utf-8')

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

def calculate_hmac_sha256_binary(second_hash, sequence_number, device_id, encoded_action):
    """
    Berekent HMAC-SHA256 voor sync action signing in CORRECT server formaat.
    
    Server verwacht: "password:" + base64(HMAC-SHA256(key=secondHash, message=binary_format))
    
    Binary format:
      - sequenceNumber (8 bytes, big-endian long)
      - deviceId_length (4 bytes, big-endian int)
      - deviceId_bytes
      - encodedAction_length (4 bytes, big-endian int)
      - encodedAction_bytes
    
    Args:
        second_hash: BCrypt hash string (bijvoorbeeld $2a$12$...)
        sequence_number: Integer sequence number
        device_id: String device ID
        encoded_action: JSON string van de action
    
    Returns:
        String in formaat "password:<base64_hmac>"
    """
    try:
        import struct
        
        # secondHash (bcrypt string) wordt als UTF-8 bytes gebruikt als key
        key_bytes = second_hash.encode('utf-8')
        
        # Bouw binary message:
        # 1. sequenceNumber als 8-byte big-endian (long/int64)
        seq_bytes = struct.pack('>Q', sequence_number)  # >Q = big-endian unsigned long long
        
        # 2. deviceId length + bytes
        device_id_bytes = device_id.encode('utf-8')
        device_id_len = struct.pack('>I', len(device_id_bytes))  # >I = big-endian unsigned int
        
        # 3. encodedAction length + bytes
        encoded_action_bytes = encoded_action.encode('utf-8')
        encoded_action_len = struct.pack('>I', len(encoded_action_bytes))
        
        # Combineer alle delen
        message = seq_bytes + device_id_len + device_id_bytes + encoded_action_len + encoded_action_bytes
        
        # Bereken HMAC-SHA256 (niet SHA512!)
        hmac_obj = hmac.new(key_bytes, message, hashlib.sha256)
        
        # Return met "password:" prefix
        hash_base64 = base64.b64encode(hmac_obj.digest()).decode('utf-8')
        return f"password:{hash_base64}"
        
    except Exception as e:
        raise ValueError(f"HMAC-SHA256 binary calculation failed: {str(e)}")