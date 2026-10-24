- Expired deletion tombstones are pruned after a delete has committed, in a transaction of their own,
  instead of inside the delete's transaction, so a delete never waits on pruning or holds its locks,
  and a failed prune never undoes a delete.
