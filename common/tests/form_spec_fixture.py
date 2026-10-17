"""A page-based form that uses every value the form spec covers."""

from common.models.standard_form import StandardForm

RICH_TITLE = {
    "type": "doc",
    "content": [
        {
            "type": "paragraph",
            "attrs": {"textAlign": None},
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "pipe", "attrs": {"fieldId": "f-name", "fallback": None}},
            ],
        }
    ],
}

THEME = {
    "title": "Harbour",
    "primary": "#0F172A",
    "secondary": "#1D4ED8",
    "tertiary": "#2563EB",
    "accent": "#DBEAFE",
    "style": "sheet",
    "background": {
        "type": "gradient",
        "gradientFrom": "#FFFFFF",
        "gradientTo": "#DBEAFE",
        "gradientAngle": 135,
    },
}


def varied_form_data() -> dict:
    return {
        "builder_version": "v2",
        "title": "Membership application",
        "description": "Apply in five minutes.",
        "logo": "https://files.example.org/public/logos/abc.png",
        "logo_position": "center",
        "logo_alt": "Example club",
        "use_workspace_logo": False,
        "hidden_fields": ["utm_source", "ref"],
        "theme": THEME,
        "welcome_page": {
            "title": "Welcome",
            "description": "Tell us about yourself.",
            "layout": "TWO_COLUMN_IMAGE_LEFT",
            "imageUrl": "https://images.unsplash.com/photo-1",
            "buttonText": "Start",
        },
        "thankyou_page": [
            {
                "title": "Thanks",
                "message": "We will be in touch.",
                "buttonText": "Back to the site",
                "buttonLink": "https://example.org",
                "layout": "SINGLE_COLUMN_NO_BACKGROUND",
            },
            {"message": "Second ending", "imageUrl": "https://images.unsplash.com/2"},
        ],
        "settings": {
            "privacy_policy_url": "https://example.org/privacy",
            "response_expiration_type": "days",
            "response_expiration": "30",
        },
        "fields": [
            {
                "id": "p-1",
                "index": 0,
                "type": "slide",
                "image_url": "https://images.unsplash.com/3",
                "properties": {
                    "section_title": "About you",
                    "layout": "TWO_COLUMN_IMAGE_RIGHT",
                    "show_question_numbers": True,
                    "position": {"x": 10.5, "y": -4},
                    "theme": THEME,
                    "jumps": [
                        {
                            "operator": "AND",
                            "conditions": [
                                {
                                    "fieldId": "f-member",
                                    "fieldType": "yes_no",
                                    "comparison": "IS_EQUAL",
                                    "value": "No",
                                }
                            ],
                            "target": "__SUBMIT__",
                        },
                        {
                            "operator": "OR",
                            "conditions": [
                                {
                                    "fieldId": "f-age",
                                    "fieldType": "number",
                                    "comparison": "GREATER_THAN",
                                    "value": 64,
                                }
                            ],
                            "target": "p-3",
                        },
                    ],
                    "fields": [
                        {
                            "id": "f-name",
                            "index": 0,
                            "type": "short_text",
                            "title": "Your name",
                            "description": "As on your ID",
                            "properties": {
                                "placeholder": "Jane",
                                "col_span": 6,
                                "fields": [],
                            },
                            "validations": {
                                "required": True,
                                "min_length": 2,
                                "max_length": 80,
                                "regex": "^[^0-9]+$",
                            },
                        },
                        {
                            "id": "f-email",
                            "index": 1,
                            "type": "email",
                            "title": RICH_TITLE,
                            "properties": {
                                "why_we_ask": "To send your receipt.",
                                "col_span": 6,
                            },
                            "validations": {"required": True},
                        },
                        {
                            "id": "f-age",
                            "index": 2,
                            "type": "number",
                            "title": "Age",
                            "validations": {"min_value": 16, "max_value": 120.5},
                        },
                        {
                            "id": "f-member",
                            "index": 3,
                            "type": "yes_no",
                            "title": "Member before?",
                            "properties": {
                                "choices": [
                                    {"id": "c-y", "value": "Yes"},
                                    {"id": "c-n", "value": "No"},
                                ]
                            },
                        },
                        {
                            "id": "f-since",
                            "index": 4,
                            "type": "date",
                            "title": "Member since",
                            "properties": {
                                "label": "Start date",
                                "date_format": "DD/MM/YYYY",
                                "date_rules": [
                                    {"comparison": "before", "target": "today"},
                                    {
                                        "comparison": "after",
                                        "target": "date",
                                        "date": "1990-01-01",
                                    },
                                ],
                                "logic": {
                                    "action": "SHOW",
                                    "operator": "AND",
                                    "conditions": [
                                        {
                                            "fieldId": "f-member",
                                            "fieldType": "yes_no",
                                            "comparison": "IS_EQUAL",
                                            "value": "Yes",
                                        }
                                    ],
                                },
                            },
                        },
                        {
                            "id": "f-until",
                            "index": 5,
                            "type": "date",
                            "title": "Member until",
                            "properties": {
                                "date_rules": [
                                    {
                                        "comparison": "on_or_after",
                                        "target": "field",
                                        "field_id": "f-since",
                                    }
                                ]
                            },
                        },
                    ],
                },
            },
            {
                "id": "p-2",
                "index": 1,
                "type": "slide",
                "properties": {
                    "layout": "SINGLE_COLUMN_NO_BACKGROUND",
                    "fields": [
                        {
                            "id": "f-topics",
                            "index": 0,
                            "type": "multiple_choice",
                            "title": "Topics",
                            "properties": {
                                "allow_multiple_selection": True,
                                "allow_other_choice": True,
                                "choices": [
                                    {
                                        "id": "t-1",
                                        "value": "Sailing",
                                        "label": "Sailing",
                                        "attachment": {
                                            "type": "image",
                                            "href": "https://images.unsplash.com/4",
                                            "scale": 0.5,
                                            "properties": {"description": "A boat"},
                                        },
                                    },
                                    {"id": "t-2", "value": "Rowing"},
                                ],
                            },
                            "validations": {"min_choices": 1, "max_choices": 2},
                        },
                        {
                            "id": "f-branch",
                            "index": 1,
                            "type": "dropdown",
                            "title": "Branch",
                            "properties": {
                                "choices": [
                                    {"id": "b-1", "value": "North"},
                                    {"id": "b-2", "value": "South"},
                                ]
                            },
                        },
                        {
                            "id": "f-rating",
                            "index": 2,
                            "type": "rating",
                            "title": "How likely?",
                            "properties": {
                                "steps": 5,
                                "start_from": 1,
                                "rating_shape": "star",
                                "hide_marks": True,
                                "labels": {"1": "Unlikely", "5": "Very"},
                            },
                        },
                        {
                            "id": "f-household",
                            "index": 3,
                            "type": "group",
                            "title": "Household members",
                            "description": "One per person",
                            "properties": {
                                "repeat": {
                                    "min_items": 0,
                                    "max_items": 6,
                                    "item_label": "Person",
                                    "item_title": "{{field:g-name}}",
                                    "export_layout": "rows",
                                },
                                "fields": [
                                    {
                                        "id": "g-name",
                                        "index": 0,
                                        "type": "short_text",
                                        "title": "Name",
                                    },
                                    {
                                        "id": "g-child",
                                        "index": 1,
                                        "type": "yes_no",
                                        "title": "Under 18?",
                                    },
                                    {
                                        "id": "g-school",
                                        "index": 2,
                                        "type": "short_text",
                                        "title": "School",
                                        "properties": {
                                            "logic": {
                                                "action": "SHOW",
                                                "conditions": [
                                                    {
                                                        "fieldId": "g-child",
                                                        "fieldType": "yes_no",
                                                        "comparison": "IS_EQUAL",
                                                        "value": "Yes",
                                                    }
                                                ],
                                            }
                                        },
                                    },
                                ],
                            },
                        },
                        {
                            "id": "f-notes",
                            "index": 4,
                            "type": "long_text",
                            "title": "Anything else?",
                            "internal": True,
                        },
                    ],
                },
            },
            {
                "id": "p-3",
                "index": 2,
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "f-intro",
                            "index": 0,
                            "type": "text",
                            "title": "A few last things",
                            "value": "Plain statement",
                            "image_url": "https://images.unsplash.com/5",
                            "attachment": {
                                "type": "video",
                                "href": "https://www.youtube.com/watch?v=x",
                                "embed_provider": "youtube",
                            },
                        },
                        {
                            "id": "f-grid",
                            "index": 1,
                            "type": "matrix",
                            "title": "Rate each",
                            "properties": {
                                "row_titles": ["Food", "Music"],
                                "column_titles": ["Bad", "Good"],
                            },
                        },
                        {
                            "id": "f-table",
                            "index": 2,
                            "type": "tabular_input",
                            "title": "Your boats",
                            "properties": {
                                "column_titles": ["Name", "Length"],
                                "tabular_value": [["", ""]],
                            },
                        },
                        {
                            "id": "f-doc",
                            "index": 3,
                            "type": "file_upload",
                            "title": "Upload a photo",
                        },
                        {
                            "id": "f-kids",
                            "index": 4,
                            "type": "short_text",
                            "title": "Who comes along?",
                            "properties": {
                                "logic": {
                                    "action": "HIDE",
                                    "operator": "OR",
                                    "conditions": [
                                        {
                                            "fieldId": "f-household",
                                            "fieldType": "group",
                                            "comparison": "IS_EQUAL",
                                            "value": 0,
                                            "groupMode": "COUNT",
                                        },
                                        {
                                            "fieldId": "f-household",
                                            "fieldType": "group",
                                            "comparison": "IS_EQUAL",
                                            "value": "Yes",
                                            "groupMode": "ANY",
                                            "childFieldId": "g-child",
                                            "childFieldType": "yes_no",
                                        },
                                    ],
                                }
                            },
                        },
                        {
                            "id": "f-total",
                            "index": 5,
                            "type": "calculated",
                            "title": "Your total",
                            "properties": {
                                "expression": {
                                    "if": [
                                        {"==": [{"var": "f-age"}, None]},
                                        0,
                                        {
                                            "round": [
                                                {"*": [{"var": "f-age"}, 1.21]},
                                                2,
                                            ]
                                        },
                                    ]
                                },
                                "format": {
                                    "style": "currency",
                                    "decimals": 2,
                                    "currency": "EUR",
                                },
                            },
                        },
                        {
                            "id": "f-score",
                            "index": 6,
                            "type": "calculated",
                            "title": "Score",
                            "properties": {
                                "expression": {
                                    "sum": [{"var": "f-household.g-name"}, 1]
                                },
                                "hiddenFromRespondents": True,
                            },
                        },
                    ]
                },
            },
        ],
    }


def varied_form() -> StandardForm:
    return StandardForm(**varied_form_data())
