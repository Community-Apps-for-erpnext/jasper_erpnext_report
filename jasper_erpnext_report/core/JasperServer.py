from __future__ import unicode_literals
__author__ = 'luissaguas'

from jasper_erpnext_report import jasperserverlib

try:
	import jasperserver.core as jasper
	from jasperserver.core.reportingService import ReportingService
	from jasperserver.core.ReportExecutionRequest import ReportExecutionRequest
	from jasperserver.resource_details import Details
	from jasperserver.repo_search import Search
	from jasperserver.resource_download import DownloadBinary
	from jasperserver.core.exceptions import Unauthorized, NotFound
	jasperserverlib = True
except:
	jasperserverlib = False
	pass

from frappe.utils import pprint_dict


from frappe import _
import frappe

import logging, json
from io import BytesIO
import inspect

from jasper_erpnext_report.utils.file import JasperXmlReport
import jasper_erpnext_report.utils.utils as utils

import JasperBase as Jb

_logger = logging.getLogger(frappe.__name__)



def _jasperserver(fn):
	"""
	decorator for jasperserver functions
	"""
	def innerfn(*args, **kwargs):
		newargs = {}
		me = args[0]
		try:
			fnargs, varargs, varkw, defaults = inspect.getargspec(fn)
			for a in fnargs:
				if a in kwargs:
					newargs[a] = kwargs.get(a)
			fn_result = fn(*args, **newargs)
			me.update()
			return fn_result

		except Unauthorized as e:
			me._timeout()
			fn_result = fn(*args, **newargs)
			me.update()
			utils.jaspersession_set_value("last_jasper_session_timeout", frappe.utils.now())
			return fn_result
		except Exception as e:
			print "problems!!!! {}\n".format(e)

	return innerfn



