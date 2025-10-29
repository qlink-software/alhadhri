# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo import tools

class LawFirmDashboard(models.Model):
    _name = 'managment.dashboard'
    _description = 'Management Dashboard'
    _auto = False

    name = fields.Char(string='Name', default='Dashboard')  

    @api.model
    def get_dashboard_data(self):
        # Get real data from the database
        pass
    #     Proposal = self.env['sale.order']
    #     Agreement = self.env['managment.agreement']
        
    #     total_proposals = Proposal.search_count([])
    #     pending_approvals = Proposal.search_count([('state', '=', 'in_review')])
    #     active_agreements = Agreement.search_count([('state', '=', 'active')])
        
    #     # Calculate conversion rate
    #     approved_proposals = Proposal.search_count([('state', '=', 'approved')])
    #     # conversion_rate = (active_agreements / approved_proposals * 100) if approved_proposals else 0
        
    #     # # Get proposals by status
    #     # proposal_by_status = []
    #     # states = Proposal._fields['state'].selection
    #     # for state_key, state_name in states:
    #     #     count = Proposal.search_count([('state', '=', state_key)])
    #     #     percentage = (count / total_proposals * 100) if total_proposals else 0
    #     #     proposal_by_status.append([
    #     #         state_key, state_name, state_name, count, round(percentage, 1)
    #     #     ])
        
    #     # # Get recent activities (simplified)
    #     # recent_activities = [
    #     #     [1, 'Proposal Approved', 'Client XYZ', '2 hours ago'],
    #     #     [2, 'New Agreement Created', 'Client ABC', '5 hours ago'],
    #     #     [3, 'Case Updated', 'Client DEF', '1 day ago'],
    #     # ]
        
    #     return {
    #         'total_proposals': total_proposals,
    #         'pending_approvals': pending_approvals,
    #         'active_agreements': active_agreements,
    #         'approved_proposals': approved_proposals,
    #         # 'conversion_rate': conversion_rate,
    #         # 'proposal_by_status': proposal_by_status,
    #         # 'recent_activities': recent_activities,
    #     }

    # # def init(self):
    # #     # Create a view for the dashboard if needed
    # #     tools.drop_view_if_exists(self.env.cr, self._table)
    # #     self.env.cr.execute("""
    # #         CREATE OR REPLACE VIEW %s AS (
    # #             SELECT 
    # #                 row_number() OVER () as id,
    # #                 'Dashboard' as name
    # #         )
    # #     """ % self._table)

        