import collections
import json

import frappe
from frappe.utils import flt

from mjfsd_v3.loom_production.warehouse_defaults import pick


def _source_warehouse(sizing_receipt):
	"""Warehouse the yarn is taken from for every entry made from a Sizing Receipt: the receipt's own Source Warehouse,
	else Emadi Settings > Sizing Receipt Source Warehouse. Never a fixed name."""
	return pick(sizing_receipt.get("source_warehouse"), "sizing_receipt_source_warehouse", "Source Warehouse")


def _target_warehouse(sizing_receipt):
	return pick(sizing_receipt.get("target_warehouse"), "sizing_receipt_target_warehouse", "Target Warehouse")


def create_manufacture_stock_entry(sizing_receipt, batches=None):
	"""Called from Sizing Receipt's on_submit. Consumes the Yarn Item (Lbs)
	from the Sizing Receipt's Source Warehouse and receives the Beam item (Meter) into the
	Sizing Receipt's own Target Warehouse.

	Note: unlike the old (now-removed) manual "Make Stock Entry" button
	flow in create_stock_entry_from_sizing_program.py, this does not create
	a Batch for the finished item, does not post Sizing Amount / Wastage
	Amount as additional_costs, and does not raise a Journal Entry for the
	sizing charge - none of that was in the round 13 spec. Flag if any of
	it needs to carry over to this automatic flow.
	"""
	if batches and sizing_receipt.get("yarn_items"):
		return _create_entries_per_beam_item(sizing_receipt, batches)

	source_warehouse = _source_warehouse(sizing_receipt)
	target_warehouse = _target_warehouse(sizing_receipt)

	sizing_program = frappe.get_doc("Sizing Program", sizing_receipt.sizing_program)
	# allow_zero_valuation_rate mirrors the existing convention on Sizing
	# Program's own Conversion checkbox (see its field description) - carried
	# over here so this entry doesn't hard-fail on a missing valuation rate
	# the same way the old manual flow was protected.
	allow_zero_valuation = 1 if sizing_program.conversion == 1 else 0

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Beem Receipt Entry"
	se.purpose = "Manufacture"
	se.set_posting_time = 1
	se.posting_date = sizing_receipt.get("date") or sizing_program.date
	se.sizing_program = sizing_receipt.sizing_program

	# 2026-09-16 round 19 fix: "on sizing receipt stock entry, input rate
	# is still 0" (your words) - this row never set basic_rate at all, so
	# it relied entirely on Frappe's own warehouse-ledger valuation for
	# the Yarn Item in the source warehouse. Same root cause already found
	# twice elsewhere this session (Sizing Receipt's own Yarn Item Rate
	# field, round 16; this same pattern is why fetch_current_rate.py
	# reads Item.valuation_rate directly): stock-ledger/Bin valuation
	# isn't reliable in this setup, but Item.valuation_rate is. Fetched
	# and set explicitly here for the same reason, with
	# set_basic_rate_manually so it isn't silently overwritten (round 17's
	# fix, same lesson, applied to this row too).
	# One consumption row per yarn (a multi-yarn receipt has several).
	from mjfsd_v3.loom_production.events.sizing_yarn_rows import consumption_lines

	for yarn_item, yarn_lbs in consumption_lines(sizing_receipt):
		yarn_item_rate = flt(frappe.db.get_value("Item", yarn_item, "valuation_rate"))
		se.append("items", {
			"item_code": yarn_item,
			"qty": yarn_lbs,
			"uom": "Lbs",
			"stock_uom": "Lbs",
			"conversion_factor": 1,
			"s_warehouse": source_warehouse,
			"basic_rate": yarn_item_rate,
			"basic_amount": yarn_item_rate * flt(yarn_lbs),
			"set_basic_rate_manually": 1,
			"allow_zero_valuation_rate": allow_zero_valuation,
		})

	# Finished item: the Beam item, in Meter. Length (Beam No x Beem Length,
	# round 5 formula) is the field already carrying this beam's total
	# meters, so it's used as the qty here - flag if Beem Length alone
	# (per-beam, not total) was actually intended instead.
	#
	# Round 14 item 3: rate = Final Cost Of Beam / Beem Length, per spec.
	# NOTE - flagging a real unit mismatch: Beem Length is ONE beam's meters,
	# but qty above (Length) is Beam No x Beem Length, i.e. ALL beams'
	# meters. So basic_rate (Currency/Beem Length) x qty (Beam No x Beem
	# Length) = Final Cost Of Beam x Beam No - the Stock Entry's total
	# valuation for this row is Beam No times too large whenever Beam No is
	# more than 1. Implemented exactly as specified below; if Beam No is
	# ever > 1 in practice, the rate should probably instead be Final Cost
	# Of Beam / Length (total meters) to keep rate x qty = Final Cost Of
	# Beam. Say the word if this needs switching.
	beem_length = flt(sizing_receipt.beem_length)
	basic_rate = flt(sizing_receipt.final_cost_of_beam) / beem_length if beem_length else 0

	# 2026-09-16 fix: "manufacture stock entry of sizing receipt doesn't
	# calculate finish rate of item" (your words). The basic_rate above was
	# already being computed and set correctly (this is the round 14
	# formula, unchanged) - the missing piece is set_basic_rate_manually.
	# Without it, a Manufacture-purpose Stock Entry has Frappe's own
	# valuation engine recompute the finished row's rate itself on
	# save/submit (normally from the consumed raw-material rows' value),
	# silently overwriting whatever basic_rate was set here - the exact
	# same class of bug already documented in claude/weaving-receipt.md's
	# "Lesson for future rate-dependent Stock Entry code in this project".
	# This flag tells Frappe to keep the manually-set rate instead.
	finish_amount = flt(basic_rate) * flt(sizing_receipt.length)
	raw_qty_lbs = flt(sizing_receipt.lbs)

	# 2026-09-28 (feature v3) - "Per LBS Rate = Total Incoming Value /
	# Outgoing total qty" (your words). This Stock Entry only ever has one
	# incoming row (this finish row, t_warehouse set) and one outgoing row
	# (the Yarn Item row above, s_warehouse set, already in Lbs) - so
	# Total Incoming Value is this row's own amount and Outgoing total
	# qty is the raw Yarn Item's qty. Written onto custom_per_lbs_rate,
	# the same Stock Entry Detail custom field already used the same way
	# on the Weaving Receipt's own Manufacture Stock Entry.
	per_lbs_rate = (finish_amount / raw_qty_lbs) if raw_qty_lbs else 0

	finish_row = {
		"item_code": sizing_receipt.item,
		"qty": sizing_receipt.length,
		"uom": "Meter",
		"stock_uom": "Meter",
		"conversion_factor": 1,
		"t_warehouse": target_warehouse,
		"is_finished_item": 1,
		"basic_rate": basic_rate,
		"basic_amount": finish_amount,
		"set_basic_rate_manually": 1,
		"allow_zero_valuation_rate": allow_zero_valuation,
		"custom_per_lbs_rate": per_lbs_rate,
	}

	if batches:
		# The Beam item is batch tracked: one finished row per beam/Batch. The
		# receipt's total Length is split evenly across them, so the total
		# quantity and value are exactly what they were with a single row.
		se.use_serial_batch_fields = 1
		per_beam_qty = flt(sizing_receipt.length) / len(batches)
		for batch in batches:
			se.append(
				"items",
				dict(
					finish_row,
					qty=per_beam_qty,
					basic_amount=basic_rate * per_beam_qty,
					batch_no=batch,
					use_serial_batch_fields=1,
				),
			)
	else:
		se.append("items", finish_row)

	se.save(ignore_permissions=True)
	se.submit()
	return se.name


