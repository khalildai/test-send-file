Task #18 independent V2.0.13 maturity-table copy (fixture data)

This directory is an isolated copy of the V2.0.13 service. It preserves the
main version's maturity table, organization configuration tables, filters,
editing, validation, optimistic revision checks, and audit log behavior.

The bundled data/maturity.db is a display fixture: capability achieved and
delivery values were replaced with deterministic sample values in this copy.
The original V2.0.13 source and database were not modified. Organization
names, teams, and team relations remain structurally identical to V2.0.13.

Run with start.bat (Windows) or `python app.py` from this directory. The
default admin credentials remain the V2.0.13 demo credentials. This package
is not a production release and must not overwrite E:\raft\V2.0.13\.
