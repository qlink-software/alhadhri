/** @odoo-module **/

import { Component, onRendered, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";

const chartKeyMap = {
    activityMix: "activity_mix",
    departmentLoad: "department_load",
    caseStatus: "case_status_mix",
    caseTrack: "case_track_mix",
    hoursTrend: "hours_trend",
};

class DynamicAnalysisDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
        });

        this.canvasRefs = {
            activityMix: useRef("activityMixCanvas"),
            departmentLoad: useRef("departmentLoadCanvas"),
            caseStatus: useRef("caseStatusCanvas"),
            caseTrack: useRef("caseTrackCanvas"),
            hoursTrend: useRef("hoursTrendCanvas"),
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

    get palette() {
        return this.state.data?.palette || {};
    }

    get cards() {
        return this.state.data?.cards || [];
    }

    get chartConfigs() {
        return this.state.data?.charts || {};
    }

    get insights() {
        return this.state.data?.insights || [];
    }

    get timeline() {
        return this.state.data?.timeline || [];
    }

    get hoursTasks() {
        return this.state.data?.hours_tasks || null;
    }

    get paletteStyle() {
        const palette = this.palette;
        return [
            `--qlk-primary: ${palette.primary || "#0F5CA8"}`,
            `--qlk-accent: ${palette.accent || "#22B6C8"}`,
            `--qlk-muted: ${palette.muted || "#1F3B57"}`,
            `--qlk-success: ${palette.success || "#27AE60"}`,
            `--qlk-warning: ${palette.warning || "#F39C12"}`,
            `--qlk-danger: ${palette.danger || "#C0392B"}`,
        ].join("; ");
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call("qlk.dynamic.analysis.dashboard", "get_dashboard_data", []);
            this.state.data = payload;
        } catch (error) {
            console.error("Failed to load dynamic analysis dashboard", error);
            this.notification.add(_t("Unable to load the dynamic analysis dashboard"), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    openAction(actionMeta) {
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id);
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
        return this.state.data?.charts?.[key];
    }

    _buildDataset(config) {
        const colors = Array.isArray(config.color)
            ? config.color
            : [config.color, this.palette.accent, this.palette.success, this.palette.warning, this.palette.danger].filter(Boolean);

        const datasets = (config.series || []).map((serie, index) => {
            const color = colors[index % colors.length] || "#0F5CA8";
            const common = {
                label: serie.label,
                data: serie.data || [],
                backgroundColor: color,
                borderColor: color,
                borderWidth: config.type === "bar" ? 0 : 2,
                fill: config.type === "line" ? index === 0 : true,
                tension: config.type === "line" ? 0.35 : 0,
            };

            if (config.type === "bar") {
                return {
                    ...common,
                    borderRadius: 12,
                    maxBarThickness: 48,
                };
            }

            if (config.type === "doughnut" || config.type === "pie") {
                return {
                    ...common,
                    borderWidth: 0,
                    hoverOffset: 8,
                };
            }

            return common;
        });

        return {
            labels: config.labels || [],
            datasets,
        };
    }

    _chartOptions(config) {
        const baseOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: "top",
                    labels: {
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    mode: "index",
                    intersect: false,
                },
            },
        };

        if (config.type === "line" || config.type === "bar") {
            baseOptions.scales = {
                x: {
                    grid: {
                        display: false,
                    },
                    ticks: {
                        autoSkip: true,
                        maxRotation: 0,
                    },
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: "rgba(0, 0, 0, 0.05)",
                    },
                    ticks: {
                        precision: 0,
                    },
                },
            };
        }

        return baseOptions;
    }
}

DynamicAnalysisDashboard.template = "qlk_dynamic_analysis_dashboard.DynamicAnalysisDashboard";

registry.category("actions").add("qlk.dynamic.analysis.dashboard", DynamicAnalysisDashboard);

export default DynamicAnalysisDashboard;
