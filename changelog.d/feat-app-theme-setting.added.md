- A workspace's owners and admins can choose the look of the staff dashboard, `daybreak` (the
  default) or `pigment`, through `PUT /workspaces/{id}/app-theme`. The change is recorded in the
  activity log and the choice is served to members only, never to respondents. Switch:
  `APP_THEME_PIGMENT_ENABLED` (off by default, environment only): while it is off, choosing
  `pigment` answers 422 and every workspace is served `daybreak`. See `docs/app-theme.md`.
