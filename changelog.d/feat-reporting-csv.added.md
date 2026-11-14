- Download a card of a form's report as a CSV (behind `REPORTING_ENABLED`). The Report page offers
  "Download as CSV" (in Dutch "Downloaden als CSV") on each card to people who may export responses
  (`response.export`). The file is the card's table (group, responses, share of answered, one column
  per measure) under a few lines saying what it is: the form, the card, the filters in words, the time
  zone and when it was made. It is built on request and never stored, text a spreadsheet would run
  as a formula is neutralised, and each download is written to the workspace's activity log
  (`report_exported`: form, format, number of groups; never the card or a figure) before the file is
  handed out. New route `POST /workspaces/{id}/forms/{form_id}/report/export`, limited to 10 downloads
  per user and form per hour.
