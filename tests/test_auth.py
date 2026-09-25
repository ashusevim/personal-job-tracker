from conftest import TEST_PASSWORD, csrf_token


def login(client, password=TEST_PASSWORD, next_url="", **kwargs):
    token = csrf_token(client)
    return client.post(
        "/login",
        data={
            "csrf_token": token,
            "password": password,
            "next": next_url,
        },
        **kwargs,
    )


def test_protected_pages_redirect_to_login(anonymous_client):
    dashboard = anonymous_client.get("/")
    create_page = anonymous_client.get("/jobs/new?view=table")

    assert dashboard.status_code == 302
    assert dashboard.headers["Location"] == "/login?next=/"
    assert create_page.status_code == 302
    assert create_page.headers["Location"] == "/login?next=/jobs/new?view%3Dtable"


def test_health_check_is_public(anonymous_client):
    response = anonymous_client.get("/healthz")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_wrong_password_is_rejected_without_details(anonymous_client):
    response = login(anonymous_client, password="incorrect-password")

    assert response.status_code == 401
    assert b"The master password is incorrect." in response.data
    assert b"hash" not in response.data.lower()


def test_correct_password_signs_in_and_preserves_safe_next(anonymous_client):
    response = login(anonymous_client, next_url="/?view=table", follow_redirects=True)

    assert response.status_code == 200
    assert b"Your applications" in response.data
    assert b"Sign out" in response.data


def test_external_next_url_is_rejected(anonymous_client):
    response = login(anonymous_client, next_url="https://attacker.example/steal")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_logout_requires_csrf_and_clears_session(client):
    missing_token = client.post("/logout")
    still_authenticated = client.get("/")
    logged_out = client.post("/logout", data={"csrf_token": csrf_token(client)})

    assert missing_token.status_code == 400
    assert still_authenticated.status_code == 200
    assert logged_out.status_code == 302
    assert "/login" in logged_out.headers["Location"]
    assert client.get("/").status_code == 302


def test_password_change_invalidates_existing_sessions(app, client):
    from werkzeug.security import generate_password_hash

    assert client.get("/").status_code == 200
    app.config["PASSWORD_HASH"] = generate_password_hash("a-brand-new-master-password")

    assert client.get("/").status_code == 302


def test_login_is_rate_limited(anonymous_client):
    for _ in range(5):
        assert login(anonymous_client, password="wrong").status_code == 401

    blocked = login(anonymous_client, password=TEST_PASSWORD)

    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"]
    assert b"Too many attempts" in blocked.data


def test_successful_login_clears_failures(app, anonymous_client):
    from job_tracker.auth import client_fingerprint, retry_after_seconds

    for _ in range(3):
        login(anonymous_client, password="wrong")

    assert login(anonymous_client).status_code == 302
    with app.app_context():
        assert retry_after_seconds(client_fingerprint("127.0.0.1")) == 0
