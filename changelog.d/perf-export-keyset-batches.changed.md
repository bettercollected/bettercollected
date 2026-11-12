- A response export reads a form in batches that each seek to where the last one ended
  (a keyset on the response time and id, in the order of the index of workspace, form and
  time), where each batch used to read and sort the whole form again. Some batches took
  150 to 250 ms against 20 ms; a pass no longer has them, and a batch costs its own rows
  however large the form is. Counting the responses an export holds no longer reads every
  document. Rows come out oldest first by response time, ties by id; this was id order,
  which differs only for two responses stored in the same second by different processes.
