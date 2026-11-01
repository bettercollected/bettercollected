- The address lookup no longer answers for a form that is closed, not open yet, full or hidden, nor for a
  private form unless the signed-in respondent is admitted by one of its responder groups (the same 404 as
  an unknown form, nothing is sent to the address service). Its in-memory tables now drop the entry used
  longest ago instead of emptying when full, and one process makes at most 10 calls a second and 300 a
  minute to the address service (60 a minute for one form); past that the respondent types the address.
