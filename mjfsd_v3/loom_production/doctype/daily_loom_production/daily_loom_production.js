// Copyright (c) 2026, Tech Ventures and contributors
// For license information, please see license.txt

// Round 14 Part B (2026-09-09): see claude/daily-towel-production.md for
// the full spec this was built against.
//
// Round 19 (2026-09-16) NOTE: unlike round 18's events-file rewrite,
// Kabeer's round 18 paste confirmed this specific file was unchanged from
// this history at that point - but this round's change (warehouse
// defaults in the Raw Material Selection dialog) needs to land in the
// dialog-building code below, and a fresh live copy wasn't re-pasted this
// round. Rebuilt from the documented spec plus the one change described
// under "Round 19" below - the rest (item query, Total Finish Qty
// rollup) should match what's already live; flag anything that's drifted
// so it can be reconciled against your real file.
//
// Round 19 change: the Raw Material Selection dialog's Source Warehouse
// field now arrives pre-filled (Beam Items -> the Sizing Receipt's own
// Target Warehouse, via the new `default_warehouse` the Python side now
// returns; Yarn Items -> "Stores - PT") instead of blank - still a plain
// editable Link field, not read-only, per Kabeer: "yarn item warehouse
// will be Stores - PT by default but editable."
//
// 2026-09-28 (feature v3): doctype renamed "Daily Towel Production" ->
// "Daily Loom Production" (your words) - this file itself is unchanged
// other than the event binding's name below; the events module it calls
// into (create_stock_entry_from_daily_towel_production.py) still has its
// old name/path, on purpose - see the controller .py's own note.

const RM_DELIMITER = " | ";

frappe.ui.form.on('Daily Loom Production', {
	refresh: function (frm) {
		frm.set_query('item', 'items', function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				query: 'mjfsd_v3.loom_production.events.create_stock_entry_from_daily_towel_production.get_sales_order_items',
				filters: {
					sales_order: row.sales_order
				}
			};
		});
	}
});

frappe.ui.form.on('Daily Loom Production Item', {
	sales_order: function (frm, cdt, cdn) {
		// A stale Item pick from a different Sales Order can't linger
		// once the Sales Order itself changes.
		frappe.model.set_value(cdt, cdn, 'item', '');
	},
	// 2026-09-28 (feature v3) - per your request: A/B/C/Cut Pcs Qty feed
	// Finish Qty, which now feeds Total Greige Weight, which needs Greige
	// Weight fetched off Sales Order + Item first. Wired as one small
	// cascade rather than four separate recomputes.
	item: function (frm, cdt, cdn) {
		fetch_greige_weight(frm, cdt, cdn);
	},
	a_qty: function (frm, cdt, cdn) {
		recalc_finish_qty(frm, cdt, cdn);
	},
	b_qty: function (frm, cdt, cdn) {
		recalc_finish_qty(frm, cdt, cdn);
	},
	c_qty: function (frm, cdt, cdn) {
		recalc_finish_qty(frm, cdt, cdn);
	},
	cut_pcs_qty: function (frm, cdt, cdn) {
		recalc_finish_qty(frm, cdt, cdn);
	},
	finish_qty: function (frm, cdt, cdn) {
		recalc_total_greige_weight(frm, cdt, cdn);
		recalculate_total_finish_qty(frm);
	},
	greige_weight: function (frm, cdt, cdn) {
		recalc_total_greige_weight(frm, cdt, cdn);
	},
	items_add: function (frm) {
		recalculate_total_finish_qty(frm);
	},
	items_remove: function (frm) {
		recalculate_total_finish_qty(frm);
	},
	raw_material_selection: function (frm, cdt, cdn) {
		open_raw_material_dialog(frm, cdt, cdn);
	}
});

// 2026-09-28 - "Finish Qty (Read only) = A Qty + B Qty + C Qty + Cut Pcs
// Qty" (your words). Live preview only - daily_loom_production.py's own
// validate() recomputes this authoritatively on save regardless, same
// "server is the source of truth" pattern used everywhere else in this
// project.
function recalc_finish_qty(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let finish_qty = flt(row.a_qty) + flt(row.b_qty) + flt(row.c_qty) + flt(row.cut_pcs_qty);
	frappe.model.set_value(cdt, cdn, 'finish_qty', finish_qty);
}

