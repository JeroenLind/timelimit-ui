"""Crypto helpers for hashing and integrity calculations used by the UI backend."""

import bcrypt
import hmac
import hashlib
import base64

def generate_family_hashes(password):
    """Generate BCrypt hashes for family password, matching Android app logic."""
    """Generate BCrypt hashes matching the Android app logic (cost factor 12)."""
    password_bytes = password.encode('utf-8')

    # Two unique salts for maximum safety
    salt1 = bcrypt.gensalt(rounds=12)
    salt2 = bcrypt.gensalt(rounds=12)

    # Hashes expected by the server
    hash1 = bcrypt.hashpw(password_bytes, salt1)
    hash2 = bcrypt.hashpw(password_bytes, salt2)

    return {
        "hash": hash1.decode('utf-8'),
        "secondHash": hash2.decode('utf-8'),
        "secondSalt": salt2.decode('utf-8')
    }

def regenerate_second_hash(password, second_salt):
    """Regenerate secondHash using an existing salt from the server."""
    """
    Regenerate secondHash using an existing salt.
    This is needed because the server returns only the salt, not the hash.
    
    Args:
        password: Plaintext password
        second_salt: Bcrypt salt string (e.g. "$2a$10$...")
    
    Returns:
        Bcrypt hash string
    """
    password_bytes = password.encode('utf-8')
    salt_bytes = second_salt.encode('utf-8')
    
    # Use the existing salt to regenerate the same hash
    hash_result = bcrypt.hashpw(password_bytes, salt_bytes)
    
    return hash_result.decode('utf-8')

def calculate_hmac_sha512(key_base64, message):
    """Calculate HMAC-SHA512 for sync action signing."""
    """
    Calculate HMAC-SHA512 for sync action signing.
    
    Args:
        key_base64: Base64-encoded key (secondSalt)
        message: String message (sequenceNumber|deviceId|encodedAction)
    
    Returns:
        Base64-encoded HMAC-SHA512 hash
    """
    try:
        # Decode the base64 key
        key_bytes = base64.b64decode(key_base64)
        
        # Compute HMAC-SHA512
        message_bytes = message.encode('utf-8')
        hmac_obj = hmac.new(key_bytes, message_bytes, hashlib.sha512)
        
        # Return base64-encoded hash
        return base64.b64encode(hmac_obj.digest()).decode('utf-8')
    except Exception as e:
        raise ValueError(f"HMAC calculation failed: {str(e)}")

def calculate_sha512_hex(message):
    """Calculate SHA512 hex digest for legacy integrity signing."""
    """
    Calculate SHA512 hex digest for legacy integrity signing.

    Args:
        message: String message (sequenceNumber + deviceId + secondHash + encodedAction)

    Returns:
        Hex string of the SHA512 digest.
    """
    try:
        message_bytes = message.encode('utf-8')
        return hashlib.sha512(message_bytes).hexdigest()
    except Exception as e:
        raise ValueError(f"SHA512 calculation failed: {str(e)}")

def calculate_hmac_sha256_binary(second_hash, sequence_number, device_id, encoded_action):
    """
    Calculate HMAC-SHA256 for sync action signing in the correct server format.
    
    Server verwacht: "password:" + base64(HMAC-SHA256(key=secondHash, message=binary_format))
    
    Binary format:
      - sequenceNumber (8 bytes, big-endian long)
      - deviceId_length (4 bytes, big-endian int)
      - deviceId_bytes
      - encodedAction_length (4 bytes, big-endian int)
      - encodedAction_bytes
    
    Args:
        second_hash: BCrypt hash string (e.g. $2a$12$...)
        sequence_number: Integer sequence number
        device_id: String device ID
        encoded_action: JSON string of the action
    
    Returns:
        String in the format "password:<base64_hmac>"
    """
    try:
        import struct
        
        # Use secondHash (bcrypt string) as UTF-8 bytes for the key
        key_bytes = second_hash.encode('utf-8')
        
        # Build binary message:
        # 1. sequenceNumber as 8-byte big-endian (long/int64)
        seq_bytes = struct.pack('>Q', sequence_number)  # >Q = big-endian unsigned long long
        
        # 2. deviceId length + bytes
        device_id_bytes = device_id.encode('utf-8')
        device_id_len = struct.pack('>I', len(device_id_bytes))  # >I = big-endian unsigned int
        
        # 3. encodedAction length + bytes
        encoded_action_bytes = encoded_action.encode('utf-8')
        encoded_action_len = struct.pack('>I', len(encoded_action_bytes))
        
        # Combine all parts
        message = seq_bytes + device_id_len + device_id_bytes + encoded_action_len + encoded_action_bytes
        
        # Compute HMAC-SHA256 (not SHA512!)
        hmac_obj = hmac.new(key_bytes, message, hashlib.sha256)
        
        # Return with "password:" prefix
        hash_base64 = base64.b64encode(hmac_obj.digest()).decode('utf-8')
        return f"password:{hash_base64}"
        
    except Exception as e:
        raise ValueError(f"HMAC-SHA256 binary calculation failed: {str(e)}")