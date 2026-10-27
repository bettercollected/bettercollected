- The Open Formulieren import also reads exports from the 3.x series (3.2 to 3.5, next to 4.0). The same limits and
  the same rule apply: nothing in the file is run, rendered or fetched. An appointment form of a 3.x export is
  reported as such, and a rule that only starts from a given step (an option of the old logic evaluation) is dropped
  and reported instead of acting earlier than the original. Exports of 3.0, 3.1 and releases after 4.0 are still
  refused with the release named. See `docs/open-formulieren.md`.
