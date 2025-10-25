"""
Help Scout API Client
Handles all API interactions with Help Scout.
Refactored from existing extraction scripts.
"""
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from config.config import Config


class HelpScoutAPIError(Exception):
    """Custom exception for Help Scout API errors."""
    def __init__(self, message: str, status_code: int = None, response: str = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class HelpScoutClient:
    """Client for interacting with Help Scout API."""

    def __init__(self, client_id: str = None, client_secret: str = None):
        """
        Initialize Help Scout client.

        Args:
            client_id: Help Scout OAuth client ID (defaults to Config value)
            client_secret: Help Scout OAuth client secret (defaults to Config value)
        """
        self.client_id = client_id or Config.HELPSCOUT_CLIENT_ID
        self.client_secret = client_secret or Config.HELPSCOUT_CLIENT_SECRET
        self.token_url = Config.HELPSCOUT_TOKEN_URL
        self.api_base = Config.HELPSCOUT_API_BASE

        self._access_token = None
        self._token_expiry = None

        if not self.client_id or not self.client_secret:
            raise ValueError("Help Scout client ID and secret are required")

    def _get_access_token(self) -> str:
        """
        Get OAuth access token (with caching).
        Tokens are cached and reused until near expiry.

        Returns:
            Access token string

        Raises:
            HelpScoutAPIError: If authentication fails
        """
        # Return cached token if still valid
        if self._access_token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                return self._access_token

        # Request new token
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            response = requests.post(self.token_url, data=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self._access_token = data['access_token']
                # Token expires in 'expires_in' seconds, refresh 5 min early
                expires_in = data.get('expires_in', 7200)  # Default 2 hours
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
                return self._access_token
            else:
                raise HelpScoutAPIError(
                    f"Authentication failed: {response.text}",
                    status_code=response.status_code,
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            raise HelpScoutAPIError(f"Authentication request failed: {str(e)}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        access_token = self._get_access_token()
        return {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None,
        delay: float = None,
        timeout: int = 120,
        max_retries: int = 3
    ) -> Dict:
        """
        Make an API request to Help Scout with automatic retry on timeout.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            data: Request body data
            delay: Optional delay after request (defaults to Config.RATE_LIMIT_DELAY)
            timeout: Request timeout in seconds (default: 120)
            max_retries: Maximum number of retry attempts on timeout (default: 3)

        Returns:
            Response data as dictionary

        Raises:
            HelpScoutAPIError: If request fails after all retries
        """
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        last_exception = None
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout
                )

                # Add rate limiting delay
                if delay is None:
                    delay = Config.HELPSCOUT_RATE_LIMIT
                if delay > 0:
                    time.sleep(delay)

                # Handle success
                if response.status_code in [200, 201, 204]:
                    if response.status_code == 204:
                        return {}
                    return response.json() if response.content else {}

                # Handle errors
                error_msg = f"{method} {endpoint} failed with status {response.status_code}"
                raise HelpScoutAPIError(
                    error_msg,
                    status_code=response.status_code,
                    response=response.text
                )

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5, 10, 15 seconds
                    print(f"  ⚠ Request timeout (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise HelpScoutAPIError(f"Request failed after {max_retries} retries: {str(e)}")

            except requests.exceptions.RequestException as e:
                raise HelpScoutAPIError(f"Request failed: {str(e)}")

    # ===== Customer Methods =====

    def get_customers(self, mailbox: int = None, page: int = 1, **filters) -> Dict:
        """
        Get list of customers.

        Args:
            mailbox: Optional mailbox ID filter
            page: Page number (default 1)
            **filters: Additional filters (firstName, lastName, modifiedSince, etc.)

        Returns:
            Response with _embedded.customers array and page info
        """
        params = {'page': page, **filters}
        if mailbox:
            params['mailbox'] = mailbox

        return self._make_request('GET', '/customers', params=params)

    def get_customer(self, customer_id: int) -> Dict:
        """
        Get a customer by ID.

        Args:
            customer_id: Help Scout customer ID

        Returns:
            Customer data dictionary
        """
        return self._make_request('GET', f'/customers/{customer_id}')

    def get_all_customers(self, mailbox: int = None) -> List[Dict]:
        """
        Get all customers (handles pagination automatically).

        Args:
            mailbox: Optional mailbox ID filter

        Returns:
            List of all customer dictionaries
        """
        all_customers = []
        page = 1

        while True:
            response = self.get_customers(mailbox=mailbox, page=page)
            customers = response.get('_embedded', {}).get('customers', [])

            if not customers:
                break

            all_customers.extend(customers)

            # Check if there are more pages
            page_info = response.get('page', {})
            total_pages = page_info.get('totalPages', 1)

            if page >= total_pages:
                break

            page += 1

        return all_customers

    # ===== Conversation Methods =====

    def get_conversations(
        self,
        mailbox: int = None,
        status: str = 'all',
        page: int = 1,
        modified_since: str = None,
        **filters
    ) -> Dict:
        """
        Get list of conversations.

        Args:
            mailbox: Mailbox ID
            status: Conversation status (all, active, closed, open, pending, spam)
            page: Page number (default 1)
            modified_since: ISO 8601 datetime string (e.g., '2025-10-20T00:00:00Z')
                           Returns conversations modified after this time
            **filters: Additional filters (tag, assigned_to, query, etc.)

        Returns:
            Response with _embedded.conversations array and page info
        """
        params = {'status': status, 'page': page, **filters}
        if mailbox:
            params['mailbox'] = mailbox
        if modified_since:
            params['modifiedSince'] = modified_since

        return self._make_request('GET', '/conversations', params=params)

    def get_conversation(self, conversation_id: int, embed: str = None) -> Dict:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Help Scout conversation ID
            embed: Optional comma-separated list of resources to embed (e.g., 'threads')

        Returns:
            Conversation data dictionary
        """
        params = {}
        if embed:
            params['embed'] = embed

        return self._make_request('GET', f'/conversations/{conversation_id}', params=params)

    def get_conversation_threads(self, conversation_id: int) -> List[Dict]:
        """
        Get all threads for a conversation.

        Args:
            conversation_id: Help Scout conversation ID

        Returns:
            List of thread dictionaries
        """
        response = self._make_request('GET', f'/conversations/{conversation_id}/threads')
        return response.get('_embedded', {}).get('threads', [])

    def download_attachment(self, conversation_id: int, attachment_id: int) -> bytes:
        """
        Download attachment data from Help Scout.

        The Help Scout API returns attachment data as JSON: {"data": "base64..."}
        This method decodes the Base64 and returns the raw binary data.

        Args:
            conversation_id: Help Scout conversation ID
            attachment_id: Attachment ID

        Returns:
            Attachment data as bytes (decoded from Base64)

        Raises:
            HelpScoutAPIError: If download fails
        """
        url = f"{self.api_base}/conversations/{conversation_id}/attachments/{attachment_id}/data"
        headers = self._get_headers()

        try:
            response = requests.get(url, headers=headers, timeout=60)

            if response.status_code == 200:
                # Help Scout returns JSON: {"data": "base64_encoded_string"}
                import base64
                import json

                data_json = response.json()
                base64_data = data_json.get('data', '')

                if not base64_data:
                    raise HelpScoutAPIError(
                        f"No data field in attachment response for attachment {attachment_id}"
                    )

                # Decode Base64 to get raw binary data
                binary_data = base64.b64decode(base64_data)
                return binary_data
            else:
                raise HelpScoutAPIError(
                    f"Failed to download attachment {attachment_id}",
                    status_code=response.status_code,
                    response=response.text
                )

        except requests.exceptions.RequestException as e:
            raise HelpScoutAPIError(f"Attachment download failed: {str(e)}")

    def get_all_conversations(
        self,
        mailbox: int = None,
        status: str = 'all',
        customer_id: int = None,
        exclude_tags: List[str] = None,
        include_tags: List[str] = None,
        query: str = None,
        modified_since: str = None
    ) -> List[Dict]:
        """
        Get all conversations (handles pagination automatically).

        Args:
            mailbox: Optional mailbox ID filter
            status: Conversation status filter (active, closed, spam, all, etc.)
            customer_id: Optional filter by customer ID
            exclude_tags: List of tags to exclude (e.g., ['spam', 'low-priority'])
            include_tags: List of tags to include (only conversations with these tags)
            query: Custom query string for advanced filtering
            modified_since: ISO 8601 datetime (e.g., '2025-10-20T00:00:00Z')
                           Only return conversations modified after this time
                           Useful for incremental syncs

        Returns:
            List of all conversation dictionaries

        Examples:
            # Exclude spam and low-priority conversations
            get_all_conversations(exclude_tags=['spam', 'low-priority'])

            # Only active conversations, exclude certain tags
            get_all_conversations(status='active', exclude_tags=['spam'])

            # Incremental sync - only conversations modified since last sync
            get_all_conversations(modified_since='2025-10-20T00:00:00Z')

            # Custom query
            get_all_conversations(query='(assigned:"john" AND NOT tag:"spam")')
        """
        all_conversations = []
        page = 1

        filters = {}

        # Build query string
        query_parts = []

        # Add customer ID filter to query
        if customer_id:
            query_parts.append(f'customerId:{customer_id}')

        # Add exclude tags to query
        if exclude_tags:
            for tag in exclude_tags:
                query_parts.append(f'NOT tag:"{tag}"')

        # Add include tags to query
        if include_tags:
            tag_conditions = [f'tag:"{tag}"' for tag in include_tags]
            if len(tag_conditions) > 1:
                query_parts.append(f'({" OR ".join(tag_conditions)})')
            else:
                query_parts.append(tag_conditions[0])

        # Add custom query if provided
        if query:
            query_parts.append(query)

        # Combine query parts
        if query_parts:
            filters['query'] = f'({" AND ".join(query_parts)})'

        while True:
            response = self.get_conversations(
                mailbox=mailbox,
                status=status,
                page=page,
                modified_since=modified_since,
                **filters
            )
            conversations = response.get('_embedded', {}).get('conversations', [])

            if not conversations:
                break

            all_conversations.extend(conversations)

            # Check if there are more pages
            page_info = response.get('page', {})
            total_pages = page_info.get('totalPages', 1)

            if page >= total_pages:
                break

            page += 1

        return all_conversations

    # ===== User Methods =====

    def get_users(self, page: int = 1, page_size: int = 100) -> Dict:
        """
        Get list of users.

        Args:
            page: Page number (default 1)
            page_size: Results per page (default 100)

        Returns:
            Response with _embedded.users array and page info
        """
        return self._make_request('GET', '/users', params={'page': page})

    def get_all_users(self) -> List[Dict]:
        """
        Get all users (handles pagination automatically).

        Returns:
            List of all user dictionaries
        """
        all_users = []
        page = 1

        while True:
            response = self.get_users(page=page)
            users = response.get('_embedded', {}).get('users', [])

            if not users:
                break

            all_users.extend(users)

            # Check if there are more pages
            page_info = response.get('page', {})
            total_pages = page_info.get('totalPages', 1)

            if page >= total_pages:
                break

            page += 1

        return all_users

    # ===== Mailbox Methods =====

    def get_mailboxes(self, page: int = 1) -> Dict:
        """
        Get list of mailboxes.

        Args:
            page: Page number (default 1)

        Returns:
            Response with _embedded.mailboxes array
        """
        return self._make_request('GET', '/mailboxes', params={'page': page})

    def get_all_mailboxes(self) -> List[Dict]:
        """
        Get all mailboxes (handles pagination automatically).

        Returns:
            List of all mailbox dictionaries
        """
        all_mailboxes = []
        page = 1

        while True:
            response = self.get_mailboxes(page=page)
            mailboxes = response.get('_embedded', {}).get('mailboxes', [])

            if not mailboxes:
                break

            all_mailboxes.extend(mailboxes)

            # Check if there are more pages
            page_info = response.get('page', {})
            total_pages = page_info.get('totalPages', 1)

            if page >= total_pages:
                break

            page += 1

        return all_mailboxes
