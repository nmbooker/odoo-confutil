# -*- coding: utf-8 -*-

##############################################################################
#
# Odoo confutil
# Copyright (C) 2014 OpusVL (<http://opusvl.com/>)
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

"""Functions to help with post-installation configuration of a module.

This is for stuff that doesn't readily work with XML/CSV imports, for example
ones where dependent records don't have external IDs, or changes to Settings -> Config
screens need to be made (so execute() has to be called afterwards).
"""

import logging
_logger = logging.getLogger(__name__)

class Lookup(object):
    """Implements common lookups.

    Initialise as follows:

        lookup = Lookup(cr, registry, SUPERUSER_ID, context=context.copy())

    Then you can do things like:

        map(lookup.tax_id_by_code, ['UKST1', 'USST1', 'FRST1'])
    """
    def __init__(self, cr, registry, uid, context=None):
        self._cr = cr
        self._registry = registry
        self._uid = uid
        self._context = context


    def tax_id_by_code(self, code):
        """Return account.tax id matching given tax_code.

        tax_code: The tax code you're interested in, e.g. ST1.
                  Actually the value of 'description' field on account.tax

        Return type: int

        Raises as per get_exactly_one_id if there isn't precisely one match.
        """
        return self.exactly_one_id('account.tax', [('description', '=', code)])


    def account_id(self, company, code):
        """Return the id of the account for company with given code.
        """
        return self.exactly_one_id('account.account', [
            ('company_id', '=', company.id),
            ('code', '=', code)
        ])


    def xmlid(self, module_or_dotted_xmlid, xmlid=None):
        """Return the object with XMLID = 'module.xmlid'.

        This can be called in two ways:
            self.xmlid(module, xmlid)

                module: The module bit of the id (the bit before the dot) e.g. 'purchase'
                xmlid:  The bit after the dot e.g. 'route_warehouse0_buy'


            self.xmlid(xmlid)

                xmlid: The XMLID as one string e.g. 'purchase.route_warehouse0_buy'

        If the first argument is a string containing a dot '.' then
        the second signature is assumed.
        Otherwise the first is expected.

        Note this returns an OBJECT, not a numeric database id.
        """
        IMD = self._registry['ir.model.data']
        if '.' in module_or_dotted_xmlid:
            module, identifier = module_or_dotted_xmlid.split('.')
        else:
            if not isinstance(xmlid, (str, unicode)):
                raise TypeError('xmlid(module, xmlid) form: xmlid must be a string')
            module, identifier = module_or_dotted_xmlid, xmlid
        return IMD.get_object(self._cr, self._uid, module, identifier)


    def xmlid_id(self, module_or_dotted_xmlid, xmlid=None):
        """Like xmlid() but returns the numeric id"""
        return self.xmlid(module_or_dotted_xmlid, xmlid).id


    def exactly_one_id(self, model, domain):
        """Get exactly one object from model matching domain.

        Raises TooManyRecordsError if more than one record is found.
        Raises NoRecordsError if no records are found.
        """
        modobj = self._autoresolve_model(model)
        return get_exactly_one_id(modobj, self._cr, self._uid, domain, context=self._context.copy())


    def maybe_id(self, model, domain):
        """Return single record id or None matching the domain.

        Raises TooManyRecordsError if more than one record is found.
        """
        return get_maybe_id(self._autoresolve_model(model), self._cr, self._uid,
            domain=domain,
            context=self._context.copy(),
        )

    def _autoresolve_model(self, model):
        return self.model(model) if isinstance(model, (str, unicode)) else model


    def model(self, model_name):
        """Return model with given name.
        """
        return self._registry[model_name]



def set_global_default_product_customer_taxes(cr, registry, uid, company_id, tax_ids, context=None):
    """Set global default sales taxes for new products.

    tax_ids: A list of integers which are ids of account.tax objects.

    Usually you'll want to have one tax id from each company in a multicompany system,
    or a singleton list containing only one for a single-company system.
    """
    registry['ir.values'].set_default(cr, uid,
        model='product.template',
        field_name='taxes_id',
        for_all_users=True,
        company_id=company_id,
        value=tax_ids,
    )

