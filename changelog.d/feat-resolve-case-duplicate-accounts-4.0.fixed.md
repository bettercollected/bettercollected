- **Deleting an account no longer deletes another account's Google Forms connection.** The Google
  Forms integration removed every stored credential with the deleted account's email address, so
  a second account connected to the same Google account lost its connection too. It now removes
  the account's own credentials by user id, and by email only the legacy ones that have no user id.
