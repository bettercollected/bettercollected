from http import HTTPStatus

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from googleform.app.exceptions import HTTPException
from googleform.app.utils.google import dict_to_credential


class GoogleService:
    """
    Class for interacting with Google services.

    This class provides a convenient way to access various Google
    services using a single set of credentials.
    """

    @staticmethod
    def _build_service(credentials, service_name: str, version: str = "v1"):
        """
        Build a Google service object.

        Args:
            credentials (dict): A dictionary containing the credentials' information.
            service_name (str): The name of the service to build.
            version (str, optional): The version of the service to build.
                Defaults to "v1".

        Returns:
            googleapiclient.discovery.Resource: A Google service object.
        """
        return build(
            serviceName=service_name,
            version=version,
            credentials=dict_to_credential(credentials),
        )

    def create_sheet(self, title: str, credentials):
        try:
            spreadsheet = {"properties": {"title": title}}
            google_sheet = (
                self._build_service(credentials=credentials, service_name="sheets", version="v4")
                .spreadsheets()
                .create(body=spreadsheet, fields="spreadsheetId")
                .execute()
            )
            return google_sheet.get("spreadsheetId")
        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content="Sheet not found in Google forms",
                )
            if e.status_code == HTTPStatus.FORBIDDEN:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED, content=e.reason
                )
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Error Creating Sheet in Google",
            )
        except RefreshError as e:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Refresh error"
            )
        except TimeoutError as e:
            raise HTTPException(
                status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
            )

    def write_in_sheet(self, google_sheet_id: str, credentials, responses):
        try:
            body = {"values": responses}
            google_sheet = (
                self._build_service(credentials=credentials, service_name="sheets", version="v4")
                .spreadsheets().values()
                .update(spreadsheetId=google_sheet_id,
                        range="Sheet1",
                        valueInputOption="USER_ENTERED",
                        body=body, )
                .execute()
            )
            return google_sheet
        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content="Sheet with given ID not found",
                )
            if e.status_code == HTTPStatus.FORBIDDEN:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED, content=e.reason
                )
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Error Creating Sheet in Google",
            )
        except RefreshError as e:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Refresh error"
            )
        except TimeoutError as e:
            raise HTTPException(
                status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
            )

    def append_in_sheet(self, google_sheet_id: str, credentials):
        try:
            body = {"values": [['name', 'age', 'phone'], ['Sita', 123, 10101]]}
            google_sheet = (
                self._build_service(credentials=credentials, service_name="sheets", version="v4")
                .spreadsheets().values()
                .append(spreadsheetId=google_sheet_id,
                        range="Sheet1",
                        valueInputOption="USER_ENTERED",
                        body=body, )
                .execute()
            )
            return google_sheet
        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content="Sheet with given ID not found",
                )
            if e.status_code == HTTPStatus.FORBIDDEN:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED, content=e.reason
                )
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Error Creating Sheet in Google",
            )
        except RefreshError as e:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Refresh error"
            )
        except TimeoutError as e:
            raise HTTPException(
                status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
            )

    def get_form(self, form_id: str, credentials):
        """
        Get a Google Form by its form ID.

        Args:
            form_id (str): The ID of the form to retrieve.
            credentials (dict): A dictionary containing the credentials' information.

        Returns:
            dict: A dictionary containing the form data.
        """
        try:
            google_form = (
                self._build_service(credentials=credentials, service_name="forms")
                .forms()
                .get(formId=form_id)
                .execute()
            )
            return google_form
        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content="Form not found in Google forms",
                )
            if e.status_code == HTTPStatus.FORBIDDEN:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED, content=e.reason
                )
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Error fetching form from Google",
            )
        except RefreshError as e:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Refresh error"
            )
        except TimeoutError as e:
            raise HTTPException(
                status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
            )

    def get_form_list(self, credentials, page_token=None, max_page_size=100):
        """
        Get a list of forms from Google Forms API.

        Args:
            credentials (dict): A dictionary containing the credentials' information.
            page_token: Current page token
            max_page_size: Maximum page size

        Returns:
            list: A list containing the forms.
        """

        try:
            forms = []
            drive_service = self._build_service(
                credentials=credentials, service_name="drive", version="v3"
            )
            fields = (
                "nextPageToken, files(id, name, webViewLink, iconLink, "
                "createdTime, modifiedTime, owners)"
            )
            while max_page_size > 0:
                max_page_size -= 1
                response = (
                    drive_service.files()
                    .list(
                        q="mimeType='application/vnd.google-apps.form'",
                        spaces="drive",
                        fields=fields,
                        pageToken=page_token,
                    )
                    .execute()
                )
                forms.extend(response.get("files", []))
                page_token = response.get("nextPageToken", None)
                if page_token is None:
                    break
            drive_service.close()
            return forms
        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content="Form not found in Google forms",
                )
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Error fetching form from Google",
            )
        except RefreshError as e:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Refresh error"
            )
        except TimeoutError as e:
            raise HTTPException(
                status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
            )

    def get_form_response_list(self, form_id: str, credentials):
        """
        Get a list of responses for a Google Form.

        Args:
            form_id (str): The ID of the form to retrieve responses for.
            credentials (dict): A dictionary containing the credentials' information.

        Returns:
            dict: A dictionary containing the form responses.
        """
        try:
            return (
                self._build_service(credentials=credentials, service_name="forms")
                .forms()
                .responses()
                .list(formId=form_id)
                .execute()
                .get("responses", [])
            )
        except HttpError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    content="Responses not found in Google forms",
                )
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                content="Error fetching form from Google",
            )
        except RefreshError as e:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Refresh error"
            )
        except TimeoutError as e:
            raise HTTPException(
                status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
            )
