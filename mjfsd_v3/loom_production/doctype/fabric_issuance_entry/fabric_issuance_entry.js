frappe.ui.form.on("Fabric Issuance Entry", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Dyeing Contract"),
				() => get_items_from_dyeing_contracts(frm),
				__("Get Items From")
			);
		}
		if (frm.is_new()) {
			set_default_warehouses(frm);
		}
	}
});

frappe.ui.form.on("Fabric Issuance Entry Item", {
	fetch_rolls(frm, cdt, cdn) {
		fetch_rolls_dialog(frm, locals[cdt][cdn]);
	},
	weight_kg(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "weight_lbs", flt(row.weight_kg) * 2.2046);
	},
	items_remove(frm) {
		// rolls of a deleted row go with it
		const keys = new Set((frm.doc.items || []).map((r) => r.row_key));
		frm.doc.roll_details = (frm.doc.roll_details || []).filter((r) => keys.has(r.item_row));
	}
});

function make_row_key() {
	return "fk-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
}

// Greige / Supplier warehouse default from Emadi Settings (Dyeing source / target) when still empty
function set_default_warehouses(frm) {
	if (frm.doc.greige_warehouse && frm.doc.supplier_warehouse) {
		return;
	}
	frappe.xcall("mjfsd_v3.loom_production.warehouse_defaults.get_defaults").then((d) => {
		if (!frm.doc.greige_warehouse && d.dyeing_source_warehouse) {
			frm.set_value("greige_warehouse", d.dyeing_source_warehouse);
		}
		if (!frm.doc.supplier_warehouse && d.dyeing_target_warehouse) {
			frm.set_value("supplier_warehouse", d.dyeing_target_warehouse);
		}
	});
}

// ── Get Items from Dyeing Contract ──────────────────────────────────────────────────────────
function get_items_from_dyeing_contracts(frm) {
	new frappe.ui.form.MultiSelectDialog({
		doctype: "Dyeing Contract",
		target: frm,
		setters: { supplier: frm.doc.supplier || null, sales_order: null },
		add_filters_group: 1,
		get_query() {
			return { filters: { docstatus: 1 } };
		},
		action(selections) {
			if (!selections || !selections.length) {
				return;
			}
			frappe.call({
				method: "mjfsd_v3.loom_production.events.fabric_issuance_entry.get_items_from_dyeing_contracts",
				args: { contracts: selections },
				freeze: true,
				callback: (r) => {
					const rows = r.message || [];
					const have = new Set((frm.doc.items || []).map((x) => x.dyeing_contract_item).filter(Boolean));
					let added = 0;
					rows.forEach((row) => {
						if (have.has(row.dyeing_contract_item)) {
							return;
						}
						const child = frm.add_child("items");
						[
							"item_code", "color", "type", "qty", "finish_weight", "greige_weight", "sales_order",
							"towel_costing_sheet", "greige_batch", "weaving_contract", "dyeing_contract", "dyeing_contract_item"
						].forEach((k) => {
							if (row[k] !== null && row[k] !== undefined) {
								child[k] = row[k];
							}
						});
						child.row_key = make_row_key();
						added++;
					});
					if (rows.length) {
						if (!frm.doc.supplier) {
							frm.set_value("supplier", rows[0].supplier);
						}
					}
					frm.refresh_field("items");
					cur_dialog && cur_dialog.hide();
					frappe.show_alert({ message: __("{0} row(s) added", [added]), indicator: "green" });
				}
			});
		}
	});
}

