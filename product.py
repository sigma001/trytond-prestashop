#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from decimal import Decimal
from trytond.modules.prestashop.tools import base_price_without_tax
from pystashop import PrestaShopWebservice

import logging

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    __name__ = "product.product"

    @classmethod
    def prestashop_template_dict2vals(self, shop, values):
        '''
        Convert Prestashop values to Template
        :param shop: obj
        :param values: dict from Prestashop Product API
        return dict
        '''
        vals = {
            'name': values.get('name'),
            'list_price': Decimal(values.get('price')),
            'cost_price': Decimal(values.get('price')),
            'esale_shortdescription': values.get('short_description'),
            'esale_slug': values.get('url_key'),
            }
        return vals

    @classmethod
    def prestashop_product_dict2vals(self, shop, values):
        '''
        Convert Prestashop values to Product
        :param shop: obj
        :param values: dict from Prestashop Product API
        return dict
        '''
        vals = {
            'code': values.get('sku'),
            }
        return vals

    @classmethod
    def prestashop_product_esale_saleshops(self, app, product_info):
        '''
        Get sale shops (websites)
        :param app: object
        :product_info: dict
        return shops (list)
        '''
        pool = Pool()
        PrestashopWebsite = pool.get('prestashop.website')
        PrestashopExternalReferential = pool.get('prestashop.external.referential')

        shops = []
        websites = []
        for website in product_info.get('websites'):
            website_ref = PrestashopExternalReferential.get_pts2try(app, 
            'prestashop.website', website)
            websites.append(website_ref.try_id)
        if websites:
            prestashop_websites = PrestashopWebsite.browse(websites)
            for website in prestashop_websites:
                shops.append(website.sale_shop[0].id)

        return shops

    @classmethod
    def prestashop_product_esale_taxes(self, app, product_info, tax_include=False):
        '''
        Get customer taxes and list price and cost price (with or without tax)
        :param app: object
        :product_info: dict
        return customer_taxes (list), list_price, cost_price
        '''
        pool = Pool()
        PrestashopTax = pool.get('prestashop.tax')

        customer_taxes = []
        list_price = None
        cost_price = None

        tax_id = product_info.get('tax_class_id')
        if tax_id:
            taxs = PrestashopTax.search([
                ('prestashop_app', '=', app.id),
                ('tax_id', '=', tax_id),
                ], limit=1)
            if taxs:
                customer_taxes.append(taxs[0].tax.id)
                if tax_include:
                    price = product_info.get('price')
                    rate = taxs[0].tax.rate
                    base_price = base_price_without_tax(price, rate)
                    list_price = base_price
                    cost_price = base_price

        if not customer_taxes and app.default_taxes:
            for tax in app.default_taxes:
                customer_taxes.append(tax.id)
            if tax_include:
                # Get first tax to get base price -not all default taxes-
                price = Decimal(product_info.get('price'))
                rate = app.default_taxes[0].rate
                base_price = base_price_without_tax(price, rate)
                list_price = base_price
                cost_price = base_price

        return customer_taxes, list_price, cost_price

    @classmethod
    def create_product_prestashop(self, shop, code):
        '''
        Get Prestashop product info and create
        :param shop: obj
        :param code: str
        return obj
        '''
        Template = Pool().get('product.template')
        PrestashopExternalReferential = Pool().get('prestashop.external.referential')

        ptsapp = shop.prestashop_website.prestashop_app
        tax_include = shop.esale_tax_include

        # TODO: storeview is language. Get product default language
        store_view = ptsapp.prestashop_default_storeview or None
        if store_view:
            pts_storeview = PrestashopExternalReferential.get_try2pts(ptsapp, 
            'prestashop.storeview', store_view.id)
            store_view = pts_storeview.pts_id

        if ptsapp.product_options:
            codes = code.split('-')
            if codes:
                logging.getLogger('prestashop sale').warning(
                    'Prestashop %s. Not split product %s' % (shop.name, code))

        with ProductMgn(ptsapp.uri, ptsapp.username, ptsapp.password) as product_api:
            try:
                product_info = product_api.info(code, store_view)
            except:
                logging.getLogger('prestashop sale').error(
                    'Prestashop %s. Not found product %s' % (shop.name, code))
                return None

            tvals = self.prestashop_template_dict2vals(shop, product_info)
            pvals = self.prestashop_product_dict2vals(shop, product_info)

            #Shops - websites
            shops = self.prestashop_product_esale_saleshops(ptsapp, product_info)
            if shops:
                tvals['esale_saleshops'] = [('add', shops)]

            #Taxes and list price and cost price with or without taxes
            customer_taxes, list_price, cost_price = self.prestashop_product_esale_taxes(ptsapp, product_info, tax_include)
            if customer_taxes:
                tvals['customer_taxes'] = [('add', customer_taxes)]
            if list_price:
                tvals['list_price'] = list_price
            if cost_price:
                tvals['cost_price'] = cost_price

            return Template.create_esale_product(shop, tvals, pvals)
