import frappe


@frappe.whitelist()
def get_weaving_contracts_for_selection():
	"""Feeds the "Get Items From > Weaving Contract" popup. Lists every
	submitted Weaving Contract that isn't already referenced by a
	non-cancelled Weaving Receipt - same "exclude what's already been
	drawn on" pattern as the Purchase Invoice "Get Charges From Sizing
	Receipt" picker, so the same contract can't be received twice by
	mistake. If you actually want to allow multiple/partial Weaving
	Receipts against one contract, this exclusion is the one line to
	remove.
	"""
	already_used = frappe.get_all(
		"Weaving Receipt Item",
		filters={"weaving_contract": ["is", "set"]},
		fields=["weaving_contract", "parent"],
	)

	exclude = set()
	if already_used:
		parents = list({row.parent for row in already_used})
		cancelled_parents = set(
			frappe.get_all(
				"Weaving Receipt",
				filters={"name": ["in", parents], "docstatus": 2},
				pluck="name",
			)
		)
		for row in already_used:
			if row.parent not in cancelled_parents:
				exclude.add(row.weaving_contract)

	contracts = frappe.get_all(
		"Weaving Contract",
		filters={
			"docstatus": 1,
			"name": ["not in", list(exclude) or [""]],
		},
		fields=["name", "construction as finish_item", "sales_order"],
	)

	for contract in contracts:
		contract["weaver_hint"] = _get_weaver_hint(contract)

	return contracts


def _get_weaver_hint(contract):
	"""Best-effort display hint only (shown as an extra column in the
	popup, not used to filter/restrict selection) - Weaving Contract has
	no field of its own identifying who wove it, so this reads the
	Customer off the linked Sales Order instead, same fallback used in
	create_sizing_program_from_weaving_contract.py.
	"""
	if not contract.get("sales_order"):
		return None
	return frappe.db.get_value("Sales Order", contract["sales_order"], "customer")


@frappe.whitelist()
def get_weaving_contract_items(weaving_contracts):
	"""Called once the user picks one or more contracts and clicks Fetch.
	One Weaving Contract -> one Weaving Receipt Item row (a contract only
	ever has a single Finish Item, unlike Towel Costing Sheet).
	"""
	if isinstance(weaving_contracts, str):
		weaving_contracts = frappe.parse_json(weaving_contracts)

	result = []
	for wc_name in weaving_contracts:
		wc = frappe.get_doc("Weaving Contract", wc_name)
		result.append(
			{
				"finish_item": wc.construction,
				"gross_weight": wc.gross_weight,
				"finish_weight": wc.finish_weight,
				"order_qty": wc.fabric_qty,
				"weaving_contract": wc.name,
				"sales_order": wc.sales_order,
				"towel_costing_sheet": _get_towel_costing_sheet(wc),
			}
		)
	return result


def _get_towel_costing_sheet(wc):
	if not wc.get("sales_order_item"):
		return None
	return frappe.db.get_value(
		"Sales Order Item", wc.sales_order_item, "custom_towel_costing_sheet"
	)
