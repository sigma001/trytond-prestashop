#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from lxml.etree import XMLSyntaxError
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from requests import exceptions
from decimal import Decimal
import logging

__all__ = ['PrestashopApp', 'PrestashopWebsite', 'PrestashopWebsiteLanguage',
    'PrestashopCustomerGroup', 'PrestashopState',
    'PrestashopAppCustomer', 'PrestashopShopStatus',
    'PrestashopAppCountry', 'PrestashopAppLanguage',
    'PrestashopTaxRulesGroup', 'PrestashopTax', 'PrestashopRuleTax',
    'PrestashopAppDefaultTax', 'PrestashopApp2']
__metaclass__ = PoolMeta

try:
    from pystashop import PrestaShopWebservice, PrestaShopWebserviceException
except ImportError:
    message = 'Unable to import Prestashop: pip install pystashop'
    logging.getLogger('prestashop').error(message)
    raise Exception(message)


class PrestashopApp(ModelSQL, ModelView):
    'Prestashop APP'
    __name__ = 'prestashop.app'
    name = fields.Char('Name', required=True)
    uri = fields.Char('URI', required=True,
        help='URI Prestashop App. http://yourprestashop.com/ (with / at end)')
    key = fields.Char('Key', required=True)
    prestashop_websites = fields.One2Many('prestashop.website',
        'prestashop_app', 'Websites', readonly=True)
    prestashop_countries = fields.Many2Many('prestashop.app-country.country',
        'app', 'country', 'Countries')
    prestashop_states = fields.One2Many('prestashop.state', 'prestashop_app',
        'States', readonly=True)
    prestashop_tax_rules_group = fields.One2Many('prestashop.tax.rules.group',
        'prestashop_app', 'Group Taxes')
    default_taxes = fields.Many2Many('prestashop.app-default.taxes',
        'prestashop_app', 'tax', 'Default Taxes', domain=[
        ('group.kind', 'in', ['sale', 'both']),
        ], help='Default taxes when create a product')
    debug = fields.Boolean('Debug')
    languages = fields.One2Many('prestashop.app.language', 'app', 'Languages')

    @classmethod
    def __setup__(cls):
        super(PrestashopApp, cls).__setup__()
        cls._error_messages.update({
            'connection_successfully': 'Successfully Prestashop connection!',
            'connection_website': 'Successfully Prestashop connection '
                'but you need to configure your Prestashop first.',
            'connection_error': 'Prestashop connection failed!',
            'sale_configuration': 'Add default values in configuration sale!',
            'wrong_url_n_key': 'Connection Failed! Please check URL and Key.',
            'wrong_url': 'Connection Failed! The URL provided is wrong.',
            'add_countries': 'Add countries in Prestashop App',
        })
        cls._buttons.update({
                'test_connection': {},
                'core_store': {},
                'core_customer_group': {},
                'core_taxes': {},
                'core_states': {},
                })

    def get_prestashop_client(self):
        '''
        Authenticated Prestashop client
        :return: object
        '''
        if Transaction().context.get('prestashop_uri'):
            uri = Transaction().context.get('prestashop_uri')
        else:
            uri = self.uri
        key = self.key

        if not all([uri, key]):
            self.raise_user_error('prestashop_settings_missing')

        return PrestaShopWebservice(uri, key)

    @classmethod
    @ModelView.button
    def test_connection(cls, apps):
        'Test connection to Prestashop APP'
        for app in apps:
            try:
                client = app.get_prestashop_client()
                client.shops.get_list()
            except PrestaShopWebserviceException:
                cls.raise_user_error('wrong_url_n_key')
            except (exceptions.MissingSchema, exceptions.ConnectionError):
                cls.raise_user_error('wrong_url')
            cls.raise_user_error('connection_successfully')

    @classmethod
    def core_store_website(cls, app, client):
        '''
        Create website and sale shop
        return list website ids
        '''
        pool = Pool()
        ExternalReferential = pool.get('prestashop.external.referential')
        PrestashopWebsite = pool.get('prestashop.website')
        SaleShop = pool.get('sale.shop')

        sale_conf = SaleShop.sale_configuration()
        if not sale_conf.sale_warehouse:
            cls.raise_user_error('sale_configuration')

        websites = []
        for prestashop in client.shops.get_list(display='full'):
            website_ref = ExternalReferential.get_pts2try(app,
                'prestashop.website', prestashop.id.pyval)

            if not website_ref:
                values = {
                    'name': prestashop.name.pyval,
                    'prestashop_app': app.id,
                    }
                website = PrestashopWebsite.create([values])[0]
                websites.append(website)
                ExternalReferential.set_external_referential(app,
                    'prestashop.website', website.id, prestashop.id.pyval)
                logging.getLogger('prestashop').info(
                    'Create Website. Prestashop APP: %s. '
                    'Prestashop website ID %s' % (
                        app.name,
                        prestashop.id.pyval,
                        ))

                '''Sale Shop'''
                values = {
                    'name': prestashop.name.pyval,
                    'warehouse': sale_conf.sale_warehouse.id,
                    'price_list': sale_conf.sale_price_list.id,
                    'esale_available': True,
                    'esale_shop_app': 'prestashop',
                    'esale_delivery_product':
                        sale_conf.sale_delivery_product.id,
                    'esale_discount_product':
                        sale_conf.sale_discount_product.id,
                    'esale_uom_product': sale_conf.sale_uom_product.id,
                    'esale_currency': sale_conf.sale_currency.id,
                    'esale_category': sale_conf.sale_category.id,
                    'payment_term': sale_conf.sale_payment_term.id,
                    'prestashop_website': website.id,
                    'uri': app.uri,
                }
                shop = SaleShop.create([values])[0]
                ExternalReferential.set_external_referential(app,
                    'sale.shop', shop.id, website.id)
                logging.getLogger('prestashop').info(
                    'Create Sale Shop. Prestashop APP: %s. Website %s - %s. '
                    'Sale Shop ID %s' % (
                        app.name,
                        website.id,
                        prestashop.id.pyval,
                        shop.id,
                        ))
                logging.getLogger('prestashop').warning(
                    'Remember add URI in Prestashop Shop and add shops in '
                    'user preferences')
            else:
                logging.getLogger('prestashop').warning(
                    'Website exists. Prestashop APP: %s. '
                    'Prestashop Website ID: %s. '
                    'Not create' % (
                        app.name,
                        prestashop.id.pyval,
                        ))
                websites.append(PrestashopWebsite(website_ref.try_id))
        return websites

    def core_store_website_language(self, websites, client):
        pool = Pool()
        WebsiteLanguage = pool.get('prestashop.website.language')
        languages = client.languages.get_list(display='full')
        if not languages and self.prestashop_websites:
            for website in self.prestashop_websites:
                for shop in website.sale_shop:
                    with Transaction().set_context({
                            'prestashop_uri': shop.uri
                            }):
                        client = self.get_prestashop_client()
                    try:
                        languages.extend(client.languages.get_list(
                                display='full'))
                    except XMLSyntaxError as e:
                        logging.getLogger('prestashop').warning(
                            'Error importing languages of shop %s: %s'
                            % (shop.uri, e))
                        continue
        website_languages = WebsiteLanguage.search([
                ('prestashop_website', 'in', websites),
                ])
        langs = [wl.prestashop_id for wl in website_languages]
        values = [{
                'prestashop_id': l.id.pyval,
                'name': l.name.pyval,
                'code': l.language_code.pyval,
                'prestashop_website': w.id,
                }
            for l in languages
            for w in websites
            if (l.id.pyval not in langs)
            ]
        WebsiteLanguage.create(values)

    @classmethod
    @ModelView.button
    def core_store(cls, apps):
        '''
        Import Store Prestashop to Tryton
        Create new stores; not update or delete
        - Websites
        - Languages
        '''
        websites = []
        for app in apps:
            client = app.get_prestashop_client()
            websites.extend(cls.core_store_website(app, client))
            app.core_store_website_language(websites, client)

    @classmethod
    @ModelView.button
    def core_customer_group(cls, apps):
        '''
        Import Prestashop Group to Tryton
        Only create new values if not exist; not update or delete
        '''
        pool = Pool()
        PrestashopAppLanguage = pool.get('prestashop.app.language')
        ExternalReferential = pool.get('prestashop.external.referential')
        CustomerGroup = pool.get('prestashop.customer.group')

        for app in apps:
            langs = PrestashopAppLanguage.search([('default', '=', True)])
            if not langs:
                logging.getLogger('prestashop').error(
                    'Configure Prestashop %s APP Languages' % (app.name))
                continue

            lang = langs[0].website_language.prestashop_id

            for website in app.prestashop_websites:
                for shop in website.sale_shop:
                    with Transaction().set_context({
                            'prestashop_uri': shop.uri
                            }):
                        client = app.get_prestashop_client()
                    try:
                        prestashop_groups = client.groups.get_list(
                            display='full')
                    except Exception as e:
                        logging.getLogger('prestashop').info(
                            'An exception occurred when importing groups: '
                            '%s' % (e))
                        continue
                    customer_groups = CustomerGroup.search([
                            ('prestashop_app', '=', app.id),
                            ])
                    customer_groups = [cg.customer_group
                        for cg in customer_groups]
                    values = [{
                            'name': g.name.language[lang].pyval,
                            'customer_group': g.id.pyval,
                            'prestashop_app': app.id,
                            }
                        for g in prestashop_groups
                        if g.id.pyval not in customer_groups
                        ]
                    customer_groups = CustomerGroup.create(values)
                    prestashop_groups = {g.id: p.id.pyval
                        for g in customer_groups
                        for p in prestashop_groups
                        if g.customer_group == p.id.pyval
                        }
                    for customer_group in customer_groups:
                        ExternalReferential.set_external_referential(
                            app,
                            'prestashop.customer.group',
                            customer_group.id,
                            prestashop_groups[customer_group.id])
                        logging.getLogger('prestashop').info(
                            'Create Group %s. Prestashop APP %s.ID %s' % (
                                prestashop_groups[customer_group.id],
                                app.name,
                                customer_group.id,
                                ))

    @classmethod
    @ModelView.button
    def core_taxes(self, apps):
        '''
        Import Prestashop Taxes to Tryton
        Only create new values if not exist; not update or delete
        '''
        pool = Pool()
        AccountTax = pool.get('account.tax')
        Tax = pool.get('prestashop.tax')
        RuleTax = pool.get('prestashop.rule.tax')
        TaxRulesGroup = pool.get('prestashop.tax.rules.group')
        Subdivision = pool.get('country.subdivision')
        Country = pool.get('country.country')

        for app in apps:
            to_create_taxes = []
            to_create_rules = []
            to_create_groups = []

            if not app.prestashop_countries:
                self.raise_user_error('add_countries')

            for website in app.prestashop_websites:
                for shop in website.sale_shop:
                    with Transaction().set_context({
                            'prestashop_uri': shop.uri
                            }):
                        client = app.get_prestashop_client()

                    ptaxes = client.taxes.get_list(filters={}, display='full')
                    prules = client.tax_rules.get_list(filters={},
                        display='full')
                    pgrups = client.tax_rule_groups.get_list(filters={},
                        display='full')
                    pcountries = client.countries.get_list(filters={},
                        display='full')
                    pstates = client.states.get_list(filters={},
                        display='full')

                    # Rules Group
                    for grup in pgrups:
                        groups = TaxRulesGroup.search([
                            ('prestashop_app', '=', app),
                            ('tax_rules_group_id', '=', '%s' % grup.id.pyval),
                            ], limit=1)
                        if groups:
                            continue

                        to_create_groups.append({
                            'name': '%s' % grup.name.pyval,
                            'tax_rules_group_id': '%s' % grup.id.pyval,
                            'prestashop_app': app,
                            })
                    if to_create_groups:
                        TaxRulesGroup.create(to_create_groups)
                    Transaction().cursor.commit()

                    # Taxes
                    for tax in ptaxes:
                        ptaxes = Tax.search([
                            ('prestashop_app', '=', app),
                            ('tax_id', '=', '%s' % tax.id.pyval),
                            ], limit=1)
                        if ptaxes:
                            continue

                        rate = (Decimal(tax.rate.pyval) / 100).quantize(
                            Decimal('.01'))

                        account_taxes = AccountTax.search([
                            ('rate', '=', rate),
                            ('group.kind', 'in', ['sale', 'both']),
                            ], limit=1)
                        if account_taxes:
                            account_tax, = account_taxes
                        else:
                            account_tax = None
                            logging.getLogger('prestashop').warning('Not found'
                                ' tax rate %s. Remember to select a tax' %
                                tax.rate.pyval)

                        to_create_taxes.append({
                            'prestashop_app': app,
                            'name': '%s' % tax.name.language[0].pyval,
                            'tax_id': '%s' % tax.id.pyval,
                            'tax': account_tax,
                            })
                    if to_create_taxes:
                        Tax.create(to_create_taxes)
                    Transaction().cursor.commit()

                    # Rules
                    for rule in prules:
                        prules = RuleTax.search([
                            ('prestashop_app', '=', app),
                            ('rule_tax_id', '=', '%s' % rule.id.pyval),
                            ], limit=1)
                        if prules:
                            continue

                        papptaxes = Tax.search([
                            ('prestashop_app', '=', app),
                            ('tax_id', '=', '%s' % rule.id_tax.pyval),
                            ], limit=1)
                        if not papptaxes:
                            logging.getLogger('prestashop').warning(
                                'Not found tax %s in tax rule %s' %
                                (rule.id_tax.pyval, rule.id.pyval))
                            continue
                        papptax, = papptaxes

                        pgroups = TaxRulesGroup.search([
                            ('prestashop_app', '=', app),
                            ('tax_rules_group_id', '=', '%s' %
                                rule.id_tax_rules_group.pyval),
                            ], limit=1)
                        if not pgroups:
                            logging.getLogger('prestashop').warning(
                                'Not found rules group tax %s in tax rule %s' %
                                (rule.id_tax_rules_group.pyval, rule.id.pyval))
                            continue
                        pgroup, = pgroups

                        subdivision = None
                        if rule.id_state.pyval:
                            for s in pstates:
                                id_state = '%s' % s.id.pyval
                                id_state_rule = '%s' % rule.id_state.pyval
                                if id_state == id_state_rule:
                                    subdivisions = Subdivision.search([
                                        ('name', '=', '%s' % s.name.pyval),
                                        ], limit=1)
                                    if subdivisions:
                                        subdivision, = subdivisions

                        country = None
                        if rule.id_country.pyval:
                            for c in pcountries:
                                id_country = '%s' % c.id.pyval
                                id_country_rule = '%s' % rule.id_country.pyval
                                if id_country == id_country_rule:
                                    countries = Country.search([
                                        ('code', '=', '%s' % c.iso_code.pyval),
                                        ], limit=1)
                                    if countries:
                                        country, = countries
                        if not country:
                            logging.getLogger('prestashop').warning('Not found'
                                ' country %s in tax rule %s. Add default '
                                'country (edit)' %
                                (rule.id_country.pyval, rule.id.pyval))
                            country = app.prestashop_countries[0]

                        to_create_rules.append({
                            'prestashop_app': app,
                            'rule_tax_id': '%s' % rule.id.pyval,
                            'id_tax_rules_group': ('%s' %
                                rule.id_tax_rules_group.pyval),
                            'prestashop_tax': papptax.id,
                            'country': country,
                            'subdivision': subdivision,
                            'zip_from': '%s' % rule.zipcode_from.pyval,
                            'zip_to': '%s' % rule.zipcode_to.pyval,
                            'group': pgroup,
                            })

                    if to_create_rules:
                        RuleTax.create(to_create_rules)
            Transaction().cursor.commit()

    @classmethod
    @ModelView.button
    def core_states(self, apps):
        '''
        Import Prestashop States to Tryton
        Only create new values if not exist; not update or delete
        '''
        pool = Pool()
        PrestashopState = pool.get('prestashop.state')
        CountrySubdivision = pool.get('country.subdivision')

        for app in apps:
            to_create = []
            if not app.prestashop_countries:
                logging.getLogger('prestashop').info(
                    'Add some countries to import Prestahop States')
                continue

            client = app.get_prestashop_client()

            codes = []
            for country in app.prestashop_countries:
                codes.append(country.code)

            countries = client.countries.get_list(
                filters={'iso_code': '|'.join(codes)},
                display='full')
            if not countries:
                logging.getLogger('prestashop').info(
                    'Not found countries with code %s in Prestashop' % codes)
                continue

            countries_ids = [str(c.id) for c in countries]
            states = client.states.get_list(
                filters={'id_country': '|'.join(countries_ids)},
                display='full')

            for state in states:
                state_id = state.id.pyval
                state_name = state.name.pyval
                state_code = state.iso_code.pyval

                pst_states = PrestashopState.search([
                    ('state_id', '=', state_id),
                    ('prestashop_app', '=', app.id)
                    ], limit=1)
                if pst_states:
                    logging.getLogger('prestashop').warning(
                        'Prestashop %s. State %s already exists.' % (
                            app.name, state_name))
                    continue

                subdivisions = CountrySubdivision.search([
                    ('code', '=', state_code)
                    ], limit=1)
                values = {}
                if subdivisions:
                    values['subdivision'] = subdivisions[0]
                values['prestashop_app'] = app.id
                values['code'] = state_code
                values['state_id'] = state_id
                values['name'] = state_name
                to_create.append(values)

            if to_create:
                PrestashopState.create(to_create)
                logging.getLogger('prestashop').info(
                    'Prestashop APP %s. Create total %s states' % (
                    app.name, len(to_create)))


