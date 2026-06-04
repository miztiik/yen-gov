"""B2a seed emitters - read existing taxonomy artifacts, emit canonical CSVs.

See [TODO/20260604-b2a-csv-catalogue-subplan.md](../../../../../TODO/20260604-b2a-csv-catalogue-subplan.md).

Each module exposes one ``emit(*, src=..., out=...)`` function that lifts an
existing taxonomy artifact under ``datasets/taxonomy/`` to its long-format
CSV home under ``datasets/data/`` via
:func:`yen_gov.canonical.csv_writer.write_csv`. The writer enforces the
column contract; the validator (run as the gate) enforces FK closure.
"""