class JasperServer(Jb.JasperBase):
	def __init__(self, doc={}):
		self.is_login = False
		self.session = frappe.local.jasper_session = frappe._dict({'session': frappe._dict({})})
		super(JasperServer, self).__init__(doc)
		self.check_session()

	def check_session(self):
		if not jasperserverlib:
			return
		if self.data['data'] and self.data['data'].get('cookie', None):
			self.resume_connection()
		else:
			self.login()

	def login(self):
		self.connect()
		if not self.in_jasper_session() and self.user == "Administrator":
			self.send_email(_("Jasper Server is down. Please check Jasper Server or change to local report only (you will need pyhton module pyjnius)."), _("Jasper Server, login error"))

	def in_jasper_session(self):
		try:
			session = bool(self.session.session.getSessionId())
		except:
			session = False

		return session

	def resume_connection(self):
		self.session = frappe.local.jasper_session = jasper.session(self.doc.get("jasper_server_url"), resume=True)
		if self.session:
			self.session.resume(self.data['data']['cookie'])
			self.is_login = True


	def connect(self):
		if self.user=="Guest":
			return

		try:
			if not self.doc:
				self.get_jasperconfig_from_db()

			self.session = frappe.local.jasper_session = jasper.session(self.doc.get("jasper_server_url"), self.doc.get("jasper_username"), self.doc.get("jasper_server_password"))

			self.update_cookie()
			self.is_login = True

		except Exception as e:
			self.is_login = False
			cur_user = "no_reply@gmail.com" if self.user == "Administrator" else self.user
			self.send_email(_("Jasper Server, login error. Reason: {}".format(e)), _("Jasper Server, login error"), user=cur_user)

	def logout(self):
		if self.session:
			self.session.logout()

	def _timeout(self):
		try:
			self.logout()
			self.login()
		except:
			_logger.info("_login: JasperServerSession Error while timeout and login")

		_logger.info("_timeout JasperServerSession login successfuly {0}".format(self.doc))

	def update_cookie(self):
		self.data['data']['cookie'] = frappe.local.jasper_session.session.getSessionId() if frappe.local.jasper_session.session else {}
		self.update(force_cache=False, force_db=True)

	def get_server_info(self):
		details = Details(self.session)
		serverInfo = details.serverInfo()
		return serverInfo

	def get_jrxml_from_server(self, uri):
		f = DownloadBinary(self.session, uri)
		f.downloadBinary(file=True)
		return f.getFileContent()

	def import_all_jasper_reports(self, data, force=True):
		if self.is_login:
			reports = self.get_reports_list_from_server(force=force)
			docs = utils.do_doctype_from_jasper(data, reports, force=True)
			utils.import_all_jasper_remote_reports(docs, force)

	@_jasperserver
	def get_reports_list_from_server(self, force=False):
		ret = {}
		s = Search(self.session)
		result = s.search(path=self.doc.get("jasper_report_root_path"), type="reportUnit")
		reports = result.getDescriptor().json_descriptor()
		for report in reports:
			ics = []
			d = Details(self.session, report.get("uri"))
			r_details = d.details(expanded=False)
			r_param = r_details.getDescriptor().json_descriptor()
			uri = r_param[0].get('jrxml').get('jrxmlFileReference').get('uri')
			file_content = self.get_jrxml_from_server(uri)
			xmldoc = JasperXmlReport(BytesIO(file_content))
			params = xmldoc.get_params()
			query = self.get_query_jrxmlFile_from_server(file_content)
			for param in params:
				pname = param.xpath('./@name')
				pclass = param.xpath('./@class')
				ptype = pclass[0].split(".")
				c = len(ptype) - 1
				ics.append({"label":pname[0], "type":ptype[c].lower()})
			updateDate = report.get("updateDate", None)
			if not updateDate:
				updateDate = report.get("creationDate", frappe.utils.now())

			ret[report.get("label")] = {"uri":report.get("uri"), "inputControls": ics, "updateDate": updateDate, "queryString": query}

		return ret

	def run_remote_report_async(self, path, doc, data={}, params=[], pformat="pdf", ncopies=1):
		resps = []
		data = self.run_report_async(doc, data=data, params=params)
		"""
		Run one report at a time for Form type report and many ids
		"""
		if data.get('jasper_report_type', None) == "Form" or doc.jasper_report_type == "Form":
			ids = data.get('ids')
			for id in ids:
				data['ids'] = [id]
				resps.append(self._run_report_async(path, doc, data=data, params=params, pformat=pformat, ncopies=ncopies))
		else:
			resps.append(self._run_report_async(path, doc, data=data, params=params, pformat=pformat, ncopies=ncopies))
		cresp = self.prepareCollectResponse(resps)
		cresp["origin"] = "server"
		return [cresp]

	#run reports with http POST and run async and sync
	def _run_report_async(self, path, doc, data={}, params=[], pformat="pdf", ncopies=1):
		pram, pram_server, copies = self.do_params(data, params, pformat)
		pram_copy_index = copies.get("pram_copy_index", -1)
		pram_copy_page_index = copies.get("pram_copy_page_index", -1)
		resp = []
		pram.extend(self.get_param_hook(doc, data, pram_server))

		copies = [_("Original"), _("Duplicated"), _("Triplicate")]
		#copies = ["Original", "Duplicated", "Triplicate"]

		for m in range(ncopies):
			if pram_copy_index >= 0:
				values = pram[pram_copy_index].get("value","")[0]
				if not values:
					pram[pram_copy_index]['value'] = [copies[m]]
				else:
					pram[pram_copy_index]['value'] = frappe.utils.strip(values[m], ' \t\n\r')

			if pram_copy_page_index >= 0:
				pram[pram_copy_page_index]['value'] = [str(m) + _(" of ") + str(ncopies)]
			result = self.run_async(path, pram, data.get("report_name"), pformat=pformat)
			if result:
				requestId = result.get('requestId')
				reqDbObj = {"data":{"result": result, "report_name": data.get("report_name"), "last_updated": frappe.utils.now(),'session_expiry': utils.get_expiry_period()}}
				self.insert_jasper_reqid_record(requestId, reqDbObj)
				resp.append({"requestId":requestId, "report_name": data.get("report_name"), "status": result.get('status')})
			else:
				frappe.msgprint(_("There was an error in report request."),raise_exception=True)
		#TODO get reqId for check report state
		return resp

	@_jasperserver
	def run_async(self, path, pram, report_name, pformat="pdf"):
		rs = ReportingService(self.session)
		rr = ReportExecutionRequest()
		rr.setReportUnitUri(path)
		rr.setOutputFormat(pformat)
		rr.setParameters(pram)
		rr.setAsync(True)
		if pformat == "html":
			rr.setAttachmentsPrefix("./images/")
		try:
			req = rs.newReportExecutionRequest(rr)
			res = req.run().getResult("content")
			res = json.loads(res)
			resp = self.prepareResponse(res, res.get("requestId"))
			resp["status"] = res.get("status")
			return resp
		except Exception as e:
			if isinstance(e, Unauthorized):

				raise Unauthorized
			else:
				frappe.throw(_("Error in report %s, server error is: %s." % (self.doc.jasper_report_name, e)))

	@_jasperserver
	def polling(self, reqId):
		res = []
		try:
			rs = ReportingService(self.session)
			rexecreq = rs.reportExecutionRequest(reqId)
			status = rexecreq.status().content
			status = json.loads(status)
			if status.get("value") == "ready":
				detail = self.reportExecDetail(rexecreq)
				res = self.prepareResponse(detail, reqId)
				if res.get('status', "") == "not ready":
					res = self.prepareResponse({}, reqId)
				else:
					res["status"] = "ready"
			elif status.get("value") == "failed":
				frappe.throw(_("Error in report %s, server error is: %s." % (self.doc.jasper_report_name, status['errorDescriptor'].get('message'))))
			else:
				res = self.prepareResponse({}, reqId)
		except NotFound:
			frappe.throw(_("Not Found."))
		return res

	#rexecreq : ReportExecutionRequestBuilder instance
	#check if the report is ready and get the expids for ready reports
	def reportExecDetail(self, rexecreq):
		return rexecreq.executionDetails()

	#rs: ReportingService instance
	#get the report with reqId for the given expId
	@_jasperserver
	def getReport(self, reqId, expId):
		try:
			rs = ReportingService(self.session)
			rexecreq = rs.reportExecutionRequest(reqId, expId)
			report = rexecreq.export().outputResource().getResult("content")
			return report
		except NotFound:
			frappe.throw(_("Not Found!!!"))

	def getAttachment(self, reqId, expId, attachmentId):
		try:
			rs = ReportingService(self.session)
			rexecreq = rs.reportExecutionRequest(reqId, expId)
			content = rexecreq.export().attachment(attachmentId)
			return content
		except NotFound:
			frappe.throw(_("Not Found!!!"))

	def send_email(self, body, subject, user="no_reply@gmail.com"):
		import frappe.utils.email_lib
		try:
			frappe.utils.email_lib.sendmail_to_system_managers(subject, body)
		except Exception as e:
			_logger.info(_("Jasper Server, email error: {}".format(e)))