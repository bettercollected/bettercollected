- Reports: a pass over answers is stopped after 30 seconds (`503` `report_timeout`) and gives its
  places back; passes in flight are counted across all replicas (the shared rate limiter), not only
  per process; a stored number too large or strange to add up leaves that value empty with the
  `unreadable_answers` notice instead of failing the query; a question a later form version makes
  internal is no longer offered in reports.
