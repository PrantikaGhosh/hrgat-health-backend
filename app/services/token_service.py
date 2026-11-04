import uuid

AUTH_TOKEN_VALIDITY_DAYS = 7


def generate_auth_token() -> str:
    return str(uuid.uuid4())
