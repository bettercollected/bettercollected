- Field rules, the fixes the reviews asked for before `FIELD_RULES_ENABLED` is turned on:
  a condition reads no text over 10,000 characters (it counts as empty), a condition on an
  internal question is not active on the server either, values that set each other in a circle
  have none (the page used to rewrite them for ever), an expression nested hundreds of levels
  deep is refused instead of failing with a server error, an operation no longer checks every
  rule of the form twice, and with the flag off moving a question that has rules to another
  page or group no longer blocks the builder's autosave. Replacing or removing a choice
  question's options says which rules went with them.
- The respondent page decides field rules from the answers as they will be submitted (a skipped
  page and a hidden group left out), no longer keeps a stale state after an answer is cleared,
  shows the server's "required" message whatever the rules say, shows a dash instead of the
  prompt in an empty read-only question, gives locked dropdowns and date pickers read-only
  semantics, lets the arrow keys move between the options of a locked yes/no or choice
  question, and stores question ids such as `__proto__` like any other. Headings, paragraphs
  and dividers are not variables in the browser either. The Dutch "filled in for you" message
  says "je".
