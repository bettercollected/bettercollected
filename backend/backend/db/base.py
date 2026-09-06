from common.db import SpineColumns, make_base

SCHEMA = "app"
Base = make_base(SCHEMA)
S = SpineColumns(SCHEMA)
