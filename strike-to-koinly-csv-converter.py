#!/usr/bin/env python3
"""
Minimal converter: Only converts problematic transactions (loans and Lightning) to Koinly format.
All other transactions are ignored - import the original Strike CSV directly into Koinly.

Strike 2025 format:
Reference,Date & Time (UTC),Transaction Type,Amount USD,Fee USD,Amount BTC,Fee BTC,BTC Price,Cost Basis (USD),Destination,Description,Transaction Hash,Note

Koinly universal format:
Date,Sent Amount,Sent Currency,Received Amount,Received Currency,Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash

See: https://help.koinly.io/en/articles/3662999-how-to-create-a-custom-csv-file-with-your-data
"""

__version__ = '1.1.0'

import argparse
import csv
import re
import sys


def abs_value(value_str):
    """Convert negative string to positive, preserving precision."""
    if not value_str:
        return ''
    return value_str.lstrip('-')


def format_btc_amount(btc_float):
    """
    Format BTC amount as string, avoiding scientific notation.
    Uses up to 8 decimal places (satoshi precision).
    """
    if btc_float is None:
        return ''
    # Format with up to 8 decimal places, removing trailing zeros
    formatted = f'{btc_float:.8f}'.rstrip('0').rstrip('.')
    return formatted if formatted else '0'


def decode_lightning_invoice(invoice_str):
    """
    Decode BOLT11 Lightning invoice to extract BTC amount.
    
    BOLT11 format: lnbc{amount}{multiplier}...
    Multipliers: m=milli (0.001), u=micro (0.000001), n=nano (0.000000001), p=pico (0.000000000001)
    
    Returns BTC amount as float, or None if decoding fails.
    """
    if not invoice_str or not invoice_str.startswith('lnbc'):
        return None
    
    # Extract amount and multiplier from lnbc{amount}{multiplier}...
    # Pattern: lnbc followed by digits, then multiplier (m, u, n, p), then more chars
    match = re.match(r'lnbc(\d+)([munp])', invoice_str)
    if not match:
        return None
    
    amount_str = match.group(1)
    multiplier_char = match.group(2)
    
    try:
        amount = float(amount_str)
    except ValueError:
        return None
    
    # Convert based on multiplier
    multipliers = {
        'm': 0.001,      # milli-BTC
        'u': 0.000001,   # micro-BTC
        'n': 0.000000001,  # nano-BTC
        'p': 0.000000000001  # pico-BTC
    }
    
    multiplier = multipliers.get(multiplier_char)
    if multiplier is None:
        return None
    
    return amount * multiplier


def is_lightning_transaction(row):
    """Check if transaction involves Lightning Network (has lnbc invoice in Destination)."""
    destination = row.get('Destination', '') or ''
    return destination.startswith('lnbc')


