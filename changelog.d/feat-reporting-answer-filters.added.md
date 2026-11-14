- Answer filters and drill-down for a form's report (behind `REPORTING_ENABLED`). A report can be
  narrowed by what responses answered: a condition on a choice, a number, a yes/no or a date, built
  from the question's own options (never free text), added on the Report page, kept in the page (never
  in the address) and saved with a view. Every card then counts the responses that met them. "Open these responses"
  in a card's table lists the responses behind a group, a page at a time, each linking to its own
  page, and, for a group the responses list can filter on, to the list with the same filter. New
  route `POST /workspaces/{id}/forms/{form_id}/report/responses` and a `filterOps` entry per
  question in `GET .../report/fields`, in English and Dutch. A card grouped by deletion request or
  feedback status cannot be combined with a condition on an answer (refused with `op_not_allowed`
  and said on the card), and the drill-down is held to the same 20,000-response cap as a query.
