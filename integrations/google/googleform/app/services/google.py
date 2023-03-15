from googleapiclient.discovery import build

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
            version (str, optional): The version of the service to build. Defaults to "v1".

        Returns:
            googleapiclient.discovery.Resource: A Google service object.
        """
        return build(
            serviceName=service_name,
            version=version,
            credentials=dict_to_credential(credentials),
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
        return (
            self._build_service(credentials=credentials, service_name="forms")
            .forms()
            .get(formId=form_id)
            .execute()
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
        forms = []
        drive_service = self._build_service(
            credentials=credentials, service_name="drive", version="v3"
        )
        while max_page_size > 0:
            max_page_size -= 1
            response = (
                drive_service.files()
                .list(
                    q="mimeType='application/vnd.google-apps.form'",
                    spaces="drive",
                    fields="nextPageToken, files(id, name, webViewLink, iconLink, createdTime, modifiedTime, owners)",
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

    def get_form_response_list(self, form_id: str, credentials):
        """
        Get a list of responses for a Google Form.

        Args:
            form_id (str): The ID of the form to retrieve responses for.
            credentials (dict): A dictionary containing the credentials' information.

        Returns:
            dict: A dictionary containing the form responses.
        """
        return (
            self._build_service(credentials=credentials, service_name="forms")
            .forms()
            .responses()
            .list(formId=form_id)
            .execute()
            .get("responses", [])
        )
