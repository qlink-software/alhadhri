/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class ApprovalDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            refreshing: false,
            scope: "mine",
            activeModel: false,
            data: null,
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard(activeModel = this.state.activeModel) {
        this.state.refreshing = true;
        try {
            const payload = await this.orm.call("qlk.approval.dashboard", "get_dashboard_data", [], {
                scope: this.state.scope,
                active_model: activeModel,
            });
            this.state.data = payload;
            this.state.activeModel = payload.active_model || false;
        } catch (error) {
            console.error("Failed to load approval dashboard", error);
            this.notification.add(_t("Failed to load the approval dashboard"), { type: "danger" });
            throw error;
        } finally {
            this.state.loading = false;
            this.state.refreshing = false;
        }
    }

    get kpiCards() {
        const kpis = this.state.data?.kpis || {};
        return ["pending", "approved", "rejected", "hours"].map((key) => ({
            key,
            label: kpis[key]?.label || key,
            value: kpis[key]?.value || 0,
            tone: kpis[key]?.tone || "primary",
        }));
    }

    get sections() {
        return this.state.data?.sections || [];
    }

    get activeSection() {
        return this.sections.find((section) => section.model === this.state.activeModel) || this.sections[0] || null;
    }

    get records() {
        return this.state.data?.approvals?.[this.state.activeModel] || [];
    }

    get permissions() {
        return this.state.data?.permissions || {};
    }

    get hoursRows() {
        return this.state.data?.hours?.by_user || [];
    }

    get maxUserHours() {
        return Math.max(...this.hoursRows.map((row) => row.hours || 0), 1);
    }

    get pieSegments() {
        const section = this.activeSection;
        if (!section) {
            return [];
        }
        const counts = section.counts || {};
        const values = [
            { key: "pending", label: _t("Pending"), count: counts.pending || 0, color: "#d79b12" },
            { key: "approved", label: _t("Approved"), count: counts.approved || 0, color: "#2b9464" },
            { key: "rejected", label: _t("Rejected"), count: counts.rejected || 0, color: "#c94f4f" },
        ].filter((item) => item.count > 0);
        const total = values.reduce((sum, item) => sum + item.count, 0);
        if (!total) {
            return [];
        }
        const circumference = 263.89;
        let offset = 0;
        return values.map((item) => {
            const length = (item.count / total) * circumference;
            const segment = {
                ...item,
                dash: `${length} ${circumference - length}`,
                offset: -offset,
            };
            offset += length;
            return segment;
        });
    }

    formatNumber(value) {
        return Intl.NumberFormat().format(value || 0);
    }

    formatHours(value) {
        return Number(value || 0).toFixed(2);
    }

    async setScope(scope) {
        if (scope === "all" && !this.permissions.can_use_all) {
            return;
        }
        this.state.scope = scope;
        await this.loadDashboard(false);
    }

    async selectSection(model) {
        if (model === this.state.activeModel) {
            return;
        }
        this.state.activeModel = model;
        await this.loadDashboard(model);
    }

    refresh() {
        return this.loadDashboard(this.state.activeModel);
    }

    openAction(action) {
        if (action) {
            this.action.doAction(action);
        }
    }

    openSection(section = this.activeSection) {
        this.openAction(section?.action);
    }

    openKpi(key) {
        if (key === "hours") {
            this.openAction(this.state.data?.hours?.action);
            return;
        }
        const section = this.activeSection;
        const domain = section?.domains?.[key];
        if (!section || !domain) {
            return;
        }
        this.openAction({
            type: "ir.actions.act_window",
            name: section.label,
            res_model: section.model,
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openPieSegment(segment) {
        this.openKpi(segment.key);
    }

    openUserHours(row) {
        this.openAction(row.action);
    }

    async decide(record, decision) {
        const isApprove = decision === "approve";
        let reason = false;
        if (!isApprove) {
            reason = window.prompt(_t("Rejection reason"));
            if (reason === null) {
                return;
            }
            reason = reason.trim();
            if (!reason) {
                this.notification.add(_t("Please enter a rejection reason"), { type: "warning" });
                return;
            }
        }
        const message = isApprove ? _t("Approve this record?") : _t("Reject this record?");
        if (!window.confirm(message)) {
            return;
        }
        try {
            const result = await this.orm.call("qlk.approval.dashboard", "action_decide", [
                record.model,
                record.id,
                decision,
                reason,
            ]);
            if (result && result.type && result.tag !== "reload") {
                await this.action.doAction(result);
            }
            await this.loadDashboard(this.state.activeModel);
            this.notification.add(isApprove ? _t("Record approved") : _t("Record rejected"), {
                type: "success",
            });
        } catch (error) {
            console.error("Approval dashboard action failed", error);
            this.notification.add(_t("The approval action could not be completed"), { type: "danger" });
        }
    }
}

ApprovalDashboard.template = "qlk_approval_dashboard.ApprovalDashboard";
registry.category("actions").add("qlk.approval.dashboard", ApprovalDashboard);

registry.category("services").add("qlk_approval_dashboard_badge", {
    dependencies: ["orm"],
    start(env, { orm }) {
        const updateBadge = async () => {
            let count = 0;
            try {
                count = await orm.call("qlk.approval.dashboard", "get_pending_count", []);
            } catch {
                return;
            }
            const menu = [...document.querySelectorAll("a")].find(
                (item) =>
                    item.dataset.menuXmlid === "qlk_approval_dashboard.menu_qlk_approval_dashboard_root" ||
                    item.textContent.trim() === "Approval Dashboard"
            );
            if (!menu) {
                return;
            }
            let badge = menu.querySelector(".qlk-approval-menu-badge");
            if (!count) {
                badge?.remove();
                return;
            }
            if (!badge) {
                badge = document.createElement("span");
                badge.className = "qlk-approval-menu-badge";
                menu.appendChild(badge);
            }
            badge.textContent = count > 99 ? "99+" : String(count);
        };
        setTimeout(updateBadge, 2500);
        const timer = setInterval(updateBadge, 60000);
        return {
            updateBadge,
            stop() {
                clearInterval(timer);
            },
        };
    },
});
