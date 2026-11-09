// Copyright (c) 2023, Tech Ventures and contributors
// For license information, please see license.txt

$(document).ready(function () {
    $('input[data-fieldname="po_number"], input[data-fieldname="date"],' +
        'input[data-fieldname="supplier"],input[data-fieldname="item"],select[data-fieldname="quality"],' +
        'input[data-fieldname="yarn_count"],input[data-fieldname="lbs_per_bag"],input[data-fieldname="cones_per_bag"],' +
        'input[data-fieldname="warping_beam"],input[data-fieldname="sizing_beam"],input[data-fieldname="warp_wastage_percent"],' +
        'input[data-fieldname="beam_size"],input[data-fieldname="ends"],input[data-fieldname="bags_issue"],' +
        'input[data-fieldname="no_of_bags_required"],input[data-fieldname="item_returnable"],input[data-fieldname="fabric_construction"],' +
        'input[data-fieldname="lbs_issue"],input[data-fieldname="panna"]').css("background-color", "#FFE4C4");

    $('input[data-fieldname="po_number"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="po_number"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="date"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="date"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="supplier"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="supplier"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="item"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="item"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('select[data-fieldname="quality"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('select[data-fieldname="quality"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="yarn_count"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="yarn_count"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="lbs_per_bag"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="lbs_per_bag"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="cones_per_bag"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="cones_per_bag"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="warping_beam"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="warping_beam"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="sizing_beam"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="sizing_beam"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="warp_wastage_percent"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="warp_wastage_percent"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="beam_size"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="beam_size"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });

      $('input[data-fieldname="ends"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="ends"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
      $('input[data-fieldname="bags_issue"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="bags_issue"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
      $('input[data-fieldname="no_of_bags_required"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="no_of_bags_required"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
      $('input[data-fieldname="item_returnable"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="item_returnable"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="fabric_construction"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="fabric_construction"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="panna"]').focus(function () {
        $(this).css("background-color", "#50C878");
    });
    $('input[data-fieldname="panna"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });
    $('input[data-fieldname="lbs_issue"]').blur(function () {
        $(this).css("background-color", "#FFE4C4");
    });

});


frappe.ui.form.on("Sizing Program", {

    refresh(frm) {

        if (!frm.is_new()) {
            frm.set_value('po_number', frm.doc.name);

            // A Sizing Program can have several Sizing Receipts drawn off
            // it over time - Balance Net Meter is always re-fetched from
            // the server (Net Meter minus the sum of Beam Length already
            // issued to Sizing Receipts) rather than stored/cached.
            frappe.call({
                method: "mjfsd_v3.loom_production.events.sizing_program_balance.get_balance_net_meter",
                args: {
                    sizing_program: frm.doc.name
                },
                callback: function (r) {
                    if (r.message !== undefined) {
                        frm.set_value('balance_net_meter', r.message);
                    }
                }
            });
        }
        // Yarn Details table (multi finish item / yarn)
        frm.set_query("yarn_item", "yarn_items", function () {
            return { filters: { item_group: "Yarn" } };
        });
        frm.set_query("beam_item", "yarn_items", function () {
            return { filters: { item_group: "Beam" } };
        });
        frm.set_query("finish_item", "yarn_items", function () {
            return { filters: { item_group: "Fabric" } };
        });
        if (frm.doc.docstatus == 0 && (frm.doc.yarn_items || []).length) {
            frm.doc.yarn_items.forEach(r => window.sizing_yarn_recalc_row(frm, r.doctype, r.name));
        }
        const balances = (frm.doc.__onload || {}).row_balances;
        if (balances && (frm.doc.yarn_items || []).length) {
            frm.doc.yarn_items.forEach(r => { if (balances[r.name] !== undefined) { r.balance_net_meter = balances[r.name]; } });
            frm.refresh_field("yarn_items");
        }
        frm.set_query("item_returnable", function () {
            return {
                "filters": {
                    "item_group": "Beam"
                }
            }
        });
        frm.set_query("fabric_construction", function () {
            return {
                "filters": {
                    "item_group": "Fabric"
                }
            }
        });
        frm.set_query("item", function () {
            return {
                "filters": {
                    "item_group": "Yarn"
                }
            }
        });
        frm.set_query("item","items", function () {
            return {
                "filters": {
                    "item_group": "Beam"
                }
            }
        });
        frm.set_query("expense_account","items", function() {
            return {
                filters: {
                    account_type: "Chargeable",
                    is_group: 0
                }
            };
        });
        frm.set_query("yarn_item","stock_return_item", function () {
            return {
                "filters": {
                    "item_group": "Yarn"
                }
            }
        });
        frm.set_query("fabric_construction","fabric_construction_detail", function () {
            return {
                "filters": {
                    "item_group": "Fabric"
                }
            }
        });
        if (frm.doc.docstatus == 0) {
            frm.add_custom_button(__('Weaving Contract'), function() {
                get_items_from_weaving_contracts(frm);
            }, __('Get Items From')).css('background-color', '#2490EF').css('color', '#ffffff');
        }
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__('Stock Entry'), function() {
                frappe.call({
                    method: "mjfsd_v3.loom_production.events.create_stock_entry_from_sizing_program.create_stock_entry_from_sizing_program",
                    args: {
                        sizing_program: frm.doc.name
                    },
                    callback: function(r) {
                        if (!r.exc) {
							frappe.model.sync(r.message);
							frappe.set_route("Form", r.message.doctype, r.message.name);
						}
                    }
                });
            }).css('background-color', '#ff9800').css('color', '#ffffff','font-weight','bold');
		}
        if (frm.doc.docstatus == 1) {

            frm.add_custom_button(__('Stock Return Entry'), function() {
                frappe.call({
                    method: "mjfsd_v3.loom_production.events.create_stock_entry_from_sizing_program.make_stock_entry_for_stock_return_item",
                    args: {
                        sizing_program: frm.doc.name,
                    },
                    callback: function(r) {
                        if (!r.exc) {
							frappe.model.sync(r.message);
							frappe.set_route("Form", r.message.doctype, r.message.name);
						}
                    }
                });
            }).css('background-color', '#527DF3').css('color', '#ffffff','font-weight','bold');
		}


        frm.add_custom_button(__("Gate Pass"), function() {
            // call the server method
            frappe.call({
                method: "mjfsd_v3.loom_production.events.open_stock_entry.open_stock_entry",
                args: {
                    sizing_program_name: frm.doc.name
                },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.model.sync(r.message);
                        frappe.set_route("Form", r.message.doctype, r.message.name);
                    }
                }
            });
        }).css('background-color', '#007e00').css('color', '#ffffff','font-weight','bold');

        // Sizing Receipt no longer comes from the (now-retired) Items child
        // table - a Sizing Program can have several Sizing Receipts drawn
        // off it over its life, so this just opens a fresh one each click,
        // pre-filled from this Sizing Program the same way the old child
        // table used to be: sizing_name/yarn_count/yarn_item used to come
        // from the child table's own "form_render" handler, and
        // fabric_construction used to come from to_child() - both ported
        // here since neither runs in this doctype's own context. Panna is
        // NOT part of this mapping - it's a hidden/unused field on Sizing
        // Program (hidden since an earlier round), so it's never populated
        // here and was wrongly being required; dropped entirely.
        // frappe.route_options (rather than frappe.new_doc's own opts
        // argument) is used because it reliably sets values via frm.set_value
        // once the new form has actually loaded, including hidden/read-only
        // fields like Sizing Program itself.
        frm.add_custom_button(__("Sizing Receipt"), function() {
            if ((frm.doc.yarn_items || []).length) {
                create_receipt_for_shared_beam(frm);
                return;
            }
            if (!frm.doc.fabric_construction || !frm.doc.item_returnable) {
                frappe.msgprint(__('Please set Finish Item and Item Name on this Sizing Program before creating a Sizing Receipt.'));
                return;
            }
            frappe.route_options = {
                sizing_program: frm.doc.po_number,
                source_warehouse: frm.doc.source_warehouse,
                sizing_name: frm.doc.supplier,
                yarn_count: frm.doc.yarn_count,
                yarn_item: frm.doc.item,
                fabric_construction: frm.doc.fabric_construction,
                item: frm.doc.item_returnable,
                yarn_consumption_per_meter: frm.doc.yarn_consumption_per_meter,
                beam_no: cint(frm.doc.sizing_beam),
                ends:frm.doc.ends,
                beem_length:frm.doc.beam_length,

            };
            frappe.new_doc('Sizing Receipt');
        }, __('Create')).css('background-color', '#6f42c1').css('color', '#ffffff','font-weight','bold');


    },
    fabric_construction:function(frm){
        to_child(frm);
    },
    panna:function(frm){
        to_child(frm);
    },
    lbs_issue:function(frm){
        calculate_cones_per_bag(frm);
        recalc_sizing(frm);
    },
    // Meter is now entered manually - it no longer drives Bags Issue, so
    // Bags Issue no longer needs its own trigger (it's purely an output
    // now, see recalc_sizing below). The recalculation chain fires on
    // every field that actually feeds it.
    ends: function (frm) {
        recalc_sizing(frm);
    },
    warp_wastage_percent: function (frm) {
        recalc_sizing(frm);
        // rows with no Wastage % of their own follow the header value
        (frm.doc.yarn_items || []).forEach(r => {
            if (!flt(r.wastage_percent)) { r.wastage_percent = frm.doc.warp_wastage_percent; }
            window.sizing_yarn_recalc_row(frm, r.doctype, r.name);
        });
    },
    meter: function (frm) {
        recalc_sizing(frm);
    },
    yarn_count: function (frm) {
        recalc_sizing(frm);
    },
    lbs_per_bag: function (frm) {
        recalc_sizing(frm);
    },
    cones_per_bag: function (frm) {
        recalc_sizing(frm);
    },
    warping_beam: function (frm) {
        recalc_sizing(frm);
    },
    sizing_beam: function (frm) {
        recalc_sizing(frm);
    }
});

function recalc_sizing(frm) {
    var lbs_per_bag = flt(frm.doc.lbs_per_bag);
    var cones_per_bag = flt(frm.doc.cones_per_bag);
    var yarn_count = flt(frm.doc.yarn_count);
    var ends = flt(frm.doc.ends);
    var meter = flt(frm.doc.meter);
    var warp_wastage_percent = flt(frm.doc.warp_wastage_percent);
    var warping_beam = flt(frm.doc.warping_beam);
    var sizing_beam = flt(frm.doc.sizing_beam);
    // 2026-09-28 fix - "bags issue = (lbs issue + wastage) / 100" (your
    // words) - the formula below was already exactly this, but lbs_issue
    // itself was never read off frm.doc here, so it was an undefined
    // variable. That's not a silent zero - a reference to an undefined
    // variable throws in JavaScript, which killed this function right at
    // the Bags Issue line and skipped every calculation after it,
    // including Net Meter = Meter further down. That's why Net Meter
    // wasn't updating either - the line that sets it was already
    // correct, it just never ran.
    var lbs_issue = flt(frm.doc.lbs_issue);

    // Cone Weight = LBS/Bag / Cones per Bag - kept for reference, no longer
    // feeds Meter (Meter is entered manually, see below).
    var cone_weight = cones_per_bag ? lbs_per_bag / cones_per_bag : 0;
    frm.set_value('cone_weight', cone_weight);

    // Meter calculation commented out - Meter is now entered manually.
    // var meter = yarn_count * 768.1 * cone_weight;
    // frm.set_value('meter', meter);

    // Yarn Consumption Per Meter = Ends / 768.1 / Yarn Count
    var yarn_consumption_per_meter = yarn_count ? (ends / 768.1) / yarn_count : 0;
    frm.set_value('yarn_consumption_per_meter', yarn_consumption_per_meter);

    // LBS = Meter x Yarn Consumption Per Meter
    var lbs = meter * yarn_consumption_per_meter;
    frm.set_value('lbs', lbs);

    // Wastage = LBS x Waste %
    var wastage = lbs * (warp_wastage_percent / 100);
    frm.set_value('wastage', wastage);

    // Bags Issue = (LBS Issue + Wastage) / 100
    var bags_issue = (lbs_issue + wastage) / 100;
    frm.set_value('bags_issue', bags_issue);

    // Net Meter = Meter (your words: "net meters should be equal to
    // meters").
    var net_meter = meter;
    frm.set_value('net_meter', net_meter);

    var meter_warp_per_beam = warping_beam ? net_meter / warping_beam : 0;
    frm.set_value('meter_warp_per_beam', meter_warp_per_beam);

    var meter_sizing_beam = sizing_beam ? meter_warp_per_beam / sizing_beam : 0;
    frm.set_value('meter_sizing_beam', meter_sizing_beam);

    // Beam Length = Meter / Sizing Beam
    var beam_length = sizing_beam ? meter / sizing_beam : 0;
    frm.set_value('beam_length', beam_length);

    var no_of_bags_required = (cones_per_bag && warping_beam) ? (ends / cones_per_bag) / warping_beam : 0;
    frm.set_value('no_of_bags_required', no_of_bags_required);

    var lbs_per_sizing_beam = meter_sizing_beam * sizing_beam;
    frm.set_value('lbs_per_sizing_beam', lbs_per_sizing_beam);

    var lbs_consumed = yarn_consumption_per_meter * lbs_per_sizing_beam;
    frm.set_value('lbs_consumed', lbs_consumed);

    var lbs_returnable = lbs - lbs_consumed;
    frm.set_value('lbs_returnable', lbs_returnable);
}

frappe.ui.form.on('Sizing Program Item', {
    form_render: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];


            frappe.model.set_value(cdt, cdn, "sizing_name", frm.doc.supplier);


            frappe.model.set_value(cdt, cdn, "yarn_count", frm.doc.yarn_count);


            frappe.model.set_value(cdt, cdn, "yarn_item", frm.doc.item);

    },
    ends: function(frm, cdt, cdn) {
        calculate_value_from_ends(frm, cdt, cdn);
        calculate_warp_weight(frm, cdt, cdn)
    },
    yarn_count: function(frm, cdt, cdn) {
        calculate_warp_weight(frm, cdt, cdn)
        calculate_value_from_ends(frm, cdt, cdn);
    },
    // wastage_percentage: function(frm, cdt, cdn) {
    //     calculate_warp_weight(frm, cdt, cdn);
    //     set_rate(frm, cdt, cdn);
    //     calculate_value_from_ends(frm, cdt, cdn);
    //     // calculate_yarn_wastage(frm, cdt, cdn);
    // },
    no_of_width: function(frm, cdt, cdn) {
        calculate_warp_weight(frm, cdt, cdn);
        calculate_value_from_ends(frm, cdt, cdn);
        // calculate_total_yarn_consumption(frm, cdt, cdn);
    },

    beem_length: function(frm, cdt, cdn) {
        calculate_total_yarn_consumption(frm, cdt, cdn);
        compute_yarn_values(frm, cdt, cdn);
        // calculate_yarn_wastage(frm, cdt, cdn);
    },
    make_stock_entry: function(frm, cdt, cdn) {
        make_stock_entry(frm, cdt, cdn);
    },
    items_add:function(frm){
        to_child(frm);
    },
    yarn_item:function(frm, cdt, cdn){
        set_rate(frm, cdt, cdn);
        // calculate_yarn_wastage(frm, cdt, cdn);
        calculate_wastes(frm, cdt, cdn);
    },
    sizing_rate:function(frm, cdt, cdn){

        calculate_total_yarn_consumption(frm, cdt, cdn);
        compute_yarn_values(frm, cdt, cdn);
        calculate_beem_rate(frm, cdt, cdn);
        calculate_wastes(frm, cdt, cdn);

    },
    ends:function(frm, cdt, cdn){
        calculate_total_yarn_consumption(frm, cdt, cdn);
        compute_yarn_values(frm, cdt, cdn);
        calculate_wastes(frm, cdt, cdn);
    },
    lbs:function(frm, cdt, cdn){
        compute_yarn_values(frm, cdt, cdn);
        // calculate_yarn_wastage(frm, cdt, cdn);
        calculate_wastes(frm, cdt, cdn);
        calculate_value_from_ends(frm, cdt, cdn);
        calculate_warp_weight(frm, cdt, cdn)
    }
});

frappe.ui.form.on('Sizing Program Stock Return Item',{
    qty_lbs: function(frm, cdt, cdn) {
        update_total_yarn_return(frm);
    },
    stock_return_item_remove:function(frm,cdt,cdn){
        update_total_yarn_return(frm);
    }
});

function update_total_yarn_return(frm) {
    if (window.sizing_yarn_allocate_returns) {
        window.sizing_yarn_allocate_returns(frm);
        frm.refresh_field("yarn_items");
    }
    let total = 0;
    let lbs_issue = frm.doc.lbs_issue;
    frm.doc.stock_return_item.forEach(function(row) {
        total += flt(row.qty_lbs);
    });
    frm.set_value('total_yarn_return', total);
    frm.set_value('balance_yarn',lbs_issue - total);
}

function calculate_value_from_ends(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (row.ends && row.actual_yarn_count) {
        let result = (row.ends/row.no_of_width / 768.1) / row.actual_yarn_count;
        frappe.model.set_value(cdt, cdn, 'yarn_consumption_per_meter', result.toFixed(5));
    } else {
        frappe.model.set_value(cdt, cdn, 'yarn_consumption_per_meter', 0);
    }
}

function calculate_total_yarn_consumption(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    // const length =  row.beem_length * row.no_of_width;
    // frappe.model.set_value(cdt, cdn, 'length', length);


        let total = row.yarn_consumption_per_meter * length;
        // frappe.model.set_value(cdt, cdn, 'lbs', total.toFixed(4));
        let beem_rate_per_meter = (total.toFixed(4) * row.yarn_item_rate)/length;
        frappe.model.set_value(cdt, cdn, 'beem_rate_per_meter', beem_rate_per_meter.toFixed(4));

}

function make_stock_entry(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    frappe.call({
        method: "mjfsd_v3.loom_production.events.create_stock_entry_from_sizing_program.make_stock_entry_from_sizing_item",
        args: {
            docname: frm.doc.name,
            s_warehouse: frm.doc.source_warehouse,
            child_row: row
        },
        callback: function (r) {
            if (!r.exc && r.message) {
                frappe.msgprint(__('Stock Entry Created: <a href="/app/stock-entry/' + r.message + '" target="_blank">' + r.message + '</a>'));
            }
        }
    });
}


function calculate_cones_per_bag(frm) {
    const bags_issue = frm.doc.bags_issue;
    const lbs_issue = frm.doc.lbs_issue;

    // // Ensure both values are numbers and bags_issue is not zero
    // if (bags_issue && lbs_issue && bags_issue !== 0) {
    //     const cones = lbs_issue / bags_issue;
    //     frm.set_value('cones_per_bag', cones);
    // } else {
    //     // Set to 0 or handle as per your application's requirements
    //     frm.set_value('cones_per_bag', 0);
    // }
}

function to_child(frm) {

    const fabric_construction = frm.doc.fabric_construction;
    const panna = frm.doc.panna
    if(frm.doc.items.length > 0){
        if(fabric_construction && panna){
            frm.doc.items.forEach(row => {
                frappe.model.set_value(row.doctype, row.name, "fabric_construction", fabric_construction);
                frappe.model.set_value(row.doctype, row.name, "panna", panna);
              });
            frm.refresh_field("items");
        }else{
            frappe.msgprint(__('Please select Fabric Construction and Panna'));
        }
    }
}

function calculate_warp_weight(frm, cdt, cdn){
    let row = locals[cdt][cdn];
    const ends = row.ends;
    const no_of_width = row.no_of_width;
    const actual_yarn_count = row.actual_yarn_count;
    // const wastage_percentage = row.wastage_percentage || 0;
    if(ends && actual_yarn_count){
    const warp_wt = ends/no_of_width / 768.10 / actual_yarn_count;
    // const warp_weight = warp_wt + (warp_wt * (wastage_percentage/100));
    const warp_weight = warp_wt;
    frappe.model.set_value(cdt, cdn, 'warp_weight', warp_weight);
    }else{
        frappe.model.set_value(cdt, cdn, 'warp_weight', 0);
    }
}

function set_rate(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const source_warehouse = frm.doc.source_warehouse;
    if (row.yarn_item && source_warehouse) {
      frappe.call({
        method: 'mjfsd_v3.loom_production.events.fetch_current_rate.fetch_current_rate',
        args: {
          item_code: row.yarn_item,
          warehouse: source_warehouse
        },
        callback: (r) => {
          if (!r.exc && r.message !== undefined) {
            frappe.model.set_value(cdt, cdn, 'yarn_item_rate', r.message);
          }
        }
      });
    }
  }

  function calculate_beem_rate(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    const sizing_rate = row.sizing_rate || 0;
    const length = row.length || 0;
    const lbs = row.lbs || 0;

    frappe.model.set_value(cdt, cdn, 'sizing_amount', sizing_rate * lbs);
    const sizing_amount_by_length = row.sizing_amount / length;
    const beem_rate_plus = sizing_amount_by_length + row.beem_rate;
    frappe.model.set_value(cdt, cdn, 'beem_rate_per_meter',beem_rate_plus);


  }

function compute_yarn_values(frm, cdt, cdn) {
    // Use frappe.get_doc to get a better object reference
    let row = locals[cdt][cdn];

    let ends = row.ends || 0;
    let beem_length = row.beem_length || 0;
    let lbs = row.lbs || 0;
    let yarn_item_rate = row.yarn_item_rate || 0;
    let yarn_count = row.yarn_count || 0;

    // Prevent invalid divisions
    let actual_yarn_count = 0;
    let actual_yarn_rate = 0;

    if (lbs != 0) {
        actual_yarn_count = (ends * beem_length) / 768.10 / lbs;
    }
    if (actual_yarn_count != 0) {
        actual_yarn_rate = (yarn_item_rate / actual_yarn_count) * yarn_count;
        frappe.model.set_value(cdt, cdn, 'beem_rate', actual_yarn_rate * row.warp_weight);

    }

    // Format / rounding
    actual_yarn_count = actual_yarn_count.toFixed(2);
    actual_yarn_rate = actual_yarn_rate.toFixed(2);

    // Set back to the child row
    frappe.model.set_value(cdt, cdn, 'actual_yarn_count', actual_yarn_count);
    frappe.model.set_value(cdt, cdn, 'actual_yarn_rate', actual_yarn_rate);
}

// function calculate_yarn_wastage(frm, cdt, cdn){
//     let row = locals[cdt][cdn];
//     const lbs = row.lbs || 0;
//     const beem_rate = row.beem_rate_per_meter || 0;
//     const length = row.length || 0;
//     const yarn_rate = row.yarn_item_rate || 0;
//     const sizing_amount = row.sizing_amount || 0;
//     // const wastage_percentage = row.wastage_percentage || 0;
//     // const yarn_wastage_qty = lbs * (wastage_percentage/100);
//     const yarn_wastage_qty = lbs;
//     frappe.model.set_value(cdt, cdn, 'yarn_wastage_qty', yarn_wastage_qty);
//     const wastage_amount = (beem_rate * length) - (yarn_rate * lbs) - sizing_amount;
//     frappe.model.set_value(cdt, cdn, 'wastage_amount', wastage_amount);
// }

   function calculate_wastes(frm, cdt, cdn) {
        // Get the row using the cdt (child doctype) and cdn (child docname)
        let row = locals[cdt][cdn];

        // Retrieve the values from the row
        let yarn_item_rate = row.yarn_item_rate || 0;
        let actual_yarn_rate = row.actual_yarn_rate || 0;
        let lbs = row.lbs || 0;

        // Perform calculations for the current row
        let value_of_yarn = yarn_item_rate * lbs;
        let value_of_actual_yarn = actual_yarn_rate * lbs;
        let wastage_amount = value_of_yarn - value_of_actual_yarn;

        // Set the calculated values back to the row
        frappe.model.set_value(cdt, cdn, 'value_of_yarn', value_of_yarn);
        frappe.model.set_value(cdt, cdn, 'value_of_actual_yarn', value_of_actual_yarn);
        frappe.model.set_value(cdt, cdn, 'wastage_amount', wastage_amount);
    }

// Multi finish item / yarn mode: one Sizing Receipt per shared Sizing Beam
// (rows that carry the same Sizing Beam value go on the same receipt).
function create_receipt_for_shared_beam(frm) {
    if (frm.is_new() || frm.is_dirty()) {
        frappe.msgprint(__('Please save the Sizing Program first.'));
        return;
    }
    const open_receipt = function (beams) {
        frappe.call({
            method: "mjfsd_v3.loom_production.events.sizing_yarn_rows.make_sizing_receipt",
            args: { sizing_program: frm.doc.name, sizing_beams: JSON.stringify(beams) },
            freeze: true,
            callback: function (r) {
                if (!r.exc && r.message) {
                    frappe.model.sync(r.message);
                    frappe.set_route("Form", r.message.doctype, r.message.name);
                }
            }
        });
    };
    frappe.call({
        method: "mjfsd_v3.loom_production.events.sizing_yarn_rows.get_beam_groups",
        args: { sizing_program: frm.doc.name },
        callback: function (r) {
            const groups = (r.message || []).filter(g => flt(g.remaining) > 0.0001);
            if (!groups.length) {
                frappe.msgprint(__('All Sizing Beams of this program are already received.'));
            } else if (groups.length == 1) {
                open_receipt([groups[0].sizing_beam]);
            } else {
                // one tick per shared beam - tick several to receive them on ONE Sizing Receipt
                const d = new frappe.ui.Dialog({
                    title: __('Select Sizing Beam(s)'),
                    fields: groups.map((g, i) => ({
                        fieldname: 'beam_' + i, fieldtype: 'Check', default: 1,
                        label: g.sizing_beam + ' - ' + g.rows + ' row(s) - ' + (g.finish_items || '') + ' - balance ' + flt(g.remaining, 2) + ' m'
                    })),
                    primary_action_label: __('Create'),
                    primary_action: function (v) {
                        const picked = groups.filter((g, i) => v['beam_' + i]).map(g => g.sizing_beam);
                        if (!picked.length) { frappe.msgprint(__('Select at least one Sizing Beam.')); return; }
                        d.hide();
                        open_receipt(picked);
                    }
                });
                d.show();
            }
        }
    });
}

// ---------------------------------------------------------------------
// Yarn Details child table (multi finish item / multi yarn) - live preview
// of the same formulas the server applies on save (sizing_yarn_rows.py).
// Guarded so it registers once even if both Sizing doctype scripts load.
// ---------------------------------------------------------------------
if (!window.__sizing_yarn_rows_loaded) {
    window.__sizing_yarn_rows_loaded = true;

    // Balance Yarn = LBS Issue - returned yarn of that yarn item (returns are
    // taken off the rows of that yarn in order, same as the server).
    window.sizing_yarn_allocate_returns = function (frm) {
        const returns = {};
        (frm.doc.stock_return_item || []).forEach(x => {
            returns[x.yarn_item] = (returns[x.yarn_item] || 0) + flt(x.qty_lbs);
        });
        (frm.doc.yarn_items || []).forEach(r => {
            const ret = returns[r.yarn_item] || 0;
            const take = ret > 0 ? Math.min(ret, flt(r.lbs_issue)) : 0;
            r.balance_yarn = flt(r.lbs_issue) - take;
            returns[r.yarn_item] = ret - take;
        });
    };

    window.sizing_yarn_recalc_row = function (frm, cdt, cdn) {
        const r = locals[cdt][cdn];
        const wpct = flt(r.wastage_percent);
        const ycpm = flt(r.yarn_count) ? (flt(r.ends) / 768.1) / flt(r.yarn_count) : 0;
        const lbs = flt(r.net_meter) * ycpm;
        const wastage = lbs * wpct / 100;
        const upd = {
            cone_weight: flt(r.cones_per_bag) ? flt(r.lbs_per_bag) / flt(r.cones_per_bag) : 0,
            yarn_consumption_per_meter: ycpm,
            lbs: lbs,
            wastage: wastage,
            gross_meter: flt(r.net_meter) * (1 + wpct / 100),
            bags_issue: (flt(r.lbs_issue) + wastage) / (flt(r.lbs_per_bag) || 100)
        };
        if (!r.sizing_program_row) {
            upd.balance_net_meter = flt(r.net_meter);
        }
        Object.keys(upd).forEach(k => { r[k] = upd[k]; });
        window.sizing_yarn_allocate_returns(frm);
        frm.refresh_field("yarn_items");
    };

    const recalc_fields = ["yarn_count", "cones_per_bag", "lbs_per_bag", "net_meter", "lbs_issue", "ends", "wastage_percent"];
    const handlers = {
        form_render: function (frm, cdt, cdn) { window.sizing_yarn_recalc_row(frm, cdt, cdn); },
        yarn_items_add: function (frm, cdt, cdn) {
            const r = locals[cdt][cdn];
            if (!flt(r.lbs_per_bag)) { r.lbs_per_bag = 100; }
            if (frm.doc.warp_wastage_percent && !flt(r.wastage_percent)) { r.wastage_percent = frm.doc.warp_wastage_percent; }
            frm.refresh_field("yarn_items");
        }
    };
    recalc_fields.forEach(f => { handlers[f] = function (frm, cdt, cdn) { window.sizing_yarn_recalc_row(frm, cdt, cdn); }; });
    frappe.ui.form.on("Sizing Program Yarn", handlers);
}


// Add Yarn Details rows from any number of Weaving Contracts (Pile and
// Ground yarns that still need a Sizing Program).
function get_items_from_weaving_contracts(frm) {
    new frappe.ui.form.MultiSelectDialog({
        doctype: "Weaving Contract",
        target: frm,
        setters: { weaver: null, construction: null },
        add_filters_group: 1,
        get_query() {
            return { filters: { docstatus: 1, custom_status: "Open" } };
        },
        action(selections) {
            if (!selections || !selections.length) { return; }
            frappe.call({
                method: "emadi_v3.emadi.events.create_sizing_program_from_weaving_contract.get_yarn_rows_for_contracts",
                args: { weaving_contracts: selections },
                freeze: true,
                callback: function (r) {
                    const rows = r.message || [];
                    let added = 0;
                    rows.forEach(function (row) {
                        const dup = (frm.doc.yarn_items || []).some(x =>
                            x.weaving_contract === row.weaving_contract && x.yarn_item === row.yarn_item && x.beam_item === row.beam_item);
                        if (dup) { return; }
                        const child = frm.add_child("yarn_items");
                        ["weaving_contract", "finish_item", "yarn_item", "beam_item", "lbs_per_bag", "lbs_issue"].forEach(f => {
                            child[f] = row[f];
                        });
                        if (frm.doc.warp_wastage_percent) { child.wastage_percent = frm.doc.warp_wastage_percent; }
                        added++;
                    });
                    if (!frm.doc.weaving_contract && selections.length) { frm.set_value("weaving_contract", selections[0]); }
                    if (!frm.doc.item_returnable && rows.length && rows[0].beam_item) { frm.set_value("item_returnable", rows[0].beam_item); }
                    frm.refresh_field("yarn_items");
                    cur_dialog && cur_dialog.hide();
                    frappe.show_alert({ message: __("{0} row(s) added", [added]), indicator: "green" });
                }
            });
        }
    });
}
