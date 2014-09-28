#This file is part prestashop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool

__all__ = ['PrestashopExternalReferential']


class PrestashopExternalReferential(ModelSQL, ModelView):
    'Prestashop External Referential'
    __name__ = 'prestashop.external.referential'

    prestashop_app = fields.Many2One('prestashop.app', 'Prestashop App',
        required=True)
    model = fields.Many2One('ir.model', 'Tryton Model', required=True,
        select=True)
    try_id = fields.Integer('Tryton ID', required=True)
    pts_id = fields.Integer('Prestashop ID', required=True)

    @classmethod
    def set_external_referential(cls, app, model, try_id, pts_id):
        '''
        Create external referential
        :param app: object
        :param model: str name model
        :param try_id: int Tryton ID
        :param pts_id: int Prestashop ID
        :return prestashop_external_referential browseable record
        '''
        models = Pool().get('ir.model').search([('model', '=', model)],
            limit=1)
        values = {
            'prestashop_app': app.id,
            'model': models[0],
            'try_id': try_id,
            'pts_id': pts_id,
        }
        prestashop_external_referential = cls.create([values])[0]
        return prestashop_external_referential

    @classmethod
    def get_pts2try(cls, app, model, pts_id):
        '''
        Search prestashop app, model and prestashop ID exists in other
        syncronizations
        :param app: object
        :param model: str name model
        :param pts_id: int Prestashop ID
        :return id or None
        '''
        models = Pool().get('ir.model').search([('model', '=', model)],
            limit=1)
        values = cls.search([
            ('prestashop_app', '=', app.id),
            ('model', '=', models[0]),
            ('pts_id', '=', pts_id),
            ], limit=1)
        if values:
            return values[0]
        else:
            return None

    @classmethod
    def get_try2pts(cls, app, model, try_id):
        '''
        Search prestashop app, model and tryton ID
        :param app: object
        :param model: str name model
        :param try_id: int Tryton ID
        :return id or None
        '''
        models = Pool().get('ir.model').search([('model', '=', model)],
            limit=1)
        values = cls.search([
            ('prestashop_app', '=', app.id),
            ('model', '=', models[0]),
            ('try_id', '=', try_id),
            ], limit=1)
        if values:
            return values[0]
        else:
            return None
