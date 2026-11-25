"""Seed the farmer SMS wording as core Notification records.

One Notification per event on core's "Method" trigger: ``oan_messaging/notify.py`` fires
them explicitly from the code that changes an application or visit, finds them by event
code and hands the rendered text to ``oan_messaging_connector``. The wording, and whether
an event sends at all, is therefore editable on the desk. Existing records are never
overwritten, so an admin's edits survive a migrate.

Each text must fit one SMS part (160 GSM-7 characters, 70 with any Amharic character) at
the longest bank name (30), stage (30), place (40) and visit reference A2C substitutes;
``queue_sms`` refuses a longer one and logs it.

No amounts, rejection reasons or other free text typed by bank staff. The consent OTP
and consent notices belong to the DPI Consent Manager, not to A2C.
"""

import frappe

LOAN_APPLICATION = "A2C Loan Application"
VISIT_SCHEDULE = "A2C Visit Schedule"

#: (event code, title, document type, English text, Jinja arguments)
NOTIFICATION_EVENTS = (
	(
		"application_submitted",
		"Application Submitted",
		LOAN_APPLICATION,
		"OAN Credit: your loan application {0} was sent to {1}. We will tell you when it moves forward.",
		("app", "bank"),
	),
	(
		"stage_changed",
		"Stage Changed",
		LOAN_APPLICATION,
		"OAN Credit: your loan application {0} with {1} is now at stage: {2}.",
		("app", "bank", "stage"),
	),
	(
		"application_approved",
		"Application Approved",
		LOAN_APPLICATION,
		"OAN Credit: {0} approved your loan application {1}. The bank will contact you about next steps.",
		("bank", "app"),
	),
	(
		"application_rejected",
		"Application Rejected",
		LOAN_APPLICATION,
		"OAN Credit: {0} did not approve loan application {1}. Ask your agent or the bank for the reason.",
		("bank", "app"),
	),
	(
		"loan_disbursed",
		"Loan Disbursed",
		LOAN_APPLICATION,
		"OAN Credit: {0} has paid out the loan for application {1}. Contact the bank if you have not received it.",
		("bank", "app"),
	),
	(
		"application_completed",
		"Application Completed",
		LOAN_APPLICATION,
		"OAN Credit: {0} has completed your loan application {1}. The bank will contact you about the loan.",
		("bank", "app"),
	),
	(
		"visit_scheduled",
		"Visit Scheduled",
		VISIT_SCHEDULE,
		"OAN Credit: an agent will visit you on {0} at {1}, at {2}. Visit ref {3}.",
		("date", "time", "place", "visit"),
	),
	(
		"visit_cancelled",
		"Visit Cancelled",
		VISIT_SCHEDULE,
		"OAN Credit: agent visit {0} on {1} is cancelled. Your agent will contact you to book a new time.",
		("visit", "date"),
	),
)


def seed_notifications() -> None:
	"""Create the missing farmer SMS Notifications (idempotent, never overwrites)."""
	for code, title, document_type, source, args in NOTIFICATION_EVENTS:
		name = f"A2C: {title} (SMS)"
		if frappe.db.exists("Notification", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Notification",
				"name": name,
				"subject": title,
				"document_type": document_type,
				"event": "Method",
				"method": code,
				"channel": "SMS",
				# The English text is the translation key; the context keeps it stable.
				"message": "{{ _(%r, context=%r).format(%s) }}"
				% (source, f"A2C SMS {code}", ", ".join(args)),
				"message_type": "Plain Text",
				# Not is_standard: a standard Notification loads from a file and refuses
				# desk edits outside developer mode.
				"is_standard": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
