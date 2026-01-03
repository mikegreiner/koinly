#!/usr/bin/env python3
"""
Test suite for Strike to Koinly CSV converter (minimal version - loans only).
"""

import csv
import io
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

# Import the converter module (handles hyphenated filename)
spec = importlib.util.spec_from_file_location(
    "converter",
    Path(__file__).parent / "strike-to-koinly-csv-converter.py"
)
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""
    
    def test_abs_value_positive(self):
        """Test abs_value with positive number."""
        self.assertEqual(converter.abs_value('10.00'), '10.00')
        self.assertEqual(converter.abs_value('0.00010675'), '0.00010675')
    
    def test_abs_value_negative(self):
        """Test abs_value with negative number."""
        self.assertEqual(converter.abs_value('-10.00'), '10.00')
        self.assertEqual(converter.abs_value('-0.12345678'), '0.12345678')
    
    def test_abs_value_empty(self):
        """Test abs_value with empty string."""
        self.assertEqual(converter.abs_value(''), '')
        self.assertEqual(converter.abs_value(None), '')


class TestLoanConversion(unittest.TestCase):
    """Test loan transaction conversion."""
    
    def test_loan_conversion(self):
        """Test Loan transaction conversion to Koinly format."""
        row = {
            'Date & Time (UTC)': 'Nov 15 2025 02:59:15',
            'Transaction Type': 'Loan',
            'Reference': 'test-loan-ref-123',
            'Amount USD': '10000.00',
            'Description': '',
            'Transaction Hash': ''
        }
        koinly_line, is_loan = converter.convert_loan_to_koinly(row)
        self.assertTrue(is_loan)
        self.assertIsNotNone(koinly_line)
        self.assertIn('Nov 15 2025 02:59:15', koinly_line)
        self.assertIn(',,10000.00,USD,', koinly_line)
        self.assertIn('Loan,Loan|Strike transaction: test-loan-ref-123', koinly_line)
    
    def test_loan_collateral_conversion(self):
        """Test Loan collateral transaction conversion to Koinly format."""
        row = {
            'Date & Time (UTC)': 'Nov 15 2025 02:59:14',
            'Transaction Type': 'Loan collateral',
            'Reference': 'test-loan-collateral-ref-456',
            'Amount BTC': '-0.12345678',
            'Description': '',
            'Transaction Hash': ''
        }
        koinly_line, is_loan = converter.convert_loan_to_koinly(row)
        self.assertTrue(is_loan)
        self.assertIsNotNone(koinly_line)
        self.assertIn('Nov 15 2025 02:59:14', koinly_line)
        self.assertIn('0.12345678,BTC,', koinly_line)
        # Loan collateral can't use "Loan" label on withdrawals, so Label is empty
        # and loan info is in description
        self.assertIn('Loan collateral (not a sale)', koinly_line)
        # Label field (position 10) should be empty (no "Loan" label for withdrawals)
        parts = koinly_line.split(',')
        self.assertEqual(parts[9], '')  # Label field is empty (position 10, 0-indexed)
        self.assertIn('Loan collateral (not a sale)', parts[10])  # Description has loan info
    
    def test_non_loan_transaction_ignored(self):
        """Test that non-loan transactions are ignored."""
        row = {
            'Date & Time (UTC)': 'Jan 01 2025 03:23:34',
            'Transaction Type': 'Purchase',
            'Reference': 'test-ref-123',
            'Amount USD': '-10.00',
            'Amount BTC': '0.00010675'
        }
        koinly_line, is_loan = converter.convert_loan_to_koinly(row)
        self.assertFalse(is_loan)
        self.assertIsNone(koinly_line)
    
    def test_loan_with_missing_amount(self):
        """Test loan transaction with missing amount."""
        row = {
            'Date & Time (UTC)': 'Nov 15 2025 02:59:15',
            'Transaction Type': 'Loan',
            'Reference': 'test-loan',
            'Amount USD': '',
            'Description': '',
            'Transaction Hash': ''
        }
        koinly_line, is_loan = converter.convert_loan_to_koinly(row)
        self.assertTrue(is_loan)
        self.assertIsNone(koinly_line)  # Should return None when amount is missing


