"""The words of the mails this service sends, in English and Dutch.

A caller names the recipient's language (``locale``: "nl", "nl-NL", "en", ...);
anything that is not Dutch gets English. Values chosen by people (workspace
and form titles, an inviter's name) are never part of these strings: the
templates place them next to the words, autoescaped.

Attribution is honest: the sender is always this instance (``product``); a
workspace appears as "<workspace> via <product>", and an inviter's name is
what they call themselves, shown as such.
"""

from typing import Dict, Optional

DEFAULT_LOCALE = "en"

ROLE_NAMES_NL = {
    "Owner": "Eigenaar",
    "Admin": "Beheerder",
    "Editor": "Bewerker",
    "Reviewer": "Beoordelaar",
    "Viewer": "Kijker",
    "Privacy officer": "Privacyfunctionaris",
}

TEXTS: Dict[str, Dict[str, str]] = {
    "en": {
        # shared
        "footer_rights": "All rights reserved.",
        "footer_visit": "Visit",
        "footer_more": "for more information",
        "footer_product_of": "A product of Sireto B.V.",
        "footer_trademark": "is a registered trademark of Sireto B.V.",
        # sign-in code
        "code_subject": "Your {product} verification code",
        "code_heading": "verification code",
        "code_intro": "Use the code below to confirm your identity.",
        "code_expiry": "This code will expire in 5 minutes",
        "code_not_you": "If you did not request a verification code,",
        "code_report": "please report it to",
        # invitation
        "invite_subject": "You have been invited to a workspace on {product}",
        "invite_heading_via": "via",
        "invite_line": "invited you to join this workspace",
        "invite_line_role": "invited you to join this workspace as",
        "invite_name_note": "The name is the one they gave themselves on {product}.",
        "invite_button": "Join workspace",
        "invite_expiry": "This link will expire in 7 days",
        "invite_pitch": "Efficiently organize, manage and build trust with your form submissions.",
        "invite_learn_more": "Learn more",
        "invite_unknown_workspace": "a workspace",
        # submission update
        "update_subject": "Update on your submission",
        "update_heading": "There is an update on your submission",
        "update_from_workspace": "{workspace} responded to your submission to",
        "update_generic": "You have a response to your submission to",
        "update_sign_in": "Sign in to see it.",
        "update_button": "View your submission",
        "update_why": "You are receiving this because you submitted this form with your verified email address. If the button does not work, open",
        # Google Sheets reconnect (a grant from before drive.file)
        "sheets_subject": "Reconnect Google Sheets for one of your forms",
        "sheets_heading": "Reconnect Google Sheets",
        "sheets_intro": "The Google Sheets connection of this form must be renewed:",
        "sheets_in_workspace": "in the workspace",
        "sheets_why": "It was set up with access to all files in your Google Drive. We now only ask for access to the spreadsheets that {product} creates for you.",
        "sheets_paused": "Until you reconnect, new submissions are not added to the spreadsheet. They are still saved in {product}, so nothing is lost.",
        "sheets_button": "Reconnect Google Sheets",
        "sheets_why_you": "You are receiving this because you own the plan of this workspace. If the button does not work, open",
    },
    "nl": {
        "footer_rights": "Alle rechten voorbehouden.",
        "footer_visit": "Ga naar",
        "footer_more": "voor meer informatie",
        "footer_product_of": "Een product van Sireto B.V.",
        "footer_trademark": "is een geregistreerd handelsmerk van Sireto B.V.",
        "code_subject": "Je verificatiecode voor {product}",
        "code_heading": "verificatiecode",
        "code_intro": "Gebruik de code hieronder om te bevestigen dat jij het bent.",
        "code_expiry": "Deze code is 5 minuten geldig",
        "code_not_you": "Heb je geen code aangevraagd?",
        "code_report": "Meld het dan bij",
        "invite_subject": "Je bent uitgenodigd voor een werkruimte op {product}",
        "invite_heading_via": "via",
        "invite_line": "nodigt je uit voor deze werkruimte",
        "invite_line_role": "nodigt je uit voor deze werkruimte als",
        "invite_name_note": "Dit is de naam die deze persoon zelf op {product} heeft opgegeven.",
        "invite_button": "Naar de werkruimte",
        "invite_expiry": "Deze link is 7 dagen geldig",
        "invite_pitch": "Organiseer en beheer je formulierreacties, en bouw vertrouwen op.",
        "invite_learn_more": "Meer weten",
        "invite_unknown_workspace": "een werkruimte",
        "update_subject": "Nieuws over je inzending",
        "update_heading": "Er is nieuws over je inzending",
        "update_from_workspace": "{workspace} heeft gereageerd op je inzending voor",
        "update_generic": "Er is een reactie op je inzending voor",
        "update_sign_in": "Log in om die te lezen.",
        "update_button": "Bekijk je inzending",
        "update_why": "Je krijgt deze e-mail omdat je dit formulier hebt ingevuld met je bevestigde e-mailadres. Werkt de knop niet? Open dan",
        "sheets_subject": "Koppel Google Sheets opnieuw voor een van je formulieren",
        "sheets_heading": "Koppel Google Sheets opnieuw",
        "sheets_intro": "De koppeling met Google Sheets van dit formulier moet opnieuw worden gemaakt:",
        "sheets_in_workspace": "in de werkruimte",
        "sheets_why": "De koppeling had toegang tot alle bestanden in je Google Drive. We vragen nu alleen toegang tot de spreadsheets die {product} voor je maakt.",
        "sheets_paused": "Tot je opnieuw koppelt, komen nieuwe inzendingen niet in de spreadsheet. Ze worden wel bewaard in {product}. Er gaat dus niets verloren.",
        "sheets_button": "Google Sheets opnieuw koppelen",
        "sheets_why_you": "Je krijgt deze e-mail omdat het abonnement van deze werkruimte op jouw naam staat. Werkt de knop niet? Open dan",
    },
}


def mail_locale(value: Optional[str]) -> str:
    """ "nl" for a Dutch language tag ("nl", "nl-NL", "NL_be"), else "en"."""
    tag = (value or "").strip().lower().replace("_", "-")
    return "nl" if tag == "nl" or tag.startswith("nl-") else DEFAULT_LOCALE


def texts(locale: Optional[str]) -> Dict[str, str]:
    return TEXTS[mail_locale(locale)]


def role_name(role: Optional[str], locale: Optional[str]) -> Optional[str]:
    """A role's label (the backend sends the English one) in the mail's
    language; an unknown label is kept as it is."""
    if not role:
        return None
    if mail_locale(locale) == "nl":
        return ROLE_NAMES_NL.get(role, role)
    return role
