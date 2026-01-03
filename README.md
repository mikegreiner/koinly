# Strike to Koinly CSV Converter (Minimal)

A minimal Python tool that only converts problematic transactions (loans and Lightning) to Koinly format. All other transactions should be imported directly from the original Strike CSV.

**Version:** 1.1.0

## Quick Start

```bash
# Convert loan and Lightning transactions to Koinly format
python3 strike-to-koinly-csv-converter.py data/strike-2025-annual-transactions__ORIG.csv -o converted.csv

# View help
python3 strike-to-koinly-csv-converter.py -h

# Run tests
python3 -m pytest test_strike_converter.py -v
```

## Overview

**Koinly can import Strike 2025 CSV format directly** - except for certain transaction types (loans and Lightning). This converter:

- ✅ **Only converts problematic transactions** - Loans and Lightning transactions
- ✅ **Ignores all working transactions** - Import them directly from Strike CSV
- ✅ **Minimal conversion** - No unnecessary data transformation
- ✅ **Easy to extend** - Add new transaction types as problems arise

**Philosophy:** Only convert what's broken. Everything else stays in the original Strike format.

### What It Does

- **Only outputs transactions that need conversion** (loans and Lightning)
- **Ignores all other transactions** - they work fine in Strike format
- Converts loan transactions to Koinly format with proper tax labeling
- Decodes Lightning invoice amounts from BOLT11 format and converts to Koinly format
- Outputs minimal CSV with only problematic transactions

## Requirements

- Python 3.6 or higher
- No external dependencies required (uses only Python standard library)

## Installation

No installation needed! Just download the converter script:

```bash
# Clone or download the repository
git clone <repository-url>
cd Strike
```

## Usage

### Basic Usage

```bash
python3 strike-to-koinly-csv-converter.py [-h] [-o FILE] input_file
```

### Options

- `-h, --help`: Display help message with usage examples and exit
- `-o FILE, --output FILE`: Output file path (default: stdout)

### Examples

**Display help:**
```bash
python3 strike-to-koinly-csv-converter.py -h
```

**Convert loan and Lightning transactions to stdout:**
```bash
python3 strike-to-koinly-csv-converter.py data/strike-2025-annual-transactions__ORIG.csv
```

**Convert loan and Lightning transactions and save to file:**
```bash
python3 strike-to-koinly-csv-converter.py data/strike-2025-annual-transactions__ORIG.csv -o converted.csv
```

### How to Import into Koinly

