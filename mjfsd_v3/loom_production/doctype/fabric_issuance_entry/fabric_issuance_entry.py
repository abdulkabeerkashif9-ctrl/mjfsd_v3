import frappe
from frappe.model.document import Document

from mjfsd_v3.loom_production.events import fabric_issuance_entry as fie
from mjfsd_v3.loom_production.warehouse_defaults import fill_empty


class FabricIssuanceEntry(Document):
	def validate(self):
		fill_empty(self, {"greige_warehouse": "dyeing_source_warehouse", "supplier_warehouse": "dyeing_target_warehouse"})
		fie.validate_entry(self)

	def before_submit(self):
		fie.validate_before_submit(self)

	def on_submit(self):
		fie.make_stock_entry(self)

	def on_cancel(self):
		fie.cancel_stock_entry(self)
