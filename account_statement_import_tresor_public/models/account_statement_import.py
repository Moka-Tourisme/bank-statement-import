# Copyright 2020 CorporateHub (https://corporatehub.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountStatementImport(models.TransientModel):
    _inherit = "account.statement.import"

    def _create_bank_statements(self, stmts_vals, result):
        """Pre-filter intra-batch duplicates before creating statements.

        The base module only checks unique_import_id against the database.
        If two identical transactions appear in the same file, they get the
        same hash/unique_import_id, and both pass the DB check (since
        neither is created yet). This pre-filter removes such duplicates
        before the base logic runs.
        """
        for st_vals in stmts_vals:
            seen_ids = set()
            unique_transactions = []
            for lvals in st_vals["transactions"]:
                uid = lvals.get("unique_import_id")
                if uid and uid in seen_ids:
                    _logger.info(
                        "Skipping intra-batch duplicate: %s", uid
                    )
                    continue
                if uid:
                    seen_ids.add(uid)
                unique_transactions.append(lvals)
            st_vals["transactions"] = unique_transactions
        return super()._create_bank_statements(stmts_vals, result)
