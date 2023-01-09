# Crypto Constants
AES_HEX_KEY = "AES_HEX_KEY"

# Auth Constants
AUTH_STATE = "state"
AUTH_AUTHORIZATION = "Authorization"
AUTH_REFRESH_TOKEN = "RefreshToken"
AUTH_RESPONDER_ROLE = "RESPONDER"
AUTH_CREATOR_ROLE = "CREATOR"

# Date Constants
GOOGLE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# Message Constants
MESSAGE_UNAUTHORIZED = (
    "401 - Unauthorized: Access is denied due to invalid credentials."
)
MESSAGE_FORBIDDEN = (
    "403 - Forbidden: You don't have permission to access this resource."
)
MESSAGE_NOT_FOUND = "404 - Not found: The resource you are requesting is not available."
MESSAGE_KEY_FOUND = "Found an unexpected key. Make sure the key is expected."
MESSAGE_ITEM_TO_DATA_ERROR = (
    "Could not convert the given item representation into the expected data."
)
MESSAGE_DATA_TO_ITEM_ERROR = (
    "Could not convert the data into the expected item representation."
)
MESSAGE_CONVERSION_WARNING = (
    "A non-fatal error occurred during data-to-item or item-to-data conversion. "
    "Some information may have been lost or altered."
)

MESSAGE_SCHEDULER_START_SUCCESS = "Schedulers started!"
MESSAGE_SCHEDULER_START_FAILURE = "Schedulers startup failure!"
MESSAGE_SCHEDULER_STOP_SUCCESS = "Schedulers stopped!"
MESSAGE_SCHEDULER_STOP_FAILURE = "Could not shut down the running schedulers!"
MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_SUCCESS = "All jobs removed successfully!"
MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_FAILURE = "Schedulers remove all jobs failure!"
MESSAGE_SCHEDULER_ADD_JOB_FAILURE = "Could not schedule the request job!"
MESSAGE_SCHEDULER_REMOVE_JOB_FAILURE = "Could not remove the request job!"

MESSAGE_EMPTY_FORM_CONFIG = "No forms are imported yet!"

MESSAGE_DATABASE_EXCEPTION = "500 - We are having some issues with our database connection. Please try again later."

MESSAGE_OAUTH_INVALID_TOKEN = "Token is invalid!"
MESSAGE_OAUTH_INVALID_GRANT = "Invalid oauth2 grant!"
MESSAGE_OAUTH_INVALID_CLIENT = "Oauth invalid client error!"
MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY = (
    "Either oauth access token is missing or expiry time is missing!"
)
MESSAGE_OAUTH_MISSING_REFRESH_TOKEN = (
    "Oauth is missing Refresh Token from the credentials!"
)
MESSAGE_OAUTH_FETCH_TOKEN_ERROR = "Could not fetch oauth token!"
