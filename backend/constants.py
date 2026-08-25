"""Shared enums and constants for the JobTracker backend.

These lists define the allowed values for stage/outcome/source/event_type.
They are enforced both in validation.py and used by the frontend (via the
/api/meta endpoint) so the two stay in sync.
"""

# Ordered progression of "active pipeline" stages. Order matters: it defines
# rank for analytics such as "reached at least Interview 1". 'Closed' is a
# terminal marker and is intentionally NOT part of this ordered progression
# (an application can be Closed after any stage).
STAGE_PROGRESSION = [
    "Applied",
    "Screening",
    "Assessment",
    "Interview 1",
    "Interview 2",
    "Final Interview",
    "Offer",
]

STAGE_TERMINAL = "Closed"

ALL_STAGES = STAGE_PROGRESSION + [STAGE_TERMINAL]

STAGE_RANK = {stage: i for i, stage in enumerate(STAGE_PROGRESSION)}

OUTCOMES = ["Pending", "Positive", "Negative", "Accepted", "Withdrawn"]

DEFAULT_SOURCES = [
    "LinkedIn",
    "Company Website",
    "Referral",
    "Recruiter",
    "Indeed",
    "Other",
]

DEFAULT_EVENT_TYPES = [
    "Application Submitted",
    "Application Confirmation",
    "Recruiter Contact",
    "Screening",
    "Assessment Invitation",
    "Assessment Completed",
    "Interview Invitation",
    "Interview Completed",
    "Next Round",
    "Offer",
    "Rejection",
    "Withdrawal",
    "Stage Update",
    "Outcome Update",
    "Other",
]

# Event types created automatically by the system (not chosen by the user
# from the "add event" form, but valid values that can appear in history).
SYSTEM_EVENT_TYPES = ["Application Submitted", "Stage Update", "Outcome Update"]
