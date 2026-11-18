#!/usr/bin/env python3
# Copyright (c) 2026, OpenAgriNet Ethiopia and contributors
# For license information, please see license.txt

"""Generate the OAN A2C Administration & Team Management Postman Collection.

Covers administrative workflows across both Platform Administrators and Bank Administrators:
1. Authentication (Platform Admin & Bank Admin sign-in, token refresh)
2. Platform User Administration (/v1/admin/users - oan_auth_service)
3. Bank Onboarding & Governance (/v1/banks, status updates, KYC, compliance contacts)
4. Bank Team Management (/v1/banks/me/team - onboarding and managing Bank Agents / Loan Officers)
5. Marketplace Taxonomy Administration (/v1/admin/taxonomy/*)
6. Custom Loan Pipeline Stages (/v1/banks/me/pipeline-stages)
7. Loan Products Cataloging (/v1/banks/me/products)
8. Officer Assignment & Field Operations (/v1/leads/assignees, /v1/leads/:id/assignment, /v1/loan-applications/:id/officer)
"""

import json
from pathlib import Path


def make_test_script(checks: list[str], post_extract: list[str] | None = None) -> list[dict]:
	lines = []
	for check in checks:
		lines.append(check)
	if post_extract:
		lines.append("")
		lines.append("if (pm.response.code >= 200 && pm.response.code < 300) {")
		lines.append("    var res = pm.response.json();")
		lines.append("    var envelope = res.message || res;")
		lines.append("    var data = envelope.data || envelope;")
		for ext in post_extract:
			lines.append(f"    {ext}")
		lines.append("}")
	return [
		{
			"listen": "test",
			"script": {
				"exec": lines,
				"type": "text/javascript",
			},
		}
	]


def make_request(
	name: str,
	method: str,
	path_segments: list[str],
	description: str,
	query_params: list[dict] | None = None,
	body: dict | None = None,
	test_checks: list[str] | None = None,
	post_extract: list[str] | None = None,
	auth_override: dict | None = None,
) -> dict:
	url_raw = "{{base_url}}/" + "/".join(path_segments)
	if query_params:
		qp_str = "&".join(f"{qp['key']}={qp['value']}" for qp in query_params if not qp.get("disabled"))
		if qp_str:
			url_raw += f"?{qp_str}"

	headers = []
	req_body = None
	if body is not None:
		headers.append({"key": "Content-Type", "value": "application/json"})
		req_body = {
			"mode": "raw",
			"raw": json.dumps(body, indent=2),
		}

	req_obj = {
		"method": method,
		"header": headers,
		"url": {
			"raw": url_raw,
			"host": ["{{base_url}}"],
			"path": path_segments,
		},
		"description": description,
	}
	if query_params:
		req_obj["url"]["query"] = query_params
	if req_body:
		req_obj["body"] = req_body
	if auth_override:
		req_obj["auth"] = auth_override

	default_checks = [
		'pm.test("Status code is 2xx", function () {',
		"    pm.response.to.be.success;",
		"});",
		'pm.test("Response contains success status", function () {',
		"    var res = pm.response.json();",
		"    pm.expect(res.status).to.eql('success');",
		"});",
	]
	events = make_test_script(test_checks or default_checks, post_extract)

	return {
		"name": name,
		"event": events,
		"request": req_obj,
		"response": [],
	}


