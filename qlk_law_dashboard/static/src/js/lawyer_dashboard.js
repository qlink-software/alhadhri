/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class LawyerDashboard extends Component {
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
                const payload = await this.orm.call("qlk.lawyer.dashboard", "get_dashboard_data", []);
                this.state.data = payload;
            } catch (error) {
                console.error("Failed to load lawyer dashboard", error);
                this.notification.add(_t("Failed to load lawyer dashboard"), {
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

    get tasks() {
        return this.state.data?.tasks || { count: 0, hours: 0, action: null };
    }

    get cases() {
        return this.state.data?.cases || { items: [], count: 0, action: null };
    }

    get hearingsWeek() {
        return (
            this.state.data?.hearings_week || {
                items: [],
                count: 0,
                action: null,
                date_range: {
                    start: "",
                    end: "",
                    start_raw: "",
                    end_raw: "",
                },
            }
        );
    }

    get hearingsToday() {
        return (
            this.state.data?.hearings_today || {
                items: [],
                count: 0,
                action: null,
                date: "",
                date_raw: "",
            }
        );
    }

    get consultations() {
        return this.state.data?.consultations || { items: [], count: 0, action: null };
    }

    get complaints() {
        return this.state.data?.complaints || { items: [], count: 0, action: null };
    }

    get userInfo() {
        return this.state.data?.user || {};
    }

    get isManager() {
        return Boolean(this.state.data?.is_manager);
    }

    get hr() {
        return (
            this.state.data?.hr || {
                available: false,
                is_manager: false,
                employee: null,
                overview: [],
                upcoming_leaves: [],
                pending_leave_requests: 0,
                total_employees: 0,
                actions: {},
            }
        );
    }

    formatHours(hours) {
        if (hours === undefined || hours === null) {
            return "0.00";
        }
        return Number(hours).toFixed(2);
    }

    openRecord(record) {
        if (!record || !record.res_model || !record.res_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: record.res_model,
            res_id: record.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openAction(actionMeta, domain = []) {
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id, {
            additional_domain: domain,
        });
    }

    openActionDirect(actionMeta) {
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id);
    }

    openCases() {
        this.openAction(this.cases.action);
    }

    openConsultations() {
        this.openAction(this.consultations.action);
    }

    openComplaints() {
        this.openAction(this.complaints.action);
    }

    openHearingsWeek() {
        const section = this.hearingsWeek;
        if (!section.action) {
            return;
        }
        const domain = [];
        if (section.date_range.start_raw) {
            domain.push(["date", ">=", section.date_range.start_raw]);
        }
        if (section.date_range.end_raw) {
            domain.push(["date", "<=", section.date_range.end_raw]);
        }
        this.openAction(section.action, domain);
    }

    openHearingsToday() {
        const section = this.hearingsToday;
        if (!section.action) {
            return;
        }
        const domain = [];
        if (section.date_raw) {
            domain.push(["date", "=", section.date_raw]);
        }
        this.openAction(section.action, domain);
    }

    openHrEmployees() {
        this.openActionDirect(this.hr.actions?.employees);
    }

    openHrLeaves() {
        this.openActionDirect(this.hr.actions?.leaves);
    }
}

LawyerDashboard.template = "qlk_law_dashboard.LawyerDashboard";

registry.category("actions").add("qlk.lawyer.dashboard", LawyerDashboard);
