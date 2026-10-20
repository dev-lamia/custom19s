/** @odoo-module **/

import { FileViewer } from "@web/core/file_viewer/file_viewer";
import { createFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { _t } from "@web/core/l10n/translation";
import { downloadFile } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";


const fileViewer = createFileViewer();

/* =========================================================
 * Normal QWeb PDF reports
 * ========================================================= */

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
        "/tam_pdf_preview_19/report/download" +
        `?report_name=${encodeURIComponent(reportName)}` +
        `&docids=${encodeURIComponent(docids)}`;

    const previewUrl =
        `${baseUrl}&inline=1&_=${Date.now()}`;

    const downloadUrl =
        `${baseUrl}&download=1`;

    return {
        id:
            `report:${reportName}:` +
            `${docids || "no-docids"}:${Date.now()}`,

        name:
            `${action.name || _t("Report")}.pdf`,

        mimetype: "application/pdf",
        isPdf: true,
        isViewable: true,

        defaultSource:
            "/web/static/lib/pdfjs/web/viewer.html?file=" +
            encodeURIComponent(previewUrl) +
            "#pagemode=none",

        downloadUrl,
    };
}

async function openPdfPreview(action, options, env) {
    env.services.ui?.block();

    try {
        fileViewer.open(
            buildPdfFile(action)
        );
    } finally {
        env.services.ui?.unblock();
    }

    const onClose = options?.onClose;

    if (action.close_on_report_download) {
        return env.services.action.doAction(
            {
                type: "ir.actions.act_window_close",
            },
            {
                onClose,
            }
        );
    }

    onClose?.();

    return true;
}

registry
    .category("ir.actions.report handlers")
    .add(
        "tam_pdf_preview_handler",
        async (action, options, env) => {
            if (action.report_type !== "qweb-pdf") {
                return false;
            }

            await openPdfPreview(
                action,
                options,
                env
            );

            return true;
        }
    );


/* =========================================================
 * Odoo 19 Accounting Reports
 * Partner Ledger / Aged Receivable / Aged Payable / etc.
 * ========================================================= */

const actionHandlers =
    registry.category("action_handlers");

const originalAccountReportDownload =
    actionHandlers.get(
        "ir_actions_account_report_download"
    );

function getFilename(disposition) {
    if (!disposition) {
        return _t("Accounting Report.pdf");
    }

    const utf8Match =
        disposition.match(
            /filename\*=UTF-8''([^;]+)/i
        );

    if (utf8Match) {
        try {
            return decodeURIComponent(
                utf8Match[1]
            );
        } catch {
            return utf8Match[1];
        }
    }

    const filenameMatch =
        disposition.match(
            /filename="?([^";]+)"?/i
        );

    if (filenameMatch) {
        return filenameMatch[1];
    }

    return _t("Accounting Report.pdf");
}


function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = () => {
            resolve(reader.result);
        };

        reader.onerror = () => {
            reject(reader.error);
        };

        reader.readAsDataURL(blob);
    });
}

async function accountingReportPreview({
    env,
    action,
}) {
    const data = action.data || {};

    /*
     * Only intercept PDF.
     *
     * XLSX and every other accounting export
     * continue through Odoo's original handler.
     */
    if (
        data.file_generator !==
        "export_to_pdf"
    ) {
        return originalAccountReportDownload({
            env,
            action,
        });
    }

    env.services.ui.block();

    try {
        const formData = new FormData();

        for (
            const [key, value]
            of Object.entries(data)
        ) {
            if (
                value !== undefined &&
                value !== null
            ) {
                formData.append(
                    key,
                    typeof value === "string"
                        ? value
                        : JSON.stringify(value)
                );
            }
        }

        /*
         * This is the SAME endpoint used by
         * Odoo's standard Accounting download.
         *
         * Difference:
         * Odoo downloads the response.
         * We keep it as a Blob and preview it.
         */
        const response = await fetch(
            "/account_reports",
            {
                method: "POST",
                body: formData,
                credentials: "same-origin",
            }
        );

        if (!response.ok) {
            const errorText =
                await response.text();

            throw new Error(
                errorText ||
                _t(
                    "Could not generate accounting PDF."
                )
            );
        }

        const blob = await response.blob();

        const previewUrl =
            URL.createObjectURL(blob);

        const downloadUrl =
            await blobToDataUrl(blob);

        const filename = getFilename(
            response.headers.get(
                "Content-Disposition"
            )
        );

        fileViewer.open({
            id: `account-report:${Date.now()}`,
            name: filename,
            mimetype: "application/pdf",
            isPdf: true,
            isViewable: true,

            defaultSource:
                "/web/static/lib/pdfjs/web/viewer.html?file=" +
                encodeURIComponent(previewUrl) +
                "#pagemode=none",

            downloadUrl,
        });

        return true;
    } finally {
        env.services.ui.unblock();
    }
}

/*
 * Replace only Odoo's Accounting download handler.
 */
actionHandlers.add(
    "ir_actions_account_report_download",
    accountingReportPreview,
    {
        force: true,
    }
);


patch(FileViewer.prototype, {
    onClickDownload() {
        const file = this.state.file;

        // Only our Accounting report preview
        if (
            file?.id &&
            file.id.startsWith("account-report:")
        ) {
            return downloadFile(
                file.downloadUrl,
                file.name,
                file.mimetype
            );
        }

        // Keep normal Odoo behaviour unchanged
        return super.onClickDownload(...arguments);
    },
});