"""Multi finish item / multi yarn support for Sizing Program and Sizing Receipt.

Both documents carry the same child table ("Yarn Details", doctype
Sizing Program Yarn). One Sizing Beam value can be entered on several rows -
those rows share one physical beam (different finish items / Weaving
Contracts on the same beam). A Sizing Receipt is raised per shared beam.
"""
import frappe
from mjfsd_v3.loom_production.warehouse_defaults import default_warehouse
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
		select y.sizing_program_row, coalesce(sum(y.beem_length), 0)
		from `tabSizing Receipt Yarn` y
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
	# Quality is a Cotton/Viscose Select - never keep anything else in it
	if doc.get("quality") not in (None, "", "Cotton", "Viscose"):
		doc.quality = None
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


def total_beams(doc):
	return sum({flt(r.sizing_beam) for r in doc.get("yarn_items") or []})


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
def make_sizing_receipt(sizing_program, sizing_beam=None, sizing_beams=None):
	"""Unsaved Sizing Receipt for one OR SEVERAL shared beams (`sizing_beams`
	is a JSON list of Sizing Beam values; `sizing_beam` a single one). Carries
	every program row with one of those Sizing Beams (net meter = what is
	still left on the row)."""
	import json

	sp = frappe.get_doc("Sizing Program", sizing_program)
	if sizing_beams:
		beams = {flt(b) for b in (json.loads(sizing_beams) if isinstance(sizing_beams, str) else sizing_beams)}
	else:
		beams = {flt(sizing_beam)}
	rows = [r for r in sp.yarn_items if flt(r.sizing_beam) in beams]
	if not rows:
		frappe.throw(_("No rows with the selected Sizing Beam in {0}.").format(sp.name))
	# Pile and Ground beams (different Beam Items) can be received together.
	beam_item = next((r.get("beam_item") or sp.item_returnable for r in rows), None)
	if not any(r.get("beam_item") or sp.item_returnable for r in rows):
		frappe.throw(_("Set Item Name (beam item) on the Sizing Program, or Beam Item on the rows, first."))

	issued = get_issued_meters([r.name for r in rows])
	rec = frappe.new_doc("Sizing Receipt")
	rec.sizing_program = sp.name
	# Emadi Settings > Sizing Receipt warehouses first; the program's own only if those are not set
	rec.source_warehouse = default_warehouse("sizing_receipt_source_warehouse") or sp.source_warehouse
	rec.target_warehouse = default_warehouse("sizing_receipt_target_warehouse") or sp.target_warehouse
	rec.sizing_name = sp.supplier
	rec.item = beam_item
	rec.type = "Beam"
	rec.date = frappe.utils.nowdate()
	for r in rows:
		left = flt(r.net_meter) - issued.get(r.name, 0)
		if left <= 0.0001:
			continue
		share = left / flt(r.net_meter) if flt(r.net_meter) else 1
		rec.append(
			"yarn_items",
			{
				"sales_order": (
					frappe.db.get_value("Weaving Contract", r.weaving_contract, "sales_order")
					if r.weaving_contract
					else None
				)
				or sp.get("sales_order"),
				"beam_item": r.get("beam_item") or sp.item_returnable,
				"yarn_item": r.yarn_item,
				"yarn_count": r.yarn_count,
				"beam_no": cint(r.sizing_beam),
				"beem_length": left,
				"ends": r.ends,
				"lbs": flt(r.lbs) * share,
				"sizing_rate": sp.sizing_rate,
				"sizing_program": sp.name,
				"fabric_construction": r.finish_item,
				"sizing_beam": r.sizing_beam,
				"sizing_program_row": r.name,
			},
		)
	if not rec.get("yarn_items"):
		frappe.throw(_("Everything on the selected Sizing Beam(s) is already received."))
	apply_receipt_totals(rec)
	return rec


def calculate_receipt_row(row, default_rate=None):
	"""Same formulas the single-yarn Sizing Receipt always used (see
	sizing_receipt.js), applied to one row."""
	lbs = flt(row.lbs)
	ends = flt(row.ends)
	length = flt(row.beem_length)
	actual_yarn_count = (ends * length) / 768.10 / lbs if lbs else 0
	row.yarn_consumption_per_meter = round((ends / 768.1) / actual_yarn_count, 5) if ends and actual_yarn_count else 0
	row.warp_weight = ends / 768.10 / actual_yarn_count if ends and actual_yarn_count else 0
	if not flt(row.yarn_item_rate) and row.yarn_item:
		row.yarn_item_rate = flt(frappe.db.get_value("Item", row.yarn_item, "valuation_rate"))
	row.value_of_yarn = flt(row.yarn_item_rate) * lbs
	row.sizing_amount = flt(row.sizing_rate) * lbs
	row.beem_rate = flt(row.yarn_item_rate) + flt(row.sizing_rate)
	row.final_cost_of_beam = row.value_of_yarn + row.sizing_amount


