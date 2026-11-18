"""Fabric Issuance Entry (FIE): sends greige fabric to a dyer.

Rows come from Dyeing Contracts ("Get Items from Dyeing Contract"), the rolls of each row are picked with "Fetch Rolls"
from the Daily Loom Production / Weaving Receipt documents that created them, and on submit one Material Transfer Stock
Entry (Greige Warehouse -> Supplier Warehouse) is made and the Dyeing Contract's issued qty / rolls / weight are refreshed.
"""
import json

import frappe
from frappe import _
from frappe.utils import flt

from mjfsd_v3.loom_production.events.dyeing_calc import DYEING_TYPE_FIELDS, get_tcs_finish_row

LBS_PER_KG = 2.2046


# ───────────────────────────── Get Items from Dyeing Contract ─────────────────────────────
def find_weaving_contract(sales_order, item_code):
	"""Submitted Weaving Contract of this Sales Order that makes this item (its Finish Item, or a Finish Item of its BOM rows)."""
	if not (sales_order and item_code):
		return None
	name = frappe.db.get_value(
		"Weaving Contract", {"sales_order": sales_order, "construction": item_code, "docstatus": 1}, "name"
	)
	if name:
		return name
	rows = frappe.db.sql(
		"""
		select wc.name from `tabWeaving Contract` wc
		inner join `tabBOM Items` b on b.parent = wc.name and b.parenttype = 'Weaving Contract'
		where wc.docstatus = 1 and wc.sales_order = %s and b.finish_item = %s limit 1
		""",
		(sales_order, item_code),
	)
	return rows[0][0] if rows else None


def _type_and_qty(item):
	"""('Solid' | 'Stripe' | 'Yarn Dyed', qty) from whichever of the three columns of a Dyeing Contract Item has a value."""
	for label, field in DYEING_TYPE_FIELDS.items():
		if flt(item.get(field)):
			return label, flt(item.get(field))
	return None, flt(item.get("order_qty"))


@frappe.whitelist()
def get_items_from_dyeing_contracts(contracts):
	if isinstance(contracts, str):
		contracts = json.loads(contracts)
	out, tcs_cache = [], {}
	for name in contracts or []:
		dc = frappe.get_doc("Dyeing Contract", name)
		if dc.docstatus != 1:
			frappe.throw(_("Dyeing Contract {0} is not submitted.").format(name))
		for item in dc.items or []:
			label, qty = _type_and_qty(item)
			tcs_row = get_tcs_finish_row(tcs_cache, item.towel_costing_sheet, item.item) or {}
			greige_weight = 0
			if item.towel_costing_sheet and item.item:
				greige_weight = flt(
					frappe.db.get_value(
						"Finish Item Towel Costing", {"parent": item.towel_costing_sheet, "article": item.item}, "greige_weight"
					)
				)
			out.append(
				{
					"item_code": item.item,
					"color": item.color,
					"type": label,
					"qty": qty,
					"finish_weight": flt(tcs_row.get("finish_weight")),
					"greige_weight": greige_weight,
					"sales_order": item.sales_order,
					"towel_costing_sheet": item.towel_costing_sheet,
					"greige_batch": item.greige_batch,
					"weaving_contract": find_weaving_contract(item.sales_order, item.item),
					"dyeing_contract": dc.name,
					"dyeing_contract_item": item.name,
					"supplier": dc.supplier,
				}
			)
	return out