class PrestashopWebsite(ModelSQL, ModelView):
    'Prestashop Website'
    __name__ = 'prestashop.website'
    name = fields.Char('Name', required=True)
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True)
    sale_shop = fields.One2Many('sale.shop', 'prestashop_website', 'Sale Shop')


class PrestashopWebsiteLanguage(ModelSQL, ModelView):
    'Prestashop Website Languages'
    __name__ = 'prestashop.website.language'
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    prestashop_website = fields.Many2One('prestashop.website',
        'Prestashop Website')
    prestashop_id = fields.Integer("Prestashop ID")


class PrestashopCustomerGroup(ModelSQL, ModelView):
    'Prestashop Customer Group'
    __name__ = 'prestashop.customer.group'
    name = fields.Char('Name', required=True, readonly=True)
    customer_group = fields.Integer('Customer Group ID',
        required=True, readonly=True)
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        readonly=True)


class PrestashopState(ModelSQL, ModelView):
    'Prestashop State'
    __name__ = 'prestashop.state'
    name = fields.Char('Name', readonly=True)
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True, readonly=True)
    subdivision = fields.Many2One('country.subdivision', 'Subdivision')
    code = fields.Char('Code', required=True, readonly=True)
    state_id = fields.Integer('State ID', required=True, readonly=True)