// ── Fetch Rolls ─────────────────────────────────────────────────────────────────────────────
function fetch_rolls_dialog(frm, row) {
	if (!row.item_code || !(row.sales_order || row.weaving_contract)) {
		frappe.msgprint(__("Set the Item Code and the Sales Order Ref of this row first."));
		return;
	}
	if (!row.row_key) {
		row.row_key = make_row_key();
	}
	frappe.call({
		method: "mjfsd_v3.loom_production.events.fabric_issuance_entry.get_rolls",
		args: {
			sales_order: row.sales_order,
			item_code: row.item_code,
			weaving_contract: row.weaving_contract,
			exclude_fie: frm.is_new() ? null : frm.doc.name
		},
		freeze: true,
		callback: (r) => {
			// rolls already ticked on another row of this entry are not offered again
			const others = new Set(
				(frm.doc.roll_details || [])
					.filter((d) => d.item_row !== row.row_key)
					.map((d) => d.source_doctype + "|" + d.source_name)
			);
			const rolls = (r.message || []).filter((x) => !others.has(x.source_doctype + "|" + x.source_name));
			const mine = (frm.doc.roll_details || []).filter((d) => d.item_row === row.row_key);
			// rolls ticked on this row but not offered by the server (e.g. saved earlier) stay in the list
			const have = new Set(rolls.map((x) => x.source_doctype + "|" + x.source_name));
			mine.forEach((d) => {
				if (!have.has(d.source_doctype + "|" + d.source_name)) {
					rolls.push({ source_doctype: d.source_doctype, parent_doc: d.parent_doc, source_name: d.source_name, roll_no: d.roll_no, pcs: d.pcs, weight_kg: d.weight_kg });
				}
			});
			if (!rolls.length) {
				frappe.msgprint(__("No Roll# found for {0} against {1}. Rolls come from submitted Daily Loom Production and Weaving Receipt documents and are hidden once issued on another Fabric Issuance Entry.", [row.item_code, row.sales_order || row.weaving_contract]));
				return;
			}
			const picked = new Set(mine.map((d) => d.source_doctype + "|" + d.source_name));
			const esc = frappe.utils.escape_html;
			const body = rolls
				.map((x, i) => `<tr>
					<td><input type="checkbox" class="fie-roll" data-i="${i}" ${picked.has(x.source_doctype + "|" + x.source_name) ? "checked" : ""}></td>
					<td>${esc(x.roll_no)}</td><td>${esc(x.source_doctype)}</td><td>${esc(x.parent_doc)}</td>
					<td class="text-right">${format_number(x.pcs)}</td><td class="text-right">${format_number(x.weight_kg)}</td></tr>`)
				.join("");
			const d = new frappe.ui.Dialog({
				title: __("Rolls of {0} ({1})", [row.item_code, row.sales_order || row.weaving_contract]),
				size: "large",
				fields: [{ fieldtype: "HTML", fieldname: "rolls_html" }],
				primary_action_label: __("Save"),
				primary_action: () => {
					const chosen = [];
					d.$wrapper.find(".fie-roll:checked").each(function () {
						chosen.push(rolls[parseInt($(this).attr("data-i"))]);
					});
					apply_rolls(frm, row, chosen);
					d.hide();
				}
			});
			d.fields_dict.rolls_html.$wrapper.html(`
				<div style="overflow-x:auto"><table class="table table-bordered">
				<thead><tr><th style="width:36px"><input type="checkbox" class="fie-all"></th><th>${__("Roll#")}</th><th>${__("From")}</th><th>${__("Document")}</th>
				<th class="text-right">${__("Pcs")}</th><th class="text-right">${__("Weight (Kg)")}</th></tr></thead><tbody>${body}</tbody></table></div>`);
			d.$wrapper.find(".fie-all").on("change", function () {
				d.$wrapper.find(".fie-roll").prop("checked", this.checked);
			});
			d.show();
		}
	});
}

// Saves the ticked rolls on the row: Rolls text, Qty = pieces, Weight (Kg) and (LBS) = totals of those rolls
function apply_rolls(frm, row, chosen) {
	frm.doc.roll_details = (frm.doc.roll_details || []).filter((d) => d.item_row !== row.row_key);
	chosen.forEach((x) => {
		frm.add_child("roll_details", {
			item_row: row.row_key,
			source_doctype: x.source_doctype,
			parent_doc: x.parent_doc,
			source_name: x.source_name,
			roll_no: x.roll_no,
			pcs: x.pcs,
			weight_kg: x.weight_kg
		});
	});
	const kg = chosen.reduce((s, x) => s + flt(x.weight_kg), 0);
	const pcs = chosen.reduce((s, x) => s + flt(x.pcs), 0);
	frappe.model.set_value(row.doctype, row.name, "rolls", chosen.map((x) => x.roll_no).join(", "));
	if (chosen.length) {
		frappe.model.set_value(row.doctype, row.name, "qty", pcs);
		frappe.model.set_value(row.doctype, row.name, "weight_kg", kg);
		frappe.model.set_value(row.doctype, row.name, "weight_lbs", kg * 2.2046);
	}
	frm.refresh_field("items");
	frm.dirty();
}
