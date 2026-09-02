"""Key management module for Curve25519 signing keys.

This module provides functionality to generate and manage Curve25519 key pairs
for the dashboard device. The signing key is used for:
- End-to-end encryption of app lists and parent passwords
- Key request/response protocol for sharing decryption keys

The private key is stored persistently in the persistence file, and the public
key is stored in the devices table and displayed in the dashboard UI.
"""

import os
import json
import threading
import base64
import time
from typing import Tuple, Optional

from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from utils.logging import get_logger

logger = get_logger(__name__)


# Lock for thread-safe key operations
_key_lock = threading.Lock()


def generate_curve25519_keypair() -> Tuple[bytes, bytes]:
    """Generate a Curve25519 key pair.
    
    Returns:
        Tuple of (private_key_bytes, public_key_bytes) as raw bytes.
    """
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    return private_key_bytes, public_key_bytes


def get_or_create_signing_key(persistence_dir: str) -> Tuple[str, str]:
    """Get the existing signing key or generate a new one.
    
    The private key is stored in a JSON file for persistence across restarts.
    The public key is returned for storage in the devices table.
    
    Args:
        persistence_dir: Directory for storing the key file.
        
    Returns:
        Tuple of (private_key_base64, public_key_base64) as base64-encoded strings.
    """
    key_file_path = os.path.join(persistence_dir, 'dashboard_signing_key.json')
    
    with _key_lock:
        # Try to load existing key
        if os.path.exists(key_file_path):
            try:
                with open(key_file_path, 'r', encoding='utf-8') as f:
                    key_data = json.load(f)
                    private_key_b64 = key_data.get('private_key')
                    if private_key_b64:
                        # Decode and verify the key
                        private_key_bytes = base64.b64decode(private_key_b64)
                        # Derive public key from private key
                        private_key = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
                        public_key = private_key.public_key()
                        public_key_bytes = public_key.public_bytes(
                            encoding=serialization.Encoding.Raw,
                            format=serialization.PublicFormat.Raw
                        )
                        public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
                        
                        logger.debug(
                            "Loaded existing signing key from file",
                            component="key_manager",
                            key_file=key_file_path
                        )
                        return private_key_b64, public_key_b64
            except Exception as e:
                logger.warning(
                    "Failed to load signing key, generating new one",
                    component="key_manager",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        # Generate new key pair
        private_key_bytes, public_key_bytes = generate_curve25519_keypair()
        
        # Encode as base64 for storage
        private_key_b64 = base64.b64encode(private_key_bytes).decode('utf-8')
        public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
        
        # Save private key to file
        key_data = {
            'private_key': private_key_b64,
            'created_at': int(time.time())
        }
        
        # Ensure directory exists
        os.makedirs(persistence_dir, exist_ok=True)
        
        # Write atomically
        temp_path = key_file_path + '.tmp'
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(key_data, f, indent=2)
            os.replace(temp_path, key_file_path)
            
            logger.info(
                "Generated and saved new signing key",
                component="key_manager",
                key_file=key_file_path
            )
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
        
        return private_key_b64, public_key_b64


def get_public_key_from_private(private_key_b64: str) -> str:
    """Derive the public key from a private key.
    
    Args:
        private_key_b64: Base64-encoded private key.
        
    Returns:
        Base64-encoded public key.
    """
    private_key_bytes = base64.b64decode(private_key_b64)
    private_key = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
    public_key = private_key.public_key()
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    return base64.b64encode(public_key_bytes).decode('utf-8')