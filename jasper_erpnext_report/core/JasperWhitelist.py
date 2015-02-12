from __future__ import unicode_literals
__author__ = 'luissaguas'
from frappe import _
import frappe
import json
from urllib2 import unquote
import logging

from frappe.core.doctype.communication.communication import make

#import jasper_erpnext_report.utils.utils as utils
import JasperRoot as Jr
from jasper_erpnext_report import jasper_session_obj
from jasper_erpnext_report.utils.jasper_email import sendmail

_logger = logging.getLogger(frappe.__name__)


def boot_session(bootinfo):
	#bootinfo['jasper_server_info'] = get_server_info()
	bootinfo['jasper_reports_list'] = get_reports_list_for_all()


@frappe.whitelist()
def get_reports_list_for_all():
	jsr = jasper_session_obj or Jr.JasperRoot()
	return jsr.get_reports_list_for_all()

@frappe.whitelist()
def get_reports_list(doctype, docnames):
	jsr = jasper_session_obj or Jr.JasperRoot()
	return jsr.get_reports_list(doctype, docnames)

@frappe.whitelist()
def report_polling(data):
	jsr = jasper_session_obj or Jr.JasperRoot()
	return jsr.report_polling(data)

@frappe.whitelist()
def get_report(data):
	#print "data get_reportssss {}".format(unquote(data))
	if not data:
		frappe.throw(_("No data for this Report!!!"))
	if isinstance(data, basestring):
		data = json.loads(unquote(data))
	_get_report(data)

def _get_report(data, merge_all=True, pages=None, email=False):
	jsr = jasper_session_obj or Jr.JasperRoot()
	fileName, content, pformat = jsr.get_report_server(data)
	file_name, output = jsr.make_pdf(fileName, content, pformat, merge_all, pages)
	if not email:
		jsr.prepare_file_to_client(file_name, output)
		return

	return file_name, output

@frappe.whitelist()
def run_report(data, docdata=None, rtype="Form"):
	from frappe.utils import pprint_dict
	if not data:
		frappe.throw("No data for this Report!!!")
	if isinstance(data, basestring):
		data = json.loads(data)
	jsr = jasper_session_obj or Jr.JasperRoot()
	print "params in run_report 2 {}".format(pprint_dict(data))
	return jsr.run_report(data, docdata=docdata, rtype=rtype)

@frappe.whitelist()
def get_server_info():
	jsr = jasper_session_obj or Jr.JasperRoot()
	return jsr._get_server_info()

@frappe.whitelist()
def jasper_server_login():
	jsr = jasper_session_obj or Jr.JasperRoot()
	return jsr.login()

@frappe.whitelist()
def get_doc(doctype, docname):
	import jasper_erpnext_report.utils.utils as utils
	data = {}
	doc = frappe.get_doc(doctype, docname)
	if utils.check_jasper_perm(doc.get("jasper_roles", None)):
		data = {"data": doc}
	frappe.local.response.update(data)


@frappe.whitelist()
def jasper_make(doctype=None, name=None, content=None, subject=None, sent_or_received = "Sent",
	sender=None, recipients=None, communication_medium="Email", send_email=False,
	print_html=None, print_format=None, attachments='[]', send_me_a_copy=False, set_lead=True, date=None,
	jasper_doc=None, docdata=None, rtype="Form"):
	#jasper_polling_time
	jasper_polling_time = frappe.db.get_value('JasperServerConfig', fieldname="jasper_polling_time")
	#thread.start_new_thread(run_report, (jasper_doc, docdata, rtype, ) )
	data = json.loads(jasper_doc)
	result = run_report(data, docdata, rtype)
	print "doctype {} name {} jasper_polling_time {} jasper_doc {} ret {}".format(doctype, name, jasper_polling_time, jasper_doc, result)
	if result[0].get("status") != "ready":
		import time
		from frappe.utils import cint
		poll_data = prepare_polling(result)
		result = report_polling(poll_data)
		limit = 0
		while result[0].get("status") != "ready" and limit <= 10:
			print "not ready {}".format(result)
			#s.enter(jasper_polling_time/1000, 1, report_polling, (s,))
			time.sleep(cint(jasper_polling_time)/1000)
			result = report_polling(poll_data)
			limit += 1
		#s.run()
		print "ready {}".format(result)
	#we have to remove the original and send only duplicate
	if result[0].get("status") == "ready":
		file_name, output = _get_report(result[0], merge_all=True, pages=None, email=True)
	else:
		print "not sent by email... {}".format(result)
		return

	#attach = jasper_make_attach(data, file_name, output, attachments, result)

	make(doctype=doctype, name=name, content=content, subject=subject, sent_or_received=sent_or_received,
		sender=sender, recipients=recipients, communication_medium=communication_medium, send_email=False,
		print_html=print_html, print_format=print_format, attachments=attachments, send_me_a_copy=send_me_a_copy, set_lead=set_lead,
		date=date)

	sendmail(data, file_name, output, result[0].get("requestId"), doctype=doctype, name=name, content=content, subject=subject, sent_or_received=sent_or_received,
		sender=sender, recipients=recipients, print_html=print_html, print_format=print_format, attachments=attachments,
		send_me_a_copy=send_me_a_copy)

"""
def jasper_make_attach(data, file_name, output, attachments, result):

	from frappe.utils.file_manager import get_site_path
	path_join = os.path.join
	#rdoc = frappe.get_doc(data.get("doctype"), data.get('report_name'))
	#for_all_sites = rdoc.jasper_all_sites_report
	#jasper_path = get_jasper_path(for_all_sites)
	public = get_site_path("public")
	jasper_path_intern = path_join("jasper_sent_email", result[0].get("requestId"))
	outputPath = path_join(public, jasper_path_intern)
	frappe.create_folder(outputPath)
	file_path = path_join(outputPath, file_name)
	file_path_intern = path_join(jasper_path_intern, file_name)
	write_StringIO_to_file(file_path, output)

	attach = json.loads(attachments)
	attach.append(file_path_intern)
	print "sent by email 2... {} attach {}".format(file_path_intern, attach)

	return json.dumps(attach)
"""

def prepare_polling(data):
	reqids = []
	for d in data:
		reqids.append(d.get("requestId"))
	poll_data = {"reqIds": reqids, "reqtime": d.get("reqtime"), "pformat": d.get("pformat"), "origin": d.get("origin")}
	return poll_data




