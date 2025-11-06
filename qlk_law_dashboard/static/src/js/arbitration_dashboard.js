/** @odoo-module **/

import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { _t } from '@web/core/l10n/translation';

class ArbitrationDashboard extends Component {
    setup() {
        this.orm = useService('orm');
        this.action = useService('action');
        this.notification = useService('notification');

        this.state = useState({
            loading: true,
            data: null,
        });

        onWillStart(async () => {
            try {
                const payload = await this.orm.call('qlk.arbitration.dashboard', 'get_dashboard_data', []);
                this.state.data = payload;
            } catch (error) {
                console.error('Failed to load arbitration dashboard', error);
                this.notification.add(_t('Failed to load arbitration dashboard'), {
                    type: 'danger',
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

    get metrics() {
        return (
            this.state.data?.metrics || {
                cases_total: 0,
                cases_month: 0,
                sessions_week: 0,
                memos_week: 0,
                awards_week: 0,
                week_range: { start: '', end: '' },
                today_label: '',
            }
        );
    }

    get lists() {
        return (
            this.state.data?.lists || {
                recent_cases: [],
                upcoming_sessions: [],
                recent_sessions: [],
                recent_memos: [],
                recent_awards: [],
            }
        );
    }

    get userInfo() {
        return this.state.data?.user || {};
    }

    get isManager() {
        return Boolean(this.state.data?.is_manager);
    }

    openAction(key) {
        const actionMeta = this.state.data?.actions?.[key];
        if (!actionMeta?.id) {
            return;
        }
        this.action.doAction(actionMeta.id);
    }

    openRecord(record) {
        if (!record?.res_model || !record?.res_id) {
            return;
        }
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: record.res_model,
            res_id: record.res_id,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

ArbitrationDashboard.template = 'qlk_law_dashboard.ArbitrationDashboard';

registry.category('actions').add('qlk.arbitration.dashboard', ArbitrationDashboard);
