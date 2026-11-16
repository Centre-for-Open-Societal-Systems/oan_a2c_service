"""Credit (A2C) farmer SMS: raise events through ``oan_messaging_connector.queue_sms``.

Application events are raised from the API functions that change the application
(``submit_application``, ``update_loan_status``), not from ``on_update``: A2C mirrors
``status`` with ``db_set``, which skips ``on_update``. Visit events use the
A2C Visit Schedule ``doc_events`` in ``hooks.py``, because inserting a schedule or
cancelling it is itself the business event.

``queue_sms`` only inserts an outbox row in the current transaction; the connector sends
it after commit. It never raises, so an SMS problem never blocks a loan action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_system_timezone, get_time, getdate
from oan_messaging_connector.api import queue_sms

from .events import TemplateTooLong, event_for_transition, render, visit_deadline

#: Display language (as stored on A2C records) to message language code.
LANGUAGES = {
	"english": "en",
	"en": "en",
	"amharic": "am",
	"am": "am",
	"afaan oromo": "om",
	"oromo": "om",
	"om": "om",
	"tigrinya": "ti",
	"ti": "ti",
}
DEFAULT_VISIT_TIME = "09:00:00"
CLOSED_STATUSES = ("Completed", "Rejected")


def _lang(value: str | None) -> str:
	return LANGUAGES.get((value or "").strip().lower(), "en")


def _bank_short(bank: str | None) -> str:
	name = (frappe.db.get_value("A2C Participating Bank", bank, "bank_name") if bank else "") or ""
	name = name.strip() or "your bank"
	return name if len(name) <= 30 else name[:29].rstrip() + "."


def _lead_phone(lead: str | None) -> str | None:
	return frappe.db.get_value("A2C Lead", lead, "phone_number") if lead else None


def _queue(
	event: str,
	doc: Any,
	phone: str | None,
	lang: str,
	fields: dict[str, str],
	expires_at: datetime | None = None,
) -> str | None:
	try:
		text = render(event, lang, **fields)
	except (TemplateTooLong, KeyError, ValueError) as exc:
		frappe.log_error(f"A2C SMS not queued for {doc.name}/{event}: {exc}", "OAN Messaging")
		return None
	return queue_sms(
		recipient=phone,
		text=text,
		purpose="transactional",
		source_reference=f"a2c:{doc.name}:{event}",
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		event=event,
		language=lang,
		expires_at=expires_at,
	)


def notify_application(doc: Any, event: str | None) -> str | None:
	"""Queue ``event`` about a loan application; returns the OAN Message name or None."""
	if not event:
		return None
	fields = {
		"bank": _bank_short(doc.get("bank")),
		"app": doc.name,
		"stage": (doc.get("stage_label") or "")[:30],
	}
	return _queue(event, doc, doc.get("phone_number"), _lang(doc.get("language")), fields)


def notify_status_change(
	doc: Any, new_status: str, stage_label: str | None, status_changed: bool = True
) -> str | None:
	"""Queue the farmer event for a status or stage change, if it has one.

	A stage move on an application that is already closed (Completed or Rejected) is not
	news to the farmer, except a bank recording the payout afterwards.
	"""
	event = event_for_transition(new_status, stage_label)
	if new_status in CLOSED_STATUSES and not status_changed and event != "loan_disbursed":
		return None
	return notify_application(doc, event)


def _visit_start(schedule: Any) -> datetime | None:
	if not schedule.get("visit_date"):
		return None
	# Time fields arrive as timedelta (loaded) or as strings such as "9:00" (from the API).
	local = datetime.combine(
		getdate(schedule.visit_date), get_time(schedule.get("visit_time") or DEFAULT_VISIT_TIME)
	)
	return local.replace(tzinfo=ZoneInfo(get_system_timezone())).astimezone(UTC)


def notify_visit(schedule: Any, event: str) -> str | None:
	"""Queue a visit event; it expires when the visit starts. None for a past visit."""
	start = _visit_start(schedule)
	if start is None:
		return None
	deadline = visit_deadline(start, datetime.now(UTC))
	if deadline is None:
		return None
	local = start.astimezone(ZoneInfo(get_system_timezone()))
	place = (schedule.get("meeting_location") or schedule.get("kebele") or "the agreed place").strip()
	fields = {
		"visit": schedule.name,
		"date": f"{local.day} {local:%b %Y}",
		"time": f"{local:%H:%M}",
		"place": place[:40],
	}
	return _queue(event, schedule, _lead_phone(schedule.get("lead")), "en", fields, expires_at=deadline)


def _never_block(event: str, doc: Any) -> None:
	"""A visit hook must never fail the visit action because of an SMS."""
	try:
		notify_visit(doc, event)
	except Exception as exc:
		frappe.log_error(f"A2C SMS not queued for {doc.name}/{event}: {type(exc).__name__}", "OAN Messaging")


def on_visit_insert(doc: Any, method: str | None = None) -> None:
	if (doc.get("status") or "Scheduled") == "Scheduled":
		_never_block("visit_scheduled", doc)


def on_visit_update(doc: Any, method: str | None = None) -> None:
	if doc.has_value_changed("status") and doc.get("status") == "Cancelled":
		_never_block("visit_cancelled", doc)
