- The "Optional" and "Read only" labels beside a question follow the form's theme: on a dark
  custom theme they are a light colour instead of a fixed dark grey that was hard to read. The
  colour is derived from the theme (the questions' ink softened towards the page, never under
  4.5:1), and the theme contrast check, in the builder and on the server, now measures it.
- The enter and exit animations of dialogs, side sheets, menus, popovers and select lists
  were silently doing nothing since the move to Tailwind 4 (their classes had no stylesheet);
  they run again, and not at all for people who ask their device for reduced motion. A few
  misspelled class names in the dashboard and the dialogs (`tex-black-800`, `fap-2`,
  `sm:w-auo`, `px-auto`, `space-between`) are corrected.
