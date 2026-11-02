"""Multi finish item / multi yarn support for Sizing Program and Sizing Receipt.

Both documents carry the same child table ("Yarn Details", doctype
Sizing Program Yarn). One Sizing Beam value can be entered on several rows -
those rows share one physical beam (different finish items / Weaving
Contracts on the same beam). A Sizing Receipt is raised per shared beam.
"""
import frappe
from frappe import _
from frappe.utils import cint, flt

CONSTANT = 768.1


def has_rows(doc):
	return bool(doc.get("yarn_items"))


def calculate_rows(doc, default_wastage=None):
	"""Server-side (authoritative) version of the row formulas that
	sizing_program.js / sizing_receipt.js preview live."""
	returns = {}
	for r in doc.get("stock_return_item") or []:
		returns[r.yarn_item] = returns.get(r.yarn_item, 0) + flt(r.qty_lbs)

	for idx, row in enumerate(doc.get("yarn_items") or [], 1):
		if not flt(row.lbs_per_bag):
			row.lbs_per_bag = 100
		if row.wastage_percent in (None, "") and default_wastage:
			row.wastage_percent = default_wastage
		wpct = flt(row.wastage_percent)

		row.cone_weight = flt(row.lbs_per_bag) / flt(row.cones_per_bag) if flt(row.cones_per_bag) else 0
		row.yarn_consumption_per_meter = (
			(flt(row.ends) / CONSTANT) / flt(row.yarn_count) if flt(row.yarn_count) else 0
		)
		row.lbs = flt(row.net_meter) * row.yarn_consumption_per_meter
		row.wastage = row.lbs * wpct / 100
		row.gross_meter = flt(row.net_meter) * (1 + wpct / 100)
		row.bags_issue = (flt(row.lbs_issue) + row.wastage) / (flt(row.lbs_per_bag) or 100)

		# returned yarn is taken off the rows of that yarn in order
		ret = returns.get(row.yarn_item, 0)
		take = min(ret, flt(row.lbs_issue)) if ret > 0 else 0
		row.balance_yarn = flt(row.lbs_issue) - take
		returns[row.yarn_item] = ret - take

		if not row.get("po_ref") and doc.get("name") and not str(doc.name).startswith("new-"):
			row.po_ref = doc.name if doc.doctype == "Sizing Program" else doc.get("sizing_program")


def get_issued_meters(program_row_names, exclude_receipt=None):
	"""Net meters already put on Sizing Receipts (not cancelled) per
	Sizing Program row."""
	if not program_row_names:
		return {}
	rows = frappe.db.sql(
		"""
		select y.sizing_program_row, coalesce(sum(y.net_meter), 0)
		from `tabSizing Program Yarn` y
		inner join `tabSizing Receipt` r on r.name = y.parent and y.parenttype = 'Sizing Receipt'
		where r.docstatus < 2 and y.sizing_program_row in %s and r.name != %s
		group by y.sizing_program_row
		""",
		(tuple(program_row_names), exclude_receipt or ""),
	)
	return {k: flt(v) for k, v in rows}


def set_balance_net_meter(program):
	issued = get_issued_meters([r.name for r in program.get("yarn_items") or [] if r.name])
	for row in program.get("yarn_items") or []:
		row.balance_net_meter = flt(row.net_meter) - issued.get(row.name, 0)


def validate_program(doc):
	"""Sizing Program.validate hook for the multi-row mode."""
	if not has_rows(doc):
		return
	calculate_rows(doc, default_wastage=flt(doc.get("warp_wastage_percent")) or None)
	set_balance_net_meter(doc)
	for row in doc.yarn_items:
		if not row.yarn_item:
			frappe.throw(_("Row {0}: Yarn Item is required.").format(row.idx))
		if not flt(row.sizing_beam):
			frappe.throw(_("Row {0}: Sizing Beam is required. Use the same value on rows that share a beam.").format(row.idx))
	doc.lbs_issue = sum(flt(r.lbs_issue) for r in doc.yarn_items)
	if not doc.get("weaving_contract"):
		doc.weaving_contract = next((r.weaving_contract for r in doc.yarn_items if r.weaving_contract), None)
	if not doc.get("fabric_construction"):
		doc.fabric_construction = next((r.finish_item for r in doc.yarn_items if r.finish_item), None)
	if not doc.get("po_number") and doc.get("name"):
		doc.po_number = doc.name


def beam_groups(doc):
	"""{sizing_beam: [rows]} - rows that share one beam."""
	groups = {}
	for r in doc.get("yarn_items") or []:
		groups.setdefault(flt(r.sizing_beam), []).append(r)
	return groups


@frappe.whitelist()
def get_beam_groups(sizing_program):
	"""For the 'Sizing Receipt' button: the shared beams of this program that
	still have net meter left to receive."""
	sp = frappe.get_doc("Sizing Program", sizing_program)
	issued = get_issued_meters([r.name for r in sp.yarn_items])
	out = []
	for beam, rows in sorted(beam_groups(sp).items()):
		remaining = sum(flt(r.net_meter) - issued.get(r.name, 0) for r in rows)
		out.append(
			{
				"sizing_beam": beam,
				"rows": len(rows),
				"finish_items": ", ".join(sorted({r.finish_item for r in rows if r.finish_item})),
				"remaining": remaining,
			}
		)
	return out


