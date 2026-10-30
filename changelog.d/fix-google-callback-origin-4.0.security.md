- Connecting Google Sheets to a form: the consent popup now hands its result only to the
  dashboard origin, and only the code, the state or Google's error. The dashboard accepts
  it only from the popup it opened, on the dashboard origin. The connection's state is
  tied to the session that started it, expires after an hour and is accepted once. A
  connection started before the upgrade and finished after it is refused: start it again.
- An imported form's link to its original (opened or framed when the form is set to show
  the original) is kept only when it is an http(s) address, and the respondent page opens
  or frames nothing else.
