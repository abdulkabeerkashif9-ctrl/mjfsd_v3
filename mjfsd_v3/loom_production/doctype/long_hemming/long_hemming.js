frappe.ui.form.on("Long Hemming", {
	refresh(frm) {
		frm.toggle_reqd("b_qty_warehouse", frm.doc.transfer_b_qty);
	},

	transfer_b_qty(frm) {
		frm.toggle_reqd("b_qty_warehouse", frm.doc.transfer_b_qty);
	}
});
