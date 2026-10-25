- Request validation errors no longer mangle ordinary words: a short submitted value (3 to 7
  characters) that only occurs inside a longer word of a validator's message ("mat" in "format") is
  left alone. Longer values, and any value in quotes, are still removed wherever they occur, and the
  removal now costs little on very large inputs.
