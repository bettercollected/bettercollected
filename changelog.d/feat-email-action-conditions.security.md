- The "send me a copy" address rule now also refuses an address that holds a format character (bidirectional
  overrides and isolates, zero width characters) or an unassigned code point, so an address cannot render as another
  one in a mail header.
