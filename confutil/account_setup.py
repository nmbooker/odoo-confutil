# -*- coding: utf-8 -*-

##############################################################################
#
# Post-installation configuration helpers
# Copyright (C) 2015 OpusVL (<http://opusvl.com/>)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

"""Common code for scripting installation of a chart of accounts into a company.

The method you probably want to use is setup_company_accounts on AccountsSetup instance.

The .confutil.Lookup class contains methods that will help you to retrieve the
company object and the account chart template.
"""

from datetime import date

import logging
_logger = logging.getLogger(__name__)

class AccountsSetup(object):
    """Interface for setting up accounts.

    In the simple case you probably want to use setup_company_accounts.
    This will install the chart of accounts and set up a default fiscal year
    running from 1st January to 31st December automatically for you.

    For greater control, you probably want to call setup_chart_of_accounts
    and create_fiscal_year manually.
    You can also use company_configured() to find out whether the company you
    pass in already has a chart of accounts, because setup_chart_of_accounts
    will not check for you.
    """
    def __init__(self, cr, registry, uid, context=None):
        self._cr = cr
        self._registry = registry
        self._uid = uid
        self._context = context


    def setup_company_accounts(self, company, chart_template, code_digits=None):
        """Set up the chart of accounts, fiscal year and periods for the given company.

        company: A res.company object
        chart_template: An account.chart.template object
        code_digits: The number of digits (the default is chart_template.code_digits)

        A financial year is set up starting this year on 1st Jan and
        ending this year on 31st Dec.

        If the company already has a chart of accounts installed, then this
        method will do nothing.
        """
        if not self.company_configured(company):
            self.setup_chart_of_accounts(
                company_id=company.id,
                chart_template_id=chart_template.id,
                code_digits=code_digits,
            )

            today = date.today()
            fy_name = today.strftime('%Y')
            fy_code = 'FY' + fy_name
            account_start = today.strftime('%Y-01-01')
            account_end = today.strftime('%Y-12-31')

            self.create_fiscal_year(
                company_id=company.id,
                name=fy_name,
                code=fy_code,
                start_date=account_start,
                end_date=account_end,
            )


    def company_configured(self, company):
        """Return whether given company is configured with a chart of accounts.

        company: Should be a company object (res.company)
        """
        return company.id not in self.unconfigured_company_ids()
        

    def unconfigured_company_ids(self):
        """Return list of ids of companies without a chart of accounts.
        """
        return self._registry['account.installer'].get_unconfigured_cmp(
            self._cr, self._uid, context=self._context
        )


    def setup_chart_of_accounts(self, company_id, chart_template_id, code_digits=None):
        """Set up the chart of accounts.

        company_id: Integer id within res.company
        chart_template_id: Integer id of the account.chart.template to install
        code_digits: Number of digits.  Defaults to your chart template's default.

        Note this will try to set up the chart of accounts even if company has one,
        and will probably crash at that point (if you're lucky).

        So you probably want to check that not self.company_configured(company)
        first.
        """
        chart_wizard = self._registry['wizard.multi.charts.accounts']
        defaults = chart_wizard.default_get(self._cr, self._uid,
            ['bank_accounts_id', 'currency_id'], context=self._context)

        bank_accounts_spec = defaults.pop('bank_accounts_id')
        bank_accounts_id = [(0, False, i) for i in bank_accounts_spec]

        data = defaults.copy()
        data.update({
            "chart_template_id": chart_template_id,
            'company_id': company_id,
            'bank_accounts_id': bank_accounts_id,
        })

        onchange = chart_wizard.onchange_chart_template_id(self._cr, self._uid,
            [], data['chart_template_id'], context=self._context)
        data.update(onchange['value'])

        if code_digits:
            data.update({'code_digits': code_digits})

        conf_id = chart_wizard.create(self._cr, self._uid, data, context=self._context)
        chart_wizard.execute(self._cr, self._uid, [conf_id], context=self._context)


    def create_fiscal_year(self, company_id, name, code, start_date, end_date):
        """Create a new fiscal year.

        company_id: Integer id within res.company
        name: The name to give the new fiscal year
        code: The code to give the new fiscal year
        start_date: YYYY-mm-dd
        end_date: YYYY-mm-dd
        """
        fy_model = self._registry['account.fiscalyear']
        fy_data = fy_model.default_get(self._cr, self._uid, ['state', 'company_id'], context=self._context).copy()
        fy_data.update({
            'company_id': company_id,
            'name': name,
            'code': code,
            'date_start': start_date,
            'date_stop': end_date,
        })
        fy_id = fy_model.create(self._cr, self._uid, fy_data, context=self._context)
        fy_model.create_period(self._cr, self._uid, [fy_id], context=self._context)



# MODULE-LEVEL FUNCTIONS BELOW ARE DEPRECATED, AND DELEGATE TO THE AccountsSetup CLASS
def setup_company_accounts(cr, registry, uid, company, chart_template, code_digits=None, context=None):
    """DEPRECATED - see AccountsSetup#setup_company_accounts"""
    _logger.warn('setup_company_account: DEPRECATED: Use AccountSetup object instead of module-level function')
    return AccountsSetup(cr, registry, uid, context).setup_company_accounts(
        company, chart_template, code_digits
    )

def unconfigured_company_ids(cr, registry, uid, context=None):
    """DEPRECATED - see AccountsSetup#unconfigured_company_ids"""
    _logger.warn('unconfigured_company_ids: DEPRECATED: Use unconfigured_companies method from AccountsSetup instead of module-level function')
    return AccountsSetup(cr, registry, uid, context).unconfigured_company_ids()

def setup_chart_of_accounts(cr, registry, uid, company_id, chart_template_id, code_digits=None, context=None):
    """DEPRECATED - see AccountsSetup#setup_chart_of_accounts"""
    _logger.warn('setup_chart_of_accounts: DEPRECATED: Use AccountsSetup object instead of module-level function')
    return AccountsSetup(cr, registry, uid, context).setup_chart_of_accounts(
        company_id, chart_template_id, code_digits
    )

def create_fiscal_year(cr, registry, uid, company_id, name, code, start_date, end_date, context=None):
    """DEPRECATED - see AccountsSetup#create_fiscal_year"""
    _logger.warn('setup_chart_of_accounts: DEPRECATED: Use AccountsSetup object instead of module-level function')
    return AccountsSetup(cr, registry, uid, context).create_fiscal_year(company_id, name, code, start_date, end_date)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
