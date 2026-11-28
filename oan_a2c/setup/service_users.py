"""Machine users the gateway calls Frappe as.

Partner webhooks (consent data, lead intake) are not called with a Frappe credential. The
partner authenticates to the gateway with its own key, and the gateway replaces it with
`token <api_key>:<api_secret>` of the user below (apisix/README.md,
A2C_FRAPPE_SERVICE_AUTHORIZATION). This module creates the user, so a new site does not
depend on someone adding it by hand.

It does not generate the API key. In Kubernetes the chart does: it generates the Secret
`a2c-frappe-service-credential` (key `authorization`, value `token <api_key>:<api_secret>`)
and the apiCredential Job sets it on this user, so the gateway and Frappe share one value.
Outside Kubernetes, generate it once, after the site exists:

	bench --site <site> execute oan_a2c.setup.service_users.generate_service_keys

and give the printed token to the gateway as A2C_FRAPPE_SERVICE_AUTHORIZATION. The key is
generated only once, because Frappe invalidates the old secret when a new one is made.
"""

import frappe

from oan_a2c.a2c_marketplace.roles import DEVELOPMENT_AGENT_ROLE

# The synthetic domain oan_auth_service gives local accounts, so no mail is sent to it.
SERVICE_USER_EMAIL = "a2c-partner-service@id.openagrinet.internal"
SERVICE_USER_FIRST_NAME = "A2C Partner Service"
# receive_consent_data checks write on A2C Consent Request as this user (a real check, see
# webhook_consent_data.py). Development Agent carries it, has no desk access and is not tied
# to one bank. The lead webhook runs with ignore_permissions and needs nothing more.
SERVICE_USER_ROLES = (DEVELOPMENT_AGENT_ROLE,)


def ensure_partner_service_user():
	"""Create the partner service user, or bring an existing one back to the intended state.

	Idempotent: runs on install and on every migrate. The password is random and is never
	shown or stored, so the user can only authenticate with its API key.
	"""
	if frappe.db.exists("User", SERVICE_USER_EMAIL):
		user = frappe.get_doc("User", SERVICE_USER_EMAIL)
	else:
		user = frappe.new_doc("User")
		user.email = SERVICE_USER_EMAIL
		user.first_name = SERVICE_USER_FIRST_NAME
		user.user_type = "Website User"
		user.send_welcome_email = 0
		user.new_password = frappe.generate_hash(length=40)

	user.enabled = 1
	present = {row.role for row in user.roles}
	for role in SERVICE_USER_ROLES:
		if role not in present:
			user.append("roles", {"role": role})
	user.flags.ignore_permissions = True
	user.save()
	return user.name


def generate_service_keys():
	"""Print the gateway token for the service user. Only creates a key pair if there is none."""
	user = frappe.get_doc("User", SERVICE_USER_EMAIL)
	if user.api_key:
		print(f"{SERVICE_USER_EMAIL} already has an API key; not generating another.")
		print("To rotate it, call frappe.core.doctype.user.user.generate_keys deliberately.")
		return
	from frappe.core.doctype.user.user import generate_keys

	generate_keys(SERVICE_USER_EMAIL)
	# The secret is printed once and cannot be read back, so the key must be stored first.
	frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit
	user.reload()
	secret = user.get_password("api_secret")
	print(f"token {user.api_key}:{secret}")