def set_global_default_product_supplier_taxes(cr, registry, uid, company_id, tax_ids, context=None):
    """Set global default purchase taxes for new products.

    tax_ids: A list of integers which are ids of account.tax objects.

    Usually you'll want to have one tax id from each company in a multicompany system,
    or a singleton list containing only one for a single-company system.
    """
    registry['ir.values'].set_default(cr, uid,
        model='product.template',
        field_name='supplier_taxes_id',
        for_all_users=True,
        company_id=company_id,
        value=tax_ids,
    )

def set_default_taxes(cr, registry, uid, company, sales_code, purchase_code, context=None):
    """Set the default tax codes for the given company.

    sales_code: e.g. 'ST1UK'
    purchase_code: e.g. 'PT1UK'
    """
    taxes_model = registry['account.tax']

    # 'description' is actually the tax code.  Should be unique.
    sales_tax_id = get_exactly_one_id(
        taxes_model, cr, uid,
        [('company_id', '=', company.id), ('description', '=', sales_code)],
        context=context
    )
    purchase_tax_id = get_exactly_one_id(
        taxes_model, cr, uid,
        [('company_id', '=', company.id), ('description', '=', purchase_code)],
        context=context
    )

    set_account_settings(cr, registry, uid,
        company=company,
        changes={
            'default_sale_tax': sales_tax_id,
            'default_purchase_tax': purchase_tax_id,
        },
        context=context,
    )


def enable_multi_currency(cr, registry, uid, company, gain_account_code, loss_account_code, context=None):
    """Set up multi-currency support on the given company.
    """
    accounts_model = registry['account.account']

    _logger.debug('setup_multi_currency: Get gain account with code %s for company %s'
            % (gain_account_code, company.name))
    gain_account_id = get_exactly_one_id(
        accounts_model, cr, uid,
        [('company_id', '=', company.id), ('code', '=', gain_account_code)],
        context=context.copy(),
    )

    _logger.debug('setup_multi_currency: Get loss account with code %s for company %s'
            % (loss_account_code, company.name))
    loss_account_id = get_exactly_one_id(
        accounts_model, cr, uid,
        [('company_id', '=', company.id), ('code', '=', loss_account_code)],
        context=context.copy(),
    )

    _logger.debug('setup_multi_currency: Call set_account_settings')
    set_account_settings(cr, registry, uid,
        company=company,
        changes={
            'group_multi_currency': True,
            'income_currency_exchange_account_id': gain_account_id,     # gain account
            'expense_currency_exchange_account_id': loss_account_id,   # loss account
        },
        context=context,
    )


def set_account_settings(cr, registry, uid, changes, company, context=None):
    """Set a bunch of accounts settings on the given company.

    Note there can be an issue with first runs of this if you haven't already
    previously set 'date_stop' and 'date_start' in either XML or a previous call.

    If they haven't been set previously in the installation routine, you should
    include a date_stop and date_start in changes, matching the initial start
    and end dates of the first fiscal year.
    """
    return set_settings(cr, registry, uid, 'account.config.settings',
        changes=changes, company=company, context=context,
    )


def set_general_settings(cr, registry, uid, changes, context=None):
    """Set a bunch of general settings for the whole of Odoo.
    """
    return set_settings(cr, registry, uid, 'base.config.settings',
        changes=changes, context=context,
    )

def set_purchasing_settings(cr, registry, uid, changes, context=None):
    """Set a bunch of purchasing settings for the whole of Odoo.
    """
    return set_settings(cr, registry, uid, 'purchase.config.settings',
        changes=changes, context=context,
    )
    
def set_sale_settings(cr, registry, uid, changes, context=None):
    """Set a bunch of sale settings for the whole of Odoo.
    """
    return set_settings(cr, registry, uid, 'sale.config.settings',
        changes=changes, context=context,
    )
    
def set_warehouse_settings(cr, registry, uid, changes, context=None):
    """Set a bunch of warehouse settings for the whole of Odoo.
    """
    return set_settings(cr, registry, uid, 'stock.config.settings',
        changes=changes, context=context,
    )