# ───────────────────────────── Fetch Rolls ─────────────────────────────
DLP_ROLLS = """
	select dlpi.name as source_name, dlpi.parent as parent_doc, dlpi.roll_number as roll_no,
	       dlpi.finish_qty as pcs, dlpi.weight_kg as weight_kg
	from `tabDaily Loom Production Item` dlpi
	inner join `tabDaily Loom Production` d on d.name = dlpi.parent and dlpi.parenttype = 'Daily Loom Production'
	where d.docstatus = 1 and dlpi.item = %(item)s and ifnull(dlpi.roll_number, '') != ''
	  and (dlpi.sales_order = %(so)s or (ifnull(%(wc)s, '') != '' and dlpi.weaving_contract = %(wc)s))
"""
WR_ROLLS = """
	select wrd.name as source_name, wrd.parent as parent_doc, wrd.roll_no as roll_no,
	       wrd.total_pcs as pcs, wrd.weight as weight_kg
	from `tabWeaving Receipt Detail` wrd
	inner join `tabWeaving Receipt` w on w.name = wrd.parent and wrd.parenttype = 'Weaving Receipt'
	inner join `tabWeaving Receipt Item` wri on wri.parent = w.name and wri.row_key = wrd.item_row
	where w.docstatus = 1 and wri.finish_item = %(item)s and ifnull(wrd.roll_no, '') != ''
	  and (wri.sales_order = %(so)s or (ifnull(%(wc)s, '') != '' and wri.weaving_contract = %(wc)s))
"""


def _taken(exclude_fie=None):
	"""{(source_doctype, source_name)} already on another FIE that is not cancelled."""
	rows = frappe.db.sql(
		"""
		select r.source_doctype, r.source_name
		from `tabFabric Issuance Entry Roll` r
		inner join `tabFabric Issuance Entry` f on f.name = r.parent and r.parenttype = 'Fabric Issuance Entry'
		where f.docstatus < 2 and f.name != %s
		""",
		(exclude_fie or "",),
	)
	return {(a, b) for a, b in rows}


@frappe.whitelist()
def get_rolls(sales_order, item_code, weaving_contract=None, exclude_fie=None):
	"""Rolls created for this item against this Sales Order (Daily Loom Production + Weaving Receipt), not yet issued on another FIE."""
	args = {"so": sales_order or "", "item": item_code, "wc": weaving_contract or ""}
	taken = _taken(exclude_fie)
	out = []
	for source_doctype, sql in (("Daily Loom Production", DLP_ROLLS), ("Weaving Receipt", WR_ROLLS)):
		for r in frappe.db.sql(sql, args, as_dict=True):
			if (source_doctype, r.source_name) in taken:
				continue
			out.append(
				{
					"source_doctype": source_doctype,
					"parent_doc": r.parent_doc,
					"source_name": r.source_name,
					"roll_no": str(r.roll_no).strip(),
					"pcs": flt(r.pcs),
					"weight_kg": flt(r.weight_kg),
				}
			)
	return out


# ───────────────────────────── validate / totals ─────────────────────────────
def _rolls_of(doc, row_key):
	return [r for r in doc.get("roll_details") or [] if r.item_row == row_key]


def apply_row_totals(doc):
	"""Row figures follow the picked rolls: Rolls text, Qty = pieces, Weight (Kg) = sum, Weight (LBS) = Kg x 2.2046."""
	for row in doc.get("items") or []:
		if not row.get("row_key"):
			row.row_key = frappe.generate_hash(length=10)
		rolls = _rolls_of(doc, row.row_key)
		if rolls:
			row.rolls = ", ".join(r.roll_no for r in rolls)
			row.qty = sum(flt(r.pcs) for r in rolls)
			row.weight_kg = sum(flt(r.weight_kg) for r in rolls)
		else:
			row.rolls = ""
		row.weight_lbs = flt(row.weight_kg) * LBS_PER_KG


def _refresh_weights(doc):
	tcs_cache = {}
	for row in doc.get("items") or []:
		if not (row.towel_costing_sheet and row.item_code):
			continue
		tcs_row = get_tcs_finish_row(tcs_cache, row.towel_costing_sheet, row.item_code) or {}
		if tcs_row:
			row.finish_weight = flt(tcs_row.get("finish_weight"))
		row.greige_weight = flt(
			frappe.db.get_value(
				"Finish Item Towel Costing", {"parent": row.towel_costing_sheet, "article": row.item_code}, "greige_weight"
			)
		)


