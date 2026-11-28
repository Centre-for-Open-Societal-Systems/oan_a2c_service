"""Credit (A2C) farmer SMS: raise events through ``oan_messaging_service.queue_sms``.

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
from frappe.translate import print_language
from frappe.utils import get_system_timezone, get_time, getdate
from oan_messaging_service.api import queue_sms

from .events import event_for_transition, visit_deadline

DEFAULT_VISIT_TIME = "09:00:00"
CLOSED_STATUSES = ("Completed", "Rejected")


def _queue(
	event: str,
	doc: Any,
	phone: str | None,
	lang: str,
	fields: dict[str, str],
	expires_at: datetime | None = None,
) -> str | None:
	queued = None
	# One Notification per event: its message is the wording and ``enabled`` the switch.
	for name in frappe.get_all(
		"Notification",
		filters={
			"document_type": doc.doctype,
			"event": "Method",
			"method": event,
			"channel": "SMS",
			"enabled": 1,
		},
		pluck="name",
	):
		notification = frappe.get_doc("Notification", name)
		context = {"doc": doc, **fields}
		if notification.condition and not frappe.safe_eval(notification.condition, None, context):
			continue
		with print_language(lang):
			# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
			text = frappe.render_template(notification.message, context).strip()
		queued = queue_sms(
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
	return queued


def notify_application(doc: Any, event: str | None) -> str | None:
	"""Queue ``event`` about a loan application; returns the OAN Message name or None."""
	if not event:
		return None
	bank = doc.get("bank")
	bank_name = (
		(frappe.db.get_value("A2C Participating Bank", bank, "bank_name") if bank else "") or ""
	).strip() or "your bank"
	if len(bank_name) > 30:
		bank_name = bank_name[:29].rstrip() + "."
	raw_lang = (doc.get("language") or "").strip()
	if raw_lang and frappe.db.exists("Language", raw_lang):
		lang = raw_lang
	else:
		lang = (raw_lang and frappe.db.get_value("Language", {"language_name": raw_lang}, "name")) or "en"
	fields = {
		"bank": bank_name,
		"app": doc.name,
		"stage": (doc.get("stage_label") or "")[:30],
	}
	return _queue(event, doc, doc.get("phone_number"), lang, fields)


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


def notify_visit(schedule: Any, event: str) -> str | None:
	"""Queue a visit event; it expires when the visit starts. None for a past visit."""
	if not schedule.get("visit_date"):
		return None
	# Time fields arrive as timedelta (loaded) or as strings such as "9:00" (from the API).
	tz = ZoneInfo(get_system_timezone())
	start = (
		datetime.combine(
			getdate(schedule.visit_date), get_time(schedule.get("visit_time") or DEFAULT_VISIT_TIME)
		)
		.replace(tzinfo=tz)
		.astimezone(UTC)
	)
	deadline = visit_deadline(start, datetime.now(UTC))
	if deadline is None:
		return None
	local = start.astimezone(tz)
	place = (schedule.get("meeting_location") or schedule.get("kebele") or "the agreed place").strip()
	lead = schedule.get("lead")
	phone = frappe.db.get_value("A2C Lead", lead, "phone_number") if lead else None
	fields = {
		"visit": schedule.name,
		"date": f"{local.day} {local:%b %Y}",
		"time": f"{local:%H:%M}",
		"place": place[:40],
	}
	return _queue(event, schedule, phone, "en", fields, expires_at=deadline)


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
