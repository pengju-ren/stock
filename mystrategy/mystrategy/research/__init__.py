"""Investment research framework — Buffett/Munger/Duan/Li Lu methodologies."""

from mystrategy.research.checklist import run_checklist, ChecklistResult, VETO_LIST
from mystrategy.research.quality_screen import run_quality_screen, QualityScreenResult
from mystrategy.research.thesis import ThesisTracker, Assumption, create_thesis

__all__ = [
    "run_checklist", "ChecklistResult", "VETO_LIST",
    "run_quality_screen", "QualityScreenResult",
    "ThesisTracker", "Assumption", "create_thesis",
]
