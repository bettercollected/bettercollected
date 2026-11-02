- The field-rule check no longer slows down on a run of spaces inside an answer pipe. A title or
  description with `{{field:` followed by many spaces made each save take seconds (about 5 s at the
  1,000-character rule-description limit). The pattern now reads in linear time.
