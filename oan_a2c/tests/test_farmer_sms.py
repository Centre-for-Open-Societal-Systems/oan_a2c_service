"""Credit (A2C) farmer SMS queued through oan_messaging_connector.

Nothing is dispatched here: the connector's own tests cover dispatch and polling. Each
test runs in a transaction that IntegrationTestCase rolls back.
"""

from datetime import UTC, datetime, timedelta
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase
from oan_messaging_connector.sms import fits_one_sms

from oan_a2c.oan_messaging import events, notify
from oan_a2c.setup.notifications import NOTIFICATION_EVENTS

PHONE = "0900000711"
APP = "APP-2026-91001"


def app_doc(**kw):
	base = {
		"doctype": "A2C Loan Application",
		"name": APP,
		"phone_number": PHONE,
		"language": "English",
		"bank": None,
		"stage_label": "Verified",
	}
	base.update(kw)
	return frappe._dict(base)


class VisitDoc(frappe._dict):
	"""A2C Visit Schedule stand-in with the one Document method the hooks use."""

	def has_value_changed(self, fieldname):
		return fieldname in self.get("changed", ())


def visit_doc(starts_in=timedelta(days=2), **kw):
	start = (datetime.now() + starts_in).replace(microsecond=0)
	base = {
		"doctype": "A2C Visit Schedule",
		"name": "VSCH-2026-91001",
		"lead": "LEAD-TEST",
		"visit_date": start.date().isoformat(),
		"visit_time": start.time().isoformat(),
		"meeting_location": "Kebele 01 office",
		"status": "Scheduled",
	}
	base.update(kw)
	return VisitDoc(base)


