from conftest import csrf_token


def valid_payload(**overrides):
    payload = {
        "company": "Acme",
        "role": "Product Designer",
        "status": "Applied",
        "job_url": "https://example.com/job",
        "salary": "$120k",
        "location": "Remote",
        "applied_date": "2026-01-15",
        "notes": "Applied through referral.",
    }
    payload.update(overrides)
    return payload


def post_with_csrf(client, path, payload=None, **kwargs):
    return client.post(
        path,
        data={"csrf_token": csrf_token(client), **(payload or {})},
        **kwargs,
    )


def test_dashboard_has_empty_state(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"No applications yet" in response.data
    assert b"Add your first application" in response.data


def test_dashboard_switches_between_list_and_table_views(client):
    post_with_csrf(client, "/jobs/new", valid_payload())

    list_view = client.get("/")
    table_view = client.get("/?view=table")
    invalid_view = client.get("/?view=unknown")

    assert b'class="application-list"' in list_view.data
    assert b'class="active" aria-current="page"' in list_view.data
    assert b"<table" not in list_view.data

    assert b'class="application-table"' in table_view.data
    assert b'<th scope="col">Role</th>' in table_view.data
    assert b'class="application-list"' not in table_view.data

    assert b'class="application-list"' in invalid_view.data
    assert b"<table" not in invalid_view.data


def test_responses_include_local_security_headers(client):
    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_create_edit_and_delete_flow(client):
    created = post_with_csrf(
        client,
        "/jobs/new",
        valid_payload(),
        follow_redirects=True,
    )

    assert created.status_code == 200
    assert b"Acme was added to your tracker" in created.data
    assert b"Product Designer" in created.data

    edited = post_with_csrf(
        client,
        "/jobs/1/edit",
        valid_payload(status="Interview"),
        follow_redirects=True,
    )

    assert b"Acme was updated" in edited.data
    assert b"Interview" in edited.data

    deleted = post_with_csrf(
        client,
        "/jobs/1/delete",
        follow_redirects=True,
    )

    assert b"Acme was removed" in deleted.data
    assert b"No applications yet" in deleted.data


def test_invalid_form_renders_errors_without_writing(client):
    response = post_with_csrf(
        client,
        "/jobs/new",
        valid_payload(company="", job_url="not-a-url"),
    )

    assert response.status_code == 422
    assert b"Check these fields" in response.data
    assert b"Company is required" in response.data
    assert b"Enter a complete URL" in response.data

    dashboard = client.get("/")
    assert b"No applications yet" in dashboard.data


def test_post_without_csrf_token_is_rejected(client):
    response = client.post("/jobs/new", data=valid_payload())

    assert response.status_code == 400
    assert b"form session expired" in response.data


def test_missing_job_returns_404(client):
    assert client.get("/jobs/999/edit").status_code == 404
    assert (
        client.post(
            "/jobs/999/delete", data={"csrf_token": csrf_token(client)}
        ).status_code
        == 404
    )


def test_seed_demo_command_is_guarded_from_duplicates(app):
    runner = app.test_cli_runner()

    first = runner.invoke(args=["seed-demo"])
    second = runner.invoke(args=["seed-demo"])

    assert first.exit_code == 0
    assert "Added 3 demo applications" in first.output
    assert second.exit_code == 1
    assert "already contains applications" in second.output
