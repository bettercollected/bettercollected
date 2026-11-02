- Forms can be embedded in other websites. A workspace lists the sites that may show its
  forms in a frame (`https://` sites, or `https://*.` plus a domain of its own; none by
  default), and the form pages are served with that list as their `frame-ancestors`, on a
  custom domain as well. The share dialog gets an Embed tab with the code to paste: a small
  script (`/embed.js`, no dependencies) that shows the form in an accessible frame, keeps the
  frame as tall as the form's page needs and tells the host page only that the form loaded,
  how tall it needs to be and that it was submitted, never an answer or a page number.
  Signing in opens in a new tab. It is behind `FORM_EMBED_ENABLED`, which is off by default;
  while it is off the pages are served as before. See `docs/embed.md`.
