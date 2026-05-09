"""Wikipedia source adapters.

Wikipedia is the fallback source for reference data ECI doesn't publish in
machine-readable form: the canonical district list per state, and the
list of legislative-assembly constituencies (with reservation status) per
state.

Per docs/architecture/backend/sources-wikipedia.md this adapter only consumes the english Wikipedia; we never
fetch other-language editions or commons. URL building lives in urls.py;
each page family has its own parser module.
"""
