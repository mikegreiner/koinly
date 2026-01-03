#!/usr/bin/env python3
"""
Test suite for Strike to Koinly CSV converter (minimal version - loans and Lightning).
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
    
    def test_format_btc_amount(self):
        """Test format_btc_amount formatting."""
        self.assertEqual(converter.format_btc_amount(0.001), '0.001')
        self.assertEqual(converter.format_btc_amount(0.15), '0.15')
        self.assertEqual(converter.format_btc_amount(0.0001), '0.0001')
        self.assertEqual(converter.format_btc_amount(0.00094265), '0.00094265')
        self.assertEqual(converter.format_btc_amount(0.00000051), '0.00000051')
        self.assertEqual(converter.format_btc_amount(0), '0')
        self.assertEqual(converter.format_btc_amount(None), '')
    
    def test_decode_lightning_invoice(self):
        """Test Lightning invoice decoding."""
        # Test milli-BTC (m)
        self.assertAlmostEqual(converter.decode_lightning_invoice('lnbc1m1p...'), 0.001, places=8)
        self.assertAlmostEqual(converter.decode_lightning_invoice('lnbc150m1p...'), 0.15, places=8)
        self.assertAlmostEqual(converter.decode_lightning_invoice('lnbc50m1p...'), 0.05, places=8)
        
        # Test micro-BTC (u)
        self.assertAlmostEqual(converter.decode_lightning_invoice('lnbc100u1p...'), 0.0001, places=8)
        
        # Test nano-BTC (n)
        self.assertAlmostEqual(converter.decode_lightning_invoice('lnbc942650n1p...'), 0.00094265, places=8)
        self.assertAlmostEqual(converter.decode_lightning_invoice('lnbc8473570n1p...'), 0.00847357, places=8)
        
        # Test invalid invoices
        self.assertIsNone(converter.decode_lightning_invoice(''))
        self.assertIsNone(converter.decode_lightning_invoice('not-an-invoice'))
        self.assertIsNone(converter.decode_lightning_invoice('bc1q...'))  # On-chain address
        self.assertIsNone(converter.decode_lightning_invoice('lnbc'))  # Incomplete
    
    def test_is_lightning_transaction(self):
        """Test Lightning transaction detection."""
        self.assertTrue(converter.is_lightning_transaction({'Destination': 'lnbc1m1p...'}))
        self.assertTrue(converter.is_lightning_transaction({'Destination': 'lnbc150m1p...'}))
        self.assertFalse(converter.is_lightning_transaction({'Destination': 'bc1q...'}))
        self.assertFalse(converter.is_lightning_transaction({'Destination': ''}))
        self.assertFalse(converter.is_lightning_transaction({'Destination': 'josh_greiner'}))


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


class TestLightningConversion(unittest.TestCase):
    """Test Lightning transaction conversion."""
    
    def test_lightning_receive_conversion(self):
        """Test Lightning Receive (deposit) transaction conversion."""
        row = {
            'Date & Time (UTC)': 'Nov 15 2025 02:48:15',
            'Transaction Type': 'Receive',
            'Reference': 'test-lightning-receive-123',
            'Amount USD': '',
            'Amount BTC': '',
            'Fee BTC': '',
            'Destination': 'lnbc1m1p5306depp5jyfagjh565ezmv6h58hcky9062s5jhryskc6h4wy0nehnpfumh9qdqqcqzzsxqrrs0fppqhq8k0f78lasj2xenegmg0nzdx6gyx6fxsp5vrhs36tly67yzzja93705wc2u2twr06cnyg7kryt2ve2ufd8ah4q9qxpqysgqs5ez3p4sanv9d74kazdhkfj826ng5huwesw9tl3gk6979cmmjtr4u3ykqhaaywuw3anhlsxctdy550wy6dlwtt9jfhys0crz4vu608sp9cscv6',
            'Description': '',
            'Transaction Hash': '9113d44af4d5322db357a1ef8b10afd2a1495c6485b1abd5c47cf379853cddca'
        }
        koinly_line, is_lightning = converter.convert_lightning_to_koinly(row)
        self.assertTrue(is_lightning)
        self.assertIsNotNone(koinly_line)
        self.assertIn('Nov 15 2025 02:48:15', koinly_line)
        self.assertIn(',,0.001,BTC,', koinly_line)
        self.assertIn('Lightning Network transaction', koinly_line)
        self.assertIn('9113d44af4d5322db357a1ef8b10afd2a1495c6485b1abd5c47cf379853cddca', koinly_line)
    
    def test_lightning_receive_with_fee(self):
        """Test Lightning Receive transaction with fee."""
        row = {
            'Date & Time (UTC)': 'Nov 15 2025 02:50:07',
            'Transaction Type': 'Receive',
            'Reference': 'test-lightning-receive-fee',
            'Amount USD': '',
            'Amount BTC': '',
            'Fee BTC': '0.00000011',
            'Destination': 'lnbc150m1p53063fpp5gwztadvg3umqyuy3yfdct7n6pjxumahahm85z3a0z72wfn8gg2asdqqcqzzsxqrrs0fppqj8fklcgll4yf6dq9dv9zn57x8sl4hyp3sp5hj5yymyfxjursd95h2vfwyww24hxvvyct200jacj63pkt8phrmds9qxpqysgq7fx8f2d3hwlwup7vst263w73j2xna8svatmqc4nyz9tz9agqnq9k5hannxfdpg3xqpeazghfzy8gtfhkrfdp3mzpvnfqcrlxzf7drzgqz7xd6r',
            'Description': '',
            'Transaction Hash': '4384beb5888f36027091225b85fa7a0c8dcdf6fdbecf4147af1794e4cce842bb'
        }
        koinly_line, is_lightning = converter.convert_lightning_to_koinly(row)
        self.assertTrue(is_lightning)
        self.assertIsNotNone(koinly_line)
        self.assertIn(',,0.15,BTC,', koinly_line)
        self.assertIn('0.00000011,BTC,', koinly_line)
    
    def test_lightning_send_conversion(self):
        """Test Lightning Send (withdrawal) transaction conversion."""
        row = {
            'Date & Time (UTC)': 'Jul 27 2025 16:40:04',
            'Transaction Type': 'Send',
            'Reference': 'test-lightning-send-123',
            'Amount USD': '',
            'Amount BTC': '-0.00100051',  # Some Send transactions have Amount BTC populated
            'Fee BTC': '0.00000051',
            'Destination': 'lnbc1m1p5gv4shpp5xg2d6wpphqcpgfe3ecrjwhqdwnfyyls4047h2m6jfqvkgqk9aqnsdp9f35kw6r5de5kueeqv3jhqmmnd96zqvpwxqcrzcqzzsxqrrssrzjqvphmsywntrrhqjcraumvc4y6r8v4z5v593trte429v4hredj7ms5rdxngqqgecqqyqqqqqqqqqqqqqq2qsp5lx694ppunp6s3gk4vjl0j4gtt3xx44vynk65gx2f2hvcztep0dms9qxpqysgq3xhkk0gzam8es5rqw35sker2a40wkz9lpg4lnlyrk6cuyqjrxge4mj39fewgjefwf6zp6ju4x7ddqa0n6zsu5d2whdf3eh2trx5jtqqpr6vy2t',
            'Description': 'Lightning deposit 0.001',
            'Transaction Hash': '3214dd3821b830142731ce07275c0d74d2427e157d7d756f5248196402c5e827'
        }
        koinly_line, is_lightning = converter.convert_lightning_to_koinly(row)
        self.assertTrue(is_lightning)
        self.assertIsNotNone(koinly_line)
        self.assertIn('Jul 27 2025 16:40:04', koinly_line)
        self.assertIn('0.001,BTC,', koinly_line)  # Decoded from invoice, not from Amount BTC
        self.assertIn('0.00000051,BTC,', koinly_line)
        self.assertIn('Lightning Network transaction', koinly_line)
    
    def test_lightning_nano_amount(self):
        """Test Lightning transaction with nano-BTC amount."""
        row = {
            'Date & Time (UTC)': 'Nov 11 2025 01:04:17',
            'Transaction Type': 'Receive',
            'Reference': 'test-lightning-nano',
            'Amount USD': '',
            'Amount BTC': '',
            'Fee BTC': '',
            'Destination': 'lnbc942650n1p539zm6pp5mxqshyuzmnmthhmsj8yt4nw5nshcuye6me2h387kk20kcjz349tqdqqcqzzsxqrrs0fppqn464gptcuxz3ct0p2ra8jj3he9ljle94sp5zepn3dqqphq2zmxjw9weytavvntvwq5wjswzyy0dgtmshmjmsjjq9qxpqysgqlwa0zn4psl6n3ukusjxcajy5x25sglw2vsluq9kch4w5yr8dq29hqt5tdh52s2l85h3myazll362ajmke4ntrda7e785w7tygr09cmsqtstxs3',
            'Description': '',
            'Transaction Hash': 'd9810b9382dcf6bbdf7091c8bacdd49c2f8e133ade55789fd6b29f6c4851a956'
        }
        koinly_line, is_lightning = converter.convert_lightning_to_koinly(row)
        self.assertTrue(is_lightning)
        self.assertIsNotNone(koinly_line)
        self.assertIn(',,0.00094265,BTC,', koinly_line)
    
    def test_non_lightning_transaction_ignored(self):
        """Test that non-Lightning transactions are ignored."""
        row = {
            'Date & Time (UTC)': 'Jan 01 2025 03:23:34',
            'Transaction Type': 'Purchase',
            'Reference': 'test-ref-123',
            'Destination': 'bc1q...',  # On-chain address, not Lightning
            'Amount USD': '-10.00',
            'Amount BTC': '0.00010675'
        }
        koinly_line, is_lightning = converter.convert_lightning_to_koinly(row)
        self.assertFalse(is_lightning)
        self.assertIsNone(koinly_line)
    
    def test_lightning_with_missing_amount(self):
        """Test Lightning transaction with missing/invalid invoice."""
        row = {
            'Date & Time (UTC)': 'Nov 15 2025 02:48:15',
            'Transaction Type': 'Receive',
            'Reference': 'test-lightning-invalid',
            'Amount USD': '',
            'Amount BTC': '',  # No amount in CSV
            'Fee BTC': '',
            'Destination': 'lnbc',  # Invalid/incomplete invoice
            'Description': '',
            'Transaction Hash': 'test-hash'
        }
        koinly_line, is_lightning = converter.convert_lightning_to_koinly(row)
        self.assertTrue(is_lightning)
        self.assertIsNone(koinly_line)  # Should return None when amount can't be determined


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
    
    def test_only_problematic_transactions_output(self):
        """Test that only loan and Lightning transactions are output."""
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
            },
            {
                'Reference': 'test-lightning-receive-1',
                'Date & Time (UTC)': 'Nov 15 2025 02:48:15',
                'Transaction Type': 'Receive',
                'Amount USD': '',
                'Fee USD': '',
                'Amount BTC': '',
                'Fee BTC': '',
                'BTC Price': '',
                'Cost Basis (USD)': '',
                'Destination': 'lnbc1m1p5306depp5jyfagjh565ezmv6h58hcky9062s5jhryskc6h4wy0nehnpfumh9qdqqcqzzsxqrrs0fppqhq8k0f78lasj2xenegmg0nzdx6gyx6fxsp5vrhs36tly67yzzja93705wc2u2twr06cnyg7kryt2ve2ufd8ah4q9qxpqysgqs5ez3p4sanv9d74kazdhkfj826ng5huwesw9tl3gk6979cmmjtr4u3ykqhaaywuw3anhlsxctdy550wy6dlwtt9jfhys0crz4vu608sp9cscv6',
                'Description': '',
                'Transaction Hash': '9113d44af4d5322db357a1ef8b10afd2a1495c6485b1abd5c47cf379853cddca',
                'Note': ''
            },
            {
                'Reference': 'test-lightning-send-1',
                'Date & Time (UTC)': 'Jul 27 2025 16:40:04',
                'Transaction Type': 'Send',
                'Amount USD': '',
                'Fee USD': '',
                'Amount BTC': '-0.00100051',
                'Fee BTC': '0.00000051',
                'BTC Price': '',
                'Cost Basis (USD)': '',
                'Destination': 'lnbc1m1p5gv4shpp5xg2d6wpphqcpgfe3ecrjwhqdwnfyyls4047h2m6jfqvkgqk9aqnsdp9f35kw6r5de5kueeqv3jhqmmnd96zqvpwxqcrzcqzzsxqrrssrzjqvphmsywntrrhqjcraumvc4y6r8v4z5v593trte429v4hredj7ms5rdxngqqgecqqyqqqqqqqqqqqqqq2qsp5lx694ppunp6s3gk4vjl0j4gtt3xx44vynk65gx2f2hvcztep0dms9qxpqysgq3xhkk0gzam8es5rqw35sker2a40wkz9lpg4lnlyrk6cuyqjrxge4mj39fewgjefwf6zp6ju4x7ddqa0n6zsu5d2whdf3eh2trx5jtqqpr6vy2t',
                'Description': 'Lightning deposit 0.001',
                'Transaction Hash': '3214dd3821b830142731ce07275c0d74d2427e157d7d756f5248196402c5e827',
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
            
            # Should have header + 2 loan transactions + 2 Lightning transactions (deposit and purchase are ignored)
            self.assertEqual(len(output_lines), 5)
            
            # Check header is Koinly format
            self.assertIn('Date,Sent Amount,Sent Currency', output_lines[0])
            
            # Check loan transactions are present
            self.assertIn('Loan,Loan|Strike transaction: test-loan-1', output.getvalue())
            # Loan collateral has empty Label (can't use "Loan" on withdrawals)
            self.assertIn('Loan collateral (not a sale)', output.getvalue())
            
            # Check Lightning transactions are present
            self.assertIn('Lightning Network transaction', output.getvalue())
            self.assertIn('0.001,BTC,', output.getvalue())  # Lightning Receive amount
            self.assertIn('9113d44af4d5322db357a1ef8b10afd2a1495c6485b1abd5c47cf379853cddca', output.getvalue())
            
            # Check non-problematic transactions are NOT present
            self.assertNotIn('test-deposit-1', output.getvalue())
            self.assertNotIn('test-purchase-1', output.getvalue())
            
            # Check error message mentions both loan and Lightning counts
            self.assertIn('Converted 2 loan transaction(s)', error_content)
            self.assertIn('Converted 2 Lightning transaction(s)', error_content)
        finally:
            import os
            os.unlink(csv_file)
    
    def test_no_problematic_transactions_message(self):
        """Test that appropriate message is shown when no loans or Lightning transactions found."""
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
            self.assertIn('No loan or Lightning transactions found', error_content)
        finally:
            import os
            os.unlink(csv_file)


if __name__ == '__main__':
    unittest.main()
