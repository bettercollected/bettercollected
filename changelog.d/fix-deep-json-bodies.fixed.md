- A request body nested too deeply (more than 128 levels of arrays and objects) is
  now refused with a clear `body_too_deep` error instead of a server error.
