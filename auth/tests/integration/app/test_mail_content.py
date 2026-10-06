"""Verification-code and invitation mails (#761): the From display name is
always ORGANIZATION_NAME and the subject fixed wording; a workspace title,
chosen by any workspace owner, appears only in the body, on one line, capped
and HTML-escaped. A caller-supplied image is shown only from this instance's
storage."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auth.app.services import mail_service
from auth.app.services.auth_service import AuthService
from auth.app.services.mail_service import (
    MAX_TITLE_LENGTH,
    MailService,
    sender_name,
    storage_image_url,
    avatar_image_url,
)
from auth.app.services.user_service import UserService
from auth.config import settings

STORAGE = "https://storage.example.com/bettercollected/public/"
IMAGE = STORAGE + "20260101000000_profile.png"
HOSTILE = '"><script>alert(1)</script><a href="https://evil.example.com">PayPal</a>'
SPOOF = "PayPal Security\r\nBcc: victim@example.com\nSubject: Reset"


@pytest.fixture(autouse=True)
def instance(monkeypatch):
    monkeypatch.setattr(settings, "ORGANIZATION_NAME", "BetterCollected")
    monkeypatch.setattr(settings, "MAIL_IMAGE_URL_PREFIXES", STORAGE)
    monkeypatch.setattr(settings, "CLIENT_ADMIN_URL", "https://admin.example.com")


def _repo(**overrides):
    return SimpleNamespace(
        get_user_by_email=AsyncMock(return_value=None),
        save_otp_user=AsyncMock(),
        **overrides,
    )


async def otp_mail(workspace_title, workspace_profile_image=""):
    """The message a verification-code request would send."""
    service = AuthService(None, _repo(), None)
    with patch("auth.app.services.auth_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await service.send_otp_to_mail(
            receiver_mail="someone@example.com",
            workspace_title=workspace_title,
            workspace_profile_image=workspace_profile_image,
            creator=False,
        )
    mail.assert_called_once_with()  # no way to pass a sender name
    return mail.return_value.send_message.await_args.args[0]


async def invitation_mail(workspace_title, profile_image=None, first_name="Ann"):
    inviter = SimpleNamespace(
        first_name=first_name, email="owner@example.com", profile_image=profile_image
    )
    repo = SimpleNamespace(get_user_by_id=AsyncMock(return_value=inviter))
    with patch("auth.app.services.user_service.MailService") as mail:
        mail.return_value.send_message = AsyncMock()
        await UserService(repo, None).send_mail_to_user_for_invitation(
            workspace_title=workspace_title,
            workspace_name="acme",
            role="COLLABORATOR",
            email="new@example.com",
            token="invitation-token",
            inviter_id="5f0000000000000000000000",
        )
    mail.assert_called_once_with()
    return mail.return_value.send_message.await_args.args[0]


class TestSenderName:
    def test_from_display_name_is_the_organization_name(self, monkeypatch):
        with patch.object(mail_service, "ConnectionConfig") as config, patch.object(
            mail_service, "FastMail", MagicMock()
        ):
            MailService()
        assert config.call_args.kwargs["MAIL_FROM_NAME"] == "BetterCollected"

    def test_organization_name_is_single_line(self, monkeypatch):
        monkeypatch.setattr(settings, "ORGANIZATION_NAME", "Better\r\nCollected")
        assert sender_name() == "Better Collected"

    def test_mail_service_takes_no_sender_name(self):
        with pytest.raises(TypeError):
            MailService(organization_name="PayPal")


class TestVerificationCodeMail:
    @pytest.mark.asyncio
    async def test_subject_is_fixed_and_title_only_in_body(self):
        message = await otp_mail("Acme Hiring")
        assert message.subject == "Your BetterCollected verification code"
        assert "Acme Hiring via BetterCollected" in message.body

    @pytest.mark.asyncio
    async def test_title_is_single_line_and_capped(self):
        message = await otp_mail(SPOOF + " x" * 500)
        assert "PayPal" not in message.subject
        assert "\r" not in message.subject and "\n" not in message.subject
        assert "PayPal Security Bcc: victim@example.com Subject: Reset" in message.body
        assert "Bcc: victim@example.com\n" not in message.body
        assert ("x " * MAX_TITLE_LENGTH) not in message.body
        assert "…" in message.body  # capped

    @pytest.mark.asyncio
    async def test_title_is_escaped(self):
        message = await otp_mail(HOSTILE)
        assert "<script>" not in message.body
        assert 'href="https://evil.example.com"' not in message.body
        assert "&lt;script&gt;" in message.body

    @pytest.mark.asyncio
    async def test_the_products_own_name_is_not_repeated(self):
        message = await otp_mail("Better Collected")
        assert " via " not in message.body

    @pytest.mark.asyncio
    async def test_an_empty_title_still_sends(self):
        message = await otp_mail(None)
        assert message.subject == "Your BetterCollected verification code"
        assert "None" not in message.body and " via " not in message.body

    @pytest.mark.asyncio
    async def test_an_over_long_image_is_dropped_not_refused(self):
        message = await otp_mail("Acme", IMAGE + "x" * 5000)
        assert message.body.count("<img") == 2  # only the two product logos

    @pytest.mark.asyncio
    async def test_storage_image_is_shown(self):
        message = await otp_mail("Acme", IMAGE)
        assert f'src="{IMAGE}"' in message.body
        assert message.body.count("<img") == 3  # the workspace image and two logos

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "image",
        [
            "https://evil.example.com/logo.png",
            "https://storage.example.com.evil.example.com/bettercollected/public/x.png",
            "https://storage.example.com/other-bucket/public/x.png",
            "https://storage.example.com/bettercollected/public/../private/x.png",
            "https://user:pw@storage.example.com/bettercollected/public/x.png",
            "javascript:alert(1)",
            "data:image/png;base64,AAAA",
            IMAGE + '" onerror="alert(1)',
            IMAGE + " onerror=alert(1)",
            "",
        ],
    )
    async def test_other_images_are_dropped(self, image):
        message = await otp_mail("Acme", image)
        assert message.body.count("<img") == 2  # only the two product logos
        assert "onerror" not in message.body
        assert "evil.example.com" not in message.body


class TestInvitationMail:
    @pytest.mark.asyncio
    async def test_subject_is_fixed_and_title_only_in_body(self):
        message = await invitation_mail("PayPal Security")
        assert (
            message.subject == "You have been invited to a workspace on BetterCollected"
        )
        assert "PayPal" not in message.subject
        assert "PayPal Security" in message.body
        assert 'href="https://admin.example.com/acme/invitation/invitation-token"' in (
            message.body
        )

    @pytest.mark.asyncio
    async def test_title_and_inviter_are_single_line_and_escaped(self):
        message = await invitation_mail(SPOOF + HOSTILE, first_name="Ann\r\n<b>x</b>")
        assert "\r" not in message.subject and "\n" not in message.subject
        assert "<script>" not in message.body and "<b>x</b>" not in message.body
        assert "&lt;script&gt;" in message.body
        assert "PayPal Security Bcc: victim@example.com Subject: Reset" in message.body

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "image",
        [
            "https://lh3.googleusercontent.com/a/photo=s96-c",
            STORAGE + "avatar.png",
        ],
    )
    async def test_inviter_avatar_from_allowed_hosts(self, image):
        message = await invitation_mail("Acme", profile_image=image)
        assert f'src="{image}"' in message.body

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "image",
        [
            "https://tracker.example.com/pixel.png",
            "http://lh3.googleusercontent.com/a/photo",
            "https://lh3.googleusercontent.com.evil.example.com/a/photo",
            "javascript:alert(1)",
        ],
    )
    async def test_other_inviter_avatars_show_the_initial(self, image):
        """An avatar loads when the mail is opened: any other host would learn
        the recipient's IP."""
        message = await invitation_mail("Acme", profile_image=image)
        assert image not in message.body
        assert re.search(r">\s*A\s*</div>", message.body)  # Ann's initial

    def test_avatar_hosts_are_configurable(self, monkeypatch):
        monkeypatch.setattr(
            settings, "MAIL_AVATAR_URL_PREFIXES", "https://avatars.example.com/u/"
        )
        assert avatar_image_url("https://avatars.example.com/u/1.png")
        assert avatar_image_url("https://lh3.googleusercontent.com/a/x") is None


