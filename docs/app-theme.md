# App theme

The look of the staff dashboard is a setting of the workspace: `daybreak` (the default) or
`pigment`. It never reaches a respondent: the form pages, the sign-in screens and everything a
respondent or a visitor of a workspace's custom domain sees keep the look the form's own theme
gives them.

## The server setting

`APP_THEME_PIGMENT_ENABLED` (`true` / `false`, default `false`, set in the environment and not
in the admin portal until it is released; see the [settings inventory](settings-inventory.md)).
It is read by the backend only.

While it is **off**:

* choosing `pigment` answers `422` with the code `app_theme_disabled`;
* `daybreak` is never refused. It is compared with what the workspace has **stored**, not with
  what it is served: when the workspace has `pigment` stored (the setting was on, then turned
  off) choosing `daybreak` is a change, stored and recorded, so `pigment` does not come back
  when the setting is turned on again; when it has nothing or `daybreak` stored it is no change
  and nothing is stored or recorded;
* every workspace is served `daybreak`, whatever it has stored. A stored `pigment` is kept,
  neither enforced nor shown, and is served again when the setting is turned on (unless an
  admin chose `daybreak` in the meantime);
* the permissions answer (`GET /workspaces/{id}/permissions`) says `appThemeEnabled: false`.

While it is **on**, the owners and admins of a workspace can choose between the two themes.

## Choosing a theme

`PUT /workspaces/{id}/app-theme` with the body `{"appTheme": "daybreak"}` or
`{"appTheme": "pigment"}`. Nothing else is accepted: any other value, a missing value, a
different casing and any extra key answer `422`. The answer is `{"appTheme": "..."}`, the theme
the workspace is served now.

* **Who:** the `workspace.manage` permission (Owner and Admin). Everyone else gets `403`; a
  person who is not signed in gets `401`. The refusal for a switched-off setting comes after
  the permission check.
* **Recorded:** every change writes one entry to the workspace's [activity log](audit-log.md)
  (`app_theme_changed`: who, the new theme and the one it replaced, both as the two theme
  names), before the change is made. When it cannot be written the change is refused (`503`
  `audit_unavailable`).
* **No migration:** the choice is one more field on the workspace's stored document, like the
  workspace default of the [spam check](captcha.md). A workspace that never chose has none and
  is served `daybreak`.

## Who is served the theme

The workspace answer the dashboard already fetches (`GET /workspaces?workspace_name=...` or
`?custom_domain=...`) carries `appTheme` for a signed-in member with dashboard access, and only
for them. The answer to a visitor, a respondent or a signed-in person who is not a member has
no `appTheme` key, and neither has any other workspace answer (the caller's own list, the
workspace's patch answer): the theme is not part of the public workspace.
