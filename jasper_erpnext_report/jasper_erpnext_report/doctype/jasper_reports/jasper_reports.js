frappe.provide("jasper");

frappe.ui.form.on("Jasper Parameter", "is_copy", function(frm, doctype, name){
	var row = locals[doctype][name];
	switch(row.is_copy){
		case "Is for where clause":
			row.param_expression = "In";
			refresh_field("param_expression", name,"jasper_parameters");
			row.jasper_param_action = "Automatic";
			refresh_field("jasper_param_action",name,"jasper_parameters");
			break;
		case "Is for page number":
		case "Is for copies":
		case "Is for server hook":
			row.param_expression = "";
			row.jasper_param_action = "Automatic";
			refresh_field("param_expression", name,"jasper_parameters");
			refresh_field("jasper_param_action",name,"jasper_parameters");
			break;
		default:
			row.param_expression = "";
			row.jasper_param_action = "Ask";
			refresh_field("jasper_param_action", name,"jasper_parameters");
			refresh_field("param_expression", name,"jasper_parameters");
	}
})

frappe.ui.form.on("Jasper Parameter", "param_expression", function(frm, doctype, name){
	var row = locals[doctype][name];
	if (row.is_copy !== "Is for where clause"){
		row.param_expression = "";
		refresh_field("param_expression", name,"jasper_parameters");
	}else if(row.param_expression == ""){
		row.param_expression = "In";
		refresh_field("param_expression", name,"jasper_parameters");
	}
})

frappe.ui.form.on("Jasper Parameter", "jasper_param_action", function(frm, doctype, name){
	var row = locals[doctype][name];
	if (row.is_copy === "Is for server hook" || row.is_copy === "Is for page number" || row.is_copy === "Is for copies"){
		row.jasper_param_action = "Automatic";
	}else if (row.is_copy === "Other"){
		row.jasper_param_action = "Ask";
	}else if (row.is_copy === "Is for where clause" && frm.doc.jasper_report_type !== "General"){
		row.jasper_param_action = "Automatic";
	}

	refresh_field("jasper_param_action", name,"jasper_parameters");
})

cur_frm.cscript.refresh = function(doc){
    var cs = cur_frm.cscript;
    
    cs.show_fields(doc);
    
    var query = doc.query != undefined? doc.query:""
    var code = '<div class="panel panel-default">'
                 + '<div class="panel-heading">'
                    + '<h3 class="panel-title">SQL</h3>'
                 + '</div>'
                 + '<div class="panel-body">'
                        + '<pre class="bs-callout-bg bs-callout-warning-bg">' + query + '</pre>'
                 + '</div>'
             + '</div>'

    cur_frm.fields_dict.query_html.$wrapper.html(code)
    if(doc.__islocal !== 1){
        cs.update_upload(doc);
	}
	var locals = ["Ask"];
	locals.push.apply(locals, jasper.make_country_list());
	if (doc.jasper_report_origin === "LocalServer"){
		cur_frm.set_df_property("jasper_locale", "options", locals);
		unhide_field(["jasper_locale"]);
    }else{
		hide_field(["jasper_locale"]);
    }

}

cur_frm.cscript["jasper_locale"] = function(doc){
	var page;
	if (doc.jasper_report_type === "Form" || doc.jasper_report_type === "List"){
		page = doc.jasper_report_type  + "/" + doc.jasper_doctype;
	}
	var robj = jasper.get_jasperdoc_from_name(doc.name, page);
	if (robj){
		robj.locale = doc.jasper_locale;
	}
}

cur_frm.cscript["jasper_report_origin"] = function(doc, dt, dn){
    var origin = doc.jasper_report_origin;
    if (origin === "JasperServer"){
        hide_field(["jasper_upload_jrxml_file", "jasper_upload_btn", "jasper_virtualizer", "jasper_all_sites_report", "jasper_locale"]);
        if (doc.__islocal){
            cur_frm.set_value("jasper_report_path", "");
        }
        unhide_field(["jasper_report_path"]);
    }else if(doc.__islocal){//never saved
        hide_field(["jasper_upload_jrxml_file", "jasper_upload_btn", "jasper_virtualizer", "jasper_report_path"]);
        cur_frm.set_value("jasper_report_path", "/");
    }else{
    	var locals = ["Ask"];
		locals.push.apply(locals, jasper.make_country_list());
		cur_frm.set_df_property("jasper_locale", "options", locals);
        unhide_field(["jasper_upload_jrxml_file", "jasper_upload_btn", "jasper_virtualizer", "jasper_all_sites_report", "jasper_locale"]);
        hide_field(["jasper_report_path"]);
    }
}

cur_frm.cscript.show_fields = function(doc){
    var origin = doc.jasper_report_origin;
    if (origin === "JasperServer"){
        hide_field(["jasper_upload_jrxml_file", "jasper_upload_btn", "jasper_virtualizer", "jasper_all_sites_report"]);
    }else if(doc.__islocal){//never saved
        hide_field(["jasper_upload_jrxml_file", "jasper_upload_btn", "jasper_virtualizer", "jasper_report_path"]);
        cur_frm.set_value("jasper_report_path", "/");
    }else{
        hide_field(["jasper_report_path"]);
    }
    
};

$(document).on("save", function(ev, doc){
	var cs = cur_frm.cscript;
	if(doc.__islocal === 1){
		if (doc.jasper_report_origin === "LocalServer")
			unhide_field(["jasper_upload_jrxml_file", "jasper_upload_btn", "jasper_virtualizer", "report_images:", "jasper_all_sites_report"]);
		else
			unhide_field(["jasper_all_sites_report"]);
    }
});

cur_frm.cscript.onload = function(doc){
    if(doc.__islocal !==1){
	    var cs = cur_frm.cscript;
	    var opts = cur_frm.get_field("jasper_upload_jrxml_file");
	    opts["docname"] = cur_frm.docname;
	    cs.upload = new jasper.dialog_upload_tree(opts);
	}
}

cur_frm.cscript.jasper_upload_btn = function(doc){
	var cs = cur_frm.cscript;
	console.log("upload btn ", doc, cs);
    cs.upload.show();
}

cur_frm.cscript.update_upload = function(doc){
	var cs = cur_frm.cscript;

	function children(name, msg){
		var found = [];
		for (var i=0; i<msg.length;i++){
			if(msg[i].parent_report == name){
				found.push(i);
			}
		}
		return found;
	};

	frappe.call({
	       method:  "jasper_erpnext_report.jasper_erpnext_report.doctype.jasper_reports.jasper_reports.get_attachments",
	       args: {dn: doc.name},
	       callback: function(response_data){
	       			var msg = response_data.message;
	       			cs.upload.clear_input();
	       			if (!msg)
	       				return;
	       			var roots = children("root", msg);
	       			for (var j=0; j<roots.length;j++){
	       				var pos = roots[j];
	       				cs.upload.set_input(msg[pos].name, msg[pos].file_name, msg[pos].file_url, msg[pos].parent_report);
	       				var childrens = children(msg[pos].name, msg);
	       				for (var i=0; i<childrens.length; i++){
	       					var cpos = childrens[i];
	       					cs.upload.set_input(msg[cpos].name, msg[cpos].file_name, msg[cpos].file_url, msg[pos].name);
	       				}
	       			}
	       }
     });

};


