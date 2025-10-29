// /** @odoo-module **/

// import { Component, useState, onWillStart } from "@odoo/owl";
// import { useService } from "@web/core/utils/hooks";
// import { registry } from "@web/core/registry";
// import { Layout } from "@web/search/layout";

// export class ManagementDashboard extends Component {
//     setup() {
//         this.orm = useService("orm");
//         this.action = useService("action");
//         this.rpc = useService("rpc");
        
//         this.state = useState({
//             loading: true,
//             data: {},
//         });

//         onWillStart(async () => {
//             await this.loadDashboardData();
//         });
//     }

//     async loadDashboardData() {
//         this.state.loading = true;
//         try {
//             const data = await this.rpc("/qlk_management/dashboard/data");
//             this.state.data = data;
//         } catch (error) {
//             console.error("Error loading dashboard data:", error);
//             this.state.data = {
//                 total_proposals: 0,
//                 pending_approvals: 0,
//                 active_agreements: 0,
//                 conversion_rate: 0,
//                 proposal_by_status: [],
//                 recent_activities: []
//             };
//         } finally {
//             this.state.loading = false;
//         }
//     }

//     async refresh() {
//         await this.loadDashboardData();
//     }

//     openProposalForm() {
//         this.action.doAction({
//             type: "ir.actions.act_window",
//             res_model: "managment.proposal",
//             views: [[false, "form"]],
//             target: "current",
//             context: { default_state: "draft" },
//         });
//     }

//     openAgreementForm() {
//         this.action.doAction({
//             type: "ir.actions.act_window",
//             res_model: "managment.agreement",
//             views: [[false, "form"]],
//             target: "current",
//         });
//     }
// }

// ManagementDashboard.template = "qlk_management.DashboardTemplate";
// ManagementDashboard.components = { Layout };

// // Register the dashboard view
// registry.category("views").add("managment_dashboard", {
//     type: "form",
//     component: ManagementDashboard,
//     display: {
//         controlPanel: {
//             "top-right": false,
//             "bottom-right": false,
//         },
//     },
//     searchMenuTypes: [],
// });