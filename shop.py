# encoding: utf-8
#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.modules.prestashop.tools import unaccent, party_name, \
    remove_newlines, postcode_len
from decimal import Decimal
from datetime import datetime

import logging
import threading

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
    def get_prestashop_state(cls, state):
        '''Get subdivision (prestashop to tryton)'''
        pool = Pool()
        PrestashopState = pool.get('prestashop.state')

        subdivision = None
        if not state:
            return subdivision

        states = PrestashopState.search([
                    ('state_id', '=', state),
                    ], limit=1)
        if states:
            state, = states
            subdivision = state.subdivision
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

    def import_orders_prestashop(self, ofilter=None):
        """Import Orders from Prestashop APP
        :param shop: Obj
        :param ofilter: dict
        """
        pool = Pool()
        SaleShop = pool.get('sale.shop')

        ptsapp = self.prestashop_website.prestashop_app
        now = datetime.now()

        if not ofilter:
            from_time = SaleShop.datetime_to_str(self.esale_from_orders or now)
            if self.esale_to_orders:
                to_time = SaleShop.datetime_to_str(self.esale_to_orders)
            else:
                to_time = SaleShop.datetime_to_str(now)

            created_filter = {}
            created_filter['from'] = from_time
            created_filter['to'] = to_time
            ofilter = {'created_at': created_filter}

        client = ptsapp.get_prestashop_client()
        orders = client.orders.get_list(
            filters={
                'date_upd': '{0},{1}'.format(from_time, to_time)
                }, date=1, display='full',
            )

        #~ Update date last import
        self.write([self], {'esale_from_orders': now, 'esale_to_orders': None})

        if not orders:
            logging.getLogger('prestashop sale').info(
                'Prestashop %s. Not orders to import.' % (self.name))
        else:
            logging.getLogger('prestashop order').info(
                'Prestashop %s. Start import %s orders.' % (
                self.name, len(orders)))

            user = self.get_shop_user(self)

            db_name = Transaction().cursor.dbname
            thread1 = threading.Thread(target=self.import_orders_prestashop_thread, 
                args=(db_name, user.id, self.id, orders,))
            thread1.start()

    @classmethod
    def pts2order_values(self, shop, values, currencies, carriers):
        """
        Convert prestashop order values to sale

        :param shop: obj
        :param values: xml obj
        :param currencies: xml obj
        :param carriers: xml obj
        return dict
        """
        untaxed_amount = Decimal(values.total_paid_tax_excl.pyval).quantize(Decimal('.01'))
        total_amount = Decimal(values.total_paid_tax_incl.pyval).quantize(Decimal('.01'))
        tax_amount = Decimal(total_amount-untaxed_amount).quantize(Decimal('.01'))

        vals = {
            'party': values.id_customer.pyval,
            'carrier': carriers.get(values.id_carrier.pyval),
            'comment': values.gift_message.pyval,
            'currency': currencies.get(values.id_currency.pyval),
            'reference_external': values.reference.pyval,
            'sale_date': datetime.strptime(values.date_add.pyval,
                '%Y-%m-%d %H:%M:%S').date(),
            'external_untaxed_amount': untaxed_amount,
            'external_tax_amount': tax_amount,
            'external_total_amount': total_amount,
            'external_shipment_amount': values.total_shipping.pyval
                and Decimal(values.total_shipping.pyval).quantize(
                    Decimal('.01'))
                or None,
            'shipping_price': Decimal(values.total_shipping.pyval),
            'shipping_note': None,
            'discount': values.total_discounts.pyval
                and Decimal(values.total_discounts.pyval)
                or None,
            'payment': values.payment.pyval,
            'status': str(values.current_state.pyval),
            }
        return vals

    @classmethod
    def pts2lines_values(self, shop, values, products):
        """
        Convert prestashop values order lines to sale lines

        :param shop: obj
        :param values: xml obj
        :param products: xml obj
        return list(dict)
        """
        vals = []
        sequence = 1

        app = shop.prestashop_website.prestashop_app

        for order_row in values.associations.order_rows.iterchildren():
            line = order_row
            code = (line.product_id
                and products[line.product_id.pyval]
                or 'app.%s,product.%s' % (app.id, line.product_id.pyval))
            price = Decimal(line.unit_price_tax_excl.pyval) # get price without tax

            values = {
                'product': code,
                'quantity': Decimal(line.product_quantity.pyval),
                'description': line.product_name.pyval,
                'unit_price': price.quantize(Decimal('.01')),
                'sequence': sequence,
                }
            vals.append(values)
            sequence += 1

        return vals

    @classmethod
    def pts2extralines_values(self, shop, values):
        """
        Convert prestashop values to extra sale lines
        Super this method if in your Prestashop there are extra lines to create
        in sale order

        :param shop: obj
        :param values: xml obj
        return list(dict)
        """
        return []

    @classmethod
    def pts2party_values(self, shop, values, customers, invoice_addresses,
            delivery_addresses, countries):
        """
        Convert prestashop values to party

        :param shop: obj
        :param values: xml obj
        :param customers: xml obj
        :param invoice_address: xml obj
        :param delivery_addresses: xml obj
        :param countries: xml obj
        return dict
        """
        pool = Pool()
        eSaleAccountTaxRule = pool.get('esale.account.tax.rule')

        customer = customers.get(values.id_customer.pyval)
        firstname = customer.firstname.pyval
        lastname = customer.lastname.pyval
        invoice = invoice_addresses.get(values.id_address_invoice.pyval)
        delivery = delivery_addresses.get(values.id_address_delivery.pyval)

        vals = {
            'name': unaccent(invoice.company.pyval
                and invoice.company.pyval
                or party_name(firstname, lastname)).title(),
            'esale_email': customer.email.pyval,
            }
        if invoice.vat_number.pyval:
            vals['vat_number'] = '%s' % invoice.vat_number.pyval
        elif delivery.vat_number.pyval:
            vals['vat_number'] = '%s' % delivery.vat_number.pyval

        country = None
        if invoice.id_country:
            country = countries.get(invoice.id_country.pyval)
            vals['vat_country'] = country
        elif delivery.id_country:
            country = countries.get(delivery.id_country.pyval)
            vals['vat_country'] = country

        # Add customer/supplier tax rule
        # 1. Search Tax Rule from Billing Address State ID
        # 2. Search Tax Rule from Billing Address Post Code
        # 3. Search Tax Tule from Billing Address Country ID
        tax_rule = None
        taxe_rules = eSaleAccountTaxRule.search([])

        subdivision = self.get_prestashop_state(invoice.id_state.pyval)
        if subdivision:
            tax_rules = eSaleAccountTaxRule.search([
                ('subdivision', '=', subdivision),
                ], limit=1)
            if tax_rules:
                tax_rule, = tax_rules

        postcode = invoice.postcode
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
        #~ # End add customer/supplier tax rule

        return vals

    @classmethod
    def pts2invoice_values(self, shop, values, customers, invoice_addresses, countries):
        """
        Convert prestashop values to invoice address

        :param shop: obj
        :param values: xml obj
        :param customers: xml obj
        :param invoice_addresses: xml obj
        :param countries: xml obj
        return dict
        """

        invoice = invoice_addresses.get(values.id_address_invoice.pyval)
        customer = customers.get(values.id_customer.pyval)
        email = customer.email.pyval
        name = party_name(invoice.firstname.pyval, invoice.lastname.pyval)
        if not name:
            name = party_name(customer.firstname.pyval, customer.lastname.pyval)
        country = countries.get(invoice.id_country.pyval)

        vals = {
            'name': unaccent(name).title(),
            'street': remove_newlines(unaccent(invoice.address1.pyval).title()),
            'zip': '%s' % postcode_len(country, invoice.postcode),
            'city': unaccent(invoice.city.pyval).title(),
            'country': country,
            'phone': '%s' % invoice.phone,
            'fax': None,
            'email': email,
            'invoice': True,
            }

        return vals

    @classmethod
    def pts2shipment_values(self, shop, values, customers, delivery_addresses, countries):
        """
        Convert prestashop values to shipment address

        :param shop: obj
        :param values: xml obj
        :param customers: xml obj
        :param delivery_addresses: xml obj
        :param countries: xml obj
        return dict
        """

        delivery = delivery_addresses.get(values.id_address_delivery.pyval)
        customer = customers.get(values.id_customer.pyval)
        email = customer.email.pyval

        name = party_name(delivery.firstname.pyval,
            delivery.lastname.pyval)
        if not name:
            name = party_name(customer.firstname.pyval, customer.lastname.pyval)
        country = countries.get(delivery.id_country.pyval)

        vals = {
            'name': unaccent(name).title(),
            'street': remove_newlines(unaccent(delivery.address1.pyval).title()),
            'zip': '%s' % postcode_len(country, delivery.postcode),
            'city': unaccent(delivery.city.pyval).title(),
            'country': country,
            'phone': '%s' % delivery.phone,
            'fax': None,
            'email': email,
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

            client = ptsapp.get_prestashop_client()

            lines = [r for o in orders
                for r in o.associations.order_rows.iterchildren()]

            product_ids = '|'.join({'%s' % l.product_id.pyval for l in lines})
            products = client.products.get_list(
                filters={'id': product_ids},
                display=['id', 'reference'])
            products = {p.id.pyval: p.reference.pyval for p in products}

            customer_ids = '|'.join({'%s' % o.id_customer.pyval
                    for o in orders})
            customers = client.customers.get_list(
                filters={'id': customer_ids},
                display='full')
            customers = {c.id.pyval: c for c in customers}

            invoice_address_ids = '|'.join({'%s' % o.id_address_invoice.pyval
                    for o in orders})
            invoice_addresses = client.addresses.get_list(
                filters={'id': invoice_address_ids},
                display='full')
            invoice_addresses = {a.id.pyval: a for a in invoice_addresses}

            delivery_address_ids = '|'.join({'%s' % o.id_address_delivery.pyval
                    for o in orders})
            delivery_addresses = client.addresses.get_list(
                filters={'id': delivery_address_ids},
                display='full')
            delivery_addresses = {a.id.pyval: a for a in delivery_addresses}

            countries = client.countries.get_list(
                display=['id', 'iso_code'])
            countries = {c.id.pyval: c.iso_code.pyval for c in countries}

            carriers = client.carriers.get_list(
                display=['id', 'name'])
            carriers = {c.id.pyval: c.name.pyval for c in carriers}

            currencies = client.currencies.get_list(
                display=['id', 'iso_code'])
            currencies = {c.id.pyval: c.iso_code.pyval for c in currencies}

            for order in orders:
                reference = order.reference.pyval

                sales = Sale.search([
                    ('reference_external', '=', reference),
                    ('shop', '=', sale_shop),
                    ], limit=1)

                if sales:
                    logging.getLogger('prestashop sale').warning(
                        'Prestashop %s. Order %s exist (ID %s). Not imported'
                        % (sale_shop.name, reference, sales[0].id))
                    continue

                # Convert Prestashop order to dict
                sale_values = self.pts2order_values(sale_shop, order, currencies, carriers)
                lines_values = self.pts2lines_values(sale_shop, order, products)
                extralines_values = self.pts2extralines_values(sale_shop, order)
                party_values = self.pts2party_values(sale_shop, order, customers,
                    invoice_addresses, delivery_addresses, countries)
                invoice_values = self.pts2invoice_values(sale_shop, order, customers,
                    invoice_addresses, countries)
                shipment_values = self.pts2shipment_values(sale_shop, order, customers,
                    delivery_addresses, countries)

                # Create order, lines, party and address
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
        now = datetime.now()
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
                            str(datetime.now()),
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
