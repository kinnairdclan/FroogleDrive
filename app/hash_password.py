"""Print a password hash for FROOGLEDRIVE_PASSWORD_HASH.

Usage: python -m app.hash_password
"""
import getpass
import sys

from werkzeug.security import generate_password_hash


def main():
    password = getpass.getpass("Password: ")
    if not password:
        sys.exit("Password must not be empty")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    print(generate_password_hash(password))


if __name__ == "__main__":
    main()
