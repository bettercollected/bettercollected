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
formData_test = {
  "actions": {},
  "builder_version": "v2",
  "button_text": "string",
  "consent": [],
  "cover_image": "string",
  "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur quis sem odio. Sed commodo vestibulum leo, sit amet tempus odio consectetur in. Mauris dolor elit, dignissim mollis feugiat maximus, faucibus et eros.",
  "fields": [
    {
      "attachment": {},
      "description": "string",
      "id": "66fd10c5663803bc22bd7a69",
      "image_url": "string",
      "index": 0,
      "properties": {
        "actions": [],
        "allow_multiple_selection": False,
        "allow_other_choice": False,
        "button_text": "string",
        "choices": [],
        "conditions": [],
        "date_format": "string",
        "description": "string",
        "fields": [
          {
            "attachment": {},
            "description": "string",
            "id": "61c73e81",
            "image_url": "string",
            "index": 1,
            "properties": {},
            "ref": "string",
            "tag": "strong",
            "title": "Email",
            "type": "short_text",
            "validations": {},
            "value": "string"
          }
        ],
        "hidden": False,
        "hide_marks": True,
        "labels": {},
        "layout": "SINGLE_COLUMN_NO_BACKGROUND",
        "logical_operator": "and",
        "mentions": {},
        "placeholder": "string",
        "rating_shape": "string",
        "start_from": 5,
        "steps": 1,
        "theme":  {
            "accent": "#FFFFFF",
            "primary": "#2E2E2E",
            "secondary": "#2E2E2E",
            "tertiary": "#DBDBDB",
            "title": "Black"
          },
        "update_id": "string"
      },
      "ref": "string",
      "tag": "strong",
      "title": "string",
      "type": "slide",
      "validations": {
        "max_choices": 2,
        "max_length": 5,
        "max_value": 5.5,
        "min_choices": 1,
        "min_length": 1,
        "min_value": 1.0,
        "regex": "string",
        "required": False
      },
      "value": "string"
    }
  ],
  "form_id": "66fd10c5663803bc22bd7a6d",
  "imported_form_id": "1vkN9x0zYV-zk3Zr-ZXP7nzqVvv8xGHhbNsAPHbBCuqU",
  "is_multi_page": True,
  "logo": "string",
  "parameters": {},
   "publishedAt": "2023-07-20T06:30:47.497Z",
  "secrets": {},
  "settings": {
    "custom_url": "1vkN9x0zYV-zk3Zr-ZXP7nzqVvv8xGHhbNsAPHbBCuqU",
    "embed_url": "https://docs.google.com/forms/d/e/1FAIpQLSewW1J_HnUJ5RXjCWWTzspee_OjDCBOe9sPTvqqpKezlygTiw/viewform",
    "is_closed": True,
    "is_public": True,
    "is_response_editable": True,
    "is_trial": False,
    "language": "string",
    "privacy_policy_url": "string",
    "provider": "self",
    "response_data_owner_field": "string",
    "response_data_owner_fields": [],
    "response_expiration": "string",
    "response_expiration_type": "date",
    "screens": {}
  },
  "state": {
    "global_state": {},
    "is_locked": False,
    "processor_state": {}
  },
  "thankyou_page": [
    {
      "buttonLink": "string",
      "buttonText": "string",
      "imageUrl": "string",
      "layout": "SINGLE_COLUMN_NO_BACKGROUND",
      "message": "string"
    }
  ],
  "theme": {
    "accent": "#FFFFFF",
    "primary": "#2E2E2E",
    "secondary": "#2E2E2E",
    "tertiary": "#DBDBDB",
    "title": "Black"
  },
  "title": "string",
  "type": "string",
  "welcome_page": {
    "buttonText": "string",
    "description": "string",
    "imageUrl": "string",
    "layout": "SINGLE_COLUMN_NO_BACKGROUND",
    "title": "Untitled"
  }
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
    "showOriginalForm": None,
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
