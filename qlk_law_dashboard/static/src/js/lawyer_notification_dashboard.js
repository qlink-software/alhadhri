/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

const Dashboard = registry.category("actions").get("qlk.dashboard");

patch(Dashboard.prototype, {
    async openLawyerNotification(item) {
        if (!item?.id) {
            return;
        }
        const action = await this.orm.call(
            "qlk.lawyer.notification",
            "action_open_target",
            [[item.id]]
        );
        if (action) {
            await this.action.doAction(action);
        }
        await this._fetchData();
    },
});
