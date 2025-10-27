/** @odoo-module **/

import { Component, onRendered, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadJS } from "@web/core/assets";

class AnalysisDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            data: null,
        });
        this.filters = useState({ months: 6 });

        this.canvasRefs = {
            cases: useRef("casesCanvas"),
            hearings: useRef("hearingsCanvas"),
            consultations: useRef("consultationsCanvas"),
            complaints: useRef("complaintsCanvas"),
            projects: useRef("projectsCanvas"),
            taskHours: useRef("taskHoursCanvas"),
        };
        this.charts = {};

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this._loadData();
        });

        onRendered(() => {
            this._renderCharts();
        });
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const payload = await this.orm.call("qlk.analysis.dashboard", "get_dashboard_data", [this.filters.months]);
            this.state.data = payload;
        } catch (error) {
            console.error("Failed to load analytics dashboard", error);
            this.notification.add(_t("تعذر تحميل لوحة التحليلات"), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    get palette() {
        return this.state.data?.palette || {};
    }

    get totals() {
        return this.state.data?.totals || {};
    }

    get series() {
        return this.state.data?.series || {};
    }

    get periods() {
        return [6, 12, 18, 24];
    }

    isActivePeriod(months) {
        return this.filters?.months === months;
    }

    openAction(actionMeta) {
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id);
    }

    async changePeriod(months) {
        if (this.filters.months === months) {
            return;
        }
        this.filters.months = months;
        await this._loadData();
    }

    _renderCharts() {
        if (!this.state.data) {
            return;
        }

        const chartConfigs = {
            cases: {
                title: _t("عدد القضايا شهريًا"),
                dataset: this.series.cases,
                color: this.palette.primary || "#0F5CA8",
                type: "line",
                actionKey: "cases",
            },
            hearings: {
                title: _t("الجدول الزمني للجلسات"),
                dataset: this.series.hearings,
                color: this.palette.accent || "#22B6C8",
                type: "line",
                actionKey: "hearings",
            },
            consultations: {
                title: _t("الاستشارات الشهرية"),
                dataset: this.series.consultations || [],
                color: "#8E44AD",
                type: "line",
                actionKey: "consultations",
            },
            complaints: {
                title: _t("بلاغات الشرطة"),
                dataset: this.series.complaints || [],
                color: "#C0392B",
                type: "line",
                actionKey: "complaints",
            },
            projects: {
                title: _t("المشاريع الجديدة"),
                dataset: this.series.projects,
                color: this.palette.muted || "#0D3E7A",
                type: "bar",
                actionKey: "projects",
            },
            taskHours: {
                title: _t("الساعات المعتمدة للمشاريع"),
                dataset: this.series.task_hours,
                color: this.palette.success || "#27AE60",
                type: "bar",
                actionKey: "tasks",
            },
            caseStatus: {
                title: _t("توزيع حالات القضايا"),
                dataset: this.series.case_status || [],
                color: ["#0F5CA8", "#22B6C8", "#27AE60", "#C0392B", "#8E44AD"],
                type: "pie",
                actionKey: "cases",
            },
            hearingStage: {
                title: _t("حالات الجلسات"),
                dataset: this.series.hearing_stage || [],
                color: ["#22B6C8", "#0F5CA8", "#F39C12", "#C0392B"],
                type: "doughnut",
                actionKey: "hearings",
            },
            projectProgress: {
                title: _t("تقدم المشاريع"),
                dataset: this.series.project_progress || [],
                color: this.palette.muted || "#0D3E7A",
                type: "bar",
                actionKey: "projects",
            },
            taskDepartment: {
                title: _t("المهام حسب القسم"),
                dataset: this.series.task_department || [],
                color: ["#0F5CA8", "#22B6C8", "#27AE60", "#8E44AD"],
                type: "pie",
                actionKey: "tasks",
            },
        };

        for (const [key, ref] of Object.entries(this.canvasRefs)) {
            const canvas = ref.el;
            if (!canvas) {
                continue;
            }
            const cfg = chartConfigs[key];
            if (!cfg) {
                continue;
            }
            const source = cfg.dataset || [];
            const labels = source.map((entry) => entry.label);
            const data = source.map((entry) => entry.value);
            const type = cfg.type || "line";

            if (this.charts[key]) {
                if (!labels.length) {
                    this.charts[key].destroy();
                    delete this.charts[key];
                    continue;
                }
                const dataset = this.charts[key].data.datasets[0];
                this.charts[key].data.labels = labels;
                dataset.data = data;
                if (Array.isArray(cfg.color)) {
                    dataset.backgroundColor = cfg.color;
                    dataset.borderColor = cfg.color;
                }
                this.charts[key].update();
                continue;
            }

            if (!window.Chart || !labels.length) {
                continue;
            }

            const background = Array.isArray(cfg.color) ? cfg.color : cfg.color;
            const border = Array.isArray(cfg.color) ? cfg.color : cfg.color;

            this.charts[key] = new window.Chart(canvas.getContext("2d"), {
            type,
            data: {
                labels,
                datasets: [
                    {
                        label: cfg.title,
                        data,
                        backgroundColor: background,
                        borderColor: border,
                        tension: type === "line" ? 0.35 : 0,
                        fill: type === "line",
                        hoverOffset: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: type === "pie" || type === "doughnut",
                        position: "bottom",
                    },
                },
                scales: {
                    x: type === "pie" || type === "doughnut" ? undefined : {
                        ticks: { color: "#6f7a8c" },
                        grid: { display: false },
                    },
                    y: type === "pie" || type === "doughnut" ? undefined : {
                        ticks: { color: "#6f7a8c" },
                        grid: { color: "rgba(0,0,0,0.05)" },
                    },
                },
                onClick: (_event, elements) => {
                    if (!elements.length || !source.length) {
                        return;
                    }
                    const index = elements[0].index;
                    const entry = source[index];
                    const actionKey = entry?.action || cfg.actionKey;
                    if (!actionKey) {
                        return;
                    }
                    const actionMeta = this.state.data?.actions?.[actionKey] || { id: actionKey };
                    this.openAction(actionMeta, entry?.domain || []);
                },
            },
        });
        }
    }
}

AnalysisDashboard.template = "qlk_project_management.AnalysisDashboard";

registry.category("actions").add("qlk.analysis.dashboard", AnalysisDashboard);
