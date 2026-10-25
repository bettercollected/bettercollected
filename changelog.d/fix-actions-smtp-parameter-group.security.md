- A mail action's SMTP settings (server, port, user name, password and sender) now come from one
  side only: either all from the workspace or form, or all from the instance's defaults. Before,
  a workspace that changed only the server had the instance's SMTP login sent to its own server.
  Settings an override leaves out stay empty and the mail is refused with a message naming them.
