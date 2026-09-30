# Copyright (c) 2026, Tech Ventures and contributors
# For license information, please see license.txt

# 2026-09-28 (feature v3) - renamed from "Daily Towel Production" to
# "Daily Loom Production" (your words). The DocType record itself is
# renamed in place by a pre_model_sync patch (see
# mjfsd_v3/patches/rename_daily_towel_production_to_loom_production.py)
# so existing documents/history carry over - this is a new controller
# file matching the new name/module path Frappe requires, but the events
# module it delegates to (create_stock_entry_from_daily_towel_production.py)
# is unchanged: nothing in it is tied to the doctype's name, so renaming
# it too would only add risk for no benefit.

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from mjfsd_v3.loom_production.events.create_stock_entry_from_daily_towel_production import (
	create_stock_entries,
	cancel_linked_stock_entries,
	get_greige_weight,
)


class DailyLoomProduction(Document):
	def validate(self):
		# 2026-09-28 (feature v3) - "Finish Qty (Read only) = A Qty + B Qty +
		# C Qty + Cut Pcs Qty" and "Total Greige Weight (Calculated) (greige
		# weight * Finish Qty)" (your words). Both recomputed here so they
		# can't be edited around - mirrors daily_loom_production.js's own
		# live-preview versions of the same two formulas ("server is the
		# source of truth" pattern used throughout this project). Greige
		# Weight itself is also re-fetched here (not just client-side on
		# Sales Order/Item change) so a row added without the browser
		# JS having fired still ends up with a real value on save.
		for row in self.items:
			row.finish_qty = flt(row.a_qty) + flt(row.b_qty) + flt(row.c_qty) + flt(row.cut_pcs_qty)
			if row.sales_order and row.item:
				row.greige_weight = get_greige_weight(row.sales_order, row.item)
			row.total_greige_weight = flt(row.greige_weight) * flt(row.finish_qty)

		# Total Finish Qty is a read-only auto-sum of the child rows - not
		# explicitly specified as auto vs manual, but "Total Finish Qty" next
		# to a child table that already carries Finish Qty per row reads as a
		# rollup. Recalculated server-side (in addition to the client-side
		# total in daily_loom_production.js) so it can't be edited around.
		self.total_finish_qty = sum(flt(row.finish_qty) for row in self.items)

	def on_submit(self):
		# One Manufacture Stock Entry per child row, per spec ("Each Daily
		# Towel Production will contain multiple entries so multiple
		# manufacture entries will be created.").
		create_stock_entries(self)

	def on_cancel(self):
		cancel_linked_stock_entries(self)
