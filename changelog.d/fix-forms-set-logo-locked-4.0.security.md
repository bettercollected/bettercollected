- Forms served from Postgres (`DB_WRITE_MODE__forms=postgres_primary_dual` and beyond) no longer
  undo a change made at the same time: setting or removing a form's logo changes only the logo
  (as MongoDB's update of the logo alone does), and the builder's save, an action's secret, a
  form's workspace settings and a template's content are applied to the stored copy under its
  row lock, instead of saving a copy read before. Such a write no longer brings back a removed
  action's encrypted credentials, undoes an autosave, or stores a deleted form, form link or
  template again.
