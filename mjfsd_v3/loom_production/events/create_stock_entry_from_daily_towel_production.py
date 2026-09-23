import frappe
from frappe.utils import flt

# Round 14 Part B (2026-09-09): original Daily Towel Production events file -
# see claude/daily-towel-production.md for the full spec this was built
# against (Kabeer's original spec, the four clarifying questions he
# answered, and the resulting design).
#
# Round 18 (2026-09-16): rewritten to fold in three changes Kabeer asked
# for while amending this doctype for the Weaving/Dyeing/Sizing workflow
# changes made elsewhere this session. NOTE: unlike most files touched
# this session, Kabeer did not paste his current live copy of this
# specific events file (he pasted daily_towel_production.py/.js and both
# doctype JSONs, but not this one) - so this is rebuilt fresh from the
# documented round 14 spec plus the three round 18 changes below, not a
# patch of a pasted original. The three changes themselves are the parts
# you actually asked for; the rest (query method, formulas, error
# handling) should match what's already live - flag anything that's
# drifted from your real file so it can be reconciled.
#
# Round 18 changes:
#   1. Stock Entry reference fields - every Manufacture Stock Entry this
#      creates now sets custom_sales_order and a new custom_
#      daily_towel_production (mjfsd_v3/custom/stock_entry.json), matching
#      the reference-field convention every other Stock-Entry-creating
#      flow in this project adopted this session.
#   2. Raw material lookup - the Beam-item Sizing Receipt lookup now
#      prefers matching on Weaving Contract (via the Sales Order Item's
#      linked Weaving Contract) instead of Sales Order + Yarn Item alone,
#      per your answer: "there can be multiple sizing receipts against
#      same sizing program, sales order, weaving contract" - narrowing by
#      Weaving Contract first cuts down the candidate pool, most-recent-
#      submitted is still the tie-breaker since even that isn't always
#      unique. Falls back to the old Sales Order + Yarn Item match if no
#      Weaving Contract can be resolved, so older data keeps working.
#   3. Greige Batch - the finished towel item row now carries batch_no,
#      read from the Sales Order Item's own custom_greige_batch field
#      ("the batch is already created and saved in sales order item
#      table in custom_greige_batch field", your words) - not created or
#      picked here, just consumed.
#
# Round 19 (2026-09-16): two changes.
#   1. get_raw_materials_for_row now also returns default_warehouse per
#      raw material (Beam Items -> the resolved Sizing Receipt's own
#      Target Warehouse, Yarn Items -> YARN_DEFAULT_WAREHOUSE below) so
#      the Raw Material Selection dialog can pre-fill the warehouse field
#      instead of leaving it blank - still editable, this is a default,
#      not a lock, per Kabeer: "yarn item warehouse will be Stores - PT
#      by default but editable."
#   2. Beam Items now also carry an explicit rate. Kabeer: "In Daily
#      Towel Production stock entry, qty is calculated correctly but
#      rates of source items are incorrect" - screenshot showed Beam item
#      consumption rows at implausibly low rates (Rs 1.42, Rs 2.71),
#      while the loose Yarn Item row was correct (Rs 350, matching
#      Item.valuation_rate). Working theory, confirmed by Kabeer: Beam -
#      PT's warehouse-ledger valuation is polluted by Sizing Receipts
#      submitted before round 17/19's set_basic_rate_manually fixes -
#      that bad history is now baked into the moving average and won't
#      self-correct just because the Sizing Receipt code is fixed going
#      forward. Kabeer chose to make this deterministic rather than
#      depend on ledger history (or a one-off data cleanup): Beam item
#      rows now get basic_rate set explicitly from the same Sizing
#      Receipt used to resolve them (Final Cost Of Beam / Beem Length,
#      same formula as create_stock_entry_from_sizing_receipt.py). See
#      create_manufacture_stock_entry_for_row below for how this is
#      threaded through without needing a new persisted field on the
#      child doctype - get_raw_materials_for_row is simply called again
#      at submit time to rebuild the item_code -> rate map, since neither
#      the resolved Sizing Receipt nor a rate was ever persisted from the
#      dialog (only item_code/qty/warehouse are, via the three existing
#      Data fields).
YARN_DEFAULT_WAREHOUSE = "Stores - PT"