class PrestashopAppCustomer(ModelSQL, ModelView):
    'Prestashop App Customer'
    __name__ = 'prestashop.app.customer'
    party = fields.Many2One('party.party', 'Party', required=True)
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True)
    prestashop_customer_group = fields.Many2One('prestashop.customer.group',
        'Customer Group', required=True)  # TODO: Domain
    prestashop_emailid = fields.Char('Email Address', required=True,
        help="Prestashop uses this email ID to match the customer.")
    prestashop_vat = fields.Char('Prestashop VAT', readonly=True,
        help=('To be able to receive customer VAT number you must set '
        'it in Prestashop Admin Panel, menu System / Configuration / '
        'Client Configuration / Name and Address Options.'))


class PrestashopShopStatus(ModelSQL, ModelView):
    'Prestashop Shop Status'
    __name__ = 'prestashop.shop.status'
    status = fields.Char('Status', required=True,
        help='Code Status (example, cancel, pending, processing,..)')
    shop = fields.Many2One('sale.shop', 'Shop', required=True)
    confirm = fields.Boolean('Confirm',
        help=('Confirm order. Sale Order change state draft to done, '
        'and generate picking and/or invoice automatlly'))
    cancel = fields.Boolean('Cancel',
        help='Sale Order change state draft to cancel')
    paidinweb = fields.Boolean('Paid in web',
        help='Sale Order is paid online (virtual payment)')


