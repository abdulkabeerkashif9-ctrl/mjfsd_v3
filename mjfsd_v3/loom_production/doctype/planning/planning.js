frappe.ui.form.on("Planning", {
	select_orders(frm) {
		new frappe.ui.form.MultiSelectDialog({
			doctype: "Sales Order",
			target: frm,
			setters: { customer: null, delivery_date: null },
			add_filters_group: 1,
			get_query() {
				return { filters: { docstatus: 1 } };
			},
			action(selections) {
				if (!selections || !selections.length) {
					return;
				}
				frappe.call({
					method: "mjfsd_v3.loom_production.events.planning.get_order_items",
					args: { sales_orders: selections },
					freeze: true,
					callback: (r) => {
						const have = new Set((frm.doc.orders || []).map((x) => x.sales_order_item).filter(Boolean));
						let added = 0;
						(r.message || []).forEach((row) => {
							if (have.has(row.sales_order_item)) {
								return;
							}
							frm.add_child("orders", row);
							added++;
						});
						frm.refresh_field("orders");
						set_totals(frm);
						cur_dialog && cur_dialog.hide();
						frappe.show_alert({ message: __("{0} order row(s) added", [added]), indicator: "green" });
					}
				});
			}
		});
	},

	fetch_yarn_requirements(frm) {
		if (!(frm.doc.orders || []).length) {
			frappe.msgprint(__("Select orders first."));
			return;
		}
		frappe.call({
			method: "mjfsd_v3.loom_production.events.planning.get_yarn_requirements",
			args: { orders: frm.doc.orders.map((r) => ({ order_no: r.order_no, item: r.item, order_qty: r.order_qty, towel_costing_sheet: r.towel_costing_sheet })) },
			freeze: true,
			callback: (r) => {
				const key = (x) => [x.sales_order, x.fabric_item, x.yarn_item].join("|");
				const have = new Set((frm.doc.yarn_requirements || []).map(key));
				let added = 0;
				(r.message || []).forEach((row) => {
					if (have.has(key(row))) {
						return;
					}
					frm.add_child("yarn_requirements", row);
					added++;
				});
				frm.refresh_field("yarn_requirements");
				set_totals(frm);
				frappe.show_alert({ message: __("{0} yarn row(s) added", [added]), indicator: "green" });
			}
		});
	},

	fetch_weaving_contracts(frm) {
		if (!(frm.doc.orders || []).length) {
			frappe.msgprint(__("Select orders first."));
			return;
		}
		frappe.call({
			method: "mjfsd_v3.loom_production.events.planning.get_weaving_contracts",
			args: { orders: frm.doc.orders.map((r) => ({ order_no: r.order_no, item: r.item })) },
			freeze: true,
			callback: (r) => {
				const have = new Set((frm.doc.weaving || []).map((x) => x.weaving_contract));
				let added = 0;
				(r.message || []).forEach((row) => {
					if (have.has(row.weaving_contract)) {
						return;
					}
					frm.add_child("weaving", row);
					added++;
				});
				frm.refresh_field("weaving");
				frappe.show_alert({ message: __("{0} weaving contract(s) added - save to refresh Rcvd / Balance / Yarn Status", [added]), indicator: "green" });
			}
		});
	},

	orders_remove: set_totals,
	yarn_requirements_remove: set_totals
});

frappe.ui.form.on("Planning Order", {
	order_qty: (frm) => set_totals(frm)
});

frappe.ui.form.on("Planning Yarn", {
	reqd_qty: (frm) => set_totals(frm),
	po_qty(frm, cdt, cdn) {
		// typed PO Qty is kept (not replaced by the Purchase Order figure); 0 hands it back to the system
		frappe.model.set_value(cdt, cdn, "po_qty_manual", flt(locals[cdt][cdn].po_qty) ? 1 : 0);
	}
});

function set_totals(frm) {
	const sum = (rows, k) => (rows || []).reduce((s, r) => s + flt(r[k]), 0);
	frm.set_value("total_order_qty", sum(frm.doc.orders, "order_qty"));
	frm.set_value("total_reqd_qty", sum(frm.doc.yarn_requirements, "reqd_qty"));
	frm.set_value("total_reqd_bags", sum(frm.doc.yarn_requirements, "reqd_bags"));
}