def apply_receipt_totals(doc):
	"""Sizing Receipt.validate hook for the multi-row mode: calculate every
	row with the usual receipt formulas, then roll the rows up into the header
	figures the existing Stock Entry / costing code reads."""
	if not has_rows(doc):
		return
	rows = doc.yarn_items
	for r in rows:
		if not r.get("sizing_program"):
			r.sizing_program = doc.get("sizing_program")
		if not r.get("beam_item"):
			r.beam_item = doc.get("item")
		if not r.get("yarn_item"):
			frappe.throw(_("Row {0}: Yarn Item is required.").format(r.idx))
		if not cint(r.beam_no):
			r.beam_no = cint(r.sizing_beam) or 1
		if flt(r.sizing_beam) and cint(r.beam_no) > flt(r.sizing_beam):
			frappe.throw(
				_("Row {0}: Beam No ({1}) cannot be greater than the Sizing Beam ({2}).").format(
					r.idx, cint(r.beam_no), flt(r.sizing_beam)
				)
			)
		calculate_receipt_row(r)

	groups = beam_item_groups(doc)
	if groups and doc.get("item") not in [g["item"] for g in groups]:
		doc.item = groups[0]["item"]

	total_lbs = sum(flt(r.lbs) for r in rows)
	doc.lbs = total_lbs
	doc.beem_length = sum(flt(r.beem_length) for r in rows)
	doc.length = doc.beem_length
	doc.yarn_consumption_per_meter = total_lbs / doc.length if doc.length else 0
	doc.yarn_item = rows[0].yarn_item
	doc.yarn_count = flt(rows[0].yarn_count)
	doc.ends = flt(rows[0].ends)
	doc.fabric_construction = next((r.fabric_construction for r in rows if r.fabric_construction), None)
	doc.value_of_yarn = sum(flt(r.value_of_yarn) for r in rows)
	doc.sizing_amount = sum(flt(r.sizing_amount) for r in rows)
	doc.yarn_item_rate = doc.value_of_yarn / total_lbs if total_lbs else 0
	doc.sizing_rate = doc.sizing_amount / total_lbs if total_lbs else 0
	doc.beem_rate = flt(doc.yarn_item_rate) + flt(doc.sizing_rate)
	doc.beem_rate_per_meter = (doc.sizing_amount / doc.length if doc.length else 0) + flt(doc.beem_rate)
	doc.final_cost_of_beam = doc.value_of_yarn + doc.sizing_amount
	doc.set_no = cint(rows[0].set_no)
	doc.w_set = rows[0].w_set
	doc.beam_no = sum(g["beams"] for g in groups)
	doc.sales_order = next((r.sales_order for r in rows if r.sales_order), None)


def consumption_lines(doc):
	"""[(yarn_item, lbs)] to consume on the receipt's Stock Entry."""
	if has_rows(doc):
		lines = {}
		for r in doc.yarn_items:
			lines[r.yarn_item] = lines.get(r.yarn_item, 0) + flt(r.lbs)
		return list(lines.items())
	return [(doc.yarn_item, flt(doc.lbs))]


def beam_item_groups(doc):
	"""Receipt rows grouped into physical beam sets: same Set No + Beam Item +
	Sizing Beam (rows sharing a beam). For each: Beam Item, number of beams
	(highest Beam No on its rows), meters (sum of Beam Length), yarn LBS and
	cost (sum of each row's Final Cost Of Beam), in order of first
	appearance."""
	groups = {}
	for r in doc.get("yarn_items") or []:
		item = r.get("beam_item") or doc.get("item")
		key = (cint(r.set_no), item, flt(r.sizing_beam))
		g = groups.setdefault(
			key, {"item": item, "set_no": cint(r.set_no), "beams": 0, "net": 0.0, "lbs": 0.0, "cost": 0.0, "rows": []}
		)
		g["beams"] = max(g["beams"], cint(r.beam_no), 1)
		g["net"] += flt(r.beem_length)
		g["lbs"] += flt(r.lbs)
		g["cost"] += flt(r.final_cost_of_beam)
		g["rows"].append(r)
	return list(groups.values())
