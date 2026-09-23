import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def create_dyeing_contract_from_sales_order(sales_order):
	so = frappe.get_doc("Sales Order", sales_order)
	if so.docstatus != 1:
		frappe.throw(_("Sales Order must be submitted first - Color/Greige batches are only created on submit."))

	dc = frappe.new_doc("Dyeing Contract")
	dc.sales_order = so.name

	for row in so.items:
		if not row.get("custom_color"):
			# Rows with no Color set aren't going through dyeing (e.g. a
			# Greige-only line) - skipped rather than forced in, since
			# there's nothing to dye and no Color batch to consume/produce.
			continue

		tcs = row.get("custom_towel_costing_sheet")
		dc.append(
			"items",
			{
				"item": row.item_code,
				"color": row.custom_color,
				"order_qty": row.get("custom_ab_qty"),
				"dyeing_wastage_percent": _get_dyeing_wastage_percent(tcs, row.item_code),
				"sales_order": so.name,
				"sales_order_item": row.name,
				"towel_costing_sheet": tcs,
				"greige_batch": row.get("custom_greige_batch"),
			},
		)

	if not dc.items:
		frappe.throw(_("No Sales Order Items have a Color set - nothing to send for dyeing."))

	return dc


def _get_dyeing_wastage_percent(towel_costing_sheet, item_code):
	"""Looks up Dyeing Wastage % from the Towel Costing Sheet's Finish Item
	Towel Costing row for this item. Doesn't hard-code that child table's
	fieldname on the parent - finds it via meta instead - since the exact
	fieldname wasn't confirmed; if it can't find a match it returns 0
	(non-blocking: this only pre-fills a suggested value, which you review
	before saving/submitting the Dyeing Contract, not a stock-posting
	number). Flag if this comes back 0 when it shouldn't.
	"""
	if not towel_costing_sheet:
		return 0

	table_fieldname = None
	for df in frappe.get_meta("Towel Costing Sheet").get_table_fields():
		if df.options == "Finish Item Towel Costing":
			table_fieldname = df.fieldname
			break
	if not table_fieldname:
		return 0

	tcs = frappe.get_doc("Towel Costing Sheet", towel_costing_sheet)
	for row in tcs.get(table_fieldname) or []:
		# "article" confirmed as the real fieldname (see
		# create_stock_entry_from_weaving_receipt.py's own
		# _get_weaving_wastage_percent) - item/finish_item kept as
		# fallbacks only.
		row_item = row.get("article") or row.get("item") or row.get("finish_item")
		if row_item == item_code:
			return flt(row.get("custom_dyeing_wastage_percent"))

	return 0
