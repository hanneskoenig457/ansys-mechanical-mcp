"""PyDPF result extraction placeholders."""

from dataclasses import dataclass


@dataclass(slots=True)
class ResultSummaryRequest:
    """Request for extracting a basic result summary from a result file."""

    result_file: str
    result_name: str

