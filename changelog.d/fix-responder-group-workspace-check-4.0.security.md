- Responder groups: a form's responder groups can only be set to groups of the form's workspace.
  Linking another workspace's group to a form, which then listed that group's name and email
  pattern with the form, is refused (404, as for an unknown group) and links nothing, even when
  the other ids in the request are the workspace's own. Removing a group from a form likewise
  requires a group of the workspace, except a link to another workspace's group made before this
  check, which can be removed. On a form held by several workspaces, each sets and removes only
  its own groups. A workspace's group listing skips a link to another workspace's form instead of
  failing.
