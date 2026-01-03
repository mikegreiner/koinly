#!/usr/bin/env python3
"""
Minimal converter: Only converts problematic transactions (currently loans) to Koinly format.
All other transactions are ignored - import the original Strike CSV directly into Koinly.

Strike 2025 format:
Reference,Date & Time (UTC),Transaction Type,Amount USD,Fee USD,Amount BTC,Fee BTC,BTC Price,Cost Basis (USD),Destination,Description,Transaction Hash,Note

Koinly universal format:
Date,Sent Amount,Sent Currency,Received Amount,Received Currency,Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash

See: https://help.koinly.io/en/articles/3662999-how-to-create-a-custom-csv-file-with-your-data
"""

import argparse
import csv
import sys


def abs_value(value_str):
    """Convert negative string to positive, preserving precision."""
    if not value_str:
        return ''
    return value_str.lstrip('-')


def convert_loan_to_koinly(row):
    """
    Convert a loan transaction to Koinly format.
    
    Returns tuple: (koinly_line, is_loan)
    - koinly_line: CSV line string if loan transaction, None otherwise
    - is_loan: True if this is a loan transaction
    """
    tx_type = row['Transaction Type']
    date = row['Date & Time (UTC)']
    tx_id = row['Reference']
    tx_hash = row.get('Transaction Hash', '') or ''
    description = row.get('Description', '') or ''
    label = f'{tx_type}|Strike transaction: {tx_id}'
    
    if tx_type == 'Loan':
        # Loan: Received USD (not taxable income, tracked as liability)
        amount_usd = row.get('Amount USD', '') or ''
        if amount_usd:
            return (f'{date},,,{amount_usd},USD,,,,,Loan,{label},{description},{tx_hash}', True)
        return (None, True)
    
    elif tx_type == 'Loan collateral':
        # Loan collateral: Sent BTC (not a sale, BTC used as collateral)
        # Note: Can't use "Loan" label on withdrawals in Koinly, so we leave Label empty
        # and put loan information in description instead
        amount_btc = row.get('Amount BTC', '') or ''
        if amount_btc:
            # Leave Label empty (can't use "Loan" on withdrawals) and put loan info in description
            loan_description = f'Loan collateral (not a sale) - {description}'.strip(' -')
            if not loan_description:
                loan_description = 'Loan collateral (not a sale)'
            # Format: Date,Sent Amount,Sent Currency,Received Amount,Received Currency,
            #         Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash
            # Label (position 10) must be empty - Koinly doesn't allow "Loan" label on withdrawals
            # Description (position 11) has loan info to indicate it's not a taxable sale
            # Build row as list to ensure correct field positions (12 fields total)
            koinly_fields = [
                date,                    # 1. Date
                abs_value(amount_btc),   # 2. Sent Amount
                'BTC',                   # 3. Sent Currency
                '',                      # 4. Received Amount
                '',                      # 5. Received Currency
                '',                      # 6. Fee Amount
                '',                      # 7. Fee Currency
                '',                      # 8. Net Worth Amount
                '',                      # 9. Net Worth Currency
                '',                      # 10. Label (empty - Koinly doesn't allow "Loan" on withdrawals)
                loan_description,        # 11. Description
                tx_hash                  # 12. TxHash
            ]
            return (','.join(koinly_fields), True)
        return (None, True)
    
    return (None, False)


def convert_csv(input_csv, output_file=sys.stdout, error_file=sys.stderr):
    """
    Convert only problematic transactions (currently loans) to Koinly format.
    All other transactions are ignored - they should be imported directly from Strike CSV.
    """
    # Open input file first to catch FileNotFoundError before printing header
    try:
        strike_csv = open(input_csv, newline='')
    except FileNotFoundError:
        raise FileNotFoundError(f'Input file not found: "{input_csv}"')
    
    # Print Koinly headers
    print('Date,Sent Amount,Sent Currency,Received Amount,Received Currency,Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash', file=output_file)
    
    try:
        reader = csv.DictReader(strike_csv)
        loan_count = 0
        for row in reader:
            koinly_line, is_loan = convert_loan_to_koinly(row)
            if is_loan and koinly_line:
                print(koinly_line, file=output_file)
                loan_count += 1
            elif is_loan and not koinly_line:
                print(f'WARNING: Loan transaction with missing amount: {row.get("Reference", "unknown")}', file=error_file)
        
        if loan_count == 0:
            print('No loan transactions found. All transactions can be imported directly from Strike CSV.', file=error_file)
        else:
            print(f'Converted {loan_count} loan transaction(s) to Koinly format.', file=error_file)
            print('Import the original Strike CSV for all other transactions.', file=error_file)
    finally:
        strike_csv.close()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Convert only problematic transactions (currently loans) from Strike CSV to Koinly format. All other transactions should be imported directly from the original Strike CSV.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Convert only loan transactions to stdout
  %(prog)s data/strike-2025-annual-transactions__ORIG.csv

  # Convert only loan transactions and save to file
  %(prog)s data/strike-2025-annual-transactions__ORIG.csv -o loans.csv

How to use:
  1. Import the original Strike CSV into Koinly (it accepts Strike format directly)
  2. Import the output from this converter (loans in Koinly format)
  3. All transactions are now in Koinly!

This converter only outputs transactions that need conversion. All working
transactions should be imported directly from the original Strike CSV file.
        '''
    )
    
    parser.add_argument(
        'input_file',
        help='Input Strike CSV file (2025 format)'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='output_file',
        metavar='FILE',
        help='Output file path for converted transactions (default: stdout)'
    )
    
    args = parser.parse_args()
    
    # Determine output destination
    if args.output_file:
        try:
            output_file = open(args.output_file, 'w', newline='')
        except IOError as e:
            print(f'ERROR: Cannot open output file "{args.output_file}": {e}', file=sys.stderr)
            sys.exit(1)
    else:
        output_file = sys.stdout
    
    # Convert the CSV
    try:
        convert_csv(args.input_file, output_file=output_file)
        if args.output_file:
            print(f'\n✓ Converted transactions saved to: {args.output_file}', file=sys.stderr)
    except FileNotFoundError:
        print(f'ERROR: Input file not found: "{args.input_file}"', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
    finally:
        if args.output_file and output_file != sys.stdout:
            output_file.close()


if __name__ == '__main__':
    main()