def build_collection() -> dict:
	collection = {
		"info": {
			"_postman_id": "b1e2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
			"name": "OAN A2C - Administration & Team Management",
			"description": (
				"End-to-end administration workflows for **Platform Administrators** (`A2C Administrator`, `System Manager`) "
				"and **Bank Administrators** (`A2C Bank Admin`).\n\n"
				"### Core Capabilities Covered:\n"
				"1. **Admin Authentication**: Multi-tier sign-in for Platform Administrators and Bank Administrators, supporting both `jwt_token` and `access_token`.\n"
				"2. **Platform User Administration (`/v1/admin/users`)**: Create user accounts, assign roles (`A2C Bank Admin`, `A2C Bank Agent`, `A2C Development Agent`), retrieve user profiles, and issue temporary passwords.\n"
				"3. **Bank Onboarding & Governance (`/v1/banks`)**: Register lending organizations, upload KYC licenses, configure compliance contacts (GRO & OPS), upload bank branding, and platform-level approval/suspension status updates.\n"
				"4. **Bank Team Management (`/v1/banks/me/team`)**: Invite/provision Bank Agents (Loan Officers) with temporary passwords, list bank staff members, manage roles, re-issue passwords, and inspect assignable loan officers.\n"
				"5. **Marketplace Taxonomy Administration (`/v1/admin/taxonomy/*`)**: Configure categories, tags, product attributes, and administrative areas.\n"
				"6. **Custom Pipeline Stages (`/v1/banks/me/pipeline-stages`)**: Define and reorder organizational loan evaluation stages.\n"
				"7. **Loan Products Cataloging (`/v1/banks/me/products`)**: Create, update, publish, and audit loan products.\n"
				"8. **Loan Officer Assignment & Field Operations**: Assign loan officers/agents to leads and loan applications.\n\n"
				"### Running in Newman / CI:\n"
				"```bash\n"
				"newman run postman/a2c_admin.postman_collection.json -e postman/a2c_localhost.postman_environment.json\n"
				"```"
			),
			"schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
		},
		"auth": {
			"type": "bearer",
			"bearer": [
				{
					"key": "token",
					"value": "{{jwt_token}}",
					"type": "string",
				}
			],
		},
		"variable": [
			{"key": "base_url", "value": "http://localhost:8000", "type": "default"},
			{"key": "admin_usr", "value": "Administrator", "type": "default"},
			{"key": "admin_pswd", "value": "admin", "type": "secret"},
			{"key": "bank_admin_email", "value": "bankadmin@coopbank.com", "type": "default"},
			{"key": "bank_admin_password", "value": "AdminPass#2026", "type": "secret"},
			{"key": "bank_admin_name", "value": "Chala Degefa", "type": "default"},
			{"key": "jwt_token", "value": "", "type": "secret"},
			{"key": "access_token", "value": "", "type": "secret"},
			{"key": "refresh_token", "value": "", "type": "secret"},
			{"key": "bank_code", "value": "CBO001", "type": "default"},
			{"key": "bank_name", "value": "Cooperative Bank of Oromia", "type": "default"},
			{"key": "agent_email", "value": "loan.officer@coopbank.com", "type": "default"},
			{"key": "agent_name", "value": "Haile Gebrselassie", "type": "default"},
			{"key": "agent_phone", "value": "+251911223344", "type": "default"},
			{"key": "agent_temp_password", "value": "", "type": "secret"},
			{"key": "product_id", "value": "", "type": "default"},
			{"key": "stage_id", "value": "", "type": "default"},
			{"key": "lead_id", "value": "", "type": "default"},
			{"key": "loan_application_id", "value": "", "type": "default"},
		],
		"item": [],
	}

	# -------------------------------------------------------------
	# Folder 0: Authentication & Session Setup
	# -------------------------------------------------------------
	auth_items = [
		make_request(
			name="1. Platform Admin Login",
			method="POST",
			path_segments=["v1", "auth", "login"],
			description=(
				"Authenticates Platform Administrator credentials (`A2C Administrator` or `System Manager`) "
				"and stores `jwt_token`, `access_token`, and `refresh_token` in collection and environment variables."
			),
			body={
				"usr": "{{admin_usr}}",
				"pwd": "{{admin_pswd}}",
				"remember_me": False,
			},
			auth_override={"type": "noauth"},
			test_checks=[
				'pm.test("Status code is 200 OK", function () { pm.response.to.have.status(200); });',
				'pm.test("Access token received", function () {',
				"    var res = pm.response.json();",
				"    var d = res.data || res.message || res;",
				"    pm.expect(d.access_token).to.be.a('string').and.not.empty;",
				"});",
			],
			post_extract=[
				"if (data && data.access_token) {",
				'    pm.collectionVariables.set("jwt_token", data.access_token);',
				'    pm.collectionVariables.set("access_token", data.access_token);',
				"}",
				'if (data && data.refresh_token) pm.collectionVariables.set("refresh_token", data.refresh_token);',
				"if (pm.environment && pm.environment.name && data) {",
				"    if (data.access_token) {",
				'        pm.environment.set("jwt_token", data.access_token);',
				'        pm.environment.set("access_token", data.access_token);',
				"    }",
				'    if (data.refresh_token) pm.environment.set("refresh_token", data.refresh_token);',
				"}",
			],
		),
		make_request(
			name="2. Bank Admin Login",
			method="POST",
			path_segments=["v1", "auth", "login"],
			description="Authenticates Bank Administrator credentials for bank-scoped administrative operations.",
			body={
				"usr": "{{bank_admin_email}}",
				"pwd": "{{bank_admin_password}}",
				"remember_me": False,
			},
			auth_override={"type": "noauth"},
			test_checks=[
				'pm.test("Status code is 200 OK", function () { pm.response.to.have.status(200); });',
				'pm.test("Bank Admin access token received", function () {',
				"    var res = pm.response.json();",
				"    var d = res.data || res.message || res;",
				"    pm.expect(d.access_token).to.be.a('string').and.not.empty;",
				"});",
			],
			post_extract=[
				"if (data && data.access_token) {",
				'    pm.collectionVariables.set("jwt_token", data.access_token);',
				'    pm.collectionVariables.set("access_token", data.access_token);',
				"}",
				"if (pm.environment && pm.environment.name && data) {",
				"    if (data.access_token) {",
				'        pm.environment.set("jwt_token", data.access_token);',
				'        pm.environment.set("access_token", data.access_token);',
				"    }",
				"}",
			],
		),
		make_request(
			name="3. Refresh Token",
			method="POST",
			path_segments=["v1", "auth", "refresh"],
			description="Exchanges the single-use refresh token for a fresh JWT token pair.",
			body={"refresh_token": "{{refresh_token}}"},
			auth_override={"type": "noauth"},
			post_extract=[
				"if (data && data.access_token) {",
				'    pm.collectionVariables.set("jwt_token", data.access_token);',
				'    pm.collectionVariables.set("access_token", data.access_token);',
				"}",
				'if (data && data.refresh_token) pm.collectionVariables.set("refresh_token", data.refresh_token);',
			],
		),
	]
	collection["item"].append({"name": "0. Authentication & Session Setup", "item": auth_items})

	# -------------------------------------------------------------
	# Folder 1: Platform User Administration (/v1/admin/users)
	# -------------------------------------------------------------
	platform_user_items = [
		make_request(
			name="1. List Platform Users",
			method="GET",
			path_segments=["v1", "admin", "users"],
			query_params=[
				{"key": "role", "value": "A2C Bank Admin", "description": "Filter by A2C role"},
				{"key": "page", "value": "1"},
				{"key": "page_size", "value": "20"},
			],
			description="List user accounts holding an A2C service role. Supports search, email, role, and enabled filters.",
		),
		make_request(
			name="2. Onboard User Account (Bank Admin)",
			method="POST",
			path_segments=["v1", "admin", "users"],
			description=(
				"Create a user account in the auth service for a Bank Administrator with role `A2C Bank Admin`. "
				"A temporary password is generated and returned once in the response."
			),
			body={
				"full_name": "{{bank_admin_name}}",
				"email": "{{bank_admin_email}}",
				"phone_number": "+251911334455",
				"roles": ["A2C Bank Admin"],
			},
			test_checks=[
				'pm.test("Status code is 200 or 201", function () {',
				"    pm.expect(pm.response.code).to.be.oneOf([200, 201]);",
				"});",
			],
			post_extract=[
				'if (data && data.temporary_password) pm.collectionVariables.set("bank_admin_password", data.temporary_password);',
			],
		),
		make_request(
			name="3. Onboard User Account (Bank Agent / Loan Officer)",
			method="POST",
			path_segments=["v1", "admin", "users"],
			description="Create a user account in the auth service for a Bank Agent / Loan Officer with role `A2C Bank Agent`.",
			body={
				"full_name": "{{agent_name}}",
				"email": "{{agent_email}}",
				"phone_number": "{{agent_phone}}",
				"roles": ["A2C Bank Agent"],
			},
			test_checks=[
				'pm.test("Status code is 200 or 201", function () {',
				"    pm.expect(pm.response.code).to.be.oneOf([200, 201]);",
				"});",
			],
			post_extract=[
				'if (data && data.temporary_password) pm.collectionVariables.set("agent_temp_password", data.temporary_password);',
			],
		),
		make_request(
			name="4. Onboard User Account (Field Development Agent)",
			method="POST",
			path_segments=["v1", "admin", "users"],
			description="Create a user account for a platform-wide field Development Agent with role `A2C Development Agent`.",
			body={
				"full_name": "Field DA Agent",
				"email": "field.da@openagrinet.org",
				"phone_number": "+251911778899",
				"roles": ["A2C Development Agent"],
			},
			test_checks=[
				'pm.test("Status code is 200 or 201", function () {',
				"    pm.expect(pm.response.code).to.be.oneOf([200, 201]);",
				"});",
			],
		),
		make_request(
			name="5. Get User Details",
			method="GET",
			path_segments=["v1", "admin", "users", "{{agent_email}}"],
			description="Account details, contact info, assigned roles, and app profiles of an onboarded user.",
		),
		make_request(
			name="6. Update User Profile",
			method="PATCH",
			path_segments=["v1", "admin", "users", "{{agent_email}}"],
			description="Update user account profile information (first_name, last_name, mobile number).",
			body={
				"first_name": "Haile",
				"last_name": "Gebrselassie (Updated)",
			},
		),
		make_request(
			name="7. Get User Roles",
			method="GET",
			path_segments=["v1", "admin", "users", "{{agent_email}}", "roles"],
			description="List the service roles granted to a specific user account.",
		),
		make_request(
			name="8. Issue Temporary Password",
			method="POST",
			path_segments=["v1", "admin", "users", "{{agent_email}}", "temporary-password"],
			description="Generate a new temporary password for the user and revoke existing sessions.",
			body={"temporary_password": "TempPass#2026"},
			post_extract=[
				'if (data && data.temporary_password) pm.collectionVariables.set("agent_temp_password", data.temporary_password);',
			],
		),
		make_request(
			name="9. List Assignable Service Roles",
			method="GET",
			path_segments=["v1", "admin", "roles"],
			description="List all roles within the A2C service scope that can be granted by an administrator.",
		),
	]
	collection["item"].append(
		{"name": "1. Platform User Administration (/v1/admin/users)", "item": platform_user_items}
	)

	# -------------------------------------------------------------
	# Folder 2: Bank Onboarding & Governance (/v1/banks)
	# -------------------------------------------------------------
	bank_admin_items = [
		make_request(
			name="1. Register Lending Organization (Bank)",
			method="POST",
			path_segments=["v1", "banks"],
			description=(
				"Registers a new lending organization (`A2C Participating Bank`), creates user permission binding, "
				"and sets lifecycle status to `'In Review'`."
			),
			body={
				"bank_name": "{{bank_name}}",
				"bank_code": "{{bank_code}}",
				"entity_type": "Commercial Bank",
				"registered_street": "Bole Sub City, Woreda 03",
				"registered_kebele_village": "Kebele 01",
				"registered_woreda_district": "Bole",
				"registered_zone": "Addis Ababa Zone",
				"registered_region": "Addis Ababa",
				"registered_country": "Ethiopia",
				"registered_postal_code": "1000",
				"registered_email": "compliance@coopbank.com",
				"registered_phone": "+251911000000",
				"website": "https://www.coopbankoromia.com.et",
			},
		),
		make_request(
			name="2. Get Bank Profile",
			method="GET",
			path_segments=["v1", "banks", "me"],
			description="Retrieves caller's organization profile, brand info, address, compliance contacts, and KYC status.",
		),
		make_request(
			name="3. Update Bank Profile",
			method="PATCH",
			path_segments=["v1", "banks", "me"],
			description="Updates organization profile, brand name, website, registered address, and logo URL.",
			body={
				"brand_name": "Coopbank AgriFinance",
				"website": "https://www.coopbankoromia.com.et",
				"registered_street": "Africa Avenue, Mega Building 4th Floor",
			},
		),
		make_request(
			name="4. Upload Bank Logo",
			method="POST",
			path_segments=["v1", "images"],
			description="Uploads a public PNG/JPEG image (max 5MB) for bank branding and returns the storage URL.",
			body={
				"filename": "coopbank_logo.png",
				"filedata": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
			},
			post_extract=[
				'if (data && data.file_url) pm.collectionVariables.set("bank_logo_url", data.file_url);',
			],
		),
		make_request(
			name="5. Upload Regulatory KYC Document (PDF)",
			method="POST",
			path_segments=["v1", "banks", "me", "kyc-documents"],
			description="Uploads private PDF regulatory / banking license compliance document to secure storage.",
			body={
				"filename": "banking_license.pdf",
				"filedata": "JVBERi0xLjQKJcTl8uXrp/Og0MTGCjQgMCBvYmoKPDwgL0xlbmd0aCA1IDAgUiAvRmlsdGVyIC9GbGF0ZURlY29kZSA+PgpzdHJlYW0KeAErVAhUKC4pysxLVwhILClJLVIoLinKzEsHAC9qB44KZW5kc3RyZWFtCmVuZG9iago1IDAgb2JqCjI0CmVuZG9iagoxIDAgb2JqCjw8IC9UeXBlIC9DYXRhbG9nIC9QYWdlcyAyIDAgUiA+PgplbmRvYmoKMiAwIG9iago8PCAvVHlwZSAvUGFnZXMgL0tpZHMgWyAzIDAgUiBdIC9Db3VudCAxID4+CmVuZG9iagozIDAgb2JqCjw8IC9UeXBlIC9QYWdlIC9QYXJlbnQgMiAwIFIgL01lZGlhQm94IFsgMCAwIDYxMiA3OTIgXSAvQ29udGVudHMgNCAwIFIgPj4KZW5kb2JqCnhyZWYKMCA2CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDEzNCAwMDAwMCBuIAowMDAwMDAwMTgzIDAwMDAwIG4gCjAwMDAwMDAyNDQgMDAwMDAgbiAKMDAwMDAwMDAxOSAwMDAwMCBuIAowMDAwMDAwMTE1IDAwMDAwIG4gCnRyYWlsZXIKPDwgL1NpemUgNiAvUm9vdCAxIDAgUiA+PgpzdGFydHhyZWYKMzQ1CiUlRU9GCg==",
			},
		),
		make_request(
			name="6. Download / View KYC Document",
			method="GET",
			path_segments=["v1", "banks", "me", "kyc-documents"],
			query_params=[
				{"key": "view", "value": "1", "description": "Stream document inline for browser preview"}
			],
			description="Streams the bank's stored private KYC compliance document back to the authorized Bank Admin.",
		),
		make_request(
			name="7. Configure Compliance Contacts (GRO & OPS)",
			method="PUT",
			path_segments=["v1", "banks", "me", "contacts"],
			description="Configures mandatory Grievance Redressal Officer (GRO) and Operations (OPS) contacts for the bank.",
			body={
				"gro_name": "Solomon Bogale",
				"gro_mobile": "+251911445566",
				"ops_name": "Tigist Hailu",
				"ops_mobile": "+251911778899",
			},
		),
		make_request(
			name="8. Governance: Approve Bank (In Review -> Active)",
			method="PATCH",
			path_segments=["v1", "banks", "me", "status"],
			description=(
				"Marketplace Governance action: Platform Administrator approves a bank under review "
				"to `'Active'` status, unlocking loan product publishing."
			),
			body={
				"bank_code": "{{bank_code}}",
				"new_status": "Active",
			},
		),
		make_request(
			name="9. Governance: Suspend Bank (Active -> Suspended)",
			method="PATCH",
			path_segments=["v1", "banks", "me", "status"],
			description="Marketplace Governance action: Platform Administrator places a bank on hold / suspended status.",
			body={
				"bank_code": "{{bank_code}}",
				"new_status": "Suspended",
			},
		),
		make_request(
			name="10. Get Bank Dashboard Metrics",
			method="GET",
			path_segments=["v1", "banks", "me", "dashboard", "stats"],
			description="Retrieves aggregate performance metrics (active products, leads, loan applications, approvals).",
		),
	]
	collection["item"].append(
		{"name": "2. Bank Onboarding & Governance (/v1/banks)", "item": bank_admin_items}
	)

	# -------------------------------------------------------------
	# Folder 3: Bank Team Management (/v1/banks/me/team)
	# -------------------------------------------------------------
	team_items = [
		make_request(
			name="1. List Team Members (Bank Agents & Loan Officers)",
			method="GET",
			path_segments=["v1", "banks", "me", "team"],
			description=(
				"Lists all staff members of the caller's bank with role (`A2C Bank Agent`), "
				"active status (`enabled`), and temporary password rotation indicator (`must_change_password`)."
			),
		),
		make_request(
			name="2. Invite / Onboard Bank Agent (Loan Officer)",
			method="POST",
			path_segments=["v1", "banks", "me", "team"],
			description=(
				"Provisions a new Bank Agent / Loan Officer in the caller's bank with a temporary password. "
				"Assigns the `A2C Bank Agent` role, sets `oan_must_change_password=1`, and creates bank `User Permission`."
			),
			body={
				"email": "{{agent_email}}",
				"full_name": "{{agent_name}}",
				"role": "A2C Bank Agent",
				"password": "TempPassword#2026",
			},
		),
		make_request(
			name="3. List Assignable Loan Officers (CRM & Field Ops)",
			method="GET",
			path_segments=["v1", "leads", "assignees"],
			description="Returns all available active bank agents who can be assigned to leads or loan applications.",
		),
		make_request(
			name="4. Update Team Member Profile & Status",
			method="PATCH",
			path_segments=["v1", "banks", "me", "team", "{{agent_email}}"],
			description="Updates team member full name, role assignment, or enables/disables access.",
			body={
				"full_name": "Haile Gebrselassie (Senior Loan Officer)",
				"role": "A2C Bank Agent",
				"enabled": True,
			},
		),
		make_request(
			name="5. Reissue Team Member Temporary Password",
			method="POST",
			path_segments=["v1", "banks", "me", "team", "{{agent_email}}", "password-reset"],
			description=(
				"Reissues a temporary password to an agent (forgotten password path). "
				"Terminates active sessions and requires password rotation at next sign-in."
			),
			body={"password": "NewTempPass#2026"},
		),
		make_request(
			name="6. Deactivate Team Member",
			method="PATCH",
			path_segments=["v1", "banks", "me", "team", "{{agent_email}}"],
			description="Disables bank agent account (`enabled: false`), preventing login and session access.",
			body={"enabled": False},
		),
	]
	collection["item"].append({"name": "3. Bank Team Management (/v1/banks/me/team)", "item": team_items})

	# -------------------------------------------------------------
	# Folder 4: Marketplace Taxonomy Administration (/v1/admin/taxonomy/*)
	# -------------------------------------------------------------
	taxonomy_items = [
		make_request(
			name="1. List Marketplace Categories",
			method="GET",
			path_segments=["v1", "taxonomy", "categories"],
			description="List product categories configured across the agricultural credit marketplace.",
		),
		make_request(
			name="2. Create Marketplace Category",
			method="POST",
			path_segments=["v1", "admin", "taxonomy", "categories"],
			description="Platform Admin action: register a new category for loan cataloging (e.g. Input Loans, Equipment, Livestock).",
			body={
				"name": "Agricultural Input Loan",
				"code": "AGRI-INPUT-01",
				"description": "Short-term seasonal financing for certified seeds, fertilizers, and agrochemicals",
			},
		),
		make_request(
			name="3. List Marketplace Tags",
			method="GET",
			path_segments=["v1", "taxonomy", "tags"],
			description="List discoverability tags defined for product classification.",
		),
		make_request(
			name="4. Create Marketplace Tag",
			method="POST",
			path_segments=["v1", "admin", "taxonomy", "tags"],
			description="Platform Admin action: register a searchable keyword tag (e.g. Seasonal, Low Interest, Smallholder).",
			body={
				"name": "Smallholder Friendly",
				"description": "Products tailored specifically for smallholder farming households",
			},
		),
		make_request(
			name="5. List Product Attributes",
			method="GET",
			path_segments=["v1", "taxonomy", "attributes"],
			description="List dynamic product attribute definitions (e.g. Collateral Type, Repayment Frequency).",
		),
		make_request(
			name="6. Create Attribute Term",
			method="POST",
			path_segments=["v1", "admin", "taxonomy", "attribute-terms"],
			description="Platform Admin action: add an allowed discrete value term under an attribute definition.",
			body={
				"attribute_name": "Collateral Requirement",
				"term_name": "Psychometric / Credit Scoring",
				"code": "PSYCHO-SCORE",
			},
		),
		make_request(
			name="7. List Administrative Areas",
			method="GET",
			path_segments=["v1", "administrative-areas"],
			description="List geographic administrative areas (Regions, Zones, Woredas) available for loan eligibility scoping.",
		),
	]
	collection["item"].append({"name": "4. Marketplace Taxonomy Administration", "item": taxonomy_items})

	# -------------------------------------------------------------
	# Folder 5: Custom Pipeline Stages (/v1/banks/me/pipeline-stages)
	# -------------------------------------------------------------
	stage_items = [
		make_request(
			name="1. List Custom Pipeline Stages",
			method="GET",
			path_segments=["v1", "banks", "me", "pipeline-stages"],
			description="Retrieves the custom loan underwriting pipeline stages configured for the caller's bank.",
		),
		make_request(
			name="2. Add Pipeline Stage",
			method="POST",
			path_segments=["v1", "banks", "me", "pipeline-stages"],
			description="Adds an individual pipeline stage mapped to an archetype state (`In Transition`, `Terminal`).",
			body={
				"label": "Farm Inspection & Verification",
				"archetype_state": "In Transition",
				"sequence": 2,
				"description": "Field visit by loan officer to verify plot boundaries and crop health",
			},
			post_extract=[
				'if (data && data.stage_id) pm.collectionVariables.set("stage_id", data.stage_id);',
			],
		),
		make_request(
			name="3. Sync & Reorder Pipeline Stages",
			method="PUT",
			path_segments=["v1", "banks", "me", "pipeline-stages"],
			description="Bulk synchronizes and reorders the bank's complete underwriting workflow stages.",
			body={
				"stages": [
					{"label": "Document Review", "archetype_state": "In Transition", "sequence": 1},
					{"label": "Field Inspection", "archetype_state": "In Transition", "sequence": 2},
					{"label": "Credit Committee Approval", "archetype_state": "In Transition", "sequence": 3},
					{"label": "Disbursement Ready", "archetype_state": "Terminal", "sequence": 4},
				]
			},
		),
	]
	collection["item"].append(
		{"name": "5. Custom Pipeline Stages (/v1/banks/me/pipeline-stages)", "item": stage_items}
	)

	# -------------------------------------------------------------
	# Folder 6: Loan Products Cataloging (/v1/banks/me/products)
	# -------------------------------------------------------------
	product_items = [
		make_request(
			name="1. List Bank Loan Products",
			method="GET",
			path_segments=["v1", "banks", "me", "products"],
			description="List loan products cataloged by the bank, with filtering by status (`Draft`, `Published`, `Archived`).",
			post_extract=[
				'if (data && data.products && data.products.length > 0) pm.collectionVariables.set("product_id", data.products[0].id);',
			],
		),
		make_request(
			name="2. Create Loan Product",
			method="POST",
			path_segments=["v1", "banks", "me", "products"],
			description="Defines a new agricultural loan product with loan amount thresholds, tenure, interest rate, and requirements.",
			body={
				"product_name": "Smallholder Fertilizer Financing 2026",
				"product_type": "Crop Loan",
				"description": "Financing for inorganic fertilizers (Urea & NPSB) for the Meher crop season.",
				"min_amount": 5000,
				"max_amount": 50000,
				"currency": "ETB",
				"min_tenure_months": 3,
				"max_tenure_months": 12,
				"interest_rate": 14.5,
				"processing_fee_percentage": 1.0,
			},
			post_extract=[
				'if (data && data.id) pm.collectionVariables.set("product_id", data.id);',
			],
		),
		make_request(
			name="3. Get Loan Product Details",
			method="GET",
			path_segments=["v1", "banks", "me", "products", "{{product_id}}"],
			description="Inspect loan product attributes, categories, eligible regions, and fee schedules.",
		),
		make_request(
			name="4. Update Loan Product",
			method="PATCH",
			path_segments=["v1", "banks", "me", "products", "{{product_id}}"],
			description="Update product terms: maximum borrowing limits, interest rate, or tenure options.",
			body={
				"max_amount": 60000,
				"interest_rate": 13.9,
			},
		),
		make_request(
			name="5. Publish Loan Product",
			method="PATCH",
			path_segments=["v1", "banks", "me", "products", "{{product_id}}", "status"],
			description="Transitions product lifecycle status from `'Draft'` to `'Published'`, making it visible to farmers and agents.",
			body={"status": "Published"},
		),
		make_request(
			name="6. Get Product Audit Log",
			method="GET",
			path_segments=["v1", "banks", "me", "products", "{{product_id}}", "audit-log"],
			description="Retrieves the chronological status transition history and audit timestamps for the product.",
		),
	]
	collection["item"].append(
		{"name": "6. Loan Products Cataloging (/v1/banks/me/products)", "item": product_items}
	)

	# -------------------------------------------------------------
	# Folder 7: Officer Assignment & Field Operations
	# -------------------------------------------------------------
	ops_items = [
		make_request(
			name="1. Assign Loan Officer / Agent to Lead",
			method="PATCH",
			path_segments=["v1", "leads", "{{lead_id}}", "assignment"],
			description="Assigns a specific bank agent / loan officer to follow up on a referred borrower lead.",
			body={"agent": "{{agent_email}}"},
		),
		make_request(
			name="2. Assign Loan Officer to Loan Application",
			method="PATCH",
			path_segments=["v1", "loan-applications", "{{loan_application_id}}", "officer"],
			description="Assigns or reassigns the dedicated underwriting loan officer responsible for reviewing a submitted loan application.",
			body={"officer": "{{agent_email}}"},
		),
	]
	collection["item"].append({"name": "7. Officer Assignment & Field Operations", "item": ops_items})

	return collection


def main():
	col = build_collection()
	out_file = Path("postman/a2c_admin.postman_collection.json")
	with open(out_file, "w", encoding="utf-8") as f:
		json.dump(col, f, indent=2)
	print(f"Generated {out_file} successfully with {len(col['item'])} modules!")


if __name__ == "__main__":
	main()
