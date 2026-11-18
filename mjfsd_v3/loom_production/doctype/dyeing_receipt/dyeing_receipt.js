frappe.ui.form.on("Dyeing Receipt", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Select Rolls"), () => select_rolls_dialog(frm));
		}
		if (frm.is_new()) {
			set_default_warehouses(frm);
		}
	},

	items_remove(frm) {
		recalc_parent_total(frm);
	}
});

frappe.ui.form.on("Dyeing Receipt Item", {
	received_qty(frm, cdt, cdn) {
		recalc_finish_weight(frm, cdt, cdn);
		recalc_parent_total(frm);
	},
	weight_received_kg(frm, cdt, cdn) {
		recalc_finish_weight(frm, cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		recalc_finish_weight(frm, cdt, cdn);
	}
});

function recalc_finish_weight(frm, cdt, cdn) {
	// Live preview only - Dyeing Receipt's own validate() recomputes this
	// authoritatively on save regardless, same "server is the source of
	// truth" pattern used everywhere else in this project.
	let row = locals[cdt][cdn];
	if (!row.towel_costing_sheet || !row.item) {
		return;
	}
	frappe.call({
		method: "mjfsd_v3.loom_production.events.create_dyeing_receipt.get_tcs_finish_weight",
		args: { towel_costing_sheet: row.towel_costing_sheet, item_code: row.item },
		callback: (r) => {
			let tcs_finish_weight = flt(r.message);
			let finish_weight = (tcs_finish_weight / 1000) * flt(row.received_qty);
			frappe.model.set_value(cdt, cdn, "finish_weight", finish_weight);
			// 2026-09-28 (feature v3) - "calculate weight as following
			// ((Pcs * finish weight mentioned in TCS)/1000)*2.2046 ...
			// amount = dyeing rate * weight (lbs)" (your words). Was
			// Rate x Received Qty (Pcs) - fixed to match the server
			// (dyeing_receipt.py recalculate_totals), which this had
			// drifted from.
			// Actual Weight is entered in LBS; the TCS-derived weight is the fallback
			let weight_lbs = flt(row.weight_received_kg) || finish_weight * 2.2046;
			frappe.model.set_value(cdt, cdn, "weight_received_lbs", weight_lbs);
			frappe.model.set_value(cdt, cdn, "amount", flt(row.rate) * weight_lbs);
		}
	});
}

// Receipt Source = supplier warehouse, Target = greige/dyeing warehouse (Emadi Settings Dyeing pair); editable afterwards
function set_default_warehouses(frm) {
	frappe.xcall("mjfsd_v3.loom_production.warehouse_defaults.get_defaults").then((d) => {
		if (!frm.doc.source_warehouse && d.dyeing_target_warehouse) {
			frm.set_value("source_warehouse", d.dyeing_target_warehouse);
		}
		if (!frm.doc.target_warehouse && d.dyeing_source_warehouse) {
			frm.set_value("target_warehouse", d.dyeing_source_warehouse);
		}
	});
}

// ── Select Rolls: rolls issued to the supplier on submitted Fabric Issuance Entries, grouped item-wise ──
function select_rolls_dialog(frm) {
	if (!frm.doc.supplier) {
		frappe.msgprint(__("Select the Supplier first."));
		return;
	}
	frappe.call({
		method: "mjfsd_v3.loom_production.events.create_dyeing_receipt.get_issued_rolls",
		args: { supplier: frm.doc.supplier, exclude_receipt: frm.is_new() ? null : frm.doc.name },
		freeze: true,
		callback: (r) => {
			const have = new Set((frm.doc.items || []).map((x) => x.fie_roll_ref).filter(Boolean));
			const rolls = (r.message || []).filter((x) => !have.has(x.fie_roll_ref));
			if (!rolls.length) {
				frappe.msgprint(__("No issued rolls are pending receipt from {0}.", [frm.doc.supplier]));
				return;
			}
			const esc = frappe.utils.escape_html;
			let body = "";
			let last = null;
			rolls.forEach((x, i) => {
				const grp = x.item_code + "|" + (x.color || "");
				if (grp !== last) {
					last = grp;
					body += `<tr class="active"><td><input type="checkbox" class="dr-grp" data-g="${esc(grp)}"></td>
						<td colspan="5"><b>${esc(x.item_code)}</b>${x.color ? " &mdash; " + esc(x.color) : ""}</td></tr>`;
				}
				body += `<tr><td><input type="checkbox" class="dr-roll" data-g="${esc(grp)}" data-i="${i}"></td>
					<td>${esc(x.roll_no)}</td><td>${esc(x.fabric_issuance_entry)}</td><td>${esc(x.sales_order || "")}</td>
					<td class="text-right">${format_number(x.pcs)}</td><td class="text-right">${format_number(x.weight_lbs)}</td></tr>`;
			});
			const d = new frappe.ui.Dialog({
				title: __("Select Rolls — {0}", [frm.doc.supplier]),
				size: "large",
				fields: [{ fieldtype: "HTML", fieldname: "rolls_html" }],
				primary_action_label: __("Save"),
				primary_action: () => {
					const chosen = [];
					d.$wrapper.find(".dr-roll:checked").each(function () {
						chosen.push(rolls[parseInt($(this).attr("data-i"))]);
					});
					if (!chosen.length) {
						frappe.msgprint(__("Tick at least one roll."));
						return;
					}
					add_roll_rows(frm, chosen);
					d.hide();
				}
			});
			d.fields_dict.rolls_html.$wrapper.html(`
				<div style="overflow-x:auto"><table class="table table-bordered">
				<thead><tr><th style="width:36px"></th><th>${__("Roll#")}</th><th>${__("Fabric Issuance Entry")}</th><th>${__("Sales Order")}</th>
				<th class="text-right">${__("Issued Qty")}</th><th class="text-right">${__("Issued Weight (LBS)")}</th></tr></thead>
				<tbody>${body}</tbody></table></div>`);
			d.$wrapper.find(".dr-grp").on("change", function () {
				const g = $(this).attr("data-g");
				const on = this.checked;
				d.$wrapper.find(".dr-roll").filter(function () { return $(this).attr("data-g") === g; }).prop("checked", on);
			});
			d.show();
		}
	});
}

// one row per roll; Actual Qty / Weight start from the issued figures, Actual Rolls = 1
function add_roll_rows(frm, chosen) {
	// drop the empty first row Frappe leaves in a new form
	frm.doc.items = (frm.doc.items || []).filter((x) => x.item || x.roll_no);
	chosen.forEach((x) => {
		frm.add_child("items", {
			item: x.item_code,
			color: x.color,
			roll_no: x.roll_no,
			issued_qty: flt(x.pcs),
			issued_weight: flt(x.weight_lbs),
			received_qty: flt(x.pcs),
			rolls_received: 1,
			weight_received_kg: flt(x.weight_lbs),
			rate: flt(x.rate),
			dyeing_wastage_percent: flt(x.dyeing_wastage_percent),
			sales_order: x.sales_order,
			towel_costing_sheet: x.towel_costing_sheet,
			dyeing_contract: x.dyeing_contract,
			dyeing_contract_item: x.dyeing_contract_item,
			greige_batch: x.greige_batch,
			color_batch: x.color_batch,
			fie_roll_ref: x.fie_roll_ref,
			fabric_issuance_entry: x.fabric_issuance_entry
		});
	});
	frm.refresh_field("items");
	recalc_parent_total(frm);
	frm.dirty();
}

function recalc_parent_total(frm) {
	let total = 0;
	(frm.doc.items || []).forEach((row) => {
		total += flt(row.received_qty);
	});
	frm.set_value("total_received_qty", total);
}
