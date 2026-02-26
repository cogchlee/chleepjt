"""
Unit tests for the news_fetcher module.
"""

import unittest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from news_fetcher import (
    get_sent_links,
    save_sent_links,
    clean_html_summary,
    translate_to_korean
)


class TestSentLinksHandling(unittest.TestCase):
    """Test cases for sent links JSON file handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test_sent_links.json")
    
    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        os.rmdir(self.test_dir)
    
    def test_get_sent_links_empty(self):
        """Test retrieving links from non-existent file returns empty set."""
        with patch('news_fetcher.SENT_LINKS_FILE', self.test_file):
            links = get_sent_links()
            self.assertEqual(links, set())
    
    def test_save_and_retrieve_links(self):
        """Test saving and retrieving links."""
        test_links = ['https://example.com/1', 'https://example.com/2']
        
        with patch('news_fetcher.SENT_LINKS_FILE', self.test_file):
            save_sent_links(test_links)
            retrieved = get_sent_links()
            self.assertEqual(retrieved, set(test_links))
    
    def test_save_empty_links_does_nothing(self):
        """Test that saving empty list doesn't create file."""
        with patch('news_fetcher.SENT_LINKS_FILE', self.test_file):
            save_sent_links([])
            # Should not create the file
            retrieved = get_sent_links()
            self.assertEqual(retrieved, set())


class TestHTMLSummaryClean(unittest.TestCase):
    """Test cases for HTML content cleaning."""
    
    def test_clean_html_basic(self):
        """Test basic HTML tag removal."""
        html = "<p>This is a test <strong>paragraph</strong>.</p>"
        result = clean_html_summary(html)
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
    
    def test_clean_html_sentence_limit(self):
        """Test sentence limiting."""
        html = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        result = clean_html_summary(html, max_sentences=2)
        self.assertIn("Sentence one", result)
        self.assertIn("Sentence two", result)
        self.assertTrue(result.endswith("..."))
    
    def test_clean_empty_html(self):
        """Test cleaning empty HTML."""
        result = clean_html_summary("")
        self.assertEqual(result, "")


class TestTranslation(unittest.TestCase):
    """Test cases for translation functionality."""
    
    @patch('news_fetcher.translator')
    def test_translate_to_korean_success(self, mock_translator):
        """Test successful translation."""
        mock_translator.translate.return_value = MagicMock(text='안녕하세요')
        result = translate_to_korean("Hello")
        self.assertEqual(result, '안녕하세요')
    
    def test_translate_empty_string(self):
        """Test translation of empty string returns empty."""
        result = translate_to_korean("")
        self.assertEqual(result, "")


class TestLinkValidity(unittest.TestCase):
    """Test cases for link validation."""
    
    @patch('news_fetcher.requests.head')
    def test_valid_link(self, mock_head):
        """Test valid link returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        from news_fetcher import check_link_validity
        result = check_link_validity("https://example.com")
        self.assertTrue(result)
    
    @patch('news_fetcher.requests.head')
    def test_invalid_link(self, mock_head):
        """Test invalid link returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response
        
        from news_fetcher import check_link_validity
        result = check_link_validity("https://example.com/notfound")
        self.assertFalse(result)
    
    @patch('news_fetcher.requests.head')
    def test_timeout_link(self, mock_head):
        """Test timeout returns False."""
        import requests
        mock_head.side_effect = requests.exceptions.Timeout()
        
        from news_fetcher import check_link_validity
        result = check_link_validity("https://example.com/slow")
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
