import frappe
from frappe import _
from frappe.utils import cint, flt


def validate_beam_no(doc):
	"""Beam No on a Sizing Receipt can't be more than the Sizing Beam of its
	Sizing Program."""
	if doc.get("yarn_items"):
		return  # checked per row in sizing_yarn_rows.apply_receipt_totals
	if not (doc.get("sizing_program") and cint(doc.get("beam_no"))):
		return
	if doc.get("yarn_items"):
		sizing_beam = sum({flt(r.sizing_beam) for r in doc.yarn_items})
	else:
		sizing_beam = flt(frappe.db.get_value("Sizing Program", doc.sizing_program, "sizing_beam"))
	if cint(doc.beam_no) > sizing_beam:
		frappe.throw(
			_("Beam No ({0}) cannot be greater than the Sizing Beam ({1}) of Sizing Program {2}.").format(
				cint(doc.beam_no), sizing_beam, doc.sizing_program
			)
		)


def validate_before_submit(doc):
	if doc.get("yarn_items"):
		for r in doc.yarn_items:
			if cint(r.get("beam_no")) < 1:
				frappe.throw(_("Row {0}: enter Beam No - one Batch is created for every beam.").format(r.idx))
			if not cint(r.get("set_no")):
				frappe.throw(_("Row {0}: enter Set No - it is used to name the Batches.").format(r.idx))
		return
	if cint(doc.get("beam_no")) < 1:
		frappe.throw(_("Enter Beam No before submitting - one Batch is created for every beam."))
	if not cint(doc.get("set_no")):
		frappe.throw(_("Enter Set No before submitting - it is used to name the Batches."))


def get_beam_type(doc):
	"""Pile or Ground, from the Beam item (BEAM-Pile-... / BEAM-Ground-...),
	else from the Weaving Contract's BOM row of this yarn."""
	item = doc.get("item") or ""
	for beam_type in ("Pile", "Ground"):
		if item.startswith(f"BEAM-{beam_type}-"):
			return beam_type

	contract = doc.get("weaving_contract")
	if contract and doc.get("yarn_item"):
		types = {
			r.get("for")
			for r in frappe.get_doc("Weaving Contract", contract).bom_items or []
			if r.get("yarn_count") == doc.yarn_item and r.get("for") in ("Pile", "Ground")
		}
		if len(types) == 1:
			return types.pop()
	return None


def _ensure_item_has_batches(item):
	"""Batches can only be made for an Item with Has Batch No. The Beam item is
	switched on here if it has no stock yet; with existing stock it must be
	done by hand."""
	if frappe.db.get_value("Item", item, "has_batch_no"):
		return
	if frappe.db.exists("Stock Ledger Entry", {"item_code": item, "is_cancelled": 0}):
		frappe.throw(
			_("Item {0} already has stock and \"Has Batch No\" is off, so Batches can't be created. Enable \"Has Batch No\" on the item first.").format(item)
		)
	frappe.db.set_value("Item", item, "has_batch_no", 1)


def get_batch_ids(doc):
	"""Set No 01, Beam No 2 -> 01-1, 01-2"""
	set_no = f"{cint(doc.set_no):02d}"
	return [f"{set_no}-{n}" for n in range(1, cint(doc.beam_no) + 1)]


def _beam_type_for_item(item):
	for beam_type in ("Pile", "Ground"):
		if (item or "").startswith(f"BEAM-{beam_type}-"):
			return beam_type
	return None


def _plan_batches(doc):
	"""[(batch_id, item, beam_type)] in order. A multi Beam Item receipt
	(Pile + Ground) numbers its beams one after the other: Set 01 with 2 Pile
	and 1 Ground beam -> 01-1, 01-2 (Pile), 01-3 (Ground)."""
	if doc.get("yarn_items"):
		from mjfsd_v3.loom_production.events.sizing_yarn_rows import beam_item_groups

		plan = []
		counter = {}
		for g in beam_item_groups(doc):
			for _i in range(g["beams"]):
				counter[g["set_no"]] = counter.get(g["set_no"], 0) + 1
				plan.append(
					(
						f"{g['set_no']:02d}-{counter[g['set_no']]}",
						g["item"],
						_beam_type_for_item(g["item"]) or get_beam_type(doc),
					)
				)
		return plan
	beam_type = get_beam_type(doc)
	return [(bid, doc.item, beam_type) for bid in get_batch_ids(doc)]


def create_batches(doc):
	"""One Batch per beam, named <Set No>-<beam number>, with Beam Type set."""
	names = []

	for batch_id, item, beam_type in _plan_batches(doc):
		_ensure_item_has_batches(item)
		existing = frappe.db.get_value(
			"Batch", batch_id, ["name", "item", "reference_doctype", "reference_name"], as_dict=True
		)
		if existing:
			# reusable only when it was made by a Sizing Receipt that has since been cancelled
			stale = (
				existing.item == item
				and existing.reference_doctype == "Sizing Receipt"
				and existing.reference_name != doc.name
				and frappe.db.get_value("Sizing Receipt", existing.reference_name, "docstatus") == 2
			)
			if not stale:
				frappe.throw(
					_("Batch {0} already exists (item {1}). Use a different Set No.").format(batch_id, existing.item)
				)
			batch = frappe.get_doc("Batch", batch_id)
			batch.reference_doctype = "Sizing Receipt"
			batch.reference_name = doc.name
			batch.disabled = 0
			batch.beam_type = beam_type
			batch.save(ignore_permissions=True)
		else:
			batch = frappe.new_doc("Batch")
			batch.batch_id = batch_id
			batch.item = item
			batch.reference_doctype = "Sizing Receipt"
			batch.reference_name = doc.name
			batch.beam_type = beam_type
			batch.insert(ignore_permissions=True)
		names.append(batch.name)

	return names


def disable_batches(doc):
	"""On cancel the Batches made by this receipt are disabled (they may be
	referenced by the cancelled Stock Entry, so they are not deleted)."""
	for name in frappe.get_all(
		"Batch", filters={"reference_doctype": "Sizing Receipt", "reference_name": doc.name}, pluck="name"
	):
		frappe.db.set_value("Batch", name, "disabled", 1)
