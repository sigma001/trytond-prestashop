#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from requests import exceptions

import logging

__all__ = ['PrestashopApp', 'PrestashopWebsite', 'PrestashopWebsiteLanguage',
    'PrestashopCustomerGroup','PrestashopRegion',
    'PrestashopAppCustomer','PrestashopShopStatus',
    'PrestashopAppCountry', 'PrestashopAppLanguage',
    'PrestashopTax', 'PrestashopAppDefaultTax',
    'PrestashopApp2']
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
    prestashop_websites = fields.One2Many('prestashop.website', 'prestashop_app',
        'Websites', readonly=True)
    prestashop_countries = fields.Many2Many('prestashop.app-country.country', 
        'app', 'country', 'Countries')
    prestashop_regions = fields.One2Many('prestashop.region', 'prestashop_app',
        'Regions', readonly=True)
    product_options = fields.Boolean('Product Options',
        help='Orders with product options. Split reference order line by "-"')
    prestashop_taxes = fields.One2Many('prestashop.tax', 'prestashop_app',
        'Taxes')
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
        })
        cls._buttons.update({
                'test_connection': {},
                'core_store': {},
                'core_customer_group': {},
                'core_regions': {},
                })

    def get_prestashop_client(self):
        '''Authenticated Prestashop client

        :return: object
        '''
        if not all([self.uri, self.key]):
            self.raise_user_error('prestashop_settings_missing')
        return PrestaShopWebservice(self.uri, self.key)

    @classmethod
    @ModelView.button
    def test_connection(cls, apps):
        '''Test connection to Prestashop APP'''
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
        PrestashopExternalReferential = pool.get('prestashop.external.referential')
        PrestashopWebsite = pool.get('prestashop.website')
        SaleShop = pool.get('sale.shop')

        sale_configuration = SaleShop.sale_configuration()
        if not sale_configuration.sale_warehouse:
            cls.raise_user_error('sale_configuration')

        websites = []
        for prestashop in client.shops.get_list(display='full'):
            website_ref = PrestashopExternalReferential.get_pts2try(app,
                'prestashop.website', prestashop.id.pyval)

            if not website_ref:
                values = {
                    'name': prestashop.name.pyval,
                    'prestashop_app': app.id,
                    }
                website = PrestashopWebsite.create([values])[0]
                websites.append(website)
                PrestashopExternalReferential.set_external_referential(app,
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
                    'warehouse': sale_configuration.sale_warehouse.id,
                    'price_list': sale_configuration.sale_price_list.id,
                    'esale_available': True,
                    'esale_shop_app': 'prestashop',
                    'esale_delivery_product': sale_configuration.sale_delivery_product.id,
                    'esale_discount_product': sale_configuration.sale_discount_product.id,
                    'esale_uom_product': sale_configuration.sale_uom_product.id,
                    'esale_currency': sale_configuration.sale_currency.id,
                    'esale_category': sale_configuration.sale_category.id,
                    'payment_term': sale_configuration.sale_payment_term.id,
                    'prestashop_website': website.id,
                }
                shop = SaleShop.create([values])[0]
                PrestashopExternalReferential.set_external_referential(app,
                    'sale.shop', shop.id, website.id)
                logging.getLogger('prestashop').info(
                    'Create Sale Shop. Prestashop APP: %s. Website %s - %s. '
                    'Sale Shop ID %s' % (
                        app.name,
                        website.id,
                        prestashop.id.pyval,
                        shop.id,
                        ))
            else:
                logging.getLogger('prestashop').warning(
                    'Website exists. Prestashop APP: %s. '
                    'Prestashop Website ID: %s. '
                    'Not create' % (
                        app.name,
                        prestashop.id.pyval,
                        ))
        return websites

    @classmethod
    def core_store_website_language(cls, websites, client):
        pool = Pool()
        WebsiteLanguage = pool.get('prestashop.website.language')
        languages = client.languages.get_list(display='full')
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
        cls.core_store_website_language(websites, client)

    @classmethod
    @ModelView.button
    def core_customer_group(self, apps):
        """Import Prestashop Group to Tryton
        Only create new values if not exist; not update or delete
        """
        pool = Pool()
        PrestashopExternalReferential = pool.get('prestashop.external.referential')
        PrestashopCustomerGroup = pool.get('prestashop.customer.group')

        for app in apps:
            # TODO: call prestashop groups
            with CustomerGroup(app.uri,app.username,app.password) as \
                    customer_group_api:
                for customer_group in customer_group_api.list():
                    groups = PrestashopCustomerGroup.search([
                        ('customer_group', '=', customer_group[
                                'customer_group_id'
                                ]),
                        ('prestashop_app', '=', app.id),
                        ], limit=1)
                    if groups:
                        logging.getLogger('prestashop').warning(
                            'Group %s already exists. Prestashop APP: %s: ' + \
                            'Not created' % (
                            customer_group['customer_group_code'],
                            app.name,
                            ))
                        continue

                    values = {
                        'name': customer_group['customer_group_code'],
                        'customer_group': customer_group['customer_group_id'],
                        'prestashop_app': app.id,
                    }
                    prestashop_customer_group = PrestashopCustomerGroup.create([values])[0]
                    PrestashopExternalReferential.set_external_referential(
                        app,
                        'prestashop.customer.group',
                        prestashop_customer_group.id,
                        customer_group['customer_group_id'])
                    logging.getLogger('prestashop').info(
                        'Create Group %s. Prestashop APP %s.ID %s' % (
                        customer_group['customer_group_code'],
                        app.name, 
                        prestashop_customer_group,
                        ))

    @classmethod
    @ModelView.button
    def core_regions(self, apps):
        """Import Prestashop Regions to Tryton
        Only create new values if not exist; not update or delete
        """
        pool = Pool()
        PrestashopRegion = pool.get('prestashop.region')
        CountrySubdivision = pool.get('country.subdivision')

        for app in apps:
            # TODO: call regions prestashop
            with Region(app.uri,app.username,app.password) as region_api:
                countries = app.prestashop_countries
                if not countries:
                    logging.getLogger('prestashop').warning('Select a countries to ' \
                        'load regions')
                    return None

                for country in countries:
                    regions = region_api.list(country.code)
                    for region in regions:
                        mag_regions = PrestashopRegion.search([
                            ('region_id','=',region['region_id']),
                            ('prestashop_app','=',app.id)
                            ], limit=1)
                        if not mag_regions: #not exists
                            subdivisions = CountrySubdivision.search([
                                ('name','ilike',region['code'])
                                ], limit=1)
                            values = {}
                            if subdivisions:
                                values['subdivision'] = subdivisions[0]
                            values['prestashop_app'] = app.id
                            values['code'] = region['code']
                            values['region_id'] = region['region_id']
                            values['name'] = region['name'] and \
                                    region['name'] or region['code']
                            mregion = PrestashopRegion.create([values])[0]
                            logging.getLogger('prestashop').info(
                                'Create region %s. Prestashop APP %s. ID %s' % (
                                region['region_id'],
                                app.name, 
                                mregion,
                                ))
                        else:
                            logging.getLogger('prestashop').warning(
                                'Region %s already exists. Prestashop %s. ' \
                                'Not created' % (
                                app.name, 
                                region['region_id'],
                                ))


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
    prestashop_website = fields.Many2One('prestashop.website', 'Prestashop Website')
    prestashop_id = fields.Integer("Prestashop ID")