# DELIMITER matches the parent daily_towel_production.js's RM_DELIMITER -
# keep both in sync if this ever changes.
DELIMITER = " | "


@frappe.whitelist()
def get_sales_order_items(doctype, txt, searchfield, start, page_len, filters):
	"""Link-query for the Items child table's `item` field, wired via
	frm.set_query('item', 'items', ...) in daily_towel_production.js -
	restricts the dropdown to items actually listed on the row's own
	Sales Order, per Kabeer's original spec ("drop-down of item(s) listed
	in sales order")."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	sales_order = filters.get("sales_order")
	if not sales_order:
		return []

	return frappe.db.sql(
		"""
		SELECT item_code, item_name
		FROM `tabSales Order Item`
		WHERE parent = %(sales_order)s
		AND item_code LIKE %(txt)s
		LIMIT %(page_len)s OFFSET %(start)s
		""",
		{
			"sales_order": sales_order,
			"txt": "%{}%".format(txt or ""),
			"start": start,
			"page_len": page_len,
		},
	)


def _get_sales_order_item_row(sales_order, item_code):
	"""Resolve the one Sales Order Item row this Daily Towel Production row
	is producing. Used for the Towel Costing Sheet lookup (round 14,
	unchanged) and, as of round 18, also for the Weaving Contract match
	and the Greige Batch - all three live on this same row, so it's
	fetched once and reused rather than three separate queries."""
	row = frappe.db.get_value(
		"Sales Order Item",
		{"parent": sales_order, "item_code": item_code},
		["name", "custom_towel_costing_sheet", "custom_greige_batch"],
		as_dict=True,
	)
	if not row:
		frappe.throw(
			"No Sales Order Item found for Item {} on Sales Order {}.".format(item_code, sales_order)
		)
	return row


def _get_weaving_contract(sales_order, sales_order_item_name):
	"""Round 18: resolve 'the' Weaving Contract governing this Sales Order
	Item's Article. Weaving Contract's own sales_order_item field is plain
	Data (stores the Sales Order Item row's `name`), not a Link - matched
	as a string here for exactly that reason. Returns None (not an error)
	if nothing matches, so callers can fall back to the pre-round-18
	Sales Order + Yarn Item match for older data that predates this
	field."""
	return frappe.db.get_value(
		"Weaving Contract",
		{
			"sales_order": sales_order,
			"sales_order_item": sales_order_item_name,
			"docstatus": ["!=", 2],
		},
		"name",
	)


def _find_sizing_receipt(sales_order, yarn_item, weaving_contract=None):
	"""Beam-item source lookup for a Pile/Ground raw material. Round 18:
	prefers narrowing by weaving_contract when one was resolved above,
	falling back to the original Sales Order + Yarn Item match if that
	comes up empty (receipt predates the weaving_contract field, or no
	Weaving Contract could be resolved at all). Most-recent-submitted is
	the tie-breaker either way - per Kabeer, even Sales Order + Weaving
	Contract + Yarn Item isn't guaranteed unique."""
	base_filters = {
		"sales_order": sales_order,
		"yarn_item": yarn_item,
		"docstatus": 1,
	}

	# Round 19: target_warehouse fetched so the caller can default the
	# Beam Items warehouse field to where this Beam actually is (see
	# YARN_DEFAULT_WAREHOUSE above); final_cost_of_beam/beem_length
	# fetched so the caller can compute this Beam's rate the same way
	# create_stock_entry_from_sizing_receipt.py does.
	fields = ["name", "item", "lbs", "length", "target_warehouse", "final_cost_of_beam", "beem_length"]

	if weaving_contract:
		receipt = frappe.db.get_value(
			"Sizing Receipt",
			dict(base_filters, weaving_contract=weaving_contract),
			fields,
			as_dict=True,
			order_by="creation desc",
		)
		if receipt:
			return receipt

	return frappe.db.get_value(
		"Sizing Receipt",
		base_filters,
		fields,
		as_dict=True,
		order_by="creation desc",
	)


@frappe.whitelist()
def get_raw_materials_for_row(sales_order, item_code, finish_qty):
	"""Popup data source for the Raw Material Selection button. Returns
	[{item_code, group, qty, reference}, ...] - see
	claude/daily-towel-production.md for the full formula/grouping spec
	this implements (Pile/Ground -> Beam Items via Sizing Receipt,
	Weft/Fancy -> Yarn Items directly)."""
	finish_qty = flt(finish_qty)
	so_item = _get_sales_order_item_row(sales_order, item_code)

	if not so_item.custom_towel_costing_sheet:
		frappe.throw(
			"Sales Order Item {} on {} has no Towel Costing Sheet set "
			"(custom_towel_costing_sheet) - can't work out raw materials without it.".format(
				item_code, sales_order
			)
		)

	# Round 18: resolved once here, threaded into every Sizing Receipt
	# lookup below rather than re-resolved per raw-material row.
	weaving_contract = _get_weaving_contract(sales_order, so_item.name)

	materials = frappe.get_all(
		"Towel Costing Sheet Raw Material",
		filters={"parent": so_item.custom_towel_costing_sheet, "item": item_code},
		fields=["`for`", "raw_material", "yarn_required_in_lbs"],
	)

	result = []
	for m in materials:
		yarn_required_per_lbs = flt(m.yarn_required_in_lbs)

		if m.get("for") in ("Pile", "Ground"):
			receipt = _find_sizing_receipt(sales_order, m.raw_material, weaving_contract)
			if not receipt:
				frappe.throw(
					"No submitted Sizing Receipt found for Sales Order {} / Yarn Item {} - "
					"can't resolve a Beam item for the {} raw material.".format(
						sales_order, m.raw_material, m.get("for")
					)
				)
			# Length (Beam No x Beem Length - ALL beams' meters), not
			# Beem Length alone - same reasoning as the parallel note on
			# Sizing Receipt's own Stock Entry rate (round 14 item 3, see
			# claude/sizing-receipt.md): lbs on a Sizing Receipt is the
			# total yarn for every beam on it, so the meters side of the
			# ratio has to match.
			ratio = flt(receipt.lbs) / flt(receipt.length) if flt(receipt.length) else 0
			qty = (yarn_required_per_lbs / ratio) * finish_qty if ratio else 0
			# Round 19: same formula as create_manufacture_stock_entry in
			# create_stock_entry_from_sizing_receipt.py - this Beam's own
			# per-meter cost, used to set an explicit rate on the DTP
			# consumption row below instead of trusting Beam - PT's
			# warehouse-ledger valuation.
			beem_length = flt(receipt.beem_length)
			rate = flt(receipt.final_cost_of_beam) / beem_length if beem_length else 0
			result.append({
				"item_code": receipt.item,
				"group": "Beam Items",
				"qty": qty,
				"reference": receipt.name,
				# Round 19: default warehouse for the dialog - see
				# YARN_DEFAULT_WAREHOUSE above.
				"default_warehouse": receipt.target_warehouse,
				"rate": rate,
			})
		else:
			qty = yarn_required_per_lbs * finish_qty
			result.append({
				"item_code": m.raw_material,
				"group": "Yarn Items",
				"qty": qty,
				"reference": None,
				"default_warehouse": YARN_DEFAULT_WAREHOUSE,
				# Round 19: not set for the Yarn Items group - Kabeer's
				# screenshot showed this row's rate was already correct
				# (matches Item.valuation_rate), only the Beam Items group
				# was reported wrong, so left to Frappe's own valuation
				# here rather than changing something that already works.
				"rate": None,
			})

	return result


def create_manufacture_stock_entry_for_row(doc, row):
	"""One Manufacture Stock Entry per child row - consumes that row's
	parsed Raw Material Items/Qty/Warehouses, produces Finish Qty of the
	row's own Item into the parent's Target Warehouse."""
	items = (row.raw_material_items or "").split(DELIMITER)
	qtys = (row.raw_material_qty or "").split(DELIMITER)
	warehouses = (row.raw_material_warehouses or "").split(DELIMITER)

	if not items or not items[0] or not (len(items) == len(qtys) == len(warehouses)):
		frappe.throw(
			"Row {}: Raw Material Selection hasn't been run (or its result is incomplete) - "
			"click Raw Material Selection before submitting.".format(row.idx)
		)

	# Round 18: Greige Batch for the finished row - see module docstring.
	so_item = _get_sales_order_item_row(row.sales_order, row.item)
	if not so_item.custom_greige_batch:
		frappe.throw(
			"Row {}: Sales Order Item {} on {} has no Greige Batch set "
			"(custom_greige_batch) - can't raise the Manufacture Stock Entry without one.".format(
				row.idx, row.item, row.sales_order
			)
		)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Manufacture"
	se.purpose = "Manufacture"
	se.set_posting_time = 1
	se.posting_date = doc.date
	# Round 18: reference fields, same convention as every other
	# Stock-Entry-creating flow in this project - see custom field
	# descriptions in mjfsd_v3/custom/stock_entry.json.
	se.custom_sales_order = row.sales_order
	se.custom_daily_towel_production = doc.name
	# Round 18: required whenever batch_no is set directly via the API
	# rather than left for Frappe to pick - same convention used
	# everywhere else in this project batch_no is set this way.
	se.use_serial_batch_fields = 1

	# Round 19: rebuild an item_code -> rate map for the Beam Items group
	# by calling get_raw_materials_for_row again - neither the resolved
	# Sizing Receipt nor a rate was persisted from the dialog (only
	# item_code/qty/warehouse are, in the three Data fields parsed
	# above), so this is the only way to get back to "which Sizing
	# Receipt priced this Beam item" without adding a new child-table
	# field. Best-effort: if the underlying data shifted since Raw
	# Material Selection was run (a Sizing Receipt was cancelled, say)
	# and this throws, the Stock Entry still goes through - it just falls
	# back to Frappe's own valuation for whichever rows aren't covered,
	# same as before this round.
	rate_by_item = {}
	try:
		for m in get_raw_materials_for_row(row.sales_order, row.item, row.finish_qty):
			if m.get("rate"):
				rate_by_item[m["item_code"]] = flt(m["rate"])
	except Exception:
		frappe.log_error(frappe.get_traceback(), "DTP Beam rate re-resolution failed")

	for item_code, qty, warehouse in zip(items, qtys, warehouses):
		item_row = {
			"item_code": item_code,
			"qty": flt(qty),
			"uom": frappe.db.get_value("Item", item_code, "stock_uom"),
			"s_warehouse": warehouse,
		}
		if item_code in rate_by_item:
			rate = rate_by_item[item_code]
			item_row.update({
				"basic_rate": rate,
				"basic_amount": rate * flt(qty),
				"set_basic_rate_manually": 1,
			})
		se.append("items", item_row)

	se.append("items", {
		"item_code": row.item,
		"qty": row.finish_qty,
		"uom": frappe.db.get_value("Item", row.item, "stock_uom"),
		"t_warehouse": doc.target_warehouse,
		"is_finished_item": 1,
		"batch_no": so_item.custom_greige_batch,
	})

	se.save(ignore_permissions=True)
	se.submit()
	return se.name


def create_stock_entries(doc):
	"""Called from Daily Towel Production's on_submit. Loops every child
	row, creating and submitting one Manufacture Stock Entry each, and
	records the Stock Entry name back onto that row so on_cancel below
	knows exactly what to cancel."""
	for row in doc.items:
		se_name = create_manufacture_stock_entry_for_row(doc, row)
		row.db_set("stock_entry", se_name, update_modified=False)


def cancel_linked_stock_entries(doc):
	"""Called from Daily Towel Production's on_cancel. Cancels every
	row's tracked Stock Entry."""
	for row in doc.items:
		if row.stock_entry and frappe.db.exists("Stock Entry", row.stock_entry):
			se = frappe.get_doc("Stock Entry", row.stock_entry)
			if se.docstatus == 1:
				se.cancel()
