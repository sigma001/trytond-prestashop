# encoding: utf-8
#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from decimal import Decimal
from lxml.etree import Element
from lxml.objectify import NumberElement, NoneElement, StringElement, \
    ObjectifiedElement
import unicodedata

SRC_CHARS = u"""/*+?¿!&$[]{}@#`^<>=~%|\\"""
#TODO: Add len postcodes and countries if postcode start with 0 (zero)
POSTCODE_COUNTRY = {
    'es': 5,
}


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
    From price with taxes and return price without tax
    :param price: total price
    :param rate: rate tax
    '''
    price = price / (1 + rate)
    return '%.4f' % (price)


def base_price_with_tax(price, rate):
    '''
    From price without taxes and return with tax
    :param price: total price
    :param rate: rate tax
    '''
    price = price * (1 + rate)
    return '%.4f' % (price)


def postcode_len(country, postcode):
    '''
    Detected in Prestashop 1.6, postcode is int and not str.
    In some postcodes started with 0. In this examle, 08720 return 8720.
    This method add len acccording postcode lenght to the country
    '''
    if not country:
        return ''
    postcode_lenght = POSTCODE_COUNTRY.get(country.lower(), None)
    if postcode_lenght:
        return str(postcode).zfill(postcode_lenght)
    return postcode


def xml2dict(xml_object):
    dict_object = xml_object.__dict__
    dict_values = {k: dict_object[k].pyval
        if isinstance(dict_object[k],
            (NumberElement, NoneElement, StringElement))
        else xml2dict(dict_object[k])
        if isinstance(dict_object[k], ObjectifiedElement)
        else xml2dict(dict_object[k].associations)
        for k in dict_object}
    values = {}
    for value in dict_values:
        if not isinstance(dict_values[value], dict):
            values[value] = dict_values[value]
        elif 'language' in dict_values[value]:
            langs = {}
            for k in xml_object.__getattr__(value).descendantpaths():
                if 'language' in k:
                    if '[' in k:
                        lang_id = int(k.split('[')[1].split(']')[0])
                    else:
                        lang_id = 0
                    langs[lang_id + 1] = (
                        xml_object.__getattr__(value).language[lang_id].pyval)
            values[value] = langs
    return values


def set_xml_attributes(xml_model, dict_values, delete_fields=None):
    if not delete_fields:
        delete_fields = []
    for child in xml_model.getchildren():
        if child.tag in delete_fields:
                xml_model.__delattr__(child.tag)
        elif child.tag == 'id':
            continue
        elif child.tag in dict_values:
            if isinstance(child, (NumberElement, NoneElement, StringElement)):
                if type(dict_values[child.tag]) == Decimal:
                    dict_values[child.tag] = float(dict_values[child.tag])
                xml_model.__setattr__(child.tag, dict_values[child.tag])
            else:
                grandchild = child.getchildren()[0]
                if grandchild.tag == 'language':
                    tag = Element(child.tag)
                    for lang in sorted(dict_values[child.tag]):
                        language = Element('language', id='%s' % lang)
                        language.text = dict_values[child.tag][lang]
                        tag.append(language)
                    xml_model.__delattr__(child.tag)
                    xml_model.append(tag)