def test_image_url_checks():
    assert storage_image_url(IMAGE) == IMAGE
    assert storage_image_url(None) is None
    assert (
        storage_image_url("ftp://storage.example.com/bettercollected/public/a") is None
    )
    assert storage_image_url(IMAGE + "x" * 5000) is None


def test_otp_send_takes_any_title_length(app_runner):
    """The backend does not cap titles: a long one is capped in the body, an
    over-long image dropped; neither fails the send (#761)."""
    with patch.object(AuthService, "send_otp_to_mail", new_callable=AsyncMock) as send:
        response = app_runner.get(
            "auth/otp/send",
            params={
                "receiver_email": "someone@example.com",
                "creator": False,
                "workspace_title": "t" * 3000,
                "workspace_profile_image": IMAGE + "x" * 3000,
            },
        )
    assert response.status_code == 200, response.text
    assert len(send.await_args.kwargs["workspace_title"]) == 3000


def test_otp_send_needs_no_workspace_values(app_runner):
    """The creator sign-in has no workspace: title and image are optional."""
    with patch.object(AuthService, "send_otp_to_mail", new_callable=AsyncMock) as send:
        response = app_runner.get(
            "auth/otp/send",
            params={"receiver_email": "someone@example.com", "creator": True},
        )
    assert response.status_code == 200, response.text
    assert send.await_args.kwargs["workspace_title"] is None
