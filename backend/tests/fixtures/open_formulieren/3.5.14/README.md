# Open Formulieren 3.5.14 fixtures

Archives (`*.zip`) used by `tests/app/open_formulieren/test_importer_3x.py` and the other tests that take
`FIXTURE_NAMES_3X`. They are **our own exports** of **synthetic** forms made on 2026-10-27 in a throwaway local
instance of Open Formulieren 3.5.14 (image `openformulieren/open-forms:3.5.14`, tag commit
`92a999b1e2527d034a3cf84401e15f8113c585be`, its own database, ports bound to 127.0.0.1, no real data). None of them
comes from Open Formulieren's test data or from any production system, and none contains a secret, token or service
credential. Instance links inside them point at the placeholder host `localhost`, as their export writes them; the
`of_git_sha` in `_meta.json` is the public commit of the release.

How they were made: the forms were created through the instance's REST API (the component JSON follows the form
builder's shapes; it was not made by clicking in the 3.5 designer), then exported with the product's own export
endpoint. The content of the first six is the content of the 4.0.6 fixtures one level up, so the two series can be
compared; the last two exist only for 3.x.

| File | Content |
|---|---|
| `all-components.en.zip` | three steps with every common component type, simple show/hide conditions, per-component English and Dutch texts, retention and consent settings, one generic JSON registration backend |
| `all-components.nl.zip` | the same form exported with the Dutch interface language |
| `logic-variables.en.zip` | JSON logic rules (property, disable-next, step applicability, variable actions), user-defined variables, a component that carries legacy script keys (inert text; nothing evaluates them) |
| `signin-prefill-payment.en.zip` | a sign-in plugin option, a payment plugin, prefill settings |
| `special-components.en.zip` | components that need identity-register or map services, an email registration backend |
| `appointment.en.zip` | an appointment form: 3.x has no form `type`, the form says `appointment_options.is_appointment` |
| `legacy-logic.en.zip` | a form on the old logic evaluation (`new_logic_evaluation_enabled: false`) with a rule that only starts from a given step (`trigger_from_step`) and an ordinary show/hide rule |
| `pre35-shapes.en.zip` | components in the shapes releases before 3.5 wrote (empty strings in `conditional`, `datePicker` limits and `minTime`/`maxTime`; `errors`, a `defaultValue` among the translations, a number condition written as text), injected through the API on purpose: the instance stores components verbatim |

Notes

- The legacy script keys in `logic-variables.en.zip` and the older shapes in `pre35-shapes.en.zip` were added through
  the API on purpose, so the importer meets them (the 3.5 designer does not write them).
- Regenerate the golden files in `../golden/3.5.14/` with
  `OF_UPDATE_GOLDEN=1 uv run pytest tests/app/open_formulieren/test_importer_3x.py` and read the diff.
- Format reference and the differences from 4.0: `docs/open-formulieren.md` ("Versions").
