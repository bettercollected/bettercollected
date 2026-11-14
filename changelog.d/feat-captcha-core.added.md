- Automatic spam check on a form's response submit, behind `CAPTCHA_ENABLED` (off by
  default): the respondent's browser does a small proof-of-work calculation in the
  background, in a Web Worker after the first interaction (no puzzle, no cookie, no
  third party, nothing stored about the respondent). A stateless signed challenge
  (`POST /workspaces/{id}/captcha/challenge`, valid 15 minutes, bound to the form
  and a day-salted tag of the network) is solved in the `X-BC-Captcha` header and
  spent once. Difficulty starts at 17 bits (`API_CAPTCHA_BASE_BITS_SUBMIT`), rises for
  a client that asks or fails a lot, for a busy form and with the operator's
  `API_CAPTCHA_DIFFICULTY_BOOST`, never past 20, and is 3 bits lower for a signed-in
  respondent (and good only for a signed-in submit). Creators can turn it off per
  form in Settings, Respondent experience. The Submissions API with a key is not
  affected. See `docs/captcha.md`.
