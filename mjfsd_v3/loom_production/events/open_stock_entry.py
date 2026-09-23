import frappe
from frappe import _

@frappe.whitelist()
def open_stock_entry(sizing_program_name):
    """Creates a Stock Entry for a given Sizing Program"""
    sp = frappe.get_doc("Sizing Program", sizing_program_name)
    # You will need to define what type of Stock Entry, items, etc.
    # Here's a simplified example

    # Create a new Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"  # or appropriate type
    se.custom_sizing_program_gate_pass = sp.name
    se.purpose = "Material Transfer"
    se.set_posting_time = 1
    se.posting_date = sp.date
    item = frappe.get_doc("Item", sp.item)
    # Maybe link back (custom field) to Sizing Program?
    se.append("items", {
        "item_code": sp.item,  # or from sp
        "qty": sp.lbs,
        "t_warehouse": sp.source_warehouse,
        "uom": item.stock_uom,
        "stock_uom": item.stock_uom
    })
    # If you want set other fields
    # se.save()
    # Optionally submit or leave draft
    # se.submit()

    return se