1. **Import the original Strike CSV** into Koinly (it accepts Strike format directly)
2. **Delete any Lightning transactions** that were imported with missing/zero amounts (they'll be duplicates)
3. **Import the output from this converter** (loans and Lightning transactions in Koinly format)
4. All transactions are now in Koinly!

**Example:**
```bash
# Generate converted file
python3 strike-to-koinly-csv-converter.py strike-2025-annual-transactions__ORIG.csv -o converted.csv

# Then in Koinly:
# 1. Import strike-2025-annual-transactions__ORIG.csv (all non-problematic transactions)
# 2. Delete any Lightning transactions that have 0.0 or missing amounts (identified by transaction hash)
# 3. Import converted.csv (loan and Lightning transactions with correct amounts)
```

**Note:** Lightning transactions in the original Strike CSV often have empty Amount BTC/USD fields. The converter decodes the amounts from the Lightning invoice (BOLT11 format) and creates properly formatted transactions. You'll need to delete the old Lightning transactions with missing amounts before importing the corrected ones.

## Input/Output Formats

### Strike 2025 Format (Input - also used directly in Koinly)

```
Reference,Date & Time (UTC),Transaction Type,Amount USD,Fee USD,Amount BTC,Fee BTC,BTC Price,Cost Basis (USD),Destination,Description,Transaction Hash,Note
```

**Most transactions use this format** - import directly into Koinly.

### Koinly Universal Format (Output - only for problematic transactions)

```
Date,Sent Amount,Sent Currency,Received Amount,Received Currency,Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash
```

**Only problematic transactions** (loans and Lightning) are converted to this format.

## Supported Transaction Types

The converter handles all Strike transaction types:

| Transaction Type | Description | Tax Treatment |
|-----------------|-------------|----------------|
| **Purchase** | USD → BTC conversion | Taxable event (cost basis tracked) |
| **Sale** | BTC → USD conversion | Taxable event (capital gains/losses) |
| **Deposit** | USD deposit to account | Not taxable |
| **Withdrawal** | USD withdrawal from account | Not taxable |
| **Send** | BTC send (usually Lightning) | Not taxable (transfer) |
| **Receive** | BTC receive (Lightning or on-chain) | Not taxable (transfer) |
| **Loan** | USD loan receipt | **Not taxable income** (labeled "Loan" for Koinly) |
| **Loan collateral** | BTC used as collateral | **Not a sale** (empty Label, loan info in Description) |

### Currently Supported Problematic Transactions

- **Loan**: USD loan receipt (not taxable income, labeled "Loan" for Koinly)
- **Loan collateral**: BTC used as collateral (not a sale, **empty Label field** because Koinly doesn't allow "Loan" label on withdrawals; loan information is in Description field for manual categorization)
- **Lightning Receive**: BTC received via Lightning Network (deposits) - amounts decoded from BOLT11 invoice format
- **Lightning Send**: BTC sent via Lightning Network (withdrawals) - amounts decoded from BOLT11 invoice format

**Why Lightning transactions need conversion:**
- Strike CSV exports often have empty Amount BTC/USD fields for Lightning transactions
- The converter decodes the BTC amount from the Lightning invoice (BOLT11 format) in the Destination field
- Supports all BOLT11 multipliers: milli (m), micro (u), nano (n), pico (p)
- Properly formats amounts to avoid scientific notation

**All other transaction types** (Purchase, Sale, Deposit, Withdrawal, non-Lightning Send/Receive) work fine in Strike format and are ignored by this converter.

## Testing

The project includes a comprehensive test suite to validate the converter and support future changes.

### Running Tests

**Using pytest (recommended):**
```bash
# Install test dependencies (optional)
pip install -r requirements.txt

# Run all tests
python3 -m pytest test_strike_converter.py -v

# Run with coverage report
python3 -m pytest test_strike_converter.py --cov=strike_to_koinly_csv_converter --cov-report=term-missing
```

**Using unittest (built-in, no dependencies):**
```bash
python3 -m unittest test_strike_converter.py -v
```

**Using the test runner script:**
```bash
./run_tests.sh
```

### Test Coverage

The test suite includes **20+ tests** covering:

- ✅ **Helper functions**: `abs_value()`, `format_btc_amount()`, `decode_lightning_invoice()`, `is_lightning_transaction()`
- ✅ **Loan conversion**: Loan and Loan collateral transactions
- ✅ **Lightning conversion**: Lightning Receive and Send transactions with various amounts
- ✅ **Transaction filtering**: Non-problematic transactions are correctly ignored
- ✅ **Full CSV processing**: End-to-end file processing
- ✅ **Edge cases**: Missing amounts, invalid invoices, no problematic transactions found

### Test Files

- `test_strike_converter.py`: Main test suite (20+ tests)
- `test_data_sample.csv`: Sample test data covering all transaction types
- `pytest.ini`: Pytest configuration
- `requirements.txt`: Test dependencies (pytest, pytest-cov)

## Project Structure

```
Strike/
├── strike-to-koinly-csv-converter.py  # Main converter script
├── test_strike_converter.py            # Test suite
├── test_data_sample.csv                # Sample test data
├── requirements.txt                    # Test dependencies
├── pytest.ini                          # Pytest configuration
├── run_tests.sh                        # Test runner script
├── README.md                           # This file
└── data/
    ├── strike-2025-annual-transactions__ORIG.csv  # Example input file
    └── archive/                        # Archived old format files
```

## Troubleshooting

### Common Issues

**"Input file not found" error:**
- Verify the file path is correct
- Use absolute path if relative path doesn't work
- Check file permissions

**"Cannot open output file" error:**
- Ensure the output directory exists
- Check write permissions for the output location

**Unknown transaction type warnings:**
- The converter will print warnings for unsupported transaction types
- These transactions will be skipped in the output
- Check the Strike CSV format matches the 2025 format

**Empty output:**
- Verify the input CSV has data rows (not just headers)
- Check that transactions have required amount fields
- Transactions with missing required amounts are skipped

**Koinly import error: "Label for a withdrawal cannot be loan":**
- This was a known issue with Loan collateral transactions
- Fixed: Loan collateral transactions now have an empty Label field (Koinly doesn't allow "Loan" label on withdrawals)
- Loan information is preserved in the Description field for manual categorization
- If you see this error, regenerate the loans CSV file with the latest converter version

## How It Works

1. **Reads** the Strike CSV file using Python's `csv.DictReader`
2. **Processes** each row based on transaction type
3. **Converts** amounts, fees, and metadata to Koinly format
4. **Labels** special transactions (loans) appropriately
5. **Outputs** the converted CSV to stdout or a file

### Key Features

- **Preserves precision**: Uses string manipulation to avoid floating-point rounding issues
- **Handles missing data**: Gracefully skips transactions with missing required fields
- **Error reporting**: Prints errors to stderr while output goes to stdout/file
- **Flexible output**: Can output to file or stdout for piping

## Contributing

When making changes:

1. Run the test suite to ensure nothing breaks:
   ```bash
   python3 -m pytest test_strike_converter.py -v
   ```

2. Add tests for new transaction types or features

3. Update this README if adding new functionality

## License

[Add your license information here]

## References

- [Koinly Custom CSV Format Documentation](https://help.koinly.io/en/articles/3662999-how-to-create-a-custom-csv-file-with-your-data)
- Strike CSV export format (2025 version)

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the test suite for usage examples
- Run with `-h` flag to see detailed help
