import frappe
from frappe.model.document import Document

from mjfsd_v3.loom_production.events import planning


class Planning(Document):
	def onload(self):
		# opening shows PO / received / balance / yarn status as they are now
		planning.refresh_figures(self)

	def validate(self):
		planning.refresh_figures(self)
		planning.set_totals(self)
