# Copyright 2019 ForgeFlow, S.L.
# Copyright 2020 CorporateHub (https://corporatehub.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Bank Statement Tresor Public Import",
    "summary": "Import TXT/CSV or XLSX files as Bank Statements in Odoo",
    "version": "15.0.2.0.3",
    "category": "Accounting",
    "website": "https://github.com/OCA/bank-statement-import",
    "license": "AGPL-3",
    "installable": True,
    "depends": [
        "account_statement_import_txt_xlsx",
    ],
    "external_dependencies": {"python": ["xlrd", "chardet"]},
    "data": [
        "data/map_data.xml",
        "views/account_statement_import_sheet_mapping.xml",
    ],
}
