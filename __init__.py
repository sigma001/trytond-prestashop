#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.pool import Pool
from .prestashop_core import *
from .prestashop_referential import *
from .product import *
from .shop import *

def register():
    Pool.register(
        PrestashopApp,
        PrestashopWebsite,
        PrestashopWebsiteLanguage,
        PrestashopCustomerGroup,
        PrestashopState,
        PrestashopAppCustomer,
        PrestashopShopStatus,
        PrestashopAppCountry,
        PrestashopAppLanguage,
        PrestashopApp2,
        PrestashopExternalReferential,
        PrestashopTax,
        PrestashopAppDefaultTax,
        Product,
        SaleShop,
        module='prestashop', type_='model')
