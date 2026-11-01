- Webhooks, email actions and registrations can now send the answers to time, day, currency, date
  range and tags questions. They went out as nothing before (the questions were greyed out as
  "cannot be sent yet"). Each is sent in the shape the public API answers it in: `"HH:MM"`, a date,
  `{"code": "EUR", "amount": "12.50"}` (the amount stays a decimal string), `{"start": …, "end": …}`
  and a list of strings. A test event carries made-up values of the same shapes.
