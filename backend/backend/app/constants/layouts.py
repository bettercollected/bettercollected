"""Layout options with AI-friendly descriptions."""

from common.models.standard_form import LayoutType

layout_descriptions = {
    LayoutType.SINGLE_COLUMN_NO_BACKGROUND: (
        "A clean single-column layout with no background image. Best for text-heavy "
        "forms, multi-step surveys, and any form where clarity and focus are the "
        "priority. Works well with all themes. (Default / recommended)"
    ),
    LayoutType.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN: (
        "A single-column layout left-aligned with no background. Suited for detailed "
        "questionnaires, academic forms, or anywhere a document-style flow is preferred."
    ),
    LayoutType.SINGLE_COLUMN_IMAGE_BACKGROUND: (
        "A single-column layout with a full-width background image. Visually engaging "
        "— ideal for welcome/landing slides, event registrations, and brand-driven "
        "forms where imagery reinforces the form's message."
    ),
    LayoutType.TWO_COLUMN_IMAGE_LEFT: (
        "A two-column layout with an image on the left side and the form fields on the "
        "right. Great for product feedback, e-commerce surveys, showcasing a visual "
        "context alongside questions."
    ),
    LayoutType.TWO_COLUMN_IMAGE_RIGHT: (
        "A two-column layout with the form fields on the left and an image on the right. "
        "Useful for onboarding, job applications, and any form pairing text with a "
        "supporting visual."
    ),
}


def get_layouts_for_ai() -> list[dict]:
    """Return layout options with descriptions for use in AI tool calls."""
    return [
        {
            "value": layout.value,
            "description": description,
        }
        for layout, description in layout_descriptions.items()
    ]
