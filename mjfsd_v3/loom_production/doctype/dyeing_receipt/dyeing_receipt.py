import frappe
from frappe.model.document import Document
from frappe.utils import flt

from mjfsd_v3.loom_production.events.create_repack_stock_entry_from_dyeing_receipt import (
	cancel_linked_stock_entry,
	create_repack_stock_entry,
)


class DyeingReceipt(Document):
	def validate(self):
		self.recalculate_totals()

	def on_submit(self):
		create_repack_stock_entry(self)

	def on_cancel(self):
		cancel_linked_stock_entry(self)

	def recalculate_totals(self):
		tcs_cache = {}
		for row in self.items or []:
			# 2026-09-15 (feature v3) - Weight (Actual) in Lbs, needed by the
			# new Per LBS Rate field on the Repack Stock Entry's finish row.
			row.weight_received_lbs = flt(row.weight_received_kg) * 2.2046
			# 2026-09-16 fix: Rate is a rate PER LBS (fetched from the
			# Dyeing Contract), not per piece - `Rate x Received Qty` was
			# the same per-lbs/per-piece unit mismatch fixed the same day
			# on the Repack Stock Entry's finish row. This row's own
			# dyeing charge is Rate x total Lbs, not Rate x Pcs.
			row.amount = flt(row.rate) * row.weight_received_lbs
			# 2026-09-15: Finish Weight is no longer a manual entry - it's
			# derived from the Towel Costing Sheet's own Finish Weight for
			# this row's Article ("finish weight (mentioned in towel cost
			# sheet)" - your words). Gross Weight is hidden client-side
			# (dyeing_receipt_item.json) since it's no longer part of this.
			tcs_finish_weight = _get_tcs_finish_weight(tcs_cache, row.towel_costing_sheet, row.item)
			row.finish_weight = (flt(tcs_finish_weight) / 1000) * flt(row.received_qty)

		self.total_received_qty = sum(flt(row.received_qty) for row in self.items or [])


def _get_tcs_finish_weight(tcs_cache, towel_costing_sheet, item_code):
	if not towel_costing_sheet:
		return 0.0
	tcs = tcs_cache.get(towel_costing_sheet)
	if tcs is None:
		tcs = frappe.get_doc("Towel Costing Sheet", towel_costing_sheet)
		tcs_cache[towel_costing_sheet] = tcs
	for row in tcs.finish_item_towel_costing or []:
		if row.article == item_code:
			return flt(row.finish_weight)
	return 0.0