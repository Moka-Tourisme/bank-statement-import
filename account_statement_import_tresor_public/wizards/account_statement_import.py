# Copyright 2004-2020 Odoo S.A.
# Licence LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
import csv
import hashlib
import logging
import os
import tempfile

from odoo import _, models
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class AccountStatementImport(models.TransientModel):
    _inherit = "account.statement.import"

    def _import_file(self):
        self.ensure_one()
        result = {
            "statement_ids": [],
            "notifications": [],
        }
        logger.info(
            "Start to import bank statement file %s", self.statement_filename
        )

        file_data = base64.b64decode(self.statement_file)

        if self.sheet_mapping_id.is_tresor_public:
            file_data = self._convert_tresor_public(file_data)

        self.import_single_file(file_data, result)
        logger.debug("result=%s", result)
        if not result["statement_ids"]:
            raise UserError(
                _(
                    "You have already imported this file, or this file "
                    "only contains already imported transactions."
                )
            )
        self.env["ir.attachment"].create(self._prepare_create_attachment(result))
        return result

    def _convert_tresor_public(self, file_data):
        """Convert a Tresor Public CSV file to the standard sheet format.

        Returns the converted file content as bytes.
        """
        decoded = file_data.decode('utf-8')
        dataTransaction = []
        header1, header2 = None, None
        header1data, header2data = None, None
        header3 = None

        lines = decoded.splitlines(True)
        reader = csv.reader(
            lines,
            delimiter=';',
            quoting=csv.QUOTE_NONE,
            quotechar='"',
            doublequote=False,
        )

        for row_idx, row in enumerate(reader):
            if row_idx == 3:
                header1 = row[0][1:-3].replace(':', '')
                header2 = row[2][1:-3].replace(':', '')
            elif row_idx == 4:
                header1data = row[0][:-1].replace(':', '').replace('"', '')
                header2data = row[2][:-1].replace(':', '').replace('"', '')
            elif row_idx == 8:
                header3 = [
                    x.replace(' ', '').replace('"', '') for x in row
                ]
                header3.pop()
            elif row_idx >= 9:
                data = [x.replace('"', '') for x in row]
                data.pop()
                if data[0] != "":
                    for col_idx, value in enumerate(data):
                        if col_idx == 3:
                            data[col_idx] = (
                                value.replace(' ', '') if value else "0,0"
                            )
                        elif col_idx == 4:
                            data[col_idx] = (
                                value.replace(' ', '') if value else "0,0"
                            )
                    data.insert(0, header1data)
                    data.insert(1, header2data)
                    data.insert(2, "EUR")
                    # Hash only the transaction-specific fields
                    # (date, valeur, libellé, débit, crédit) to avoid
                    # header2data trailing spaces changing between exports
                    hash_data = [x.strip() for x in data]
                    data.append(
                        hashlib.md5(
                            str(hash_data).encode('utf-8')
                        ).hexdigest()
                    )
                    dataTransaction.append(data)

        header3.insert(0, header1)
        header3.insert(1, header2)
        header3.insert(2, "Devise")
        header3.append("Id")

        # Write to a temp file and read back
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False, newline=''
        ) as tmp:
            writer = csv.writer(
                tmp,
                delimiter=';',
                quotechar='"',
                quoting=csv.QUOTE_MINIMAL,
            )
            writer.writerow(header3)
            writer.writerows(dataTransaction)
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            converted = f.read()

        os.unlink(tmp_path)

        # Remove all quotes
        converted = converted.replace(b'"', b'')
        return converted

    def _convert_file(self, data_file):
        """Kept for backward compatibility. Use _convert_tresor_public."""
        return self._convert_tresor_public(
            open(data_file, 'rb').read()
        )
