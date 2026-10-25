- Single sign-on: when it is switched on but not fully set up, the workspace
  single sign-on and directory sync pages now ask workspace admins to contact
  the instance's administrator or support team, with the setup guide as a
  secondary link for people running their own instance (English and Dutch).
- Admin portal: the Health page and the overview read a stored `SSO_ENABLED`
  text value ("true", "1", "yes", "on" in any case) the same way the services
  do, so they no longer show single sign-on as off while it is on.