def get_account_id(cr, registry, uid, company, code, context=None):
    """Get id of a company's account with the given code.
    """
    _logger.warn('get_account_id: DEPRECATED: consider using lookup.account_id(company, code) instead')
    return get_exactly_one_id(registry['account.account'], cr, uid,
        [('company_id', '=', company.id), ('code', '=', code)],
        context=context,
    )


def set_settings(cr, registry, uid, settings_model_name, changes, company=None, context=None):
    """Update and execute a settings form.

    settings_model_name: for example 'account.config.settings' or 'base.config.settings'
    changes: Dictionary mapping field names to their new values.
    company: If defined, will create or find a config object matching company_id == company.id
    """
    settings_model = registry[settings_model_name]
    domain = [('company_id', '=', company.id)] if company else []
    settings_id = get_maybe_id(settings_model, cr, uid, domain, context=context)
    if settings_id is None:
        data = settings_model.default_get(cr, uid,
            list(settings_model.fields_get(cr, uid, context=context)),
            context=context,
        )
        data.update(changes)
        if company:
            data['company_id'] = company.id
        settings_id = settings_model.create(cr, uid, data, context=context)
    else:
        settings_model.write(cr, uid, [settings_id], changes, context=context)
    settings_model.execute(cr, uid, [settings_id], context=context)


def create_consolidation_account(cr, registry, uid, company, code, name, children, context=None):
    """Create a consolidation account for a company.  Return its id.

    company: The company that will own the new consolidation account.
    code: Code for the new consolidation account
    name: Name for the new consolidation account
    children: List of ids of child accounts
    """
    account_type_view_id = get_exactly_one_id(
        registry['account.account.type'], cr, uid,
        [('name', '=', 'Root/View')],
        context=context,
    )
    ADD_EXISTING_ID = 4
    data = {
        'code': code,
        'name': name,
        'type': 'consolidation',
        'user_type': account_type_view_id,
        'child_consol_ids': [
            (ADD_EXISTING_ID, child_id, False) for child_id in children
            for child in children
        ],
    }
    return registry['account.account'].create(cr, uid, data, context=context)


def set_default_customer_sale_pricelist(cr, registry, uid, company, pricelist, context=None):
    """Set the default customer sale pricelist for a company.
    """
    field_id = get_field_id(cr, registry, uid,
        model_name='res.partner',
        field_name='property_product_pricelist',
        context=context,
    )
    ir_property = registry['ir.property']
    existing_ids = ir_property.search(cr, uid,
        [
            ('company_id', '=', company.id),
            ('fields_id', '=', field_id),
            ('res_id', '=', False),
        ],
        context=context,
    )
    if existing_ids:
        ir_property.unlink(cr, uid, existing_ids, context=context)
    ir_property.create(cr, uid,
        dict(
            company_id=company.id,
            fields_id=field_id,
            res_id=False,
            type='many2one',
            value_reference=makeref('product.pricelist', pricelist.id),
        ),
        context=context,
    )

def makeref(model_name, identifier):
    """Return a string reference for an object in the database.

    e.g.

    >>> makeref('product.pricelist', 3)
    'product.pricelist,3'
    """
    return '%s,%d' % (model_name, identifier)


def get_field_id(cr, registry, uid, model_name, field_name, context=None):
    """Return the id for a model field's record in the Odoo database.
    """
    return get_exactly_one_id(
        registry['ir.model.fields'], cr, uid,
        [
            ('model', '=', model_name),
            ('name', '=', field_name),
        ],
        context=context,
    )


def select_sale_user_level(cr, registry, uid, user, level, context=None):
    """Set user's access level for the Sale application.

    Handles the difference in group names between if the 'crm' module is installed
    or not.

    user: User object to modify
    level: The level according to the 'sale' module
        either 'See all Leads', 'See Own Leads', 'Manager' or False
    """
    crm_perm_map = {
        False: False,
        'See all Leads': 'User: All Leads',
        'See Own Leads': 'User: Own Leads Only',
        'Manager': 'Manager',
    }

    try:
        _logger.debug('select_sale_user_level: Trying level=%r' % (level,))
        select_user_levels(cr, registry, uid,
            user=user,
            changes={'Sales': level},
            context=context.copy(),
        )
    except NoRecordsError, exc:
        _logger.debug('select_sale_user_level: Caught NoRecordsError in select_user_levels: %s' % (exc,))
        crm_level = crm_perm_map[level]
        _logger.debug('select_sale_user_level: Trying level=%r instead' % (crm_level,))
        select_user_levels(cr, registry, uid,
            user=user,
            changes={'Sales': crm_level},
            context=context.copy(),
        )


