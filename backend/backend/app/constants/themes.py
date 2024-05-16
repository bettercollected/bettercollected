# Theme colors dictionary
from common.models.standard_form import Theme

theme_dict = {
    "Default": {
        "title": "Default",
        "primary": "#2E2E2E",
        "secondary": "#0764EB",
        "tertiary": "#A2C5F8",
        "accent": "#F2F7FF",
    },
    "Blue": {
        "title": "Blue",
        "primary": "#2E2E2E",
        "secondary": "#337FC2",
        "tertiary": "#61A9E9",
        "accent": "#B0DAFF",
    },
    "Green": {
        "title": "Green",
        "primary": "#2E2E2E",
        "secondary": "#459E73",
        "tertiary": "#81D8AE",
        "accent": "#D7F6E7",
    },
    "Red": {
        "title": "Red",
        "primary": "#2E2E2E",
        "secondary": "#BE3032",
        "tertiary": "#E75759",
        "accent": "#FFB2B3",
    },
    "Black": {
        "title": "Black",
        "primary": "#2E2E2E",
        "secondary": "#2E2E2E",
        "tertiary": "#DBDBDB",
        "accent": "#FFFFFF",
    },
    "Orange": {
        "title": "Orange",
        "primary": "#2E2E2E",
        "secondary": "#DA8C0B",
        "tertiary": "#F1B85A",
        "accent": "#FFEFCC",
    },
    "Purple": {
        "title": "Purple",
        "primary": "#2E2E2E",
        "secondary": "#533CAF",
        "tertiary": "#846BEC",
        "accent": "#CFC3FF",
    },
}

themes = {title: Theme(**colors) for title, colors in theme_dict.items()}
