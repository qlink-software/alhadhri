/** @odoo-module **/

import { Component, onRendered, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";

const chartKeyMap = {
    casesByStage: "cases_by_stage",
    courtsDistribution: "courts_distribution",
    casesTrend: "cases_trend",
    sessionsByStatus: "sessions_by_status",
    memosByType: "memos_by_type",
    lawyerWorkload: "lawyer_workload",
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

        this.canvasRefs = {
            casesByStage: useRef("casesByStageCanvas"),
            courtsDistribution: useRef("courtsDistributionCanvas"),
            casesTrend: useRef("casesTrendCanvas"),
            sessionsByStatus: useRef("sessionsByStatusCanvas"),
            memosByType: useRef("memosByTypeCanvas"),
            lawyerWorkload: useRef("lawyerWorkloadCanvas"),
        };
        this.chartInstances = {};

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this._loadData();
        });

        onRendered(() => {
            this._renderCharts();
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
            `--qlk-warning: ${palette.warning || "#D87A4A"}`,
            `--qlk-danger: ${palette.danger || "#B83A3A"}`,
            `--qlk-bg: ${palette.bg || "#F6F8FB"}`,
            `--qlk-card: ${palette.card || "#FFFFFF"}`,
            `--qlk-text: ${palette.text || "#1F2933"}`,
            `--qlk-border: ${palette.border || "#E6EAF0"}`,
            `--qlk-shadow: ${palette.shadow || "rgba(31, 41, 51, 0.08)"}`,
        ].join("; ");
    }

    get kpis() {
        return this.state.data?.kpis || [];
    }

    get charts() {
        return this.state.data?.charts || {};
    }

    get sideMetrics() {
        return this.state.data?.side_metrics || [];
    }

    get tables() {
        return this.state.data?.tables || {};
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

    openAction(actionMeta, domain) {
        if (!actionMeta) {
            return;
        }
        if (actionMeta.type) {
            const action = { ...actionMeta };
            if (domain) {
                action.domain = domain;
            }
            this.action.doAction(action);
            return;
        }
        this.action.doAction(actionMeta);
    }

    openRecord(target) {
        if (!target?.res_model || !target?.res_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: target.res_model,
            res_id: target.res_id,
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

    _chartConfig(key) {
        return this.charts[key];
    }

    _buildDataset(config) {
        const palette = ["#1F6FEB", "#27AE60", "#F4B740", "#E86A50", "#8E7CC3", "#2D9CDB"];
        const source = config.datasets || config.series || [];
        const datasets = source.map((serie, index) => {
            const fallbackColor = palette[index % palette.length];
            const data = serie.data || [];
            const isCircular = config.type === "doughnut" || config.type === "pie";
            let backgroundColor = serie.backgroundColor;
            if (!backgroundColor) {
                backgroundColor = isCircular ? palette.slice(0, data.length) : fallbackColor;
            }
            return {
                ...serie,
                label: serie.label || `Series ${index + 1}`,
                data,
                borderColor: serie.borderColor || fallbackColor,
                backgroundColor,
                tension: serie.tension ?? 0.35,
                fill: serie.fill ?? (config.type === "line"),
            };
        });
        return {
            labels: config.labels || [],
            datasets,
        };
    }

    _chartOptions(config) {
        const isCircular = config.type === "doughnut" || config.type === "pie";
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: isCircular ? "right" : "bottom",
                    labels: {
                        color: "#475569",
                        boxWidth: 12,
                        boxHeight: 12,
                    },
                },
                tooltip: {
                    enabled: true,
                },
            },
            scales: isCircular
                ? {}
                : {
                      x: {
                          stacked: !!config.stacked,
                          ticks: {
                              color: "#475569",
                          },
                          grid: {
                              display: false,
                          },
                      },
                      y: {
                          stacked: !!config.stacked,
                          ticks: {
                              color: "#475569",
                          },
                          grid: {
                              color: "rgba(15, 23, 42, 0.08)",
                          },
                      },
                  },
        };
    }
}

ExecutiveDashboard.template = "qlk_executive_dashboard.ExecutiveDashboard";
registry.category("actions").add("qlk.executive.dashboard", ExecutiveDashboard);
