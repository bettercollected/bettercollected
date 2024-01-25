import hashlib


def hash_string(input_string):
    # Convert the string to bytes using UTF-8 encoding
    data = input_string.encode('utf-8')

    # Create an MD5 hash object
    hash_object = hashlib.md5()

    # Update the hash object with the bytes-like object (data)
    hash_object.update(data)

    # Get the hexadecimal representation of the hash
    hash_hex = hash_object.hexdigest()

    return hash_hex
