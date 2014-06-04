# encoding: utf-8
#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.modules.prestashop.tools import unaccent, party_name, \
    remove_newlines, base_price_without_tax
from pystashop import PrestaShopWebservice
from decimal import Decimal

import logging
import threading
import datetime

__all__ = ['SaleShop']
__metaclass__ = PoolMeta

PRODUCT_TYPE_OUT_ORDER_LINE = ['configurable']


class SaleShop:
    __name__ = 'sale.shop'
    prestashop_website = fields.Many2One('prestashop.website', 'Prestashop Website', 
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(SaleShop, cls).__setup__()
        cls._error_messages.update({
            'prestashop_product': 'Install Prestashop Product module to export ' \
                'products to Prestashop',
            'prestashop_error_get_orders': ('Prestashop "%s". ' \
                'Error connection or get earlier date: "%s".'),
        })

    @classmethod
    def get_shop_app(cls):
        '''Get Shop APP (tryton, prestashop, prestashop,...)'''
        res = super(SaleShop, cls).get_shop_app()
        res.append(('prestashop','Prestashop'))
        return res

    @classmethod
    def get_prestashop_region(cls, region):
        '''Get subdivision (prestashop to tryton)'''
        pool = Pool()
        PrestashopRegion = pool.get('prestashop.region')

        subdivision = None
        if not region:
            return subdivision

        regions = PrestashopRegion.search([
                    ('region_id', '=', region),
                    ], limit=1)
        if regions:
            region, = regions
            subdivision = region.subdivision
        return subdivision

    @classmethod
    def get_shop_user(self, shop):
        '''Get user
        User is not active change user defined in sale shop
        :param shop: object
        :return user
        '''
        User = Pool().get('res.user')

        user = User(Transaction().user)
        if not user.active:
            if shop.esale_user:
                user = shop.esale_user
            else:
                logging.getLogger('prestashop order').info(
                    'Add a default user in %s configuration.' % (shop.name))
        return user

    def import_orders_prestashop(self, shop, ofilter=None):
        """Import Orders from Prestashop APP
        :param shop: Obj
        :param ofilter: dict
        """
        pool = Pool()
        SaleShop = pool.get('sale.shop')

        ptsapp = shop.prestashop_website.prestashop_app
        now = datetime.datetime.now()

        if not ofilter:
            from_time = SaleShop.datetime_to_str(shop.esale_from_orders or now)
            if shop.esale_to_orders:
                to_time = SaleShop.datetime_to_str(shop.esale_to_orders)
            else:
                to_time = SaleShop.datetime_to_str(now)

            created_filter = {}
            created_filter['from'] = from_time
            created_filter['to'] = to_time
            ofilter = {'created_at': created_filter}

        # TODO: Call Import Prestashop orders

        #~ Update date last import
        self.write([shop], {'esale_from_orders': now, 'esale_to_orders': None})

        if not orders:
            logging.getLogger('prestashop sale').info(
                'Prestashop %s. Not orders to import.' % (shop.name))
        else:
            logging.getLogger('prestashop order').info(
                'Prestashop %s. Start import %s orders.' % (
                shop.name, len(orders)))

            user = self.get_shop_user(shop)

            db_name = Transaction().cursor.dbname
            thread1 = threading.Thread(target=self.import_orders_prestashop_thread, 
                args=(db_name, user.id, shop.id, orders,))
            thread1.start()

    @classmethod
    def pts2order_values(self, shop, values):
        """
        Convert prestashop values to sale
        :param shop: obj
        :param values: dict
        return dict
        """
        comment = values.get('customer_note')
        if values.get('gift_message'):
            comment = '%s\n%s' % (values.get('customer_note'), values.get('gift_message'))

        status_history = []
        if values.get('status_history'):
            for history in values['status_history']:
                status_history.append('%s - %s - %s' % (
                    str(history['created_at']), 
                    str(history['status']), 
                    str(unicode(history['comment']).encode('utf-8')),
                    ))

        payment_type = None
        if 'method' in values.get('payment'):
            payment_type = values.get('payment')['method']

        vals = {
            'reference_external': values.get('increment_id'),
            'sale_date': values.get('created_at')[:10],
            'carrier': values.get('shipping_method'),
            'payment': payment_type,
            'currency': values.get('order_currency_code'),
            'comment': comment,
            'status': values['status_history'][0]['status'],
            'status_history': '\n'.join(status_history),
            'external_untaxed_amount': Decimal(values.get('base_subtotal')),
            'external_tax_amount': Decimal(values.get('base_tax_amount')),
            'external_total_amount': Decimal(values.get('base_grand_total')),
            'external_shipment_amount': Decimal(values.get('shipping_amount')),
            'shipping_price': Decimal(values.get('shipping_amount')),
            'shipping_note': values.get('shipping_description'),
            'discount': Decimal(values.get('discount_amount'))
            }

        # fooman surchage extension
        if values.get('fooman_surcharge_amount'):
            surcharge = None
            if values.get('base_fooman_surcharge_amount'):
                surcharge = values.get('base_fooman_surcharge_amount')
            elif values.get('fooman_surcharge_amount'):
                surcharge = values.get('fooman_surcharge_amount')
            surcharge = Decimal(surcharge)
            if surcharge != 0.0000:
                vals['surcharge'] = surcharge

        return vals

    @classmethod
    def pts2lines_values(self, shop, values):
        """
        Convert prestashop values to sale lines
        :param shop: obj
        :param values: dict
        return list(dict)
        """
        Product = Pool().get('product.product')

        app = shop.prestashop_website.prestashop_app
        vals = []
        sequence = 1
        for item in values.get('items'):
            if item['product_type'] not in PRODUCT_TYPE_OUT_ORDER_LINE:
                code = item.get('sku')
                price = Decimal(item.get('price'))

                # Price include taxes. Calculate base price - without taxes
                if shop.esale_tax_include:
                    customer_taxes = None
                    product = Product.search([('code', '=', code)], limit=1)
                    if product:
                        customer_taxes = product[0].template.customer_taxes_used
                    if not product and app.default_taxes:
                        customer_taxes = app.default_taxes
                    if customer_taxes:
                        rate = customer_taxes[0].rate
                        price = Decimal(base_price_without_tax(price, rate))

                values = {
                    'quantity': Decimal(item.get('qty_ordered')),
                    'description': item.get('description') or item.get('name'),
                    'unit_price': price,
                    'note': item.get('gift_message'),
                    'sequence': sequence,
                    }
                if app.product_options and item.get('sku'):
                    for sku in item['sku'].split('-'):
                        values['product'] = sku
                        vals.append(values)
                else:
                    values['product'] = item.get('sku')
                    vals.append(values)
                sequence += 1
        return vals

    def pts2extralines_values(self, shop, values):
        """
        Convert prestashop values to extra sale lines
        Super this method if in your Prestashop there are extra lines to create
        in sale order
        :param shop: obj
        :param values: dict
        return list(dict)
        """
        return []

    @classmethod
    def pts2party_values(self, shop, values):
        """
        Convert prestashop values to party
        :param shop: obj
        :param values: dict
        return dict
        """
        pool = Pool()
        eSaleAccountTaxRule = pool.get('esale.account.tax.rule')

        firstname = values.get('customer_firstname')
        lastname = values.get('customer_lastname')
        billing = values.get('billing_address')
        shipping = values.get('shipping_address')

        vals = {
            'name': unaccent(billing.get('company') and 
                billing.get('company').title() or 
                party_name(firstname, lastname)).title(),
            'esale_email': values.get('customer_email'),
            }

        vals['vat_number'] = values.get('customer_taxvat')
        if billing:
            vals['vat_country'] = billing.get('country_id')
        else:
            vals['vat_country'] = shipping.get('country_id')

        # Add customer/supplier tax rule
        # 1. Search Tax Rule from Billing Address Region ID
        # 2. Search Tax Rule from Billing Address Post Code
        # 3. Search Tax Tule from Billing Address Country ID
        tax_rule = None
        taxe_rules = eSaleAccountTaxRule.search([])

        subdivision = self.get_prestashop_region(billing.get('region_id'))
        if subdivision:
            tax_rules = eSaleAccountTaxRule.search([
                ('subdivision', '=', subdivision),
                ], limit=1)
            if tax_rules:
                tax_rule, = tax_rules

        postcode = billing.get('postcode')
        if postcode and not tax_rule:
            for tax in taxe_rules:
                if not tax.start_zip or not tax.end_zip:
                    continue
                try:
                    if (int(tax.start_zip) <= int(postcode) <= int(tax.end_zip)):
                        tax_rule = tax
                        break
                except:
                    break

        country = billing.get('country_id')
        if country and not tax_rule:
            for tax in taxe_rules:
                if tax.subdivision or tax.start_zip or tax.end_zip:
                    continue
                if tax.country.code.lower() == country.lower():
                    tax_rule = tax
                    break

        if tax_rule:
            vals['customer_tax_rule'] = tax_rule.customer_tax_rule.id
            vals['supplier_tax_rule'] = tax_rule.supplier_tax_rule.id
        # End add customer/supplier tax rule

        return vals

    @classmethod
    def pts2invoice_values(self, shop, values):
        """
        Convert prestashop values to invoice address
        :param shop: obj
        :param values: dict
        return dict
        """
        billing = values.get('billing_address')

        name = party_name(values.get('customer_firstname'), 
            values.get('customer_lastname'))
        if billing.get('firstname'):
            name = party_name(billing.get('firstname'), 
                billing.get('lastname'))

        email = values.get('customer_email')
        if billing.get('email') and not billing.get('email') != 'n/a@na.na':
            email = values.get('customer_email')
        vals = {
            'name': unaccent(name).title(),
            'street': remove_newlines(unaccent(billing.get('street')).title()),
            'zip': billing.get('postcode'),
            'city': unaccent(billing.get('city')).title(),
            'subdivision': self.get_prestashop_region(billing.get('region_id')),
            'country': billing.get('country_id'),
            'phone': billing.get('telephone'),
            'email': email,
            'fax': billing.get('fax'),
            'invoice': True,
            }
        return vals

    @classmethod
    def pts2shipment_values(self, shop, values):
        """
        Convert prestashop values to shipment address
        :param shop: obj
        :param values: dict
        return dict
        """
        shipment = values.get('shipping_address')

        name = party_name(values.get('customer_firstname'), 
            values.get('customer_lastname'))
        if shipment.get('firstname'):
            name = party_name(shipment.get('firstname'), shipment.get('lastname'))

        email = values.get('customer_email')
        if shipment.get('email') and not shipment.get('email') != 'n/a@na.na':
            email = values.get('customer_email')
        vals = {
            'name': unaccent(name).title(),
            'street': remove_newlines(unaccent(shipment.get('street')).title()),
            'zip': shipment.get('postcode'),
            'city': unaccent(shipment.get('city')).title(),
            'subdivision': self.get_prestashop_region(shipment.get('region_id')),
            'country': shipment.get('country_id'),
            'phone': shipment.get('telephone'),
            'email': email,
            'fax': shipment.get('fax'),
            'delivery': True,
            }
        return vals

    def import_orders_prestashop_thread(self, db_name, user, shop, orders):
        """Create orders from Prestashop APP
        :param db_name: str
        :param user: int
        :param shop: int
        :param orders: list
        """
        with Transaction().start(db_name, user):
            pool = Pool()
            SaleShop = pool.get('sale.shop')
            Sale = pool.get('sale.sale')

            sale_shop, = SaleShop.browse([shop])
            ptsapp = sale_shop.prestashop_website.prestashop_app

            for order in orders:
                reference = order['increment_id']

                sales = Sale.search([
                    ('reference_external', '=', reference),
                    ('shop', '=', sale_shop),
                    ], limit=1)

                if sales:
                    logging.getLogger('prestashop sale').warning(
                        'Prestashop %s. Order %s exist (ID %s). Not imported' % (
                        sale_shop.name, reference, sales[0].id))
                    continue

                #Get details Prestashop order
                # TODO Call info/detail prestashop order by reference. Example:
                #~ values = order_api.info(reference)

                #Convert Prestashop order to dict
                sale_values = self.pts2order_values(sale_shop, values)
                lines_values = self.pts2lines_values(sale_shop, values)
                extralines_values = self.pts2extralines_values(sale_shop, values)
                party_values = self.pts2party_values(sale_shop, values)
                invoice_values = self.pts2invoice_values(sale_shop, values)
                shipment_values = self.pts2shipment_values(sale_shop, values)

                #Create order, lines, party and address
                Sale.create_external_order(sale_shop, sale_values, 
                    lines_values, extralines_values, party_values, 
                    invoice_values, shipment_values)
                Transaction().cursor.commit()

            logging.getLogger('prestashop sale').info(
                'Prestashop %s. End import sales' % (sale_shop.name))

    def export_state_prestashop(self, shop):
        """Export State sale to Prestashop
        :param shop: Obj
        """
        now = datetime.datetime.now()
        date = shop.esale_last_state_orders or now

        orders = self.get_sales_from_date(shop, date)

        #~ Update date last import
        self.write([shop], {'esale_last_state_orders': now})

        if not orders:
            logging.getLogger('prestashop sale').info(
                'Prestashop %s. Not orders to export state' % (shop.name))
        else:
            sales = [s.id for s in orders]
            logging.getLogger('prestashop order').info(
                'Prestashop %s. Start export %s state orders' % (
                shop.name, len(orders)))
            db_name = Transaction().cursor.dbname
            thread1 = threading.Thread(target=self.export_state_prestashop_thread, 
                args=(db_name, Transaction().user, shop.id, sales,))
            thread1.start()

    def export_state_prestashop_thread(self, db_name, user, shop, sales):
        """Export State sale to Prestashop APP
        :param db_name: str
        :param user: int
        :param shop: int
        :param sales: list
        """
        with Transaction().start(db_name, user):
            pool = Pool()
            Sale = pool.get('sale.sale')
            SaleShop = pool.get('sale.shop')

            sale_shop = SaleShop.browse([shop])[0]
            ptsapp = sale_shop.prestashop_website.prestashop_app

            states = {}
            for s in sale_shop.esale_states:
                states[s.state] = {'code': s.code, 'notify': s.notify}

            for sale in Sale.browse(sales):
                status = None
                notify = None
                cancel = None
                comment = None
                if sale.state == 'cancel':
                    status = states['cancel']['code']
                    notify = states['cancel']['notify']
                    cancel = True
                if sale.invoices_paid:
                    status = states['paid']['code']
                    notify = states['paid']['notify']
                if sale.shipments_done:
                    status = states['shipment']['code']
                    notify = states['shipment']['notify']
                if sale.invoices_paid and sale.shipments_done:
                    status = states['paid-shipment']['code']
                    notify = states['paid-shipment']['notify']

                if not status or status == sale.status:
                    logging.getLogger('prestashop sale').info(
                        'Prestashop %s. Not status or not update state %s' % (
                        sale_shop.name, sale.reference_external))
                    continue

                try:
                    # TODO: Export state order to Prestashop
                    Sale.write([sale], {
                        'status': status,
                        'status_history': '%s\n%s - %s' % (
                            sale.status_history,
                            str(datetime.datetime.now()),
                            status),
                        })
                    logging.getLogger('prestashop sale').info(
                        'Prestashop %s. Export state %s - %s' % (
                        sale_shop.name, sale.reference_external, status))
                except:
                    logging.getLogger('prestashop sale').error(
                        'Prestashop %s. Not export state %s' % (
                        sale_shop.name, sale.reference_external))
            Transaction().cursor.commit()
            logging.getLogger('prestashop sale').info(
                'Prestashop %s. End export state' % (sale_shop.name))

    def export_products_prestashop(self, shop):
        """Export Products to Prestashop
        This option is available in prestashop_product module
        """
        self.raise_user_error('prestashop_product')

    def export_prices_prestashop(self, shop):
        """Export Prices to Prestashop
        This option is available in prestashop_product module
        """
        self.raise_user_error('prestashop_product')

    def export_stocks_prestashop(self, shop):
        """Export Stocks to Prestashop
        This option is available in prestashop_product module
        """
        self.raise_user_error('prestashop_product')

    def export_images_prestashop(self, shop):
        """Export Images to Prestashop
        This option is available in prestashop_product module
        """
        self.raise_user_error('prestashop_product')

    def export_menus_prestashop(self, shop, tpls=[]):
        """Export Menus to Prestashop
        :param shop: object
        :param tpls: list
        """
        self.raise_user_error('prestashop_product')
