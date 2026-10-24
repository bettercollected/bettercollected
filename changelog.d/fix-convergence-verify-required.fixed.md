- Mirror convergence is capped as a whole, at twice the mirror timeout and including its writes, so a
  hung store can no longer hold a request longer; a copy cut off by the cap is still re-checked. A copy
  whose re-check failed is recorded in the outbox as `CopyUnverified`, and only a clean full `verify`,
  not `reconcile`, resolves it.