class TestCSVProcessing(unittest.TestCase):
    """Test full CSV file processing."""
    
    def create_test_csv(self, rows):
        """Create a temporary CSV file with test data."""
        csv_content = 'Reference,Date & Time (UTC),Transaction Type,Amount USD,Fee USD,Amount BTC,Fee BTC,BTC Price,Cost Basis (USD),Destination,Description,Transaction Hash,Note\n'
        for row in rows:
            csv_content += ','.join(str(row.get(col, '')) for col in [
                'Reference', 'Date & Time (UTC)', 'Transaction Type', 'Amount USD', 'Fee USD',
                'Amount BTC', 'Fee BTC', 'BTC Price', 'Cost Basis (USD)', 'Destination',
                'Description', 'Transaction Hash', 'Note'
            ]) + '\n'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            return f.name
    
    def test_only_loans_output(self):
        """Test that only loan transactions are output."""
        rows = [
            {
                'Reference': 'test-deposit-1',
                'Date & Time (UTC)': 'Jan 01 2025 03:23:18',
                'Transaction Type': 'Deposit',
                'Amount USD': '10.00',
                'Fee USD': '',
                'Amount BTC': '',
                'Fee BTC': '',
                'BTC Price': '',
                'Cost Basis (USD)': '',
                'Destination': '',
                'Description': '',
                'Transaction Hash': '',
                'Note': ''
            },
            {
                'Reference': 'test-loan-1',
                'Date & Time (UTC)': 'Nov 15 2025 02:59:15',
                'Transaction Type': 'Loan',
                'Amount USD': '10000.00',
                'Fee USD': '',
                'Amount BTC': '',
                'Fee BTC': '',
                'BTC Price': '',
                'Cost Basis (USD)': '',
                'Destination': '',
                'Description': '',
                'Transaction Hash': '',
                'Note': ''
            },
            {
                'Reference': 'test-purchase-1',
                'Date & Time (UTC)': 'Jan 01 2025 03:23:34',
                'Transaction Type': 'Purchase',
                'Amount USD': '-10.00',
                'Fee USD': '',
                'Amount BTC': '0.00010675',
                'Fee BTC': '',
                'BTC Price': '93676.81',
                'Cost Basis (USD)': '10.00',
                'Destination': '',
                'Description': '',
                'Transaction Hash': '',
                'Note': ''
            },
            {
                'Reference': 'test-loan-collateral-1',
                'Date & Time (UTC)': 'Nov 15 2025 02:59:14',
                'Transaction Type': 'Loan collateral',
                'Amount USD': '',
                'Fee USD': '',
                'Amount BTC': '-0.12345678',
                'Fee BTC': '',
                'BTC Price': '',
                'Cost Basis (USD)': '',
                'Destination': '',
                'Description': '',
                'Transaction Hash': '',
                'Note': ''
            }
        ]
        
        csv_file = self.create_test_csv(rows)
        try:
            output = io.StringIO()
            error_output = io.StringIO()
            converter.convert_csv(csv_file, output_file=output, error_file=error_output)
            
            output_lines = output.getvalue().strip().split('\n')
            error_content = error_output.getvalue()
            
            # Should have header + 2 loan transactions (deposit and purchase are ignored)
            self.assertEqual(len(output_lines), 3)
            
            # Check header is Koinly format
            self.assertIn('Date,Sent Amount,Sent Currency', output_lines[0])
            
            # Check only loan transactions are present
            self.assertIn('Loan,Loan|Strike transaction: test-loan-1', output_lines[1])
            # Loan collateral has empty Label (can't use "Loan" on withdrawals)
            self.assertIn('Loan collateral (not a sale)', output_lines[2])
            
            # Check non-loan transactions are NOT present
            self.assertNotIn('test-deposit-1', output.getvalue())
            self.assertNotIn('test-purchase-1', output.getvalue())
            
            # Check error message mentions loan count
            self.assertIn('Converted 2 loan transaction(s)', error_content)
        finally:
            import os
            os.unlink(csv_file)
    
    def test_no_loans_message(self):
        """Test that appropriate message is shown when no loans found."""
        rows = [
            {
                'Reference': 'test-deposit-1',
                'Date & Time (UTC)': 'Jan 01 2025 03:23:18',
                'Transaction Type': 'Deposit',
                'Amount USD': '10.00',
                'Fee USD': '',
                'Amount BTC': '',
                'Fee BTC': '',
                'BTC Price': '',
                'Cost Basis (USD)': '',
                'Destination': '',
                'Description': '',
                'Transaction Hash': '',
                'Note': ''
            }
        ]
        
        csv_file = self.create_test_csv(rows)
        try:
            output = io.StringIO()
            error_output = io.StringIO()
            converter.convert_csv(csv_file, output_file=output, error_file=error_output)
            
            output_lines = output.getvalue().strip().split('\n')
            error_content = error_output.getvalue()
            
            # Should have only header
            self.assertEqual(len(output_lines), 1)
            
            # Check message
            self.assertIn('No loan transactions found', error_content)
        finally:
            import os
            os.unlink(csv_file)


if __name__ == '__main__':
    unittest.main()
