import base64


def basic_auth_headers(
    username: str = "test-admin", password: str = "test-admin"
) -> dict:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}