def _create_entries_per_beam_item(sizing_receipt, batches):
	"""Yarn Details mode. ERPNext allows only ONE finished item per
	Manufacture Stock Entry, so a receipt holding several Beam Items (Pile and
	Ground) raises one Beem Receipt entry per Beam Item. Each one consumes
	the yarn of its own rows and receives its beams, one row per beam
	(Batch): the item's meters are split evenly over its beams and the rate
	is that item's yarn + sizing cost / its meters. Names of all the entries
	are kept in the receipt's stock_entries_json (the first also in
	manufacture_stock_entry) so cancel removes every one."""
	from mjfsd_v3.loom_production.events.sizing_yarn_rows import beam_item_groups

	source_warehouse = _source_warehouse(sizing_receipt)
	target_warehouse = _target_warehouse(sizing_receipt)

	sizing_program = frappe.get_doc("Sizing Program", sizing_receipt.sizing_program)
	allow_zero = 1 if sizing_program.conversion == 1 else 0

	# batches were created in the order of beam_item_groups
	per_item = collections.OrderedDict()
	i = 0
	for g in beam_item_groups(sizing_receipt):
		entry = per_item.setdefault(g["item"], {"beams": [], "yarn": {}, "cost": 0.0, "lbs": 0.0})
		for _n in range(g["beams"]):
			entry["beams"].append((batches[i], g["net"] / g["beams"], g["cost"] / g["net"] if g["net"] else 0))
			i += 1
		entry["cost"] += g["cost"]
		entry["lbs"] += g["lbs"]
		for r in g["rows"]:
			entry["yarn"][r.yarn_item] = entry["yarn"].get(r.yarn_item, 0) + flt(r.lbs)

	names = []
	for item, entry in per_item.items():
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Beem Receipt Entry"
		se.purpose = "Manufacture"
		se.set_posting_time = 1
		se.posting_date = sizing_receipt.get("date") or sizing_program.date
		se.sizing_program = sizing_receipt.sizing_program
		se.use_serial_batch_fields = 1

		for yarn_item, yarn_lbs in entry["yarn"].items():
			rate = flt(frappe.db.get_value("Item", yarn_item, "valuation_rate"))
			se.append("items", {
				"item_code": yarn_item,
				"qty": yarn_lbs,
				"uom": "Lbs",
				"stock_uom": "Lbs",
				"conversion_factor": 1,
				"s_warehouse": source_warehouse,
				"basic_rate": rate,
				"basic_amount": rate * flt(yarn_lbs),
				"set_basic_rate_manually": 1,
				"allow_zero_valuation_rate": allow_zero,
			})

		per_lbs = entry["cost"] / entry["lbs"] if entry["lbs"] else 0
		for batch, qty, rate in entry["beams"]:
			se.append("items", {
				"item_code": item,
				"qty": qty,
				"uom": "Meter",
				"stock_uom": "Meter",
				"conversion_factor": 1,
				"t_warehouse": target_warehouse,
				"is_finished_item": 1,
				"basic_rate": rate,
				"basic_amount": rate * qty,
				"set_basic_rate_manually": 1,
				"allow_zero_valuation_rate": allow_zero,
				"custom_per_lbs_rate": per_lbs,
				"batch_no": batch,
				"use_serial_batch_fields": 1,
			})

		se.save(ignore_permissions=True)
		se.submit()
		names.append(se.name)

	sizing_receipt.db_set("stock_entries_json", json.dumps(names), update_modified=False)
	return names[0]