class PrestashopAppCountry(ModelSQL, ModelView):
    'Prestashop APP - Country'
    __name__ = 'prestashop.app-country.country'
    _table = 'prestashop_app_country_country'
    app = fields.Many2One('prestashop.app', 'Prestashop APP',
        ondelete='RESTRICT', select=True, required=True)
    country = fields.Many2One('country.country', 'Country', ondelete='CASCADE',
        select=True, required=True)


class PrestashopAppLanguage(ModelSQL, ModelView):
    'Prestashop APP - Language'
    __name__ = 'prestashop.app.language'
    _rec_name = 'lang'
    app = fields.Many2One('prestashop.app', 'Prestashop APP',
        ondelete='CASCADE', select=True, required=True)
    lang = fields.Many2One('ir.lang', 'Language', required=True)
    website_language = fields.Many2One('prestashop.website.language',
        'Website Language', required=True,
        domain=[('prestashop_website.prestashop_app', '=', Eval('app'))],
        depends=['app'])
    default = fields.Boolean('Default',
        help='Language is default Language in Prestashop')


class PrestashopTaxRulesGroup(ModelSQL, ModelView):
    'Prestashop Tax Rules Group'
    __name__ = 'prestashop.tax.rules.group'
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True)
    prestashop_rule_taxes = fields.One2Many('prestashop.rule.tax', 'group',
        'Prestashop Rule Taxes')
    tax_rules_group_id = fields.Char('Prestashop Tax Rules Group',
        required=True)
    name = fields.Char('name', required=True)


