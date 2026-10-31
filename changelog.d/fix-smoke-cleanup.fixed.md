- The smoke test now deletes every form it creates, also when a step fails, and
  only those forms (by the ids it was given). A key without `forms:delete` no
  longer hides this: the run still passes, with a warning that names the scope
  and the forms left behind. A new one-off cleanup (`python -m smoke.cleanup`,
  or the production smoke workflow's `cleanup` choice) lists, and with
  `--delete` removes, the forms earlier runs left behind.
