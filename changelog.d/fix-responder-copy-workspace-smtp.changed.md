- **Upgrade note (mail):** mails no longer show the workspace as sender or in the subject. The
  sign-in code, invitation and submission-update mails ("Update on your submission" included) are
  sent in the instance's name (`ORGANIZATION_NAME`) with fixed subjects; the workspace, form and
  inviter appear in the body only. Tell your users if they filter or search their mail by workspace
  name. The one exception is a respondent's copy sent by an action through the workspace's own SMTP
  server, where the workspace really is the sender.
- **Upgrade note (self-hosting, mail images):** a workspace's logo in the sign-in code mail (and an
  inviter's avatar from your storage in the invitation) is shown only when its address starts with
  one of `MAIL_IMAGE_URL_PREFIXES` (auth; admin portal settings, mail section; comma-separated).
  The default is the hosted Wasabi bucket's `public/` prefix, so a stack on other storage must set
  it to its own public storage, `<AWS_PUBLIC_URL or AWS_ENDPOINT_URL>/<bucket>/public/`; otherwise
  those mails show the workspace's initial instead of its logo.