class TestFarmerSms(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		keys = ("oan_messaging_enabled", "oan_messaging_base_url", "oan_messaging_token")
		self._conf = {k: frappe.conf.get(k) for k in keys}
		frappe.conf.oan_messaging_enabled = 1
		frappe.conf.oan_messaging_base_url = "https://oan-messaging.example.invalid"
		frappe.conf.oan_messaging_token = "oanmsg_" + "t" * 43
		self.addCleanup(self._restore_conf)
		phone = mock.patch.object(notify, "_lead_phone", return_value=PHONE)
		phone.start()
		self.addCleanup(phone.stop)

	def _restore_conf(self):
		for k, v in self._conf.items():
			frappe.conf[k] = v

	def msg(self, name):
		self.assertIsNotNone(name)
		return frappe.get_doc("OAN Message", name)

	def test_status_changes_queue_the_matching_farmer_event(self):
		cases = {
			("Rejected", "Rejected"): "application_rejected",
			("Completed", "Disbursed"): "loan_disbursed",
			("Completed", "Loan Closed"): "application_completed",
			("In Transition", "Approved"): "application_approved",
			("In Transition", "Verified"): "stage_changed",
		}
		for (status, stage), event in cases.items():
			m = self.msg(notify.notify_status_change(app_doc(), status, stage))
			self.assertEqual((m.event, m.purpose, m.recipient), (event, "transactional", PHONE))
			self.assertEqual(m.source_reference, f"a2c:{APP}:{event}")
			self.assertEqual((m.reference_doctype, m.reference_name), ("A2C Loan Application", APP))
			self.assertIn(APP, m.text)
		self.assertIsNone(notify.notify_status_change(app_doc(), "Active", None))

	def test_stage_moves_on_a_closed_application_send_only_paid_out(self):
		for status, stage in (("Completed", "Loan Closed"), ("Rejected", "Appeal Noted")):
			self.assertIsNone(notify.notify_status_change(app_doc(), status, stage, status_changed=False))
		m = self.msg(notify.notify_status_change(app_doc(), "Completed", "Disbursed", status_changed=False))
		self.assertEqual(m.event, "loan_disbursed")

	def test_paid_out_only_for_a_disbursed_stage(self):
		self.assertEqual(events.event_for_transition("Completed", " disbursed "), "loan_disbursed")
		for label in (None, "", "Approved", "Sanctioned", "Loan Closed"):
			self.assertEqual(events.event_for_transition("Completed", label), "application_completed", label)

	def test_submitted_event_without_a_bank_names_your_bank(self):
		m = self.msg(notify.notify_application(app_doc(), "application_submitted"))
		self.assertIn("sent to your bank", m.text)
		self.assertIsNone(m.expires_at)

	def test_untranslated_language_falls_back_to_english(self):
		m = self.msg(notify.notify_application(app_doc(language="አማርኛ"), "stage_changed"))
		self.assertEqual(m.language, "am")
		self.assertTrue(m.text.startswith("OAN Credit:"))

	def test_no_phone_no_message(self):
		self.assertIsNone(notify.notify_application(app_doc(phone_number=None), "stage_changed"))

	def test_long_bank_name_is_shortened_not_refused(self):
		real = frappe.db.get_value

		def bank_name(doctype, *args, **kwargs):
			if doctype == "A2C Participating Bank":
				return "B" * 60
			return real(doctype, *args, **kwargs)

		with mock.patch.object(frappe.db, "get_value", side_effect=bank_name):
			m = self.msg(notify.notify_application(app_doc(bank="BANK-1"), "application_submitted"))
		self.assertIn("B" * 29 + ".", m.text)

	def test_visit_scheduled_expires_at_the_visit(self):
		doc = visit_doc()
		notify.on_visit_insert(doc)
		name = frappe.db.get_value("OAN Message", {"reference_name": doc.name, "event": "visit_scheduled"})
		m = self.msg(name)
		self.assertEqual((m.recipient, m.source_reference), (PHONE, f"a2c:{doc.name}:visit_scheduled"))
		self.assertIn("Kebele 01 office", m.text)
		self.assertIsNotNone(m.expires_at)

	def test_visit_cancelled_only_on_the_change_to_cancelled(self):
		notify.on_visit_update(visit_doc(status="Cancelled"))  # status did not change
		notify.on_visit_update(visit_doc(status="Completed", changed=("status",)))
		self.assertFalse(
			frappe.db.exists("OAN Message", {"reference_name": "VSCH-2026-91001", "event": "visit_cancelled"})
		)
		notify.on_visit_update(visit_doc(status="Cancelled", changed=("status",)))
		self.assertTrue(
			frappe.db.exists("OAN Message", {"reference_name": "VSCH-2026-91001", "event": "visit_cancelled"})
		)

	def test_visit_time_as_stored_or_typed(self):
		"""A loaded Time field is a timedelta ("9:00:00"); the API may send "9:00"."""
		day = (datetime.now() + timedelta(days=2)).date().isoformat()
		for value in (timedelta(hours=9), "9:00", "09:00:00", None):
			self.assertIsNotNone(
				notify.notify_visit(visit_doc(visit_date=day, visit_time=value), "visit_scheduled"), value
			)

	def test_visit_hooks_never_raise(self):
		with mock.patch.object(notify, "notify_visit", side_effect=ValueError("bad time")):
			notify.on_visit_insert(visit_doc())
			notify.on_visit_update(visit_doc(status="Cancelled", changed=("status",)))

	def test_past_visit_sends_nothing(self):
		self.assertIsNone(notify.notify_visit(visit_doc(starts_in=-timedelta(days=1)), "visit_scheduled"))

	def test_visit_deadline_is_capped_inside_the_expiry_horizon(self):
		now = datetime.now(UTC)
		self.assertEqual(events.visit_deadline(now + timedelta(days=2), now), now + timedelta(days=2))
		self.assertEqual(
			events.visit_deadline(now + timedelta(days=30), now),
			now + events.MAX_EXPIRY_HORIZON - events.EXPIRY_SAFETY_MARGIN,
		)
		self.assertIsNone(events.visit_deadline(now - timedelta(hours=1), now))

	def test_every_seeded_text_fits_one_sms_at_maximum_field_lengths(self):
		longest = {"bank": 30, "app": 14, "stage": 30, "visit": 15, "date": 11, "time": 5, "place": 40}
		fields = {k: "W" * n for k, n in longest.items()}
		for code, title, *_ in NOTIFICATION_EVENTS:
			message = frappe.db.get_value("Notification", f"A2C: {title} (SMS)", "message")
			self.assertTrue(message, code)
			self.assertTrue(fits_one_sms(frappe.render_template(message, fields)), code)

	def test_hooks_wire_the_visit_events(self):
		hooks = frappe.get_hooks("doc_events").get("A2C Visit Schedule", {})
		self.assertIn("oan_a2c.oan_messaging.notify.on_visit_insert", hooks.get("after_insert", []))
		self.assertIn("oan_a2c.oan_messaging.notify.on_visit_update", hooks.get("on_update", []))
