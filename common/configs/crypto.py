from binascii import unhexlify

import base58
from Crypto.Cipher import AES


class Crypto:
    """
    Class for performing cryptographic operations.

    Parameters
    ----------
    aes_key : str
        Hexadecimal representation of the key to be used for
        AES encryption and decryption.
    """

    def __init__(self, aes_key):
        """
        Initialize the `Crypto` class.

        Parameters
        ----------
        aes_key : str
            Hexadecimal representation of the key to be used for
            AES encryption and decryption.
        """
        self.key = unhexlify(aes_key)

    def encrypt(self, data, encode=True):
        """Encrypt the given data using AES in EAX mode.

        Parameters
        ----------
        data : str
            The data to be encrypted.
        encode : bool, optional
            If True, the encrypted data will be encoded using base58 encoding.
            If False, the encrypted data will be returned as bytes.
            Default is True.

        Returns
        -------
        str
            The encrypted and encoded data, as a string.
        """
        cipher = AES.new(self.key, AES.MODE_EAX)
        cipher_text, tag = cipher.encrypt_and_digest(data.encode())
        full_cipher_text = cipher.nonce + tag + cipher_text
        encoded = base58.b58encode(full_cipher_text) if encode else full_cipher_text
        return encoded.decode("utf-8")

    def decrypt(self, cipher_text, encoded=True):
        """Decrypt the given data using AES in EAX mode.

        Parameters
        ----------
        cipher_text : str or bytes
            The encrypted data, as a string or bytes.
        encoded : bool, optional
            If True, the `cipher_text` is assumed to be encoded using base58
            encoding and will be decoded before being decrypted.
            If False, the `cipher_text` is assumed to be the raw encrypted data as bytes.
            Default is True.

        Returns
        -------
        str
            The decrypted data, as a string.
        """
        cipher_text = (
            cipher_text.encode() if isinstance(cipher_text, str) else cipher_text
        )
        cipher_text = base58.b58decode(cipher_text) if encoded else cipher_text
        nonce = cipher_text[:16]
        tag = cipher_text[16:32]
        encrypted = cipher_text[32:]

        cipher = AES.new(self.key, AES.MODE_EAX, nonce)
        return cipher.decrypt_and_verify(encrypted, tag).decode("utf-8")