// "Total Greige Weight (Calculated) (greige weight * Finish Qty)" (your
// words). Live preview only, same reasoning as above.
function recalc_total_greige_weight(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let total = flt(row.greige_weight) * flt(row.finish_qty);
	frappe.model.set_value(cdt, cdn, 'total_greige_weight', total);
}

// "Fetch ... greige weight (from TCS finish table)(New Field)" (your
// words). Live preview only, same reasoning as above - needs both Sales
// Order and Item set, same lookup Raw Material Selection already uses.
function fetch_greige_weight(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (!row.sales_order || !row.item) {
		return;
	}
	frappe.call({
		method: 'mjfsd_v3.loom_production.events.create_stock_entry_from_daily_towel_production.get_greige_weight',
		args: {
			sales_order: row.sales_order,
			item_code: row.item
		},
		callback: function (r) {
			if (r.message === undefined) {
				return;
			}
			frappe.model.set_value(cdt, cdn, 'greige_weight', flt(r.message));
			recalc_total_greige_weight(frm, cdt, cdn);
		}
	});
}

function recalculate_total_finish_qty(frm) {
	let total = 0;
	(frm.doc.items || []).forEach(function (row) {
		total += flt(row.finish_qty);
	});
	frm.set_value('total_finish_qty', total);
}

function open_raw_material_dialog(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	if (!row.sales_order || !row.item || !row.finish_qty) {
		frappe.msgprint(__('Set Sales Order, Item and Finish Qty on this row first.'));
		return;
	}

	frappe.call({
		method: 'mjfsd_v3.loom_production.events.create_stock_entry_from_daily_towel_production.get_raw_materials_for_row',
		args: {
			sales_order: row.sales_order,
			item_code: row.item,
			finish_qty: row.finish_qty
		},
		callback: function (r) {
			if (r.exc || !r.message || !r.message.length) {
				return;
			}
			show_raw_material_dialog(frm, cdt, cdn, r.message);
		}
	});
}

function show_raw_material_dialog(frm, cdt, cdn, materials) {
	const fields = [];

	materials.forEach(function (m, idx) {
		fields.push({
			fieldtype: 'Section Break',
			label: `${m.group}: ${m.item_code}`
		});
		fields.push({
			fieldname: `source_${idx}`,
			fieldtype: 'Data',
			label: 'Source',
			default: m.item_code,
			read_only: 1
		});
		fields.push({
			fieldname: `qty_${idx}`,
			fieldtype: 'Float',
			label: 'Qty',
			default: m.qty,
			read_only: 1
		});
		fields.push({
			fieldname: `warehouse_${idx}`,
			fieldtype: 'Link',
			options: 'Warehouse',
			label: 'Source Warehouse',
			// Round 19: pre-filled from the Python side's default_warehouse
			// (Beam Items -> that Beam's Sizing Receipt Target Warehouse,
			// Yarn Items -> "Stores - PT") - still editable, not a lock.
			default: m.default_warehouse || '',
			reqd: 1
		});
	});

	const dialog = new frappe.ui.Dialog({
		title: __('Raw Material Selection'),
		fields: fields,
		primary_action_label: __('Confirm'),
		primary_action: function (values) {
			const items = [];
			const qtys = [];
			const warehouses = [];

			materials.forEach(function (m, idx) {
				items.push(m.item_code);
				qtys.push(m.qty);
				warehouses.push(values[`warehouse_${idx}`]);
			});

			frappe.model.set_value(cdt, cdn, 'raw_material_items', items.join(RM_DELIMITER));
			frappe.model.set_value(cdt, cdn, 'raw_material_qty', qtys.join(RM_DELIMITER));
			frappe.model.set_value(cdt, cdn, 'raw_material_warehouses', warehouses.join(RM_DELIMITER));

			dialog.hide();
		}
	});

	dialog.show();
}
