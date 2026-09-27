"""Download links for uploaded answer files point at the key the file is
stored under (#465: links signed for the bare file id gave NoSuchKey)."""

from backend.app.container import container


class FakeStore:
    def __init__(self, keys):
        self.keys = set(keys)
        self.signed = []

    def check_if_key_exists(self, key, bucket=None):
        return key in self.keys

    def generate_presigned_url(self, key, bucket=None):
        self.signed.append(key)
        return f"https://files.example/{key}?signed"


def service_with(monkeypatch, keys):
    service = container.form_response_service()
    store = FakeStore(keys)
    monkeypatch.setattr(service, "_aws_service", store)
    return service, store


def test_a_submitted_file_is_signed_in_its_response_folder(monkeypatch):
    key = "private/ws/form/resp/file-1"
    service, store = service_with(monkeypatch, [key, "file-1"])
    url = service.file_download_url("ws", "form", "resp", "file-1")
    assert store.signed == [key] and url.endswith(f"{key}?signed")


def test_older_uploads_are_found_where_they_were_stored(monkeypatch):
    service, store = service_with(monkeypatch, ["private/file-2"])
    assert service.file_download_url("ws", "form", "resp", "file-2")
    assert store.signed == ["private/file-2"]
    service, store = service_with(monkeypatch, ["file-3"])
    assert service.file_download_url("ws", "form", "resp", "file-3")
    assert store.signed == ["file-3"]


def test_a_missing_file_gets_no_link_instead_of_a_broken_one(monkeypatch):
    service, store = service_with(monkeypatch, [])
    assert service.file_download_url("ws", "form", "resp", "gone") == ""
    assert service.file_download_url("ws", "form", "resp", "") == ""
    assert store.signed == []


def test_an_id_that_names_another_key_gets_no_link(monkeypatch):
    victim = "private/other-ws/form/imports/abc/source.pdf"
    service, store = service_with(
        monkeypatch, [victim, "private/" + victim, "other-ws/form/x"]
    )
    for crafted in (victim, "other-ws/form/x", "..", ".", "a" * 129, None, 7):
        assert service.file_download_url("ws", "form", "resp", crafted) == ""
    assert store.signed == []


async def test_uploads_with_a_crafted_file_id_are_refused(
    client, workspace, published_form, monkeypatch
):
    import json

    from backend.app.services.workspace_form_service import WorkspaceFormService

    uploads = []

    async def fake_upload(self, *args, **kwargs):
        uploads.append(args)
        return args[1] if len(args) > 1 else kwargs.get("response")

    monkeypatch.setattr(
        WorkspaceFormService, "upload_files_to_s3_and_update_url", fake_upload
    )
    refused = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{published_form.form_id}/response",
        data={
            "response": json.dumps({"answers": {}}),
            "file_field_ids": ["f"],
            "file_ids": ["other-ws/form/imports/abc/source.pdf"],
        },
        files={"files": ("a.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert refused.status_code == 422, refused.text
    assert uploads == []
