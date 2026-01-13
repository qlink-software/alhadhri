/** @odoo-module **/

import { Component, onRendered, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";

const chartKeyMap = {
    litigationCourt: "cases_by_court",
    litigationStatus: "cases_by_status",
    litigationSessions: "sessions_timeline",
    financeRevenue: "revenue_by_month",
    financeFees: "fees_by_case",
    financePaid: "paid_vs_unpaid",
    hrDept: "employees_by_department",
    hrPosition: "employees_by_position",
    hrLeaves: "leave_status",
    approvalsByModel: "approvals_by_model",
};

class ExecutiveDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
        });
        this.activeSection = this.props?.action?.context?.executive_section || "overview";
        this.hasScrolled = false;

        this.canvasRefs = {
            litigationCourt: useRef("litigationCourtCanvas"),
            litigationStatus: useRef("litigationStatusCanvas"),
            litigationSessions: useRef("litigationSessionsCanvas"),
            financeRevenue: useRef("financeRevenueCanvas"),
            financeFees: useRef("financeFeesCanvas"),
            financePaid: useRef("financePaidCanvas"),
            hrDept: useRef("hrDeptCanvas"),
            hrPosition: useRef("hrPositionCanvas"),
            hrLeaves: useRef("hrLeavesCanvas"),
            approvalsByModel: useRef("approvalsByModelCanvas"),
        };
        this.chartInstances = {};

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this._loadData();
        });

        onRendered(() => {
            this._renderCharts();
            this._scrollToSection();
        });

        onWillUnmount(() => {
            this._destroyCharts();
        });
    }

    get paletteStyle() {
        const palette = this.state.data?.palette || {};
        return [
            `--qlk-primary: ${palette.primary || "#0B2C3F"}`,
            `--qlk-accent: ${palette.accent || "#C9A56A"}`,
            `--qlk-muted: ${palette.muted || "#1C3D4B"}`,
            `--qlk-success: ${palette.success || "#2C8C6A"}`,
            `--qlk-warning: ${palette.warning || "#D87A4A"}`,
            `--qlk-danger: ${palette.danger || "#B83A3A"}`,
        ].join("; ");
    }

    get litigation() {
        return this.state.data?.litigation || {};
    }

    get finance() {
        return this.state.data?.finance || {};
    }

    get hr() {
        return this.state.data?.hr || {};
    }

    get approvals() {
        return this.state.data?.approvals || {};
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call("qlk.executive.dashboard", "get_dashboard_data", []);
            this.state.data = payload;
        } catch (error) {
            console.error("Failed to load executive dashboard", error);
            this.notification.add(_t("Unable to load the executive dashboard"), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(actionMeta) {
        if (!actionMeta) {
            return;
        }
        this.action.doAction(actionMeta);
    }

    openApproval(record) {
        if (!record?.id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "approval.request",
            res_id: record.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    _destroyCharts() {
        Object.values(this.chartInstances).forEach((chart) => {
            if (chart?.destroy) {
                chart.destroy();
            }
        });
        this.chartInstances = {};
    }

    _renderCharts() {
        if (!window.Chart || !this.state.data) {
            return;
        }
        for (const [refKey, ref] of Object.entries(this.canvasRefs)) {
            const canvas = ref.el;
            if (!canvas) {
                continue;
            }
            const chartKey = chartKeyMap[refKey];
            const config = this._chartConfig(chartKey);
            if (!config) {
                if (this.chartInstances[refKey]) {
                    this.chartInstances[refKey].destroy();
                    delete this.chartInstances[refKey];
                }
                continue;
            }
            const chartData = this._buildDataset(config);
            const options = this._chartOptions(config);
            if (this.chartInstances[refKey]) {
                this.chartInstances[refKey].data = chartData;
                this.chartInstances[refKey].options = options;
                this.chartInstances[refKey].update();
                continue;
            }
            this.chartInstances[refKey] = new window.Chart(canvas.getContext("2d"), {
                type: config.type || "line",
                data: chartData,
                options,
            });
        }
    }

    _scrollToSection() {
        if (this.hasScrolled || !this.activeSection || this.activeSection === "overview") {
            return;
        }
        const target = this.el?.querySelector(`#section-${this.activeSection}`);
        if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
            this.hasScrolled = true;
        }
    }

    _chartConfig(key) {
        const charts = {
            ...(this.litigation.charts || {}),
            ...(this.finance.charts || {}),
            ...(this.hr.charts || {}),
            ...(this.approvals.charts || {}),
        };
        return charts[key];
    }

    _buildDataset(config) {
        const color = config.color || "#0B2C3F";
        const datasets = (config.series || []).map((serie, index) => {
            const palette = ["#0B2C3F", "#C9A56A", "#2C8C6A", "#D87A4A", "#B83A3A"];
            const backgroundColor =
                config.type === "doughnut"
                    ? palette.slice(0, (serie.data || []).length)
                    : palette[index % palette.length];
            return {
                label: serie.label,
                data: serie.data || [],
                borderColor: config.type === "line" ? color : palette[index % palette.length],
                backgroundColor: config.type === "line" ? "rgba(11, 44, 63, 0.1)" : backgroundColor,
                tension: 0.35,
            };
        });
        return {
            labels: config.labels || [],
            datasets,
        };
    }

    _chartOptions(config) {
        const isDoughnut = config.type === "doughnut";
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: isDoughnut,
                    position: "bottom",
                    labels: {
                        color: "#2C3E50",
                    },
                },
                tooltip: {
                    enabled: true,
                },
            },
            scales: isDoughnut
                ? {}
                : {
                      x: {
                          ticks: {
                              color: "#2C3E50",
                          },
                          grid: {
                              display: false,
                          },
                      },
                      y: {
                          ticks: {
                              color: "#2C3E50",
                          },
                          grid: {
                              color: "rgba(0,0,0,0.08)",
                          },
                      },
                  },
        };
    }
}

ExecutiveDashboard.template = "qlk_executive_dashboard.ExecutiveDashboard";
registry.category("actions").add("qlk.executive.dashboard", ExecutiveDashboard);
