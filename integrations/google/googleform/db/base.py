from common.db import SpineColumns, make_base

SCHEMA = "google"
Base = make_base(SCHEMA)
S = SpineColumns(SCHEMA)
