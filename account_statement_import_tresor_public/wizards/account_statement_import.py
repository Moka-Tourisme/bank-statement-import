# Copyright 2004-2020 Odoo S.A.
# Licence LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
import csv
import hashlib
import logging
import shutil

from odoo import _, fields, models
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
        logger.info("Start to import bank statement file ICI %s", self.statement_filename)

        file_data = base64.b64decode(self.statement_file)

        if self.sheet_mapping_id.is_tresor_public:
            filename = f'{self.statement_filename}'
            file = file_data.decode('utf-8')
            # Save the file in a temp file
            with open(filename, 'w') as f:
                f.write(file)
            # Convert the file
            self._convert_file(filename)
            file_data = open(filename, 'rb').read()
            # Remove all " from the file
            file_data = file_data.replace(b'"', b'')
            print("file_data", file_data)

        self.import_single_file(file_data, result)
        logger.debug("result=%s", result)
        print("result", result)
        if not result["statement_ids"]:
            raise UserError(
                _(
                    "You have already imported this file, or this file "
                    "only contains already imported transactions."
                )
            )
        self.env["ir.attachment"].create(self._prepare_create_attachment(result))
        return result

    def import_single_file(self, file_data, result):
        print("Ici import single file")
        parsing_data = self.with_context(active_id=self.ids[0])._parse_file(file_data)
        print('parsing_data', parsing_data)
        if not isinstance(parsing_data, list):  # for backward compatibility
            parsing_data = [parsing_data]
        logger.info(
            "Bank statement file %s contains %d accounts",
            self.statement_filename,
            len(parsing_data),
        )
        i = 0
        for single_statement_data in parsing_data:
            print("ICI single_statement_data", single_statement_data)
            i += 1
            logger.debug(
                "account %d: single_statement_data=%s", i, single_statement_data
            )
            self.import_single_statement(single_statement_data, result)

    def import_single_statement(self, single_statement_data, result):
        if not isinstance(single_statement_data, tuple):
            raise UserError(
                _("The parsing of the statement file returned an invalid result.")
            )
        currency_code, account_number, stmts_vals = single_statement_data
        # Check raw data
        if not self._check_parsed_data(stmts_vals):
            return False
        if not currency_code:
            raise UserError(_("Missing currency code in the bank statement file."))
        # account_number can be None (example : QIF)
        currency = self._match_currency(currency_code)
        journal = self._match_journal(account_number, currency)
        if not journal.default_account_id:
            raise UserError(
                _("The Bank Accounting Account is not set on the journal '%s'.")
                % journal.display_name
            )
        # Prepare statement data to be used for bank statements creation
        stmts_vals = self._complete_stmts_vals(stmts_vals, journal, account_number)
        # Create the bank statements
        self._create_bank_statements(stmts_vals, result)
        # Now that the import worked out, set it as the bank_statements_source
        # of the journal
        if journal.bank_statements_source != "file_import_oca":
            # Use sudo() because only 'account.group_account_manager'
            # has write access on 'account.journal', but 'account.group_account_user'
            # must be able to import bank statement files
            journal.sudo().write({"bank_statements_source": "file_import_oca"})

    def _create_bank_statements(self, stmts_vals, result):
        """Create new bank statements from imported values,
        filtering out already imported transactions,
        and return data used by the reconciliation widget"""
        abs_obj = self.env["account.bank.statement"]
        absl_obj = self.env["account.bank.statement.line"]
        print("passage create bank statement")
        # Filter out already imported transactions and create statements
        statement_ids = []
        existing_st_line_ids = {}
        for st_vals in stmts_vals:
            st_lines_to_create = []
            for lvals in st_vals["transactions"]:
                existing_line = False
                if lvals.get("unique_import_id"):
                    existing_line = absl_obj.sudo().search(
                        [
                            ("unique_import_id", "=", lvals["unique_import_id"]),
                        ],
                        limit=1,
                    )
                    # we can only have 1 anyhow because we have a unicity SQL constraint
                if existing_line:
                    existing_st_line_ids[existing_line.id] = True
                    if "balance_start" in st_vals:
                        st_vals["balance_start"] += float(lvals["amount"])
                else:
                    st_lines_to_create.append(lvals)

            if len(st_lines_to_create) > 0:
                if not st_lines_to_create[0].get("sequence"):
                    for seq, vals in enumerate(st_lines_to_create, start=1):
                        vals["sequence"] = seq
                # Remove values that won't be used to create records
                st_vals.pop("transactions", None)
                # Create the statement with lines
                st_vals["line_ids"] = [[0, False, line] for line in st_lines_to_create]
                statement = abs_obj.create(st_vals)
                statement_ids.append(statement.id)

        if not statement_ids:
            return False
        result["statement_ids"].extend(statement_ids)

        # Prepare import feedback
        num_ignored = len(existing_st_line_ids)
        if num_ignored > 0:
            result["notifications"].append(
                {
                    "type": "warning",
                    "message": _(
                        "%d transactions had already been imported and were ignored."
                    )
                               % num_ignored
                    if num_ignored > 1
                    else _("1 transaction had already been imported and was ignored."),
                    "details": {
                        "name": _("Already imported items"),
                        "model": "account.bank.statement.line",
                        "ids": list(existing_st_line_ids.keys()),
                    },
                }
            )
        statements = self.env["account.bank.statement"].browse(result["statement_ids"])
        for statement in statements:
            if not statement.balance_end_real:
                amount = sum(statement.line_ids.mapped("amount"))
                statement.balance_end_real = statement.balance_start + amount
        return statements

    def _convert_file(self, data_file):
        # print("data_file", data_file)
        dataTransaction = []
        output_file = "convertFileTemp.csv"
        with open(data_file, 'r', encoding='utf-8') as csvfile:
            # Read the CSV file using the semicolon as a delimiter, and data like 0.19 as a float
            reader = csv.reader(csvfile, delimiter=';', quoting=csv.QUOTE_NONE, quotechar='"', doublequote=False)
            header1, header2 = None, None  # Initialize variables for the headers

            # Loop through the CSV file
            for index, row in enumerate(reader):
                if index == 3:
                    # Store data[0] and data[2] as headers and remove the last character
                    header1 = row[0][1:-3].replace(':', '')
                    header2 = row[2][1:-3].replace(':', '')
                    print(header1, header2)
                elif index == 4:
                    header1data = row[0][:-1].replace(':', '').replace('"', '')
                    header2data = row[2][:-1].replace(':', '').replace('"', '')
                    print(header1data, header2data)
                elif index == 8:
                    header3 = row
                    header3 = [x.replace(' ', '').replace('"', '') for x in header3]
                    header3.pop()
                elif index >= 9:
                    data = row
                    data = [x.replace('"', '') for x in data]
                    data.pop()
                    if data[0] != "":
                        for index, value in enumerate(data):
                            if index == 3:
                                if value == "":
                                    data[index] = "0,0"
                                else:
                                    data[index] = value.replace(' ', '')
                            elif index == 4:
                                if value == "":
                                    data[index] = "0,0"
                                else:
                                    data[index] = value.replace(' ', '')
                        data.insert(0, header1data)
                        data.insert(1, header2data)
                        data.insert(2, "EUR")
                        print("data-ici", data)
                        # Create an md5 hash of the data
                        data.append(hashlib.md5(str(data).encode('utf-8')).hexdigest())
                        dataTransaction.append(data)
        header3.insert(0, header1)
        header3.insert(1, header2)
        header3.insert(2, "Devise")
        header3.append("Id")

        # Write the cleaned data to a new CSV file
        with open(output_file, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(header3)
            writer.writerows(dataTransaction)
            shutil.move(output_file, data_file)

        return data_file
#
