- **The Pigment look can be turned on by an instance admin.** The setting `APP_THEME_PIGMENT_ENABLED` is now an
  ordinary setting in the admin portal's settings (off by default; the environment still works, and an
  environment value wins over the stored one, as for the other settings). One switch covers the Pigment app theme a
  workspace can choose (Themes page, Appearance) and the Pigment form preset with its lettered answer keys. A change
  in the portal is picked up when the backend restarts. Turning it off again deletes nothing: a workspace that chose
  Pigment is shown the default look until it is turned on again, and forms that wear the preset keep working.
