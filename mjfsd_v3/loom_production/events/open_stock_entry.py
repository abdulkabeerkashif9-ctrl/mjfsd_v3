import frappe
from frappe import _
from frappe.utils import flt

from mjfsd_v3.loom_production.warehouse_defaults import pick

# 2026-09-28 fix - "Sizing Program Gate Pass (Material Transfer Stock
# Entry) Source Warehouse = Stores - PT, Target Warehouse = Supplier - PT,
# Qty not calculated correctly. Qty = bags_issue (from sizing program) *
# 100" (your words). This was leftover scaffolding (its own comments said
# "simplified example" / "or appropriate type") - it only ever set
# t_warehouse (to sp.source_warehouse, the wrong field entirely), never
# set s_warehouse at all, and used sp.lbs as qty instead of the Bags
# Issue formula. Fixed to the fixed Source/Target pair below (same
# pattern as Issue Yarn's own SOURCE_WAREHOUSE/TARGET_WAREHOUSE) and the
# qty formula given.

# Source/Target: the Sizing Program's own warehouses, else Emadi Settings > Sizing Program (no hardcoded names).


@frappe.whitelist()
def open_stock_entry(sizing_program_name):
	"""Creates the "Gate Pass" (a Material Transfer Stock Entry) for a
	given Sizing Program. Draft only - user reviews and submits it
	himself, same pattern as every other "prefill, open the form" button
	in this project."""
	sp = frappe.get_doc("Sizing Program", sizing_program_name)
	SOURCE_WAREHOUSE = pick(sp.get("source_warehouse"), "sizing_program_source_warehouse", "Source Warehouse")
	TARGET_WAREHOUSE = pick(sp.get("target_warehouse"), "sizing_program_target_warehouse", "Target Warehouse")

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.custom_sizing_program_gate_pass = sp.name
	se.purpose = "Material Transfer"
	se.set_posting_time = 1
	se.posting_date = sp.date

	if sp.get("yarn_items"):
		# Yarn Details mode: one row per Yarn Item with the LBS Issue of the program (rows of the same yarn added together)
		totals = {}
		for r in sp.yarn_items:
			if not r.yarn_item:
				frappe.throw(_("Row {0}: Yarn Item is required.").format(r.idx))
			totals[r.yarn_item] = totals.get(r.yarn_item, 0) + flt(r.lbs_issue)
		lines = [(item, qty) for item, qty in totals.items() if qty > 0]
		if not lines:
			frappe.throw(_("LBS Issue is 0 on every row of {0}; enter Net Meter, Ends and Yarn Count first.").format(sp.name))
	else:
		if not sp.item:
			frappe.throw(_("Set Brand (the yarn item) on {0} first.").format(sp.name))
		lines = [(sp.item, flt(sp.bags_issue) * 100)]

	for item_code, qty in lines:
		stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
		if not stock_uom:
			frappe.throw(_("Item {0} not found.").format(item_code))
		se.append("items", {
			"item_code": item_code,
			"qty": qty,
			"s_warehouse": SOURCE_WAREHOUSE,
			"t_warehouse": TARGET_WAREHOUSE,
			"uom": stock_uom,
			"stock_uom": stock_uom,
			"conversion_factor": 1,
		})

	return se
