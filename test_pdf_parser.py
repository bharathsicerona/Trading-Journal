import unittest
from unittest.mock import patch, MagicMock
from datetime import date
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pdf_parser import (
    extract_text_from_pdf,
    parse_trades,
    extract_trade_date,
    extract_funds_data,
    extract_pledges_data,
    extract_account_summary,
    _normalize_number
)

class TestPDFParser(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.sample_trade_date = date(2024, 1, 15)
        self.sample_broker = "TestBroker"

    @patch('pdfplumber.open')
    def test_extract_text_from_pdf(self, mock_pdf_open):
        """Test PDF text extraction"""
        # Mock PDF pages
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Sample text from page"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        result = extract_text_from_pdf("dummy.pdf")
        self.assertEqual(result, "Sample text from page")

        mock_pdf_open.assert_called_once_with("dummy.pdf")

    def test_normalize_number_edge_cases(self):
        """Test number normalization with Dr/Cr suffixes and other formats"""
        cases = [
            ("1,500.50", 1500.5),
            ("1,500.50 Dr", -1500.5),
            ("1,500.50 CR", 1500.5),
            ("200.00 dr", -200.0),
            ("(500.25)", -500.25),
            ("₹100", 100.0),
            ("$50.5", 50.5),
            ("invalid", None)
        ]
        for num_str, expected in cases:
            with self.subTest(num_str=num_str):
                self.assertEqual(_normalize_number(num_str), expected)

    def test_extract_trade_date_valid(self):
        """Test trade date extraction with valid date"""
        text = "Some text Trade Date 15-01-2024 more text"
        result = extract_trade_date(text)
        expected = date(2024, 1, 15)
        self.assertEqual(result, expected)

    def test_extract_trade_date_flexible_separators(self):
        """Test trade date extraction with dots and spaces"""
        self.assertEqual(extract_trade_date("Trade Date 15.01.2024"), date(2024, 1, 15))
        self.assertEqual(extract_trade_date("Trade Date: 15/01/2024"), date(2024, 1, 15))
        self.assertEqual(extract_trade_date("15 Jan 2024"), date(2024, 1, 15))

    def test_extract_trade_date_invalid(self):
        """Test trade date extraction with no date"""
        text = "Some text without date"
        result = extract_trade_date(text)
        self.assertIsNone(result)

    def test_parse_trades_valid_data(self):
        """Test trade parsing with valid trade data"""
        text = """
        Some header text
        Buy(B)/Sell(S) Quantity
        NSE RELIANCE 2500 CE 20 Jan 2024 B 10 250.50 5.00 255.50 2555.00
        BSE TCS 3000 PE 25 Feb 2024 S 5 150.25 2.50 152.75 763.75
        Future & Options Summary
        """

        trades = parse_trades(text, self.sample_trade_date, self.sample_broker)

        self.assertEqual(len(trades), 2)

        # Check first trade
        trade1 = trades[0]
        self.assertEqual(trade1['Exchange'], 'NSE')
        self.assertEqual(trade1['Underlying'], 'RELIANCE')
        self.assertEqual(trade1['Strike'], 2500.0)
        self.assertEqual(trade1['Type'], 'CE')
        self.assertEqual(trade1['Buy/Sell'], 'B')
        self.assertEqual(trade1['Quantity'], 10)
        # WAP may be present as float
        self.assertAlmostEqual(trade1['WAP'], 250.50)
        self.assertEqual(trade1['Broker'], self.sample_broker)

        # Check second trade
        trade2 = trades[1]
        self.assertEqual(trade2['Exchange'], 'BSE')
        self.assertEqual(trade2['Underlying'], 'TCS')
        self.assertEqual(trade2['Type'], 'PE')

    def test_parse_trades_no_trades_section(self):
        """Test trade parsing with no trades section"""
        text = "Some random text without trades section"
        trades = parse_trades(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(trades), 0)

    def test_parse_trades_invalid_format(self):
        """Test trade parsing with malformed data"""
        text = """
        Buy(B)/Sell(S) Quantity
        NSE RELIANCE invalid data here
        """
        trades = parse_trades(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(trades), 0)

    def test_extract_funds_data_pay_in(self):
        """Test funds extraction for Pay In"""
        text = "Pay In / Pay Out Obligation 1000.50"
        funds = extract_funds_data(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(funds), 1)
        self.assertEqual(funds[0]['Type'], 'Deposit')
        self.assertEqual(funds[0]['Amount'], 1000.50)
        self.assertEqual(funds[0]['Currency'], 'INR')

    def test_extract_funds_data_pay_out(self):
        """Test funds extraction for Pay Out"""
        text = "Pay In / Pay Out Obligation -500.25"
        funds = extract_funds_data(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(funds), 1)
        self.assertEqual(funds[0]['Type'], 'Withdrawal')
        self.assertEqual(funds[0]['Amount'], 500.25)

    def test_extract_funds_data_net_receivable(self):
        """Test funds extraction for Net Receivable"""
        text = "Net Amount Receivable 750.00"
        funds = extract_funds_data(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(funds), 1)
        self.assertEqual(funds[0]['Type'], 'Settlement Receivable')
        self.assertEqual(funds[0]['Amount'], 750.00)

    def test_extract_funds_data_net_payable(self):
        """Test funds extraction for Net Payable"""
        text = "Net Amount Payable -300.00"
        funds = extract_funds_data(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(funds), 1)
        self.assertEqual(funds[0]['Type'], 'Settlement Payable')
        self.assertEqual(funds[0]['Amount'], 300.00)

    def test_extract_funds_data_cr_dr_suffixes(self):
        """Test funds extraction with Cr/Dr accounting suffixes"""
        text = "Net Amount Payable 1,500.50 Dr"
        funds = extract_funds_data(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(funds), 1)
        self.assertEqual(funds[0]['Type'], 'Settlement Payable')

    def test_extract_pledges_data(self):
        """Test pledge data extraction"""
        text = "Pledge utilised 50000.00 for margin"
        pledges = extract_pledges_data(text, self.sample_trade_date, self.sample_broker)
        self.assertEqual(len(pledges), 1)
        self.assertEqual(pledges[0]['Amount'], 50000.00)
        self.assertIn('Pledge utilised', pledges[0]['Description'])

    def test_extract_account_summary(self):
        """Test account summary extraction"""
        text = "Some summary text"
        summary = extract_account_summary(text, self.sample_trade_date, self.sample_broker, "test.pdf")
        self.assertEqual(summary['Date'], self.sample_trade_date)
        self.assertEqual(summary['Broker'], self.sample_broker)
        self.assertEqual(summary['Filename'], "test.pdf")
        # Other fields should be initialized to defaults
        self.assertEqual(summary['Total_Trades'], 0)
        self.assertEqual(summary['Total_Fees'], 0.0)

    def test_parse_trades_broker_layouts(self):
        """Test trade parsing for different broker layouts using subtests"""
        test_cases = [
            {
                "broker": "Groww",
                "text": "\nContract Note\nRELIANCE 2500 CE 20 Jan 2024 Buy 10 250.50 5.00 255.50 2555.00\n",
                "expected": {
                    'Underlying': 'RELIANCE', 'Strike': 2500.0, 'Type': 'CE', 'Buy/Sell': 'B', 'Quantity': 10
                }
            },
            {
                "broker": "mStock",
                "text": "\nBuy(B)/Sell(S) Quantity\nNSE RELIANCE 2500 CE 20 Jan 2024 B 10 250.50 5.00 255.50 2555.00\n",
                "expected": {
                    'Exchange': 'NSE', 'Underlying': 'RELIANCE', 'Quantity': 10
                }
            },
            {
                "broker": "Groww",
                "text": "\nContract Note\nNIFTY BANK 45000 CE 20 Jan 2024 Buy 15 250.50 5.00 255.50 3832.50\n",
                "expected": {
                    'Underlying': 'NIFTY BANK', 'Strike': 45000.0, 'Type': 'CE', 'Buy/Sell': 'B', 'Quantity': 15
                }
            },
            {
                "broker": "mStock",
                # Notice the spaces in "M&M FIN"
                "text": "\nBuy(B)/Sell(S) Quantity\nNSE M&M FIN 2500 CE 20 Jan 2024 B 10 250.50 5.00 255.50 2555.00\n",
                "expected": {
                    'Exchange': 'NSE', 'Underlying': 'M&M FIN', 'Strike': 2500.0, 'Quantity': 10, 'Type': 'CE'
                }
            },
            {
                "broker": "mStock",
                "text": "\nOPTIDX NIFTY 17MAR26 23350.00 CE (BT) B 260 0.0000 90.0000 0.0192 90.0192 0.0000-23405.0000NSEFO\n",
                "expected": {
                    'Exchange': 'NSE', 'Underlying': 'NIFTY', 'Strike': 23350.0, 'Type': 'CE', 'Buy/Sell': 'B', 'Quantity': 260, 'Net Total': -23405.0, 'WAP': 90.0
                }
            },
            {
                "broker": "Exness",
                "text": "\nEUR/USD Buy 0.10 1.23456 10.50\n",
                "expected": {
                    'Underlying': 'EUR/USD', 'Type': 'FX', 'Buy/Sell': 'B', 'Net Total': 10.50
                }
            }
        ]

        for tc in test_cases:
            with self.subTest(broker=tc["broker"]):
                trades = parse_trades(tc["text"], self.sample_trade_date, tc["broker"])
                self.assertEqual(len(trades), 1)
                for key, expected_value in tc["expected"].items():
                    if isinstance(expected_value, float):
                        self.assertAlmostEqual(trades[0][key], expected_value)
                    else:
                        self.assertEqual(trades[0][key], expected_value)

if __name__ == '__main__':
    unittest.main()