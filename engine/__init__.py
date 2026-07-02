"""Runway engine: deterministic processing of DOL LCA disclosure data.

This package is the data layer only. It never calls an LLM, never renders
HTML, and never prints - it returns tables and raises RunwayError with a
plain-English message when a run cannot continue.
"""


class RunwayError(Exception):
    """A known failure with a message written for the person running the tool.

    Scripts catch this at the top level and print the message; the user must
    never see a stack trace for an anticipated failure (no data, wrong file,
    missing quarter, failed verification).
    """