@frappe.whitelist()
def make_sizing_receipt(sizing_program, sizing_beam):
	"""Unsaved Sizing Receipt for one shared beam, carrying every program row
	that has that Sizing Beam (net meter = what is still left on the row)."""
	sp = frappe.get_doc("Sizing Program", sizing_program)
	beam = flt(sizing_beam)
	rows = [r for r in sp.yarn_items if flt(r.sizing_beam) == beam]
	if not rows:
		frappe.throw(_("No rows with Sizing Beam {0} in {1}.").format(beam, sp.name))
	if not sp.item_returnable:
		frappe.throw(_("Set Item Name (beam item) on the Sizing Program first."))

	issued = get_issued_meters([r.name for r in rows])
	rec = frappe.new_doc("Sizing Receipt")
	rec.sizing_program = sp.name
	rec.source_warehouse = sp.source_warehouse
	rec.target_warehouse = sp.target_warehouse
	rec.sales_order = sp.get("sales_order")
	rec.weaving_contract = rows[0].weaving_contract or sp.get("weaving_contract")
	rec.sizing_name = sp.supplier
	rec.item = sp.item_returnable
	rec.sizing_rate = sp.sizing_rate
	rec.type = "Beam"
	rec.beam_no = cint(beam)
	copy = [
		"weaving_contract", "finish_item", "yarn_item", "yarn_count", "cones_per_bag", "lbs_per_bag",
		"lbs_issue", "sizing_beam", "beam_size", "ends", "beam", "quality", "wastage_percent", "po_ref",
	]
	for r in rows:
		left = flt(r.net_meter) - issued.get(r.name, 0)
		if left <= 0.0001:
			continue
		line = {f: r.get(f) for f in copy}
		line["net_meter"] = left
		line["sizing_program_row"] = r.name
		rec.append("yarn_items", line)
	if not rec.get("yarn_items"):
		frappe.throw(_("Everything on Sizing Beam {0} is already received.").format(beam))
	apply_receipt_totals(rec)
	return rec


def apply_receipt_totals(doc):
	"""Sizing Receipt.validate hook for the multi-row mode: roll the rows up
	into the header figures the existing Stock Entry / costing code reads."""
	if not has_rows(doc):
		return
	calculate_rows(doc)
	rows = doc.yarn_items
	beam = flt(rows[0].sizing_beam)
	for r in rows:
		if flt(r.sizing_beam) != beam:
			frappe.throw(_("A Sizing Receipt covers one shared beam - all rows must have the same Sizing Beam."))
	doc.beam_no = cint(doc.beam_no) or cint(beam)

	total_net = sum(flt(r.net_meter) for r in rows)
	total_lbs = sum(flt(r.lbs) for r in rows)
	others = get_issued_meters(
		[r.sizing_program_row for r in rows if r.sizing_program_row],
		exclude_receipt=None if doc.is_new() else doc.name,
	)
	for r in rows:
		if r.sizing_program_row:
			program_net = flt(frappe.db.get_value("Sizing Program Yarn", r.sizing_program_row, "net_meter"))
			r.balance_net_meter = program_net - others.get(r.sizing_program_row, 0) - flt(r.net_meter)

	doc.lbs = total_lbs
	doc.beem_length = total_net / beam if beam else 0
	doc.length = doc.beem_length
	doc.yarn_consumption_per_meter = total_lbs / total_net if total_net else 0
	doc.yarn_item = rows[0].yarn_item
	doc.yarn_count = flt(rows[0].yarn_count)
	doc.ends = flt(rows[0].ends)
	if not doc.get("fabric_construction"):
		doc.fabric_construction = next((r.finish_item for r in rows if r.finish_item), None)
	if not doc.get("weaving_contract"):
		doc.weaving_contract = next((r.weaving_contract for r in rows if r.weaving_contract), None)

	value = 0.0
	for r in rows:
		value += flt(frappe.db.get_value("Item", r.yarn_item, "valuation_rate")) * flt(r.lbs)
	doc.value_of_yarn = value
	doc.yarn_item_rate = value / total_lbs if total_lbs else 0
	doc.sizing_amount = flt(doc.sizing_rate) * total_lbs
	doc.beem_rate = flt(doc.yarn_item_rate) + flt(doc.sizing_rate)
	doc.beem_rate_per_meter = (doc.sizing_amount / doc.length if doc.length else 0) + flt(doc.beem_rate)
	doc.final_cost_of_beam = doc.value_of_yarn + doc.sizing_amount


def consumption_lines(doc):
	"""[(yarn_item, lbs)] to consume on the receipt's Stock Entry."""
	if has_rows(doc):
		lines = {}
		for r in doc.yarn_items:
			lines[r.yarn_item] = lines.get(r.yarn_item, 0) + flt(r.lbs)
		return list(lines.items())
	return [(doc.yarn_item, flt(doc.lbs))]
