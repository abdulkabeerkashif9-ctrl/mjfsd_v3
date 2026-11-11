"""Default warehouses live in one place: the single doctype "Emadi Settings" (emadi_v3 app).

Rule used everywhere: the warehouse written on the document itself wins; Emadi Settings fills in only when the
document has none; if neither has one the user is told exactly which setting to fill in. Nothing is hardcoded.
"""
import frappe
from frappe import _

SETTINGS = "Emadi Settings"


def default_warehouse(key):
	"""Value of `key` in Emadi Settings, or None (also when that app/doctype is not installed)."""
	try:
		if not frappe.db.exists("DocType", SETTINGS):
			return None
		return frappe.db.get_single_value(SETTINGS, key) or None
	except Exception:
		return None


def pick(doc_value, key, what=None):
	"""doc_value if set, else the Emadi Settings default for `key`; throws a clear message when both are empty."""
	if doc_value:
		return doc_value
	wh = default_warehouse(key)
	if wh:
		return wh
	label = what or frappe.get_meta(SETTINGS).get_label(key) if frappe.db.exists("DocType", SETTINGS) else key
	frappe.throw(
		_("No warehouse set: fill in {0} on the document, or set <b>{1}</b> in <a href='/app/emadi-settings'>Emadi Settings</a>.").format(
			what or label, label
		),
		title=_("Warehouse missing"),
	)


@frappe.whitelist()
def get_defaults():
	"""All warehouse defaults, for the browser (forms pre-fill empty warehouse fields from these)."""
	if not frappe.db.exists("DocType", SETTINGS):
		return {}
	meta = frappe.get_meta(SETTINGS)
	return {
		f.fieldname: frappe.db.get_single_value(SETTINGS, f.fieldname)
		for f in meta.fields
		if f.fieldtype == "Link" and f.options == "Warehouse"
	}


def fill_empty(doc, mapping):
	"""mapping: {doc fieldname: settings key}. Fills empty fields only."""
	for fieldname, key in mapping.items():
		if not doc.get(fieldname):
			wh = default_warehouse(key)
			if wh:
				doc.set(fieldname, wh)
