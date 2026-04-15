/** @odoo-module **/

import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { getReportUrl } from "@web/webclient/actions/reports/utils";

registry.category("ir.actions.report handlers").add("xlsx_handler", async (action, options, env) => {
    if (action.report_type !== "xlsx") {
        return false;
    }

    const downloadContext = {
        ...(user.context || {}),
        ...(action.context || {}),
    };

    env.services.ui.block();
    try {
        await download({
            url: "/report/download",
            data: {
                data: JSON.stringify([getReportUrl(action, "xlsx", downloadContext), action.report_type]),
                context: JSON.stringify(downloadContext),
            },
        });
    } finally {
        env.services.ui.unblock();
    }

    const { onClose } = options || {};
    if (action.close_on_report_download) {
        return env.services.action.doAction({ type: "ir.actions.act_window_close" }, { onClose });
    }
    if (onClose) {
        onClose();
    }
    return true;
});
