"""AES-256-GCM Credential Vault for encrypted storage of OAuth tokens and secrets."""

import base64
import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.logging import logger


class VaultDecryptionError(ValueError):
    """Raised when ciphertext or AAD authentication fails."""

    pass


class VaultConfigurationError(RuntimeError):
    """Raised when encryption key is missing or misconfigured in production."""

    pass


class CredentialVault:
    """Provides authenticated AES-256-GCM envelope encryption bound to tenant and account AAD."""

    def __init__(self, master_key: Optional[bytes] = None):
        self._key = master_key or self._resolve_master_key()
        self._aesgcm = AESGCM(self._key)

    def _resolve_master_key(self) -> bytes:
        raw_key = settings.PUBLISHING_ENCRYPTION_KEY
        if raw_key:
            try:
                # Accept 64-char hex or 32-byte direct/base64
                if len(raw_key) == 64:
                    return bytes.fromhex(raw_key)
                key_bytes = (
                    base64.b64decode(raw_key) if len(raw_key) == 44 else raw_key.encode("utf-8")
                )
                if len(key_bytes) == 32:
                    return key_bytes
            except Exception:
                pass
            raise VaultConfigurationError(
                "PUBLISHING_ENCRYPTION_KEY must be a valid 256-bit (32-byte) key."
            )

        # If in production and key missing -> fail fast
        if settings.ENVIRONMENT == "production":
            raise VaultConfigurationError(
                "CRITICAL SECURITY FAILURE: PUBLISHING_ENCRYPTION_KEY is mandatory in production."
            )

        # Development/Test fallback with mandatory explicit warning
        logger.warning(
            "DEVELOPMENT ONLY WARNING: Deriving fallback encryption key from SECRET_KEY. "
            "Never use in production!"
        )
        return hashlib.pbkdf2_hmac(
            "sha256", settings.SECRET_KEY.encode("utf-8"), b"news9_dev_salt_phase6", 100_000
        )

    def _build_aad(self, tenant_id: str, account_id: str, key_version: int) -> bytes:
        return f"{tenant_id}:{account_id}:{key_version}".encode("utf-8")

    def encrypt(
        self,
        plaintext: str,
        tenant_id: str,
        account_id: str,
        key_version: int = 1,
    ) -> Tuple[str, str]:
        """Encrypts plaintext string with fresh 96-bit nonce and tenant/account AAD.

        Returns:
            Tuple of (base64_ciphertext, hex_nonce)
        """
        if not plaintext:
            raise ValueError("Plaintext credential cannot be empty.")

        nonce = os.urandom(12)  # 96-bit random nonce per encryption
        aad = self._build_aad(tenant_id, account_id, key_version)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

        b64_ciphertext = base64.b64encode(ciphertext).decode("utf-8")
        hex_nonce = nonce.hex()
        return b64_ciphertext, hex_nonce

    def decrypt(
        self,
        ciphertext_b64: str,
        nonce_hex: str,
        tenant_id: str,
        account_id: str,
        key_version: int = 1,
    ) -> str:
        """Decrypts and authenticates ciphertext against tenant/account AAD."""
        try:
            ciphertext = base64.b64decode(ciphertext_b64.encode("utf-8"))
            nonce = bytes.fromhex(nonce_hex)
            aad = self._build_aad(tenant_id, account_id, key_version)
            decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext, aad)
            return decrypted_bytes.decode("utf-8")
        except InvalidTag as e:
            logger.error(
                f"Decryption authentication failed for tenant {tenant_id} "
                f"account {account_id}: InvalidTag."
            )
            raise VaultDecryptionError(
                "Ciphertext tampering or tenant/account AAD mismatch detected."
            ) from e
        except Exception as e:
            logger.error(f"Decryption failed for tenant {tenant_id} account {account_id}: {e}")
            raise VaultDecryptionError(f"Decryption failure: {str(e)}") from e

    def encrypt_credential(
        self,
        credential_data: Dict[str, Any],
        *,
        tenant_id: str,
        account_id: str,
        key_version: int = 1,
    ) -> Tuple[str, str, int]:
        """Convenience method to encrypt JSON credential dict."""
        json_str = json.dumps(credential_data, separators=(",", ":"))
        b64_c, hex_n = self.encrypt(
            json_str, tenant_id=tenant_id, account_id=account_id, key_version=key_version
        )
        return b64_c, hex_n, key_version

    def decrypt_credential(
        self,
        ciphertext_b64: str,
        *,
        tenant_id: str,
        account_id: str,
        nonce: str,
        key_version: int = 1,
    ) -> Dict[str, Any]:
        """Convenience method to decrypt and parse JSON credential dict."""
        plaintext = self.decrypt(
            ciphertext_b64=ciphertext_b64,
            nonce_hex=nonce,
            tenant_id=tenant_id,
            account_id=account_id,
            key_version=key_version,
        )
        return json.loads(plaintext)


_vault_instance: Optional[CredentialVault] = None


def get_credential_vault() -> CredentialVault:
    """Returns singleton CredentialVault instance."""
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = CredentialVault()
    return _vault_instance
