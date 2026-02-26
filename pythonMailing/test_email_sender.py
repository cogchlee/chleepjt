"""
Unit tests for the email_sender module.
"""

import unittest
from unittest.mock import patch, MagicMock
from email_sender import format_news_html, send_email


class TestEmailFormatting(unittest.TestCase):
    """Test cases for email HTML formatting."""
    
    def test_format_news_html_empty_list(self):
        """Test formatting empty news list."""
        result = format_news_html([])
        self.assertIn("No news found", result)
    
    def test_format_news_html_single_item(self):
        """Test formatting single news item."""
        news_items = [{
            'title_en': 'Test Title',
            'title_ko': '테스트 제목',
            'topic': 'AI News',
            'link': 'https://example.com',
            'published_date': '2026-02-26',
            'summary_en': 'Test summary',
            'summary_ko': '테스트 요약'
        }]
        
        result = format_news_html(news_items)
        self.assertIn('Test Title', result)
        self.assertIn('테스트 제목', result)
        self.assertIn('https://example.com', result)
        self.assertIn('AI News', result)
    
    def test_format_news_html_multiple_items(self):
        """Test formatting multiple news items."""
        news_items = [
            {
                'title_en': 'Title 1',
                'title_ko': '제목 1',
                'topic': 'Topic A',
                'link': 'https://example1.com',
                'published_date': '2026-02-26',
                'summary_en': 'Summary 1',
                'summary_ko': '요약 1'
            },
            {
                'title_en': 'Title 2',
                'title_ko': '제목 2',
                'topic': 'Topic B',
                'link': 'https://example2.com',
                'published_date': '2026-02-26',
                'summary_en': 'Summary 2',
                'summary_ko': '요약 2'
            }
        ]
        
        result = format_news_html(news_items)
        self.assertIn('Title 1', result)
        self.assertIn('Title 2', result)
        self.assertIn('Topic A', result)
        self.assertIn('Topic B', result)
    
    def test_format_news_html_grouping(self):
        """Test that news items are grouped by topic."""
        news_items = [
            {
                'title_en': 'Item A',
                'title_ko': '항목 A',
                'topic': 'AI News',
                'link': 'https://a.com',
                'published_date': '2026-02-26',
                'summary_en': 'Summary A',
                'summary_ko': '요약 A'
            },
            {
                'title_en': 'Item B',
                'title_ko': '항목 B',
                'topic': 'ML News',
                'link': 'https://b.com',
                'published_date': '2026-02-26',
                'summary_en': 'Summary B',
                'summary_ko': '요약 B'
            },
            {
                'title_en': 'Item C',
                'title_ko': '항목 C',
                'topic': 'AI News',
                'link': 'https://c.com',
                'published_date': '2026-02-26',
                'summary_en': 'Summary C',
                'summary_ko': '요약 C'
            }
        ]
        
        result = format_news_html(news_items)
        # Should contain topic headers
        self.assertIn('AI News', result)
        self.assertIn('ML News', result)


class TestEmailSending(unittest.TestCase):
    """Test cases for email sending."""
    
    @patch('config.SENDER_EMAIL', 'test@example.com')
    @patch('config.SENDER_PASSWORD', 'password')
    @patch('config.RECEIVER_EMAIL', 'receiver@example.com')
    @patch('config.FORWARD_EMAIL', '')
    @patch('email_sender.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending."""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        news_items = [{
            'title_en': 'Test',
            'title_ko': '테스트',
            'topic': 'AI',
            'link': 'https://example.com',
            'published_date': '2026-02-26',
            'summary_en': 'Summary',
            'summary_ko': '요약'
        }]
        
        result = send_email('Test Subject', news_items)
        self.assertTrue(result)
        mock_server.send_message.assert_called_once()
    
    @patch('config.SENDER_EMAIL', '')
    @patch('config.SENDER_PASSWORD', 'password')
    @patch('config.RECEIVER_EMAIL', 'receiver@example.com')
    def test_send_email_missing_credentials(self):
        """Test email sending with missing credentials."""
        news_items = [{'title_en': 'Test', 'topic': 'AI'}]
        result = send_email('Subject', news_items)
        self.assertFalse(result)
    
    @patch('config.SENDER_EMAIL', 'test@example.com')
    @patch('config.SENDER_PASSWORD', 'password')
    @patch('config.RECEIVER_EMAIL', 'receiver@example.com')
    def test_send_email_empty_news_items(self):
        """Test email sending with empty news items."""
        result = send_email('Subject', [])
        self.assertFalse(result)
    
    @patch('config.SENDER_EMAIL', 'test@example.com')
    @patch('config.SENDER_PASSWORD', 'password')
    @patch('config.RECEIVER_EMAIL', 'receiver@example.com')
    @patch('config.FORWARD_EMAIL', 'forward@example.com')
    @patch('email_sender.smtplib.SMTP')
    def test_send_email_with_forward_address(self, mock_smtp):
        """Test email sending with forward address."""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        news_items = [{
            'title_en': 'Test',
            'title_ko': '테스트',
            'topic': 'AI',
            'link': 'https://example.com',
            'published_date': '2026-02-26',
            'summary_en': 'Summary',
            'summary_ko': '요약'
        }]
        
        result = send_email('Test Subject', news_items)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
