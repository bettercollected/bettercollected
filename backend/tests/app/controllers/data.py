from beanie import PydanticObjectId

from common.models.user import User

formData = {
    "title": "string",
    "description": "string",
    "fields": [
        {
            "id": "string",
            "ref": "string",
            "title": "string",
            "description": "string",
            "type": "date",
            "properties": {},
            "validations": {},
            "attachment": {
                "type": "image",
                "href": "string",
                "scale": 0,
                "properties": {},
                "embed_provider": "youtube",
            },
        }
    ],
    "settings": {
        "pinned": False,
        "embedUrl": "string",
        "customUrl": "string",
        "private": False,
        "responseDataOwnerField": "string",
        "provider": "string",
    },
}

formData_2 = {"title": "search_form"}

formResponse = {
    "provider": "string",
    "respondentEmail": "string",
    "answers": {},
    "createdAt": "2023-07-20T06:30:47.497Z",
    "updatedAt": "2023-07-20T06:30:47.497Z",
    "publishedAt": "2023-07-20T06:30:47.497Z",
    "dataOwnerIdentifierType": "string",
    "formTitle": "string",
    "status": "string",
    "formImportedBy": "string",
    "deletionStatus": "pending",
}

workspace_settings = {
    "pinned": True,
    "customUrl": "custom_url",
    "private": True,
    "hidden": False,
    "privacyPolicyUrl": None,
    "responseDataOwnerField": "customUser",
    "responseExpiration": None,
    "responseExpirationType": None,
    "disableBranding": None,
    "isPublished": None,
    "formCloseDate": None,
    "allowEditingResponse": None,
    "showSubmissionNumber": None,
    "requireVerifiedIdentity": None,
}

workspace_tag = {"title": "BetterCollected-Team"}

user_info = {
    "users_info": [
        {
            "_id": "64b0e6c7ae404afd00202f5d",
            "created_at": "2023-07-14T06:10:15.698298",
            "updated_at": "2023-07-14T06:10:15.707762",
            "first_name": "Test_First_Name",
            "last_name": "Test_Second_Name",
            "profile_image": "https://lh3.googleusercontent.com/a/AAcHTtd4wpSc6ZsDSTvrvoOBEMFFAn1005UjtsX6Z3X9guB_xLM=s96-c",
            "email": "testing123@gmail.com",
            "roles": ["FORM_RESPONDER", "FORM_CREATOR"],
            "otp_code": "null",
            "otp_expiry": "null",
            "plan": "FREE",
            "stripe_customer_id": "null",
            "stripe_payment_id": "null",
        }
    ]
}

user_tag_details = {
    "email": "testing123@gmail.com",
    "name": "Test_First_Name Test_Second_Name",
    "tags": ["FORM_ADDED_TO_GROUP", "GROUP_CREATED"],
}

test_form_import_data = {"form": formData, "response_data_owner": "string"}

workspace_attribute = {
    "title": "betterCollected_test_workspace",
    "description": "It is a testing workspace",
    "custom_domain": "test_custom_domain",
    "workspace_name": "test_workspace_name",
}
workspace_attribute_1 = {
    "title": "new_testing_workspace",
    "description": "It is another testing workspace",
}

testUser = User(
    id=str(PydanticObjectId()), sub="test@email.com", roles=["ADMIN", "FORM_CREATOR"]
)
testUser1 = User(id=str(PydanticObjectId()), sub="bettercollected@email.com")
testUser2 = User(
    id=str(PydanticObjectId()), sub="random@email.com", roles=["FORM_RESPONDER"]
)
proUser = User(id=str(PydanticObjectId()), sub="prouser@gmail.com", plan="PRO")

invited_user = User(
    id=str(PydanticObjectId()), sub="invited_daemon@gmail.com", roles=["FORM_RESPONDER"]
)

invitation_request = {"email": "invited_daemon@gmail.com", "role": "COLLABORATOR"}
