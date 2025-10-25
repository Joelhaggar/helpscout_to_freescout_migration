"""
FreeScout API Client
Handles all API interactions with FreeScout.
"""
import requests
import time
from typing import Dict, List, Optional, Any
from config.config import Config


class FreeScoutAPIError(Exception):
    """Custom exception for FreeScout API errors."""
    def __init__(self, message: str, status_code: int = None, response: str = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class FreeScoutClient:
    """Client for interacting with FreeScout API."""

    def __init__(self, api_key: str = None, base_url: str = None):
        """
        Initialize FreeScout client.

        Args:
            api_key: FreeScout API key (defaults to Config value)
            base_url: FreeScout base URL (defaults to Config value)
        """
        self.api_key = api_key or Config.FREESCOUT_API_KEY
        self.base_url = (base_url or Config.FREESCOUT_URL).rstrip('/')
        self.api_base = f"{self.base_url}/api"

        if not self.api_key:
            raise ValueError("FreeScout API key is required")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            'X-FreeScout-API-Key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        params: Dict = None,
        delay: float = None
    ) -> Dict:
        """
        Make an API request to FreeScout.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without /api prefix)
            data: Request body data
            params: Query parameters
            delay: Optional delay after request (defaults to Config.RATE_LIMIT_DELAY)

        Returns:
            Response data as dictionary

        Raises:
            FreeScoutAPIError: If request fails
        """
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30
            )

            # Add rate limiting delay (FreeScout is local, no delay needed)
            if delay is None:
                delay = Config.FREESCOUT_RATE_LIMIT
            if delay > 0:
                time.sleep(delay)

            # Handle different status codes
            if response.status_code in [200, 201, 204]:
                if response.status_code == 204:
                    return {}
                return response.json() if response.content else {}

            # Handle errors
            error_msg = f"{method} {endpoint} failed with status {response.status_code}"
            raise FreeScoutAPIError(
                error_msg,
                status_code=response.status_code,
                response=response.text
            )

        except requests.exceptions.RequestException as e:
            raise FreeScoutAPIError(f"Request failed: {str(e)}")

    # ===== Mailbox Methods =====

    def get_mailboxes(self) -> List[Dict]:
        """
        Get list of all mailboxes.

        Returns:
            List of mailbox dictionaries
        """
        response = self._make_request('GET', '/mailboxes')
        return response.get('_embedded', {}).get('mailboxes', [])

    # ===== Customer Methods =====

    def create_customer(self, customer_data: Dict) -> Dict:
        """
        Create a new customer.

        Args:
            customer_data: Customer data dictionary with required fields:
                - firstName or lastName (at least one required)
                - email or phone (at least one required)

        Returns:
            Created customer data with id
        """
        return self._make_request('POST', '/customers', data=customer_data)

    def get_customer(self, customer_id: int) -> Dict:
        """
        Get a customer by ID.

        Args:
            customer_id: FreeScout customer ID

        Returns:
            Customer data dictionary
        """
        return self._make_request('GET', f'/customers/{customer_id}')

    def get_customers(self, page: int = 1, page_size: int = 50, **filters) -> Dict:
        """
        Get list of customers.

        Args:
            page: Page number (default 1)
            page_size: Number of results per page (default 50)
            **filters: Additional filter parameters (firstName, lastName, email, etc.)

        Returns:
            Response with _embedded.customers array and pagination info
        """
        params = {'page': page, 'pageSize': page_size, **filters}
        return self._make_request('GET', '/customers', params=params)

    def update_customer(self, customer_id: int, customer_data: Dict) -> Dict:
        """
        Update an existing customer.

        Args:
            customer_id: FreeScout customer ID
            customer_data: Customer data to update

        Returns:
            Updated customer data
        """
        return self._make_request('PUT', f'/customers/{customer_id}', data=customer_data)

    def search_customer_by_email(self, email: str) -> Optional[Dict]:
        """
        Search for a customer by email address.

        Args:
            email: Email address to search for

        Returns:
            Customer data if found, None otherwise
        """
        try:
            response = self.get_customers(email=email, page_size=1)
            customers = response.get('_embedded', {}).get('customers', [])
            return customers[0] if customers else None
        except FreeScoutAPIError:
            return None

    # ===== Conversation Methods =====

    def create_conversation(self, conversation_data: Dict, imported: bool = False) -> Dict:
        """
        Create a new conversation with initial threads.

        Args:
            conversation_data: Conversation data with required fields:
                - subject
                - mailboxId
                - type (email, phone, chat)
                - status (active, closed, pending, spam)
                - threads: array of thread objects
                - createdAt (optional): ISO 8601 timestamp, requires imported=True
                - closedAt (optional): ISO 8601 timestamp for closed conversations
            imported: If True, allows setting createdAt and prevents auto-emails/notifications

        Returns:
            Created conversation data with id
        """
        if imported:
            conversation_data['imported'] = True
        return self._make_request('POST', '/conversations', data=conversation_data)

    def get_conversation(self, conversation_id: int) -> Dict:
        """
        Get a conversation by ID.

        Args:
            conversation_id: FreeScout conversation ID

        Returns:
            Conversation data dictionary
        """
        return self._make_request('GET', f'/conversations/{conversation_id}')

    def get_conversations(self, page: int = 1, page_size: int = 50, **filters) -> Dict:
        """
        Get list of conversations.

        Args:
            page: Page number (default 1)
            page_size: Number of results per page (default 50)
            **filters: Additional filter parameters (mailboxId, status, etc.)

        Returns:
            Response with _embedded.conversations array and pagination info
        """
        params = {'page': page, 'pageSize': page_size, **filters}
        return self._make_request('GET', '/conversations', params=params)

    def update_conversation(self, conversation_id: int, conversation_data: Dict) -> Dict:
        """
        Update a conversation.

        Args:
            conversation_id: FreeScout conversation ID
            conversation_data: Data to update (status, assignedTo, subject, etc.)

        Returns:
            Updated conversation data
        """
        return self._make_request('PUT', f'/conversations/{conversation_id}', data=conversation_data)

    def delete_conversation(self, conversation_id: int) -> None:
        """
        Delete a conversation.

        Args:
            conversation_id: FreeScout conversation ID
        """
        self._make_request('DELETE', f'/conversations/{conversation_id}')

    # ===== Thread Methods =====

    def add_thread(self, conversation_id: int, thread_data: Dict, imported: bool = False) -> Dict:
        """
        Add a thread to an existing conversation.

        Args:
            conversation_id: FreeScout conversation ID
            thread_data: Thread data with required fields:
                - type (customer, message, note)
                - text: Thread content
                - createdBy: User/customer info
                - createdAt (optional): ISO 8601 timestamp, requires imported=True
            imported: If True, allows setting createdAt and prevents auto-emails/notifications

        Returns:
            Created thread data
        """
        if imported:
            thread_data['imported'] = True
        return self._make_request('POST', f'/conversations/{conversation_id}/threads', data=thread_data)

    # ===== Tags Methods =====

    def get_tags(self) -> List[str]:
        """
        Get list of all tags.

        Returns:
            List of tag names
        """
        response = self._make_request('GET', '/tags')
        return response.get('_embedded', {}).get('tags', [])

    def update_conversation_tags(self, conversation_id: int, tags: List[str]) -> Dict:
        """
        Update tags for a conversation.

        Args:
            conversation_id: FreeScout conversation ID
            tags: List of tag names

        Returns:
            Response data
        """
        return self._make_request('PUT', f'/conversations/{conversation_id}/tags', data={'tags': tags})

    # ===== Custom Fields Methods =====

    def update_conversation_custom_fields(self, conversation_id: int, custom_fields: Dict) -> Dict:
        """
        Update custom fields for a conversation.

        Args:
            conversation_id: FreeScout conversation ID
            custom_fields: Dictionary of custom field values

        Returns:
            Response data
        """
        return self._make_request(
            'PUT',
            f'/conversations/{conversation_id}/custom_fields',
            data=custom_fields
        )

    # ===== Users Methods =====

    def get_users(self, page: int = 1, page_size: int = 50) -> Dict:
        """
        Get list of users.

        Args:
            page: Page number (default 1)
            page_size: Number of results per page (default 50)

        Returns:
            Response with _embedded.users array and pagination info
        """
        params = {'page': page, 'pageSize': page_size}
        return self._make_request('GET', '/users', params=params)

    def get_user(self, user_id: int) -> Dict:
        """
        Get a user by ID.

        Args:
            user_id: FreeScout user ID

        Returns:
            User data dictionary
        """
        return self._make_request('GET', f'/users/{user_id}')
