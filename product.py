#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from lxml import objectify
from trytond.pool import Pool, PoolMeta
from decimal import Decimal
from trytond.modules.prestashop.tools import base_price_without_tax
from trytond.transaction import Transaction

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    __name__ = "product.product"

    @classmethod
    def prestashop_template_dict2vals(self, shop, values):
        '''
        Convert Prestashop values to Template
        :param shop: obj
        :param values: xml obj
        return dict
        '''
        pool = Pool()
        PrestashopAppLanguage = pool.get('prestashop.app.language')
        PrestashopRuleTax = pool.get('prestashop.rule.tax')

        langs = PrestashopAppLanguage.search([('default', '=', True)])
        if langs:
            lang = langs[0].website_language.prestashop_id
        else:
            lang = 1  # Force lang ID 1

        app = shop.prestashop_website.prestashop_app

        for value in values:
            # calculate price without tax (first tax in default taxes app)
            # because prestashop price is with tax and do not have
            # price without taxes (calculate)
            price = Decimal(
                getattr(value, 'price', False) and value.price.pyval or 1.0
                ).quantize(Decimal('.01'))

            # default tax: search tax by country or default tax app
            default_tax = None
            rule_taxes = PrestashopRuleTax.search([
                ('prestashop_app', '=', app),
                ('id_tax_rules_group', '=', '%s' % value.id_tax_rules_group),
                ('country', '=', shop.esale_country),
                ], limit=1)
            if rule_taxes:
                rule_tax, = rule_taxes
                default_tax = rule_tax.prestashop_tax.tax
            if not default_tax:
                taxes = app.default_taxes
                if taxes:
                    default_tax, = taxes

            if default_tax:
                rate = default_tax.rate
                price = base_price_without_tax(price, rate)

            vals = {
                'name': '%s' % value.name.language[lang].pyval,
                'list_price': price,
                'cost_price': Decimal(
                    value.wholesale_price.pyval).quantize(Decimal('.01')),
                }
            return vals
        return {}

    @classmethod
    def prestashop_product_dict2vals(self, shop, values):
        '''
        Convert Prestashop values to Product
        :param shop: obj
        :param values: xml obj
        return dict
        '''

        for value in values:
            if getattr(value, 'reference', False):
                vals = {
                    'code': '%s' % value.reference.pyval,
                    }
                return vals
        return {}

    @classmethod
    def prestashop_product_shops(cls, products, app):
        '''
        Get sale shops (websites)
        :param app: obj
        :param products: list
        return shops (list)
        '''
        pool = Pool()
        PrestashopWebsite = pool.get('prestashop.website')
        ExternalReferential = pool.get('prestashop.external.referential')

        shops = []
        websites = []
        for product in products:
            website_ref = ExternalReferential.get_pts2try(app,
            'prestashop.website', product.id_shop_default.pyval)
            websites.append(website_ref.try_id)
        if websites:
            prestashop_websites = PrestashopWebsite.browse(websites)
            for website in prestashop_websites:
                if website.sale_shop:
                    shops.append(website.sale_shop[0].id)

        return shops

    @classmethod
    def prestashop_product_esale_taxes(self, app, products, tax_include=False):
        '''
        Get customer taxes and list price and cost price (with or without tax)
        :param app: obj
        :param products: list
        :param tax_include: bool
        return customer_taxes (list), list_price, cost_price
        '''
        pool = Pool()
        PrestashopTax = pool.get('prestashop.tax')

        customer_taxes = []
        list_price = None
        cost_price = None

        for product in products:
            tax_id = '%s' % product.id_tax_rules_group.pyval
            if tax_id:
                taxes = PrestashopTax.search([
                    ('prestashop_app', '=', app.id),
                    ('tax_id', '=', tax_id),
                    ], limit=1)
                if taxes:
                    customer_taxes.append(taxes[0].tax.id)
                    if tax_include:
                        price = product.get('price')
                        rate = taxes[0].tax.rate
                        base_price = base_price_without_tax(price, rate)
                        list_price = base_price
                        cost_price = base_price

            if not customer_taxes and app.default_taxes:
                for tax in app.default_taxes:
                    customer_taxes.append(tax.id)
                if tax_include:
                    # Get first tax to get base price -not all default taxes-
                    price = Decimal(product.get('price'))
                    rate = app.default_taxes[0].rate
                    base_price = base_price_without_tax(price, rate)
                    list_price = base_price
                    cost_price = base_price

        return customer_taxes, list_price, cost_price

    @classmethod
    def create_product_prestashop(cls, shop, code):
        '''
        Get Prestashop product info and create
        :param shop: obj
        :param code: str
        return obj
        '''
        pool = Pool()
        Template = pool.get('product.template')

        app = shop.prestashop_website.prestashop_app
        with Transaction().set_context({
                'prestashop_uri': shop.uri
                }):
            client = app.get_prestashop_client()
        tax_include = shop.esale_tax_include

        products = client.products.get_list(filters={'reference': '%s' % code},
            display='full')

        if products:
            tvals = cls.prestashop_template_dict2vals(shop, products)
            pvals = cls.prestashop_product_dict2vals(shop, products)
        elif code.startswith('payment'):
            tvals = {
                'name': code.split('_')[1],
                'list_price': Decimal('1.0').quantize(Decimal('.01')),
                'cost_price': Decimal('1.0').quantize(Decimal('.01')),
                }
            pvals = {
                'code': '%s' % code,
                }

        tvals['shops'] = [('add', [shop])]

        # Taxes and list price and cost price with or without taxes
        customer_taxes, list_price, cost_price = (
            cls.prestashop_product_esale_taxes(app, products, tax_include))
        if customer_taxes:
            tvals['customer_taxes'] = [('add', customer_taxes)]
        if list_price:
            tvals['list_price'] = list_price
        if cost_price:
            tvals['cost_price'] = cost_price

        return Template.create_esale_product(shop, tvals, pvals)
