"""Backend Aggregator composers (per ADR-0024).

A composer reads N upstream indicator artifacts and emits ONE facetted
indicator artifact. The frontend chart adapter then reads that single
file. This is the canonical Pipes-and-Filters Aggregator boundary;
frontend adapters stay one-input one-output (Message Translator).

Each composer is a small module with a single ``compose()`` entry point
that accepts a repository root and writes the output artifact under
``datasets/indicators/in/<category>/...``.
"""