def create_material_transfer_stock_entry(sizing_receipt):
	"""Called from Sizing Receipt's on_submit, only when the Stock Return
	Item table has rows. One Material Transfer entry covering every row,
	from the Source Warehouse (same source as the Manufacture entry above) to
	each row's own Target Warehouse.
	"""
	sizing_program = frappe.get_doc("Sizing Program", sizing_receipt.sizing_program)
	source_warehouse = _source_warehouse(sizing_receipt)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.purpose = "Material Transfer"
	se.set_posting_time = 1
	se.posting_date = sizing_receipt.get("date") or sizing_program.date
	se.sizing_program = sizing_receipt.sizing_program

	for row in sizing_receipt.stock_return_item:
		se.append("items", {
			"item_code": row.yarn_item,
			"qty": row.qty_lbs,
			"uom": "Lbs",
			"stock_uom": "Lbs",
			"conversion_factor": 1,
			"s_warehouse": source_warehouse,
			"t_warehouse": row.target_warehouse,
		})

	se.save(ignore_permissions=True)
	se.submit()
	return se.name


def cancel_linked_stock_entries(sizing_receipt):
	"""Called from Sizing Receipt's on_cancel. Cancels whichever of the two
	tracked Stock Entries were actually created (Material Transfer is
	conditional, so it may not exist)."""
	extra = []
	if sizing_receipt.get("stock_entries_json"):
		try:
			extra = json.loads(sizing_receipt.stock_entries_json)
		except ValueError:
			extra = []
	names = [sizing_receipt.get("manufacture_stock_entry"), *extra, sizing_receipt.get("material_transfer_stock_entry")]
	for se_name in dict.fromkeys(n for n in names if n):
		if frappe.db.exists("Stock Entry", se_name):
			se = frappe.get_doc("Stock Entry", se_name)
			if se.docstatus == 1:
				se.cancel()
