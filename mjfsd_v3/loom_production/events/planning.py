"""Planning: orders -> yarn requirements -> weaving, with PO / received / yarn-dispatch figures read from the system."""
import json

import frappe
from frappe import _
from frappe.utils import flt


def _tcs_weights(tcs, item_code):
	if not (tcs and item_code):
		return 0.0, 0.0
	row = frappe.db.get_value(
		"Finish Item Towel Costing", {"parent": tcs, "article": item_code}, ["finish_weight", "greige_weight"], as_dict=True
	)
	return (flt(row.finish_weight), flt(row.greige_weight)) if row else (0.0, 0.0)


@frappe.whitelist()
def get_order_items(sales_orders):
	"""One row per Sales Order Item of the selected Sales Orders. Order Qty = AB Qty (Qty when AB Qty is empty)."""
	if isinstance(sales_orders, str):
		sales_orders = json.loads(sales_orders)
	out = []
	for so in sales_orders or []:
		for r in frappe.get_all(
			"Sales Order Item",
			filters={"parent": so, "parenttype": "Sales Order"},
			fields=["name", "item_code", "qty", "custom_ab_qty", "custom_towel_costing_sheet"],
			order_by="idx asc",
		):
			finish, greige = _tcs_weights(r.custom_towel_costing_sheet, r.item_code)
			out.append(
				{
					"order_no": so,
					"item": r.item_code,
					"order_qty": flt(r.custom_ab_qty) or flt(r.qty),  # AB Qty, else Qty
					"finish_weight": finish,
					"greige_weight": greige,
					"sales_order_item": r.name,
					"towel_costing_sheet": r.custom_towel_costing_sheet,
				}
			)
	return out


def requirement_rows(order_rows):
	"""Yarn lines of the order rows: TCS raw materials x order qty, merged per Sales Order + fabric item + yarn."""
	from emadi_v3.emadi.events.weaving_yarn_balance import get_tcs_lines

	merged, order = {}, []
	delivery = {}
	for r in order_rows:
		so = r.get("order_no")
		if so not in delivery:
			delivery[so] = frappe.db.get_value("Sales Order", so, "delivery_date")
		for (_item, _for, yarn), line in get_tcs_lines(r.get("towel_costing_sheet"), r.get("item")).items():
			key = (so, r.get("item"), yarn)
			if key not in merged:
				merged[key] = {
					"sales_order": so,
					"reqd_by_date": delivery[so],
					"fabric_item": r.get("item"),
					"yarn_item": yarn,
					"reqd_qty": 0.0,
					"reqd_bags": 0.0,
				}
				order.append(key)
			merged[key]["reqd_qty"] += flt(r.get("order_qty")) * line["per_pc"]
			merged[key]["reqd_bags"] += flt(r.get("order_qty")) * line["bags_per_pc"]
	return [merged[k] for k in order]


@frappe.whitelist()
def get_yarn_requirements(orders):
	if isinstance(orders, str):
		orders = json.loads(orders)
	return requirement_rows(orders or [])


@frappe.whitelist()
def get_weaving_contracts(orders):
	"""Submitted Weaving Contracts of the Sales Orders / fabric items on the Orders tab."""
	if isinstance(orders, str):
		orders = json.loads(orders)
	out, seen = [], set()
	for r in orders or []:
		for wc in frappe.get_all(
			"Weaving Contract",
			filters={"docstatus": 1, "sales_order": r.get("order_no"), "construction": r.get("item")},
			fields=["name", "sales_order", "construction", "fabric_qty", "weaver", "type"],
			order_by="creation asc",
		):
			if wc.name in seen:
				continue
			seen.add(wc.name)
			out.append(
				{
					"sales_order": wc.sales_order,
					"weaving_contract": wc.name,
					"fabric_item": wc.construction,
					"contract_qty": flt(wc.fabric_qty),
					"weaver": wc.weaver,
					"weaving_type": wc.type,
				}
			)
	return out


# ───────────────────────────── figures re-read from the system ─────────────────────────────
def po_figures(sales_order, yarn_item):
	"""(PO qty, received qty, first supplier) of the submitted Purchase Orders of this Sales Order + yarn."""
	row = frappe.db.sql(
		"""
		select ifnull(sum(i.qty), 0), ifnull(sum(i.received_qty), 0), min(p.supplier)
		from `tabPurchase Order Item` i
		inner join `tabPurchase Order` p on p.name = i.parent
		where p.docstatus = 1 and i.sales_order = %s and i.item_code = %s
		""",
		(sales_order, yarn_item),
	)
	return (flt(row[0][0]), flt(row[0][1]), row[0][2]) if row else (0.0, 0.0, None)


def yarn_status(issued, required):
	"""Dispatched / Not Dispatched / Partially Dispatched from yarn issued vs required on the contract's BOM rows."""
	if flt(issued) <= 0.0005:
		return "Not Dispatched"
	if flt(issued) + 0.001 >= flt(required):
		return "Dispatched"
	return "Partially Dispatched"


def refresh_figures(doc):
	for r in doc.get("yarn_requirements") or []:
		if r.sales_order and r.yarn_item:
			po_qty, r.received_qty, supplier = po_figures(r.sales_order, r.yarn_item)
			# a PO Qty typed by hand is kept; clearing it to 0 hands it back to the system
			if not flt(r.po_qty):
				r.po_qty_manual = 0
			if not r.get("po_qty_manual"):
				r.po_qty = po_qty
			if not r.get("supplier") and supplier:
				r.supplier = supplier
		r.balance_qty = flt(r.reqd_qty) - flt(r.received_qty)
	for r in doc.get("weaving") or []:
		if not r.weaving_contract:
			continue
		received = frappe.db.sql(
			"""
			select ifnull(sum(i.pcs_actual), 0) from `tabWeaving Receipt Item` i
			inner join `tabWeaving Receipt` w on w.name = i.parent
			where w.docstatus = 1 and i.weaving_contract = %s
			""",
			(r.weaving_contract,),
		)[0][0]
		r.received_qty = flt(received)
		r.balance_qty = flt(r.contract_qty) - flt(received)
		bom = frappe.db.sql(
			"select ifnull(sum(yarn_issued), 0), ifnull(sum(yarn_qty), 0) from `tabBOM Items` where parent = %s and parenttype = 'Weaving Contract'",
			(r.weaving_contract,),
		)[0]
		r.yarn_status = yarn_status(bom[0], bom[1])


def set_totals(doc):
	doc.total_order_qty = sum(flt(r.order_qty) for r in doc.get("orders") or [])
	doc.total_reqd_qty = sum(flt(r.reqd_qty) for r in doc.get("yarn_requirements") or [])
	doc.total_reqd_bags = sum(flt(r.reqd_bags) for r in doc.get("yarn_requirements") or [])
