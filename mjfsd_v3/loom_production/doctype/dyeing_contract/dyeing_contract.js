frappe.ui.form.on("Dyeing Contract", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Sales Order"), () => get_items_from_sales_orders(frm), __("Get Items From"));
		}
		if (frm.doc.docstatus === 1) {
			// "Create Dyeing Receipt": same "create a prefilled draft and route to
			// it" pattern already used by Weaving Contract's own "Weaving
			// Receipt" button, reusing Dyeing Receipt's existing
			// Get-Items-From-Dyeing-Contract row-building logic so both
			// paths stay consistent.
			frm.add_custom_button(__("Create Dyeing Receipt"), () => create_dyeing_receipt(frm));
			// Self-heals Issued Qty/Rolls/Weight from a live query against
			// actually-submitted Stock Entries every time this form loads
			// (fabric is issued through Fabric Issuance Entry now).
			sync_issued_totals(frm);
		}
	}
});

// Get Items from Sales Order: pick one or several submitted Sales Orders; every row with a Color and some AB Qty
// still unassigned is added. The qty goes into Solid / Stripe / Yarn Dyed by the Dyeing Type on the Towel Costing Sheet.
function get_items_from_sales_orders(frm) {
	new frappe.ui.form.MultiSelectDialog({
		doctype: "Sales Order",
		target: frm,
		setters: { customer: null, transaction_date: null },
		add_filters_group: 1,
		get_query() {
			return { filters: { docstatus: 1 } };
		},
		action(selections) {
			if (!selections || !selections.length) {
				return;
			}
			frappe.call({
				method: "mjfsd_v3.loom_production.events.create_dyeing_contract.get_items_from_sales_orders",
				args: { sales_orders: selections },
				freeze: true,
				callback: (r) => {
					const rows = r.message || [];
					const have = new Set((frm.doc.items || []).map((x) => x.sales_order_item).filter(Boolean));
					let added = 0;
					rows.forEach((row) => {
						if (have.has(row.sales_order_item)) {
							return;
						}
						const child = frm.add_child("items");
						Object.keys(row).forEach((k) => {
							if (row[k] !== null && row[k] !== undefined) {
								child[k] = row[k];
							}
						});
						added++;
					});
					const orders = new Set((frm.doc.items || []).map((x) => x.sales_order).filter(Boolean));
					if (orders.size === 1) {
						frm.set_value("sales_order", [...orders][0]);
					}
					frm.refresh_field("items");
					recalc_contract_amount(frm);
					cur_dialog && cur_dialog.hide();
					frappe.show_alert({ message: __("{0} row(s) added", [added]), indicator: "green" });
				}
			});
		}
	});
}

// LBS = AB Qty x Finish Weight (Gram: /1000 x 2.2046, LBS/Dozen: /12); Amount = LBS x Rate.
// Live preview - the server recalculates the same on save.
frappe.ui.form.on("Dyeing Contract Item", {
	order_qty: (frm, cdt, cdn) => recalc_dyeing_row(frm, cdt, cdn),
	rate: (frm, cdt, cdn) => recalc_dyeing_row(frm, cdt, cdn),
	finish_weight: (frm, cdt, cdn) => recalc_dyeing_row(frm, cdt, cdn),
	items_remove: (frm) => recalc_contract_amount(frm)
});

function recalc_dyeing_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const fw = flt(row.finish_weight);
	const lbs = row.finish_weight_uom === "LBS/Dozen"
		? flt(row.order_qty) * (fw / 12)
		: flt(row.order_qty) * (fw / 1000) * 2.2046;
	frappe.model.set_value(cdt, cdn, "lbs", lbs);
	frappe.model.set_value(cdt, cdn, "amount", flt(row.rate) * lbs);
	recalc_contract_amount(frm);
}

function recalc_contract_amount(frm) {
	frm.set_value("contract_amount", (frm.doc.items || []).reduce((sum, r) => sum + flt(r.amount), 0));
}

function sync_issued_totals(frm) {
	frappe.call({
		method: "mjfsd_v3.loom_production.events.issue_fabric.sync_issued_totals",
		args: { dyeing_contract: frm.doc.name },
		callback: (r) => {
			if (r.message && r.message.changed) {
				frm.reload_doc();
			}
		}
	});
}

function create_dyeing_receipt(frm) {
	frappe.call({
		method: "mjfsd_v3.loom_production.events.create_dyeing_receipt.create_dyeing_receipt_from_dyeing_contract",
		args: { dyeing_contract: frm.doc.name },
		freeze: true,
		callback: (r) => {
			if (!r.message) return;
			frappe.model.sync(r.message);
			frappe.set_route("Form", r.message.doctype, r.message.name);
		}
	});
}
