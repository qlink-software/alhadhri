/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const CHART_COLORS = [
    "#0F5CA8",
    "#22B6C8",
    "#27AE60",
    "#F4B740",
    "#E86A50",
    "#0D3E7A",
];

class SimpleBarChart extends Component {
    static template = "qlk_executive_dashboard.SimpleBarChart";
    static props = {
        chartId: String,
        recordSets: { type: Array, optional: true },
        update_chart: { type: Function, optional: true },
    };

    get items() {
        const data = this.props.recordSets || [];
        const values = data.map((item) => item.count || item.value || 0);
        const max = Math.max(...values, 1);
        return data.map((item, index) => {
            const value = item.count || item.value || 0;
            return {
                label: item.category || item.label || "Unassigned",
                value,
                percent: Math.round((value / max) * 100),
                color: CHART_COLORS[index % CHART_COLORS.length],
                domain: item.domain || item.record_id || [],
            };
        });
    }

    onClick(item) {
        if (this.props.update_chart) {
            const chartId = Number(this.props.chartId || 0);
            this.props.update_chart(chartId, "bar_chart", item);
        }
    }
}

class SimplePieChart extends Component {
    static template = "qlk_executive_dashboard.SimplePieChart";
    static props = {
        chartId: String,
        recordSets: { type: Array, optional: true },
        update_chart: { type: Function, optional: true },
    };

    get items() {
        const data = this.props.recordSets || [];
        const total = data.reduce((sum, item) => sum + (item.value || item.count || 0), 0);
        return data.map((item, index) => {
            const value = item.value || item.count || 0;
            const percent = total ? Math.round((value / total) * 100) : 0;
            return {
                label: item.category || item.label || "Unassigned",
                value,
                percent,
                color: CHART_COLORS[index % CHART_COLORS.length],
                domain: item.domain || item.record_id || [],
            };
        });
    }

    get pieStyle() {
        const items = this.items;
        const total = items.reduce((sum, item) => sum + item.value, 0);
        if (!total) {
            return "background: conic-gradient(#e2e8f0 0% 100%);";
        }
        let current = 0;
        const segments = items.map((item) => {
            const start = current;
            const end = current + item.value / total;
            current = end;
            return `${item.color} ${start * 100}% ${end * 100}%`;
        });
        return `background: conic-gradient(${segments.join(", ")});`;
    }

    onClick(item) {
        if (this.props.update_chart) {
            const chartId = Number(this.props.chartId || 0);
            this.props.update_chart(chartId, "pie_chart", item);
        }
    }
}

class ExecutiveDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            data: null,
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("qlk.executive.dashboard", "get_dashboard_data", []);
        } catch (error) {
            console.error("Failed to load executive dashboard", error);
            this.notification.add(_t("Failed to load the executive dashboard"), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    get isManager() {
        return this.state.data && this.state.data.role === "manager";
    }

    get managerData() {
        return (this.state.data && this.state.data.manager) || {};
    }

    get managerLists() {
        return this.managerData.lists || {};
    }

    get assistantLists() {
        return this.assistantData.lists || {};
    }

    get recordLists() {
        return Object.keys(this.managerLists).length ? this.managerLists : this.assistantLists;
    }

    get listLeaves() {
        return this.recordLists.leaves || { items: [], action: null };
    }

    get listProposals() {
        return this.recordLists.proposals || { items: [], action: null };
    }

    get listAgreements() {
        return this.recordLists.agreements || { items: [], action: null };
    }

    get listProjects() {
        return this.recordLists.projects || { items: [], action: null };
    }

    get listCases() {
        return this.recordLists.cases || { items: [], action: null };
    }

    get listHearings() {
        return this.recordLists.hearings || { items: [], action: null };
    }

    get assistantData() {
        return (this.state.data && this.state.data.assistant) || {};
    }

    get approvalInboxAction() {
        return this.managerData.approval_inbox ? this.managerData.approval_inbox.action : null;
    }

    get approvalInboxItems() {
        return (this.managerData.approval_inbox && this.managerData.approval_inbox.items) || [];
    }

    get pipelineQuotations() {
        return (this.managerData.pipeline && this.managerData.pipeline.quotations) || { cards: [], action: null };
    }

    get pipelineAgreements() {
        return (this.managerData.pipeline && this.managerData.pipeline.agreements) || { cards: [], action: null };
    }

    get pipelineProjects() {
        return (this.managerData.pipeline && this.managerData.pipeline.projects) || { cards: [], action: null };
    }

    get pipelineQuotationsAction() {
        return this.pipelineQuotations.action || null;
    }

    get pipelineAgreementsAction() {
        return this.pipelineAgreements.action || null;
    }

    get pipelineProjectsAction() {
        return this.pipelineProjects.action || null;
    }

    get legalUpcoming() {
        return (this.managerData.legal && this.managerData.legal.upcoming_sessions) || { items: [], action: null };
    }

    get legalUpcomingAction() {
        return this.legalUpcoming.action || null;
    }

    get preApprovalAction() {
        return this.assistantData.pre_approval ? this.assistantData.pre_approval.action : null;
    }

    get preApprovalItems() {
        return (this.assistantData.pre_approval && this.assistantData.pre_approval.items) || [];
    }

    get caseMonitoringDelayed() {
        return (this.assistantData.case_monitoring && this.assistantData.case_monitoring.delayed) || {
            count: 0,
            action: null,
        };
    }

    get caseMonitoringNoSessions() {
        return (this.assistantData.case_monitoring && this.assistantData.case_monitoring.no_sessions) || {
            count: 0,
            action: null,
        };
    }

    get caseMonitoringUpcoming() {
        return (this.assistantData.case_monitoring && this.assistantData.case_monitoring.upcoming_hearings) || {
            items: [],
            action: null,
        };
    }

    get caseMonitoringDelayedAction() {
        return this.caseMonitoringDelayed.action || null;
    }

    get caseMonitoringNoSessionsAction() {
        return this.caseMonitoringNoSessions.action || null;
    }

    get caseMonitoringUpcomingAction() {
        return this.caseMonitoringUpcoming.action || null;
    }

    openAction(action, domain) {
        if (!action) {
            return;
        }
        const payload = { ...action };
        if (domain && domain.length) {
            payload.domain = domain;
        }
        this.action.doAction(payload);
    }

    openKpi(kpi) {
        if (!kpi || !kpi.action) {
            return;
        }
        this.openAction(kpi.action, []);
    }

    openRequest(request) {
        if (!request || !request.action) {
            return;
        }
        this.openAction(request.action, []);
    }

    openRecord(item) {
        if (!item || !item.model || !item.id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: item.model,
            res_id: item.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onApprove(item) {
        if (!item) {
            return;
        }
        if (!window.confirm(_t("Approve this request?"))) {
            return;
        }
        await this.performAction("action_approve_record", [item.model, item.id]);
    }

    async onReject(item) {
        if (!item) {
            return;
        }
        const reason = window.prompt(_t("Rejection reason"));
        if (!reason) {
            this.notification.add(_t("Rejection reason is required."), { type: "warning" });
            return;
        }
        await this.performAction("action_reject_record", [item.model, item.id, reason]);
    }

    async onRecommend(item) {
        if (!item) {
            return;
        }
        const note = window.prompt(_t("Recommendation note (optional)")) || "";
        await this.performAction("action_assistant_recommend", [item.model, item.id, "recommend", note]);
    }

    async onNeedsRevision(item) {
        if (!item) {
            return;
        }
        const note = window.prompt(_t("Revision note (required)"));
        if (!note) {
            this.notification.add(_t("Revision note is required."), { type: "warning" });
            return;
        }
        await this.performAction("action_assistant_recommend", [item.model, item.id, "revision", note]);
    }

    async performAction(method, args) {
        try {
            await this.orm.call("qlk.executive.dashboard", method, args);
            await this.loadDashboard();
            this.notification.add(_t("Action completed."), { type: "success" });
        } catch (error) {
            console.error("Dashboard action failed", error);
            this.notification.add(_t("Action failed."), { type: "danger" });
        }
    }

    onChartClick(chartId, chartType, dataPoint) {
        const chartActionMap = {
            1: this.managerData.legal ? this.managerData.legal.cases_by_court.action : null,
            2: this.managerData.legal ? this.managerData.legal.cases_by_status.action : null,
        };
        const action = (dataPoint && dataPoint.action) || chartActionMap[chartId];
        const domain = (dataPoint && (dataPoint.domain || dataPoint.record_id)) || [];
        this.openAction(action, domain);
    }
}

ExecutiveDashboard.template = "qlk_executive_dashboard.ExecutiveDashboard";
ExecutiveDashboard.components = { SimpleBarChart, SimplePieChart };

registry.category("actions").add("qlk.executive.dashboard", ExecutiveDashboard);
