# -*- coding: utf-8 -*-
import re
from odoo import http
from odoo.http import request, content_disposition


class TamPdfPreviewController(http.Controller):

    def _sanitize_filename(self, name):
        name = (name or "Report").strip()
        name = re.sub(r'[\\/:*?"<>|]+', "_", name)
        return name

    def _get_report_filename(self, report, records):
        filename = report.name or "Report"

        if len(records) == 1:
            record = records[0]

            # Example: "Request for Quotation TT/04/26-R0025"
            if getattr(record, "name", False):
                filename = f"{report.name or 'Report'} {record.name}"
            else:
                filename = f"{report.name or 'Report'} {record.display_name or ''}".strip()

        return self._sanitize_filename(filename)

    @http.route(
        "/tam_pdf_preview_19/report/download",
        type="http",
        auth="user",
        methods=["GET", "POST"],
        csrf=False,
    )
    def tam_report_download(self, report_name=None, docids=None, **kwargs):
        if not report_name:
            return request.not_found()

        report = request.env["ir.actions.report"].sudo()._get_report_from_name(report_name)
        if not report:
            return request.not_found()

        ids = [int(x) for x in (docids or "").split(",") if x]
        records = request.env[report.model].sudo().browse(ids).exists() if ids else request.env[report.model]

        pdf_content, _content_type = report.sudo()._render_qweb_pdf(report_name, ids)

        filename = self._get_report_filename(report, records)
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        disposition = content_disposition(filename)
        if kwargs.get("inline"):
            # PDF.js preview needs an inline PDF response. Keep normal attachment
            # disposition for the Download button.
            disposition = disposition.replace("attachment;", "inline;", 1)

        headers = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", str(len(pdf_content))),
            ("Content-Disposition", disposition),
            ("Cache-Control", "no-store"),
        ]
        return request.make_response(pdf_content, headers=headers)