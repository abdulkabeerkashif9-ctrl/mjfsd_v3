import frappe
from frappe.model.document import Document
from frappe.utils import flt

from mjfsd_v3.loom_production.events.issue_fabric import cancel_issued_stock_entries


class DyeingContract(Document):
	def validate(self):
		self.recalculate_totals()

	def on_cancel(self):
		cancel_issued_stock_entries(self)

	def recalculate_totals(self):
		# 2026-09-15: Amount was described on the doctype as "= Rate x
		# Order Qty" but was never actually being computed anywhere -
		# fixed alongside making Order Qty itself user-editable (see
		# dyeing_contract_item.json/.js).
		for row in self.items or []:
			row.amount = flt(row.rate) * flt(row.order_qty)

		self.total_issue_qty = sum(flt(row.issued_qty) for row in self.items or [])
		self.total_received_qty = sum(flt(row.received_qty) for row in self.items or [])
		self.total_rolls_issued = sum(flt(row.rolls_issued) for row in self.items or [])
		self.total_rolls_received = sum(flt(row.rolls_received) for row in self.items or [])
		self.total_weight_issued_kg = sum(flt(row.weight_issued_kg) for row in self.items or [])
		self.total_weight_received_kg = sum(flt(row.weight_received_kg) for row in self.items or [])

		self.balance_qty = self.total_issue_qty - self.total_received_qty
		self.balance_rolls = self.total_rolls_issued - self.total_rolls_received
		self.balance_weight_kg = self.total_weight_issued_kg - self.total_weight_received_kg
