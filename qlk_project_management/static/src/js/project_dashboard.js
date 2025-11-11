/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class ProjectDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
        });

        onWillStart(async () => {
            try {
                const payload = await this.orm.call("qlk.project.dashboard", "get_dashboard_data", []);
                this.state.data = payload;
            } catch (error) {
                console.error("Failed to load project dashboard", error);
                this.notification.add(_t("Failed to load the project dashboard"), {
                    type: "danger",
                });
                throw error;
            } finally {
                this.state.loading = false;
            }
        });
    }

    get palette() {
        return this.state.data?.palette || {};
    }

    get totals() {
        return this.state.data?.totals || {
            total_projects: 0,
            with_case: 0,
            hours_total: 0,
            tasks_total: 0,
            department_counts: [],
        };
    }

    get departmentStats() {
        return this.totals.department_counts || [];
    }

    get projectCards() {
        return this.state.data?.projects?.items || [];
    }

    get projectAction() {
        return this.state.data?.projects?.action || null;
    }

    get taskSummary() {
        return this.state.data?.tasks || {
            total: 0,
            waiting: 0,
            approved: 0,
            rejected: 0,
            hours: 0,
            action: null,
            hours_action: null,
        };
    }

    get actions() {
        return this.state.data?.actions || {};
    }

    formatNumber(value) {
        if (value === undefined || value === null) {
            return "0";
        }
        if (value >= 1000) {
            return Intl.NumberFormat().format(value);
        }
        return value.toString();
    }

    formatHours(value) {
        if (value === undefined || value === null) {
            return "0.00";
        }
        return Number(value).toFixed(2);
    }

    openAction(actionMeta, context = {}) {
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id, {
            additional_context: context,
        });
    }

    openProjects() {
        this.openAction(this.projectAction);
    }

    openTasks() {
        this.openAction(this.taskSummary.action);
    }

    openHours() {
        this.openAction(this.taskSummary.hours_action);
    }

    openProject(project) {
        if (!project?.url) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: project.url.res_model,
            res_id: project.url.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

ProjectDashboard.template = "qlk_project_management.ProjectDashboard";

registry.category("actions").add("qlk.project.dashboard", ProjectDashboard);
