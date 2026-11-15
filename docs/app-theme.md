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
* choosing the theme the workspace is served (`daybreak`) is no change: it passes and
  nothing is stored or recorded;
* every workspace is served `daybreak`, whatever it has stored. A stored `pigment` is kept,
  neither enforced nor shown, and is served again when the setting is turned on;
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

## In the dashboard

* **The attribute.** The admin portal's layout and the creator's sign-in screen wrap their pages in
  `data-app-theme="daybreak"` (the theme variables of `tailwind.css`); the respondent sign-in does not. Inside a workspace, the
  workspace layout adds one more element, `AppThemeScope`
  (`webapp/src/components/app-theme/app-theme-scope.tsx`), whose value is the workspace's
  `appTheme`: `pigment` when the member answer says so, `daybreak` for anything else. Custom
  properties are inherited, so a workspace on `pigment` has Daybreak's values wherever no Pigment
  block exists yet, and the app never renders without colours.
* **No flash.** The workspace layout reads the workspace on the server, so the first HTML already
  carries the right value. Nothing is read from a cookie, local storage or a script. After a
  change in the Appearance card the store's workspace changes and the attribute follows at once,
  without a reload. A later answer that replaces the workspace without the theme (a rename, a
  logo) keeps the one the workspace has.
* **Respondents.** Only the admin portal layout, the creator's sign-in and `AppThemeScope` write the attribute, and only
  the workspace layout uses the scope; a test fails if any other file does. Form pages on the
  form domain and a custom domain, and the responder portal, never carry it.
* **The Appearance card.** On the workspace Themes page, for a member with `workspace.manage`,
  and only while the permissions answer says `appThemeEnabled: true`. With the switch off the
  card is not rendered and nothing is requested.
