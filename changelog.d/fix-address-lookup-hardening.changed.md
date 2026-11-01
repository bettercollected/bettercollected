- The address lookup no longer answers for a form that is closed, not open yet, full, private or hidden
  (the same 404 as an unknown form, nothing is sent to the address service). Its in-memory tables now
  drop the entry used longest ago instead of emptying when full, and one process makes at most 10 calls
  a second and 300 a minute to the address service; past that the respondent types the address.
