import pytest
from unittest.mock import MagicMock, patch
from archive_to_notes import get_messages, normalize_phone

@patch('archive_to_notes.sqlite3')
def test_get_messages_query(mock_sqlite):
    # Setup mock DB
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_sqlite.connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock data return
    mock_cursor.fetchall.return_value = [
        ('2025-01-01 12:00:00', 1, 'Hello', None, 'iMessage', 101),
        ('2025-01-01 12:05:00', 0, 'Hi back', None, 'iMessage', 102)
    ]
    
    # Run
    messages = get_messages('+15551234567', '2025-01-01')
    
    # Verify
    assert len(messages) == 2
    assert messages[0][2] == 'Hello'
    
    # Check query params normalization
    args = mock_cursor.execute.call_args[0]
    query_param_phone = args[1][0] # first param in tuple
    assert query_param_phone == '%5551234567%' # Normalized pattern

def test_normalize_phone():
    assert normalize_phone("+1 (555) 123-4567") == "5551234567"
    assert normalize_phone("555-123-4567") == "5551234567"
    assert normalize_phone("12345") == "12345" # Short codes
