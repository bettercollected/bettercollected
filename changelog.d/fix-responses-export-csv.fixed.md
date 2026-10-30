- The CSV export of responses now has the submission time (UTC, ISO 8601), the response id
  and one column per hidden field, at the end of each row, so existing columns keep their
  place. Responders without an email show as "Anonymous" instead of "- -", and a multi-select
  answer is joined with "; ". Phone numbers and plain numbers no longer get a leading
  apostrophe; any other text starting with =, +, -, @, a tab or a carriage return still does.
