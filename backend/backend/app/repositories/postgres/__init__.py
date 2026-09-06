"""Postgres twins of the Mongo repositories, one module per plan group.

Each class carries the same public methods as its Mongo counterpart and is
registered on the RoutingRepository as ``postgres=``. The Mongo class stays the
source of the method surface (and of the ``@write_op`` markers) until R3.
"""
