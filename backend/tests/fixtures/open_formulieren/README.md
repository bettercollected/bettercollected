# Open Formulieren fixtures

Archives (`*.zip`) used by `tests/app/open_formulieren/`. They are **our own exports** of **synthetic**
forms made on 2026-10-27 in a throwaway local instance of Open Formulieren 4.0.6 (image
`openformulieren/open-forms:4.0.6`, own database, ports bound to 127.0.0.1, no real data). None of them comes from
Open Formulieren's test data or from any production system, and none contains a secret, token or service credential.
Instance links inside them point at the placeholder host `localhost`, as their export writes them.

How they were made: the forms were created through the instance's REST API (the component JSON follows the form
builder's default shapes), then exported with the product's own export endpoint, and each archive was imported back
into the same instance to confirm it is a valid archive.

| File | Content |
|---|---|
| `all-components.en.zip` | three steps with every common component type, simple show/hide conditions, per-component English and Dutch texts, retention and consent settings, one generic JSON registration backend |
| `all-components.nl.zip` | the same form exported with the Dutch interface language (top-level texts Dutch) |
| `logic-variables.en.zip` | JSON logic rules (property, disable-next, step applicability, variable actions), user-defined variables, and one component that carries legacy script keys (they are inert text; nothing evaluates them) |
| `signin-prefill-payment.en.zip` | a sign-in plugin option, a payment plugin, prefill settings |
| `special-components.en.zip` | components that need identity-register or map services, an email registration backend |
| `appointment.en.zip` | a form of type `appointment` |

Notes

- The legacy script keys in `logic-variables.en.zip` were added through the API on purpose, so the importer meets
  them (the current builder does not offer them).
- The archives are regenerated rarely; if you change one, keep it synthetic and re-run the golden tests.
- Format reference and the mapping table: `docs/open-formulieren.md`.
