- A drawn signature's image is now stored encrypted with the response keyset, bound to its
  workspace, form, response and question, and is served only through an authorised route
  (`no-store`, `nosniff`, `image/png`) for people who may read the response, instead of a
  link to the stored file. An image stored before this change is not served.
