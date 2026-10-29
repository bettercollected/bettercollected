- An answer pattern whose shape can make a browser's regular-expression engine take
  exponential time (`^(a+)+$`, `(a|aa)+`, a backreference) is now refused when a form
  is saved, through the builder, the API, the AI assistant and the Open Formulieren
  import (the import lists it as not carried). The server already matched patterns
  in linear time, but the respondent form checked them in the browser and could
  freeze a tab on one unlucky answer. The respondent form no longer tests such a
  pattern in the browser; patterns already stored in a form are kept and the server
  still checks them on submit, and the builder points them out.
