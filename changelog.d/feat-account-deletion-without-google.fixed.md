- Account deletion no longer fails when the Google Forms service is off, unreachable, slow or failing:
  deleting the user's stored Google credentials there is best effort (20 s timeout) and a leftover is logged
  with the user id and the provider name only, while the rest of the deletion completes.
