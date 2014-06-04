# encoding: utf-8
#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.

import unicodedata

SRC_CHARS = u"""/*+?¿!&$[]{}@#`^<>=~%|\\"""

def unaccent(text):
    if not (isinstance(text, str) or isinstance(text, unicode)):
        return str(text)
    if isinstance(text, str):
        text = unicode(text, 'utf-8')
    text = text.lower()
    for c in xrange(len(SRC_CHARS)):
        text = text.replace(SRC_CHARS[c], '')
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore')


def party_name(firstname, lastname):
    '''
    Return party name format
    '''
    return '%s %s' % (firstname, lastname)


def remove_newlines(text):
    '''
    Remove new lines
    '''
    return ' '.join(text.splitlines())


def base_price_without_tax(price, rate):
    '''
    Return base price - without tax
    :param price: total price
    :param rate: rate tax
    '''
    price = price*(1+rate)
    return '%.4f' % (price)
