# Copyright 2019 ForgeFlow, S.L.
# Copyright 2020 CorporateHub (https://corporatehub.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountStatementImportSheetMapping(models.Model):
    _inherit = "account.statement.import.sheet.mapping"


    # Tresor Public
    is_tresor_public = fields.Boolean(
        string="Is Tresor Public",
        default=False,
    )
