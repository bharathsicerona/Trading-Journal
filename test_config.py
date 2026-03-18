import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from config import EMAIL_ACCOUNT, APP_PASSWORD, EMAIL_SENDERS

class TestConfig(unittest.TestCase):

    @patch('config.load_dotenv')
    @patch.dict(os.environ, {
        'EMAIL_ACCOUNT': 'test@example.com',
        'APP_PASSWORD': 'testpassword123'
    })
    def test_config_loading(self, mock_load_dotenv):
        """Test that configuration loads environment variables correctly"""
        # Re-import to get fresh values
        import importlib
        import config
        importlib.reload(config)

        self.assertEqual(config.EMAIL_ACCOUNT, 'test@example.com')
        self.assertEqual(config.APP_PASSWORD, 'testpassword123')
        self.assertIsInstance(config.EMAIL_SENDERS, list)
        self.assertIn('groww', config.EMAIL_SENDERS)

    @patch('config.os.getenv')
    @patch('config.load_dotenv')
    def test_config_missing_env_vars(self, mock_load_dotenv, mock_getenv):
        """Test behavior when environment variables are missing"""
        mock_getenv.return_value = None
        
        # Re-import to get fresh values
        import importlib
        import config
        importlib.reload(config)

        self.assertIsNone(config.EMAIL_ACCOUNT)
        self.assertIsNone(config.APP_PASSWORD)

if __name__ == '__main__':
    unittest.main()