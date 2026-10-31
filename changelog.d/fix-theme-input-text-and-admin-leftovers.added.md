- Themes have a separate colour for the answers typed in the white input
  boxes (`inputText`, a `#rrggbb` colour; Answer text in the theme editors,
  also in form spec v1, the API and saved themes). A dark custom theme can now
  keep light questions on a dark page with dark, readable answers. It is
  checked on white like the other colours (4.5:1), and where it is left out
  the answers keep the questions' colour, so no existing theme changes. The
  suggested fix for a dark page now sets the answer text instead of turning
  the whole page pale.
