# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class DashboardController(http.Controller):
    
    @http.route('/qlk_management/dashboard/data', type='json', auth='public')
    def get_dashboard_data(self):
        # Get data from the dashboard model
        Dashboard = request.env['managment.agreement']
        print('\\\\\\\\\\\\\\\\\\\\\sff',Dashboard)
        return Dashboard.get_dashboard_data()