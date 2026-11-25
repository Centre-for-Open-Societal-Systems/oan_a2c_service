"""Credit (A2C) farmer SMS: events and texts.

A2C owns which events reach the farmer; the texts are Notification records. Sending (outbox, keys,
dispatch, status) belongs to ``oan_messaging_connector``; see ``notify.py``.

======================  ===================================================================
Event                   Raised by
======================  ===================================================================
application_submitted   ``api/v1/farmer/applications.py`` ``submit_application``
stage_changed           ``api/v1/loan_applications.py`` ``update_loan_status`` (In Transition)
application_approved    same, when the bank's stage label is "Approved" (bank-defined)
application_rejected    same, Reject transition (status Rejected)
loan_disbursed          same, Complete transition **only** when the stage label is "Disbursed"
application_completed   same, Complete transition with any other stage label: a neutral
                        notice, because a bank may complete before paying out
visit_scheduled         A2C Visit Schedule inserted with status Scheduled
visit_cancelled         A2C Visit Schedule status changed to Cancelled
======================  ===================================================================

The wording is a core Notification per event, seeded by ``setup/notifications.py`` and
editable on the desk; see there for the rules every text follows.
"""

from __future__ import annotations

from datetime import datetime, timedelta

#: OAN accepts an expiry at most 7 days ahead; stay a little inside it.
MAX_EXPIRY_HORIZON = timedelta(days=7)
EXPIRY_SAFETY_MARGIN = timedelta(minutes=5)


def event_for_transition(new_status: str, stage_label: str | None) -> str | None:
	"""Map an application status or stage change to a farmer event (``None``: no SMS).

	``new_status`` is the application ``status`` after the transition; ``stage_label`` is
	the bank-defined stage. Banks name their own stages, so "Approved" and "Disbursed"
	are matched by label, and each bank confirms its labels.
	"""
	label = (stage_label or "").strip().lower()
	if new_status == "Rejected":
		return "application_rejected"
	if new_status == "Completed":
		return "loan_disbursed" if label == "disbursed" else "application_completed"
	if new_status == "In Transition" and label:
		return "application_approved" if label == "approved" else "stage_changed"
	return None


def visit_deadline(visit_starts_at: datetime, now: datetime) -> datetime | None:
	"""A visit message is useless after the visit starts. Capped inside OAN's expiry
	horizon; ``None`` when the visit has already started."""
	deadline = min(visit_starts_at, now + MAX_EXPIRY_HORIZON - EXPIRY_SAFETY_MARGIN)
	return deadline if deadline > now else None
