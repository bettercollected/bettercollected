- A form saved with a calculation or rule formula nested hundreds of levels
  deep now gets a clear 422 instead of an internal "circular reference" error.
- A read-only question left empty no longer has its placeholder dash read out
  by screen readers, and the logic condition rows have accessible names.
- With field rules switched off, changing the type of a question that already
  has rules no longer makes every save fail: a type that still takes the rule
  keeps it, and one that cannot carry rules drops them.