def validate_entry(doc):
	if not doc.get("items"):
		frappe.throw(_("Add at least one item."))
	_refresh_weights(doc)
	apply_row_totals(doc)

	keys = {r.row_key for r in doc.items}
	doc.roll_details = [r for r in doc.get("roll_details") or [] if r.item_row in keys]   # rolls of deleted rows go away
	taken = _taken(doc.name if not doc.is_new() else None)
	seen = set()
	for r in doc.roll_details:
		key = (r.source_doctype, r.source_name)
		if key in taken:
			frappe.throw(_("Roll# {0} ({1} {2}) is already on another Fabric Issuance Entry.").format(r.roll_no, r.source_doctype, r.parent_doc))
		if key in seen:
			frappe.throw(_("Roll# {0} is listed twice.").format(r.roll_no))
		seen.add(key)

	for row in doc.items:
		if flt(row.qty) <= 0:
			frappe.throw(_("Row {0}: Qty must be more than 0.").format(row.idx))
		if row.get("dyeing_contract_item"):
			order_qty, issued = frappe.db.get_value("Dyeing Contract Item", row.dyeing_contract_item, ["order_qty", "issued_qty"]) or (0, 0)
			if flt(row.qty) > flt(order_qty) - flt(issued) + 0.001:
				frappe.throw(
					_("Row {0}: Qty {1} is more than what is left on {2} ({3}).").format(
						row.idx, flt(row.qty), row.dyeing_contract, max(flt(order_qty) - flt(issued), 0)
					)
				)


def validate_before_submit(doc):
	for row in doc.items:
		if not row.get("greige_batch"):
			frappe.throw(_("Row {0} ({1}): Greige Batch is required.").format(row.idx, row.item_code))
		if not _rolls_of(doc, row.row_key):
			frappe.throw(_("Row {0} ({1}): pick the rolls first (Fetch Rolls).").format(row.idx, row.item_code))
	if not (doc.greige_warehouse and doc.supplier_warehouse):
		frappe.throw(_("Greige Warehouse and Supplier Warehouse are required."))


# ───────────────────────────── stock + Dyeing Contract on submit / cancel ─────────────────────────────
def _contracts(doc):
	return sorted({r.dyeing_contract for r in doc.items if r.get("dyeing_contract")})


def _resync(doc):
	from mjfsd_v3.loom_production.events.issue_fabric import sync_issued_totals

	for name in _contracts(doc):
		sync_issued_totals(name)


def make_stock_entry(doc):
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.purpose = "Material Transfer"
	se.company = frappe.defaults.get_global_default("company")
	se.set_posting_time = 1
	se.posting_date = doc.date
	se.custom_fabric_issuance_entry = doc.name
	contracts = _contracts(doc)
	if len(contracts) == 1:
		se.custom_dyeing_contract = contracts[0]

	for row in doc.items:
		rolls = _rolls_of(doc, row.row_key)
		se.append(
			"items",
			{
				"s_warehouse": doc.greige_warehouse,
				"t_warehouse": doc.supplier_warehouse,
				"item_code": row.item_code,
				"qty": flt(row.qty),
				"uom": frappe.db.get_value("Item", row.item_code, "stock_uom"),
				"batch_no": row.greige_batch,
				"use_serial_batch_fields": 1,
				"custom_no_of_rolls": len(rolls),
				"custom_weight_kgs": flt(row.weight_kg),
				"custom_roll_no": row.rolls,
				"custom_dyeing_contract_item": row.get("dyeing_contract_item"),
			},
		)
	se.insert(ignore_permissions=True)
	se.submit()
	doc.db_set("stock_entry", se.name, update_modified=False)

	for name in contracts:
		if not frappe.db.get_value("Dyeing Contract", name, "status"):
			frappe.db.set_value("Dyeing Contract", name, "status", "Fabric Issued")
	_resync(doc)


def cancel_stock_entry(doc):
	if doc.get("stock_entry") and frappe.db.exists("Stock Entry", doc.stock_entry):
		se = frappe.get_doc("Stock Entry", doc.stock_entry)
		if se.docstatus == 1:
			se.cancel()
	_resync(doc)
