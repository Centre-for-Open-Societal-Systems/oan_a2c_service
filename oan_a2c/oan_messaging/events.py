"""Credit (A2C) farmer SMS: events and texts.

A2C owns which events reach the farmer and what they say. Sending (outbox, keys,
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

Rules for every text:

* One SMS part (160 GSM-7 characters, or 70 with any Amharic character), checked by
  ``render`` at the longest field values A2C may substitute (``FIELD_LIMITS``).
* No amounts, rejection reasons or other free text typed by bank staff.
* English source texts; translations are added per language under the same key and
  must pass the same length check.

The consent OTP and consent notices belong to the DPI Consent Manager, not to A2C.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from oan_messaging_connector.sms import fits_one_sms

#: Source texts. Placeholders: bank, app, stage, visit, date, time, place.
TEMPLATES: dict[str, dict[str, str]] = {
	"application_submitted": {
		"en": "OAN Credit: your loan application {app} was sent to {bank}. We will tell "
		"you when it moves forward.",
	},
	"stage_changed": {
		"en": "OAN Credit: your loan application {app} with {bank} is now at stage: {stage}.",
	},
	"application_approved": {
		"en": "OAN Credit: {bank} approved your loan application {app}. The bank will "
		"contact you about next steps.",
	},
	"application_rejected": {
		"en": "OAN Credit: {bank} did not approve loan application {app}. Ask your agent "
		"or the bank for the reason.",
	},
	"loan_disbursed": {
		"en": "OAN Credit: {bank} has paid out the loan for application {app}. Contact the "
		"bank if you have not received it.",
	},
	"application_completed": {
		"en": "OAN Credit: {bank} has completed your loan application {app}. The bank will "
		"contact you about the loan.",
	},
	"visit_scheduled": {
		"en": "OAN Credit: an agent will visit you on {date} at {time}, at {place}. Visit ref {visit}.",
	},
	"visit_cancelled": {
		"en": "OAN Credit: agent visit {visit} on {date} is cancelled. Your agent will "
		"contact you to book a new time.",
	},
}

A2C_EVENTS = tuple(TEMPLATES)

#: Longest values A2C may substitute; the tests render every template at these lengths.
FIELD_LIMITS = {"bank": 30, "app": 14, "stage": 30, "visit": 15, "date": 11, "time": 5, "place": 40}

#: OAN accepts an expiry at most 7 days ahead; stay a little inside it.
MAX_EXPIRY_HORIZON = timedelta(days=7)
EXPIRY_SAFETY_MARGIN = timedelta(minutes=5)


class TemplateTooLong(ValueError):
	"""The rendered text does not fit one SMS part. Shorten the template or the value."""


def render(event: str, language: str = "en", **fields: str) -> str:
	"""Render ``event`` in ``language``, falling back to English when no translation exists."""
	if event not in TEMPLATES:
		raise ValueError(f"unknown A2C event {event!r}")
	for name, value in fields.items():
		if name in FIELD_LIMITS and len(value) > FIELD_LIMITS[name]:
			raise TemplateTooLong(f"{name} longer than {FIELD_LIMITS[name]} characters")
	template = TEMPLATES[event].get(language) or TEMPLATES[event]["en"]
	text = template.format(**fields)
	if not fits_one_sms(text):
		raise TemplateTooLong(f"{event}/{language} does not fit one SMS part")
	return text


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