def select_user_levels(cr, registry, uid, user, changes, context=None):
    """Set access levels for applications for the given user.

    This is for filling in the items with drop-down boxes under the
    'Application' header on the user Access Rights tab.

    user: User object to modify
    changes: Dictionary mapping Category Name: (Group Name or False)

    e.g.
    
        select_user_level(cr, registry, SUPERUSER_ID, admin_user,
            changes={
                'Accounting & Finance': 'Financial Manager',
                'Administration': False,
            },
            context=context.copy(),
        )

    
    """
    res_users = registry['res.users']

    is_user_level_field = lambda f: f.startswith('sel_groups_')
    user_fields = res_users.fields_get(cr, uid, context=context)
    level_fields = filter(is_user_level_field, user_fields.keys())

    category_field_map = {
        user_fields[field]['string']: field
        for field in level_fields
    }

    field_changes = {
        category_field_map[category]: _app_group_id(cr, registry, uid, category, group, context)
        for category, group in changes.items()
    }

    user.write(field_changes, context=context)


def set_user_access_rights(cr, registry, uid, user, changes, context=None):
    """Tick/untick user's technical settings.

    user: User object to modify
    changes: List of tuples [('Category Name', 'Group Name', True or False), ...]

    e.g.
        set_user_group_flags(cr, registry, SUPERUSER_ID, admin_user,
            changes=[
                ('Technical Settings', 'Addresses in Sales Orders', True),
                ('Usability', 'Technical Settings', True),
            ],
            context=context.copy(),
        )

    """
    group_field = lambda gid: 'in_group_%d' % (gid,)
    field_changes = {
        group_field(_app_group_id(cr, registry, uid, category, group, context)): ticked
        for (category, group, ticked) in changes
    }
    user.write(field_changes, context=context)

def _app_group_id(cr, registry, uid, category_name, group_name, context=None):
    if group_name:
        return get_exactly_one_id(registry['res.groups'], cr, uid,
            [
                ('category_id.name', '=', category_name),
                ('name', '=', group_name),
            ],
            context=context,
        )
    else:
        return False

class WrongNumberOfRecordsError(Exception):
    pass

class TooManyRecordsError(WrongNumberOfRecordsError):
    pass

class NoRecordsError(WrongNumberOfRecordsError):
    pass

def get_exactly_one_id(model, cr, uid, domain, context=None):
    """Return one record id matching the domain.  Raise if any other number is found.

    Raises TooManyRecordsError if more than one record is found.
    Raises NoRecordsError if no records are found.
    """
    retrieved_id = get_maybe_id(model, cr, uid, domain, context=context)
    if retrieved_id is None:
        raise NoRecordsError("No records matching %r" % domain)
    else:
        return retrieved_id


def get_maybe_id(model, cr, uid, domain, context=None):
    """Return single record id or None matching the domain.

    Raises TooManyRecordsError if more than one record is found.
    """
    ids = model.search(cr, uid, domain, context=context)
    if len(ids) > 1:
        raise TooManyRecordsError("More than one record matching %r" % domain)
    elif len(ids) == 0:
        return None
    else:
        return ids[0]


def refgetter(cr, registry, uid):
    """DEPRECATED Return a function with simplified interface to get references.

    cr: Cursor
    registry: Registry object
    uid: Numeric id of the user to fetch the object as (usually openerp.SUPERUSER_ID)

    Returns a function that takes:

        module: The module bit of the id (the bit before the dot)
        xmlid: The bit after the dot

    and returns the object with XMLID = 'module.xmlid'.

    The purpose of this function is to make a function that's short and
    succinct to call, because you'll be using it a lot in a
    post_init_hook, by closing on the arguments that will remain the same.
    """
    _logger.warn("refgetter: DEPRECATED: Please use xmlid method from an instance of the Lookup class instead")
    return Lookup(cr=cr, registry=registry, uid=uid).xmlid

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
