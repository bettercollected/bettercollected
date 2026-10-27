# Generic JSON registration fixtures

Request bodies sent by a real Open Formulieren 4.0.6 (`openformulieren/open-forms:4.0.6`, the "Generic JSON
registration" plugin, `json_dump`) running on a throwaway local instance, captured by a local capture server on
2026-10-27. The form (`of3-capture`) and the answers are synthetic and were made for this purpose: a first name, a
remark, an email address, an age, a date, a radio question, a selectboxes question, a checkbox, one file question
(one file) and a repeating group ("editgrid") with two items. Nothing here comes from a real person or organisation.

- `generic_json_full.json`: every question answered, file contents as base64 (selectboxes sent as a list).
- `generic_json_unanswered.json`: only the first name given; shows how an unanswered question is sent.
- `generic_json_selectboxes_as_object.json`: the same form with the selectboxes question not turned into a list.

They are parsed JSON re-indented for reading (the original bytes used Python's default separators). The golden test
(`tests/app/registration/test_body_golden.py`) compares our body for an equivalent form with these, key by key, and
lists every deliberate difference.
