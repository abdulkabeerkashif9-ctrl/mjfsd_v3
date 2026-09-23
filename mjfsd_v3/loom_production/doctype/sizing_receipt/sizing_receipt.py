# Copyright (c) 2026, Tech Ventures and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from mjfsd_v3.loom_production.events.create_stock_entry_from_sizing_receipt import (
	create_manufacture_stock_entry,
	create_material_transfer_stock_entry,
	cancel_linked_stock_entries,
)


class SizingReceipt(Document):
	def on_submit(self):
		# Round 13: submitting a Sizing Receipt now automatically raises the
		# Beem Receipt (Manufacture) Stock Entry, and - only if the Stock
		# Return Item table has rows - a Material Transfer Stock Entry too.
		# The created Stock Entry names are stored back on this document
		# (manufacture_stock_entry / material_transfer_stock_entry, both
		# hidden) so on_cancel below knows exactly what to cancel.
		manufacture_se = create_manufacture_stock_entry(self)
		self.db_set("manufacture_stock_entry", manufacture_se, update_modified=False)

		if self.stock_return_item:
			transfer_se = create_material_transfer_stock_entry(self)
			self.db_set("material_transfer_stock_entry", transfer_se, update_modified=False)

	def on_cancel(self):
		cancel_linked_stock_entries(self)
