import os
import json
import logging
from enum import Enum, auto
from datetime import datetime, timedelta, time
from dateutil import parser, tz
from typing import Optional, Tuple, List, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pytz
import google.auth.exceptions
import boto3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    OAUTH = auto()
    SERVICE_ACCOUNT = auto()
    SERVICE_ACCOUNT_BOTO3 = auto()


class GoogleCalendarHelper:
    """
    A helper class to interact with the Google Calendar API.
    Provides methods to find a free time slot and list a day's schedule.
    """

    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    def __init__(
        self,
        auth_method: AuthMethod,
        credentials_path: str = 'credentials.json',
        token_path: str = 'token.json',
        service_account_file: str = 'secrets/service_account.json',
        aws_secret_name: str = '',
        aws_region_name: str = '',
    ):
        """
        Initializes the GoogleCalendarHelper instance and authenticates with Google Calendar API.

        :param auth_method: The authentication method to use (AuthMethod enum).
        :param credentials_path: Path to the credentials.json file (for OAuth method).
        :param token_path: Path to the token.json file (for OAuth method).
        :param service_account_file: Path to the service account JSON file (for Service Account method).
        :param aws_secret_name: Name of the secret in AWS Secrets Manager (for AWS Boto3 method).
        :param aws_region_name: AWS region where the secret is stored (for AWS Boto3 method).
        """
        self.auth_method = auth_method
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service_account_file = service_account_file
        self.aws_secret_name = aws_secret_name
        self.aws_region_name = aws_region_name
        self.creds: Optional[Credentials] = None
        self.service = None
        self.authenticate()

    def authenticate(self):
        """
        Handles authentication with Google Calendar API and initializes the service object.
        """
        if self.auth_method == AuthMethod.OAUTH:
            self.authenticate_oauth()
        elif self.auth_method == AuthMethod.SERVICE_ACCOUNT:
            self.authenticate_service_account()
        elif self.auth_method == AuthMethod.SERVICE_ACCOUNT_BOTO3:
            self.authenticate_service_account_boto3()
        else:
            raise ValueError("Invalid authentication method specified.")

        # Build the service object
        self.service: Any = build('calendar', 'v3', credentials=self.creds)

    def authenticate_oauth(self):
        """
        Authenticate using OAuth 2.0 Installed App Flow with cached token.
        """
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(
                self.token_path, self.SCOPES
            )
        # If there are no valid credentials, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except google.auth.exceptions.RefreshError:
                    logger.info("Token has expired or been revoked. Re-authenticating...")
                    self.creds = self.get_new_credentials()
            else:
                self.creds = self.get_new_credentials()

            # Save the credentials for the next run
            with open(self.token_path, 'w') as token_file:
                token_file.write(self.creds.to_json())

    def get_new_credentials(self) -> Credentials:
        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_path, self.SCOPES
        )
        # Specify access_type and prompt to get a refresh token
        creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
        return creds

    def authenticate_service_account(self):
        """
        Authenticate using a service account JSON file.
        """
        self.creds = ServiceAccountCredentials.from_service_account_file(
            self.service_account_file, scopes=self.SCOPES
        )

    def authenticate_service_account_boto3(self):
        """
        Authenticate using a service account JSON file retrieved from AWS Secrets Manager using boto3.
        """
        if not self.aws_secret_name or not self.aws_region_name:
            raise ValueError(
                "AWS secret name and region name must be provided for SERVICE_ACCOUNT_BOTO3 authentication method."
            )

        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=self.aws_region_name,
        )

        # Retrieve the secret
        try:
            get_secret_value_response = client.get_secret_value(
                SecretId=self.aws_secret_name
            )
        except Exception as e:
            logger.error(f"Failed to retrieve secret from AWS Secrets Manager: {e}")
            raise

        if 'SecretString' in get_secret_value_response:
            secret_str = get_secret_value_response['SecretString']
            service_account_info = json.loads(secret_str)
        else:
            logger.error("Secret is not in string format.")
            raise ValueError("Secret is not in string format.")

        # Create credentials using the service account info
        self.creds = ServiceAccountCredentials.from_service_account_info(
            service_account_info, scopes=self.SCOPES
        )

    def find_free_time_slot(self, duration_hours: float) -> Optional[Tuple[datetime, datetime]]:
        """
        Finds the next available free time slot in the user's Google Calendar.

        :param duration_hours: Duration of the time slot in hours.
        :return: A tuple with start and end datetime objects of the free time slot, or None if not found.
        """
        # Get the current time in UTC
        now = datetime.now(pytz.UTC)
        end_date = now + timedelta(days=14)

        try:
            # Fetch events from the primary calendar
            events_result = (
                self.service.events()
                .list(
                    calendarId='primary',
                    timeMin=now.isoformat(),
                    timeMax=end_date.isoformat(),
                    singleEvents=True,
                    orderBy='startTime',
                )
                .execute()
            )
            events = events_result.get('items', [])

            # If no events, the next free slot is now
            if not events:
                next_free_start = now
                next_free_end = next_free_start + timedelta(hours=duration_hours)
                return next_free_start, next_free_end

            current_time = now
            for event in events:
                # Convert event times to UTC for comparison
                event_start = event['start'].get('dateTime')
                event_end = event['end'].get('dateTime')

                if event_start:
                    event_start = datetime.fromisoformat(event_start).astimezone(pytz.UTC)
                if event_end:
                    event_end = datetime.fromisoformat(event_end).astimezone(pytz.UTC)

                if event_end and event_end <= current_time:
                    continue

                if event_start and current_time + timedelta(hours=duration_hours) <= event_start:
                    return current_time, current_time + timedelta(hours=duration_hours)

                if event_end:
                    current_time = max(current_time, event_end)
                else:
                    current_time += timedelta(hours=1)

            return None  # No available time slot found

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return None

    def list_day_schedule(self, date: datetime.date) -> List[Dict[str, str]]:
        """
        Lists the events for a specified date in the user's Google Calendar.

        :param date: A datetime.date object representing the date.
        :return: A list of dictionaries, each representing an event.
        """
        try:
            # Define the time range for the specified date
            start_of_day = datetime.combine(date, time.min).astimezone(tz.tzlocal())
            end_of_day = datetime.combine(date, time.max).astimezone(tz.tzlocal())
            time_min = start_of_day.isoformat()
            time_max = end_of_day.isoformat()

            # Fetch events from the primary calendar
            events_result = (
                self.service.events()
                .list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime',
                )
                .execute()
            )
            events = events_result.get('items', [])

            # Create a list to hold the day's schedule
            schedule = []

            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                # Convert times to local timezone
                if 'dateTime' in event['start']:
                    start_dt = parser.isoparse(start).astimezone(tz.tzlocal())
                    end_dt = parser.isoparse(end).astimezone(tz.tzlocal())
                    start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                    end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                else:
                    start_str = start
                    end_str = end

                event_info = {
                    'summary': event.get('summary', 'No Title'),
                    'start': start_str,
                    'end': end_str,
                    'location': event.get('location', ''),
                    'description': event.get('description', ''),
                }
                schedule.append(event_info)

            return schedule

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return []

def get_tool_function_map():
    """Get the tool function map for Google Calendar-related functions"""
    tool_function_map = {
        "gcal_find_free_time_slot": {
            "function": GoogleCalendarHelper.find_free_time_slot,
            "description": "Find the next available free time slot in Google Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration_hours": {
                        "type": "number",
                        "description": "Duration of the time slot in hours",
                    },
                },
                "required": ["duration_hours"],
            },
        },
        "gcal_list_day_schedule": {
            "function": GoogleCalendarHelper.list_day_schedule,
            "description": "List events for a specified date in Google Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    },
                },
                "required": ["date"],
            },
        },
    }
    return tool_function_map 