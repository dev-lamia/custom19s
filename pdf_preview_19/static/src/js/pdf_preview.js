/** @odoo-module **/

import { createFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const fileViewer = createFileViewer();

function getReportDocIds(action) {
    const context = action.context || {};

    if (Array.isArray(context.active_ids) && context.active_ids.length) {
        return context.active_ids.join(",");
    }
    if (context.active_id) {
        return String(context.active_id);
    }
    if (Array.isArray(action.res_ids) && action.res_ids.length) {
        return action.res_ids.join(",");
    }
    if (action.res_id) {
        return String(action.res_id);
    }
    return "";
}

function buildPdfFile(action) {
    const docids = getReportDocIds(action);
    const reportName = action.report_name || "";

    const baseUrl =
        `/pdf_preview_19/report/download` +
        `?report_name=${encodeURIComponent(reportName)}` +
        `&docids=${encodeURIComponent(docids)}`;

    // PDF.js needs a direct PDF response as the file source.
    // Use our controller instead of /report/pdf so preview and download use the
    // same render path and avoid blank "0 of 0" previews in Odoo 19.
    const previewUrl = `${baseUrl}&inline=1&_=${Date.now()}`;
    const downloadUrl = `${baseUrl}&download=1`;

    return {
        id: `report:${reportName}:${docids || "no-docids"}:${Date.now()}`,
        name: `${action.name || _t("Report")}.pdf`,
        mimetype: "application/pdf",
        isPdf: true,
        isViewable: true,
        defaultSource: `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(previewUrl)}#pagemode=none`,
        downloadUrl: downloadUrl,
    };
}

async function openPdfPreview(action, options, env) {
    env.services.ui?.block();
    try {
        const pdfFile = buildPdfFile(action);
        fileViewer.open(pdfFile);
    } finally {
        env.services.ui?.unblock();
    }

    const onClose = options?.onClose;
    if (action.close_on_report_download) {
        return env.services.action.doAction({ type: "ir.actions.act_window_close" }, { onClose });
    }
    onClose?.();
    return true;
}

registry.category("ir.actions.report handlers").add("tam_pdf_preview_handler", async (action, options, env) => {
    if (action.report_type !== "qweb-pdf") {
        return false;
    }
    await openPdfPreview(action, options, env);
    return true;
});