class PrestashopTax(ModelSQL, ModelView):
    'Prestashop Tax'
    __name__ = 'prestashop.tax'
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True)
    name = fields.Char('Name', required=True, help='Prestashop Tax Name')
    tax_id = fields.Char('Prestashop Tax', required=True,
        help='Prestashop Tax ID')
    tax = fields.Many2One('account.tax', 'Tax', domain=[
        ('group.kind', 'in', ['sale', 'both']),
        ], help='Add tax related to Prestashop tax (required)')


class PrestashopRuleTax(ModelSQL, ModelView):
    'Prestashop Rule Tax'
    __name__ = 'prestashop.rule.tax'
    _rec_name = 'prestashop_tax'
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True)
    rule_tax_id = fields.Char('Prestashop Rule Tax', required=True,
        help='Prestashop Rule Tax ID')
    id_tax_rules_group = fields.Char('Prestashop Rule Groups Tax',
        required=True, help='Prestashop Rule Groups Tax ID')
    prestashop_tax = fields.Many2One('prestashop.tax', 'Prestashop Tax',
        required=True)
    country = fields.Many2One('country.country', 'Country', required=True)
    subdivision = fields.Many2One('country.subdivision', 'Subdivision')
    zip_from = fields.Char('Zip From')
    zip_to = fields.Char('Zip To')
    group = fields.Many2One('prestashop.tax.rules.group', 'Group',
        ondelete='CASCADE', select=True)


class PrestashopAppDefaultTax(ModelSQL):
    'Prestashop APP - Customer Tax'
    __name__ = 'prestashop.app-default.taxes'
    _table = 'prestashop_app_default_taxes_rel'
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop APP',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            required=True)


class PrestashopApp2:
    __name__ = 'prestashop.app'
    customer_default_group = fields.Many2One('prestashop.customer.group',
        'Customer Group', domain=[('prestashop_app', '=', Eval('id'))],
        depends=['id'],
        help='Default Customer Group')