class PrestashopCustomerGroup(ModelSQL, ModelView):
    'Prestashop Customer Group'
    __name__ = 'prestashop.customer.group'
    name = fields.Char('Name', required=True, readonly=True)
    customer_group = fields.Integer('Customer Group ID',
        required=True, readonly=True)
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App', readonly=True)


class PrestashopRegion(ModelSQL, ModelView):
    'Prestashop Region'
    __name__ = 'prestashop.region'
    name = fields.Char('Name', readonly=True) #Available in prestashop and Null
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True, readonly=True)
    subdivision = fields.Many2One('country.subdivision', 'Subdivision')
    code = fields.Char('Code', required=True, readonly=True)
    region_id = fields.Integer('Region ID', required=True, readonly=True)


class PrestashopAppCustomer(ModelSQL, ModelView):
    'Prestashop App Customer'
    __name__ = 'prestashop.app.customer'
    party = fields.Many2One('party.party', 'Party', required=True)
    prestashop_app = fields.Many2One('prestashop.app','Prestashop App', required=True)
    prestashop_customer_group = fields.Many2One('prestashop.customer.group','Customer Group', required=True) #TODO: Domain
    prestashop_emailid = fields.Char('Email Address', required=True,
        help="Prestashop uses this email ID to match the customer.")
    prestashop_vat = fields.Char('Prestashop VAT', readonly=True,
        help='To be able to receive customer VAT number you must set ' \
        'it in Prestashop Admin Panel, menu System / Configuration / ' \
        'Client Configuration / Name and Address Options.')


class PrestashopShopStatus(ModelSQL, ModelView):
    'Prestashop Shop Status'
    __name__ = 'prestashop.shop.status'
    status = fields.Char('Status', required=True,
        help='Code Status (example, cancel, pending, processing,..)')
    shop = fields.Many2One('sale.shop', 'Shop', required=True)
    confirm = fields.Boolean('Confirm',
        help='Confirm order. Sale Order change state draft to done, ' \
        'and generate picking and/or invoice automatlly')
    cancel = fields.Boolean('Cancel',
        help='Sale Order change state draft to cancel')
    paidinweb = fields.Boolean('Paid in web',
        help='Sale Order is paid online (virtual payment)')


class PrestashopAppCountry(ModelSQL, ModelView):
    'Prestashop APP - Country'
    __name__ = 'prestashop.app-country.country'
    _table = 'prestashop_app_country_country'
    app = fields.Many2One('prestashop.app', 'Prestashop APP', ondelete='RESTRICT',
            select=True, required=True)
    country = fields.Many2One('country.country', 'Country', ondelete='CASCADE',
            select=True, required=True)


class PrestashopAppLanguage(ModelSQL, ModelView):
    'Prestashop APP - Language'
    __name__ = 'prestashop.app.language'
    _rec_name = 'lang'
    app = fields.Many2One('prestashop.app', 'Prestashop APP', ondelete='CASCADE',
            select=True, required=True)
    lang = fields.Many2One('ir.lang', 'Language', required=True)
    website_language = fields.Many2One('prestashop.website.language', 'Website Language', required=True,
        domain=[('prestashop_website.prestashop_app', '=', Eval('app'))],
        depends=['app'])
    default = fields.Boolean('Default',
        help='Language is default Language in Prestashop')


class PrestashopTax(ModelSQL, ModelView):
    'Prestashop Tax'
    __name__ = 'prestashop.tax'
    _rec_name = 'tax'
    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App', required=True)
    tax_id = fields.Char('Prestashop Tax', required=True,
        help='Prestashop Tax ID')
    tax = fields.Many2One('account.tax', 'Tax', domain=[
        ('group.kind', 'in', ['sale', 'both']),
        ], required=True)
    sequence = fields.Integer('Sequence')

    @classmethod
    def __setup__(cls):
        super(PrestashopTax, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def default_sequence():
        return 1


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