def convert_lightning_to_koinly(row):
    """
    Convert a Lightning transaction to Koinly format.
    
    Returns tuple: (koinly_line, is_lightning)
    - koinly_line: CSV line string if Lightning transaction, None otherwise
    - is_lightning: True if this is a Lightning transaction
    """
    if not is_lightning_transaction(row):
        return (None, False)
    
    tx_type = row['Transaction Type']
    date = row['Date & Time (UTC)']
    tx_id = row['Reference']
    tx_hash = row.get('Transaction Hash', '') or ''
    description = row.get('Description', '') or ''
    destination = row.get('Destination', '') or ''
    
    # Decode Lightning invoice to get BTC amount
    btc_amount = decode_lightning_invoice(destination)
    
    if btc_amount is None:
        # If we can't decode, try to use existing Amount BTC if available
        amount_btc_str = row.get('Amount BTC', '') or ''
        if amount_btc_str:
            try:
                btc_amount = abs(float(amount_btc_str))
            except (ValueError, TypeError):
                return (None, True)  # Can't determine amount
        else:
            return (None, True)  # No amount available
    
    # Get fee if available
    fee_btc_str = row.get('Fee BTC', '') or ''
    fee_btc = ''
    if fee_btc_str:
        try:
            fee_btc = abs_value(fee_btc_str)
        except (ValueError, TypeError):
            pass
    
    # Build description
    lightning_desc = f'Lightning Network transaction - {description}'.strip(' -')
    if not lightning_desc or lightning_desc == 'Lightning Network transaction':
        lightning_desc = 'Lightning Network transaction'
    
    label = f'{tx_type}|Strike transaction: {tx_id}'
    
    # Format: Date,Sent Amount,Sent Currency,Received Amount,Received Currency,
    #         Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash
    if tx_type == 'Receive':
        # Lightning deposit: Received BTC
        koinly_fields = [
            date,                    # 1. Date
            '',                      # 2. Sent Amount
            '',                      # 3. Sent Currency
            format_btc_amount(btc_amount),  # 4. Received Amount
            'BTC',                   # 5. Received Currency
            fee_btc,                 # 6. Fee Amount
            'BTC' if fee_btc else '', # 7. Fee Currency
            '',                      # 8. Net Worth Amount
            '',                      # 9. Net Worth Currency
            '',                      # 10. Label
            lightning_desc,          # 11. Description
            tx_hash                  # 12. TxHash
        ]
        return (','.join(koinly_fields), True)
    
    elif tx_type == 'Send':
        # Lightning withdrawal: Sent BTC
        koinly_fields = [
            date,                    # 1. Date
            format_btc_amount(btc_amount),  # 2. Sent Amount
            'BTC',                   # 3. Sent Currency
            '',                      # 4. Received Amount
            '',                      # 5. Received Currency
            fee_btc,                 # 6. Fee Amount
            'BTC' if fee_btc else '', # 7. Fee Currency
            '',                      # 8. Net Worth Amount
            '',                      # 9. Net Worth Currency
            '',                      # 10. Label
            lightning_desc,          # 11. Description
            tx_hash                  # 12. TxHash
        ]
        return (','.join(koinly_fields), True)
    
    # Other transaction types with Lightning invoices - treat as unknown
    return (None, True)


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
    Convert problematic transactions (loans and Lightning) to Koinly format.
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
        lightning_count = 0
        for row in reader:
            # Check for loan transactions first
            koinly_line, is_loan = convert_loan_to_koinly(row)
            if is_loan:
                if koinly_line:
                    print(koinly_line, file=output_file)
                    loan_count += 1
                else:
                    print(f'WARNING: Loan transaction with missing amount: {row.get("Reference", "unknown")}', file=error_file)
                continue
            
            # Check for Lightning transactions
            koinly_line, is_lightning = convert_lightning_to_koinly(row)
            if is_lightning:
                if koinly_line:
                    print(koinly_line, file=output_file)
                    lightning_count += 1
                else:
                    print(f'WARNING: Lightning transaction with missing amount: {row.get("Reference", "unknown")}', file=error_file)
        
        total_count = loan_count + lightning_count
        if total_count == 0:
            print('No loan or Lightning transactions found. All transactions can be imported directly from Strike CSV.', file=error_file)
        else:
            if loan_count > 0:
                print(f'Converted {loan_count} loan transaction(s) to Koinly format.', file=error_file)
            if lightning_count > 0:
                print(f'Converted {lightning_count} Lightning transaction(s) to Koinly format.', file=error_file)
            print('Import the original Strike CSV for all other transactions.', file=error_file)
    finally:
        strike_csv.close()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Convert problematic transactions (loans and Lightning) from Strike CSV to Koinly format. All other transactions should be imported directly from the original Strike CSV.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Convert loan and Lightning transactions to stdout
  %(prog)s data/strike-2025-annual-transactions__ORIG.csv

  # Convert loan and Lightning transactions and save to file
  %(prog)s data/strike-2025-annual-transactions__ORIG.csv -o converted.csv

How to use:
  1. Import the original Strike CSV into Koinly (it accepts Strike format directly)
  2. Import the output from this converter (loans and Lightning transactions in Koinly format)
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
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
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
