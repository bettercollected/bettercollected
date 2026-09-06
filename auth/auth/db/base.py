from common.db import SpineColumns, make_base

SCHEMA = "auth"
Base = make_base(SCHEMA)
S = SpineColumns(SCHEMA)
