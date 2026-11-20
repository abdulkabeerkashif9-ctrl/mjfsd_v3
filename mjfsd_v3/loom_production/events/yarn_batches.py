"""Yarn batches: made when yarn is received on a Weaving Contract ("Receive Yarn"), picked again when the yarn is
issued to a Sizing Program and consumed by the beam, and referenced from the beam batch.

A yarn Batch carries Brand, PaperTip and Weaving Contract (custom fields of Batch)."""
import frappe
from frappe.utils import flt

EPS = 0.0005


def batch_info(batch_no):
	"""{brand, paper_tip, weaving_contract} of a yarn batch."""
	if not batch_no:
		return {}
	row = frappe.db.get_value(
		"Batch", batch_no, ["custom_brand", "custom_paper_tip", "custom_weaving_contract"], as_dict=True
	)
	if not row:
		return {}
	return {"brand": row.custom_brand, "paper_tip": row.custom_paper_tip, "weaving_contract": row.custom_weaving_contract}


def stock_of(batch_no, warehouse):
	try:
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		return flt(get_batch_qty(batch_no, warehouse))
	except ImportError:
		return flt(frappe.db.get_value("Batch", batch_no, "batch_qty"))


def contract_batches(item_code, weaving_contracts):
	"""Yarn batches of this item received on these Weaving Contracts, oldest first."""
	contracts = [c for c in weaving_contracts or [] if c]
	if not (item_code and contracts):
		return []
	return frappe.get_all(
		"Batch",
		filters={"item": item_code, "custom_weaving_contract": ["in", contracts], "disabled": 0},
		order_by="creation asc",
		pluck="name",
	)


def issued_batches(item_code, sizing_program):
	"""Yarn batches of this item that went out on the Sizing Program's issuance (Gate Pass) entries, in order."""
	if not (item_code and sizing_program):
		return []
	rows = frappe.db.sql(
		"""
		select d.batch_no from `tabStock Entry Detail` d
		inner join `tabStock Entry` s on s.name = d.parent
		where s.docstatus = 1 and s.custom_sizing_program_gate_pass = %s and d.item_code = %s and ifnull(d.batch_no, '') != ''
		order by s.posting_date, s.creation, d.idx
		""",
		(sizing_program, item_code),
	)
	out = []
	for (b,) in rows:
		if b not in out:
			out.append(b)
	return out


def allocate(qty, batches, warehouse):
	"""[(batch, qty)] covering `qty` from the batches (in order) that have stock in `warehouse`; whatever
	the batches cannot cover stays on the last one (ERPNext then reports the shortfall). [] when no batch has stock."""
	out, need = [], flt(qty)
	for b in batches:
		if need <= EPS:
			break
		avail = stock_of(b, warehouse)
		if avail <= EPS:
			continue
		take = min(avail, need)
		out.append([b, take])
		need -= take
	if out and need > EPS:
		out[-1][1] += need
	return [(b, q) for b, q in out]


def sizing_program_contracts(sp):
	names = [sp.get("weaving_contract")] + [r.get("weaving_contract") for r in sp.get("yarn_items") or []]
	return [n for n in dict.fromkeys(names) if n]


def batch_row_fields(batch_no):
	"""Stock Entry Detail fields that go with a yarn batch."""
	info = batch_info(batch_no)
	row = {"batch_no": batch_no, "use_serial_batch_fields": 1}
	if info.get("brand"):
		row["brand"] = info["brand"]
	if info.get("paper_tip"):
		row["custom_paper_tip"] = info["paper_tip"]
	return row


def append_yarn_rows(se, row_base, item_code, qty, batches, warehouse):
	"""Append one row per yarn batch (split by available stock) - or the plain row when no batch is available."""
	parts = allocate(qty, batches, warehouse)
	if not parts:
		se.append("items", dict(row_base, item_code=item_code, qty=qty))
		return []
	for batch_no, part in parts:
		line = dict(row_base, item_code=item_code, qty=part)
		if line.get("basic_rate") is not None and "basic_amount" in line:
			line["basic_amount"] = flt(line["basic_rate"]) * part
		line.update(batch_row_fields(batch_no))
		se.append("items", line)
	return [b for b, _q in parts]


def main_yarn_batch(sizing_receipt, warehouse):
	"""First yarn batch consumed by a Sizing Receipt (stored on its beam batches)."""
	from mjfsd_v3.loom_production.events.sizing_yarn_rows import consumption_lines

	wh = warehouse
	for item, _lbs in consumption_lines(sizing_receipt):
		cands = consumption_candidates(sizing_receipt.sizing_program, item)
		parts = allocate(_lbs, cands, wh) if wh else []
		if parts:
			return parts[0][0]
		if cands:
			return cands[0]
	return None


def consumption_candidates(sizing_program, item_code):
	sp = frappe.get_doc("Sizing Program", sizing_program)
	cands = issued_batches(item_code, sizing_program)
	for b in contract_batches(item_code, sizing_program_contracts(sp)):
		if b not in cands:
			cands.append(b)
	return cands
