- A failure while an email action's rate counters were written no longer lets the retry
  send the mail unchecked: a delivery is marked as counted only after its counters went
  up, so the retry counts again (at worst one extra count) instead of skipping the limits.
  A counter that fails half way gives back what the earlier ones admitted.
