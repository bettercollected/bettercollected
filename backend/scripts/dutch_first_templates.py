"""
Dutch-first templates with English twins, seeded into the template gallery by
scripts/seed_flow_templates.py (they are part of its TEMPLATE_BUILDERS).

Five forms organisations often need: a rental home application, a school
enrolment, a request to a local organisation, a new colleague's details and
an event registration. Each is written once below, in Dutch at B1 level with
its English twin beside it, and built into two templates (settings.language
"nl" and "en") with the same questions in the same order:

- one question per page, so every screen asks one thing;
- every question says why it is asked ("why we ask this", shown under it);
- honest defaults: only what a first assessment needs is required, nothing
  is pre-selected, follow-up questions are skipped unless they apply, and
  answers are deleted after a fixed number of days (the form's retention
  setting, so it is enforced and stated to the respondent by the page);
- no identity numbers and no documents: those are arranged in person.

Dutch uses "u" where an organisation writes to the public (housing, school,
request) and "je" for a new colleague and an event. Yes/no questions keep the
stored choices "Yes"/"No" in both languages: the respondent page shows them
in the form's language.

To change the wording of a template that is already seeded, delete it by
title first (see backend/AGENTS.md "Seed scripts"): the seed never overwrites.
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, Tuple

LAYOUT = "SINGLE_COLUMN_NO_BACKGROUND"
LANGUAGES = ("nl", "en")
SUBMIT = "__SUBMIT__"
# Stored values of a yes/no question's choices, whatever the language.
YES, NO = "Yes", "No"

Text = Dict[str, str]


def t(nl: str, en: str) -> Text:
    return {"nl": nl, "en": en}


@dataclass(frozen=True)
class Jump:
    """Leave this question's page for ``to`` (a question key or SUBMIT)
    when the answer to the yes/no question ``source`` is (``equal``) or is
    not ``value`` (YES or NO). Only yes/no questions route here: their
    condition value is the same in every language."""

    source: str
    value: str
    to: str
    equal: bool = True


@dataclass(frozen=True)
class Question:
    key: str
    type: str
    title: Text
    why: Text
    required: bool = False
    choices: Tuple[Text, ...] = ()
    jumps: Tuple[Jump, ...] = ()
    validations: Dict[str, object] = field(default_factory=dict)
    date_rules: Tuple[Dict[str, str], ...] = ()


def skip_unless_yes(source: str, to: str) -> Jump:
    """Go on to ``to`` unless ``source`` was answered "Yes": the follow-up
    pages between them are only shown after a yes. An unanswered question
    counts as not yes, so the yes/no question itself can stay optional."""
    return Jump(source, YES, to, equal=False)


@dataclass(frozen=True)
class BilingualTemplate:
    key: str
    title: Text
    description: Text
    welcome: Text
    ending_title: Text
    ending_message: Text
    questions: Tuple[Question, ...]
    start: Text = field(default_factory=lambda: t("Beginnen", "Start"))
    # Days a response is kept (the form's enforced retention setting: the
    # server deletes it then and the respondent page says so). Only a period
    # the organisation needs for the first assessment; the creator can change
    # it. Never a free-text claim in the template's wording.
    retention_days: int = 0


NOT_BEFORE_TODAY = ({"comparison": "on_or_after", "target": "today"},)
BEFORE_TODAY = ({"comparison": "before", "target": "today"},)


HOUSING_APPLICATION = BilingualTemplate(
    key="housing_application",
    retention_days=180,
    title=t("Aanvraag huurwoning", "Rental home application"),
    description=t(
        "Vraag een huurwoning aan. Het invullen duurt ongeveer 5 minuten.",
        "Apply for a rental home. It takes about 5 minutes.",
    ),
    welcome=t(
        "Met dit formulier vraagt u een huurwoning aan. Het invullen duurt "
        "ongeveer 5 minuten. We vragen alleen wat we nodig hebben om uw "
        "aanvraag te beoordelen. Bij elke vraag staat waarom we die stellen. "
        "U hoeft geen documenten mee te sturen.",
        "Use this form to apply for a rental home. It takes about 5 minutes. "
        "We only ask what we need to assess your application. Each question "
        "says why we ask it. You don't need to send any documents.",
    ),
    ending_title=t("Bedankt voor uw aanvraag", "Thank you for your application"),
    ending_message=t(
        "We hebben uw aanvraag ontvangen. We laten u per e-mail weten wat de "
        "volgende stap is.",
        "We have received your application. We'll email you about the next step.",
    ),
    questions=(
        Question(
            "name",
            "short_text",
            t("Wat is uw naam?", "What is your name?"),
            t(
                "Zo weten we van wie de aanvraag is.",
                "So we know whose application this is.",
            ),
            required=True,
        ),
        Question(
            "email",
            "email",
            t("Wat is uw e-mailadres?", "What is your email address?"),
            t(
                "We laten u per e-mail weten wat er met uw aanvraag gebeurt.",
                "We'll email you about what happens with your application.",
            ),
            required=True,
        ),
        Question(
            "phone",
            "phone_number",
            t(
                "Op welk telefoonnummer kunnen we u bellen?",
                "Which phone number can we call you on?",
            ),
            t(
                "Soms is bellen sneller. Dit hoeft u niet in te vullen.",
                "Sometimes a call is quicker. You can leave this empty.",
            ),
        ),
        Question(
            "town",
            "short_text",
            t("In welke plaats woont u nu?", "Which town or city do you live in now?"),
            t(
                "Voor sommige woningen gelden regels over waar u nu woont.",
                "Some homes have rules about where applicants live now.",
            ),
        ),
        Question(
            "living_now",
            "multiple_choice",
            t("Hoe woont u nu?", "How do you live now?"),
            t(
                "Zo begrijpen we uw situatie beter.",
                "It helps us understand your situation.",
            ),
            choices=(
                t("Ik huur een woning", "I rent a home"),
                t("Ik heb een koopwoning", "I own a home"),
                t(
                    "Ik woon bij mijn ouders of familie",
                    "I live with my parents or family",
                ),
                t(
                    "Ik heb nu geen vaste woonplek",
                    "I don't have a fixed place to live right now",
                ),
                t("Anders", "Something else"),
            ),
        ),
        Question(
            "household",
            "number",
            t(
                "Met hoeveel mensen gaat u in de woning wonen? Tel uzelf ook mee.",
                "How many people will live in the home? Count yourself too.",
            ),
            t(
                "Zo weten we welke woningen groot genoeg zijn.",
                "So we know which homes are big enough.",
            ),
            required=True,
            validations={"min_value": 1, "max_value": 20},
        ),
        Question(
            "income",
            "multiple_choice",
            t(
                "Wat is ongeveer het bruto inkomen van uw huishouden per jaar?",
                "Roughly what is your household's gross income per year?",
            ),
            t(
                "Voor veel huurwoningen is er een grens voor het inkomen. Een "
                "schatting is genoeg.",
                "Many rental homes have an income limit. An estimate is enough.",
            ),
            choices=(
                t("Minder dan € 30.000", "Less than €30,000"),
                t("€ 30.000 tot € 45.000", "€30,000 to €45,000"),
                t("€ 45.000 tot € 60.000", "€45,000 to €60,000"),
                t("€ 60.000 of meer", "€60,000 or more"),
                t("Dat weet ik niet precies", "I'm not sure"),
            ),
        ),
        Question(
            "move_date",
            "date",
            t("Vanaf wanneer wilt u verhuizen?", "From when do you want to move?"),
            t(
                "Zo kunnen we u woningen aanbieden die op tijd vrij zijn.",
                "So we can offer you homes that are free in time.",
            ),
            date_rules=NOT_BEFORE_TODAY,
        ),
        Question(
            "step_free",
            "yes_no",
            t(
                "Heeft u een woning nodig zonder trap, of met een lift?",
                "Do you need a home without stairs, or with a lift?",
            ),
            t(
                "Dan zoeken we woningen die goed bereikbaar zijn voor u.",
                "Then we look for homes that are easy for you to get into.",
            ),
        ),
        Question(
            "anything_else",
            "long_text",
            t(
                "Wilt u ons nog iets vertellen?",
                "Is there anything else you want to tell us?",
            ),
            t(
                "Hier kunt u kwijt wat u belangrijk vindt voor uw aanvraag.",
                "Room for anything you feel matters for your application.",
            ),
        ),
    ),
)


SCHOOL_ENROLMENT = BilingualTemplate(
    key="school_enrolment",
    retention_days=365,
    title=t("Aanmelding voor school", "School enrolment"),
    description=t(
        "Meld uw kind aan bij onze school. Het invullen duurt ongeveer 5 minuten.",
        "Enrol your child at our school. It takes about 5 minutes.",
    ),
    welcome=t(
        "Met dit formulier meldt u uw kind aan bij onze school. Het invullen "
        "duurt ongeveer 5 minuten. We vragen nu alleen wat we nodig hebben "
        "voor een eerste gesprek. De rest bespreken we samen met u.",
        "Use this form to enrol your child at our school. It takes about 5 "
        "minutes. For now we only ask what we need for a first conversation. "
        "We'll go through the rest together with you.",
    ),
    ending_title=t("Bedankt voor uw aanmelding", "Thank you for enrolling your child"),
    ending_message=t(
        "We hebben de aanmelding van uw kind ontvangen. We nemen contact met u "
        "op om een eerste gesprek te plannen.",
        "We have received your child's enrolment. We'll contact you to plan a "
        "first conversation.",
    ),
    questions=(
        Question(
            "child_name",
            "short_text",
            t("Wat is de naam van uw kind?", "What is your child's name?"),
            t("Zo weten we wie u aanmeldt.", "So we know who you are enrolling."),
            required=True,
        ),
        Question(
            "child_birth_date",
            "date",
            t(
                "Wat is de geboortedatum van uw kind?",
                "What is your child's date of birth?",
            ),
            t(
                "Daarmee zien we in welke groep of klas uw kind past.",
                "It tells us which year group your child fits into.",
            ),
            required=True,
            date_rules=BEFORE_TODAY,
        ),
        Question(
            "start_date",
            "date",
            t(
                "Vanaf wanneer wilt u dat uw kind bij ons op school komt?",
                "When would you like your child to start at our school?",
            ),
            t(
                "Zo kunnen we op tijd een plek voor uw kind regelen.",
                "So we can arrange a place for your child in time.",
            ),
            date_rules=NOT_BEFORE_TODAY,
        ),
        Question(
            "other_school",
            "yes_no",
            t(
                "Gaat uw kind nu naar een andere school?",
                "Does your child go to another school now?",
            ),
            t(
                "Dan kunnen we de overstap goed voorbereiden.",
                "Then we can prepare the move well.",
            ),
            jumps=(skip_unless_yes("other_school", "needs_support"),),
        ),
        Question(
            "other_school_name",
            "short_text",
            t(
                "Naar welke school gaat uw kind nu?",
                "Which school does your child go to now?",
            ),
            t(
                "We overleggen eerst met u voordat we contact opnemen met die school.",
                "We'll talk to you first before we contact that school.",
            ),
        ),
        Question(
            "needs_support",
            "yes_no",
            t(
                "Heeft uw kind extra hulp nodig bij het leren of op school?",
                "Does your child need extra help with learning or at school?",
            ),
            t(
                "Zo kunnen we op tijd met u bespreken wat uw kind nodig heeft.",
                "So we can talk with you in good time about what your child needs.",
            ),
            jumps=(skip_unless_yes("needs_support", "parent_name"),),
        ),
        Question(
            "support_details",
            "long_text",
            t(
                "Wat voor hulp heeft uw kind nodig?",
                "What kind of help does your child need?",
            ),
            t(
                "Een korte beschrijving is genoeg. We bespreken het daarna samen met u.",
                "A short description is enough. We'll talk it through with you afterwards.",
            ),
        ),
        Question(
            "parent_name",
            "short_text",
            t("Wat is uw naam?", "What is your name?"),
            t(
                "Zo weten we wie de aanmelding doet.",
                "So we know who is making the enrolment.",
            ),
            required=True,
        ),
        Question(
            "email",
            "email",
            t("Wat is uw e-mailadres?", "What is your email address?"),
            t(
                "We sturen u hier bericht over de aanmelding en het eerste gesprek.",
                "We'll send you news about the enrolment and the first conversation here.",
            ),
            required=True,
        ),
        Question(
            "phone",
            "phone_number",
            t(
                "Op welk telefoonnummer kunnen we u bellen?",
                "Which phone number can we call you on?",
            ),
            t(
                "Voor als we snel iets met u willen overleggen. Dit hoeft u niet "
                "in te vullen.",
                "In case we need to check something with you quickly. You can "
                "leave this empty.",
            ),
        ),
        Question(
            "about_child",
            "long_text",
            t(
                "Wilt u ons nog iets vertellen over uw kind?",
                "Is there anything else you'd like to tell us about your child?",
            ),
            t(
                "Bijvoorbeeld wat uw kind leuk vindt of moeilijk vindt. Zo leren "
                "we uw kind alvast een beetje kennen.",
                "For example what your child enjoys or finds hard. It helps us "
                "get to know your child a little.",
            ),
        ),
    ),
)


ORGANISATION_REQUEST = BilingualTemplate(
    key="organisation_request",
    retention_days=90,
    title=t("Verzoek aan onze organisatie", "Request to our organisation"),
    description=t(
        "Stel ons een vraag of doe een verzoek. Het invullen duurt ongeveer 3 minuten.",
        "Ask us a question or make a request. It takes about 3 minutes.",
    ),
    welcome=t(
        "Heeft u een vraag of een verzoek voor onze organisatie? Met dit "
        "formulier komt het bij de juiste persoon. Het invullen duurt ongeveer "
        "3 minuten. U kiest zelf hoe we u antwoord geven: per e-mail of per "
        "telefoon.",
        "Do you have a question or request for our organisation? This form "
        "gets it to the right person. It takes about 3 minutes. You choose how "
        "we reply: by email or by phone.",
    ),
    ending_title=t(
        "Bedankt, we hebben uw bericht ontvangen",
        "Thank you, we have received your message",
    ),
    ending_message=t(
        "We nemen contact met u op zoals u heeft gekozen.",
        "We'll get back to you the way you chose.",
    ),
    questions=(
        Question(
            "topic",
            "multiple_choice",
            t("Waar gaat uw bericht over?", "What is your message about?"),
            t(
                "Zo komt uw bericht bij de juiste persoon.",
                "So your message reaches the right person.",
            ),
            required=True,
            choices=(
                t("Een vraag", "A question"),
                t("Een verzoek om hulp", "A request for help"),
                t("Een idee of suggestie", "An idea or suggestion"),
                t("Een klacht", "A complaint"),
                t("Iets anders", "Something else"),
            ),
        ),
        Question(
            "message",
            "long_text",
            t(
                "Wat wilt u ons vragen of laten weten?",
                "What would you like to ask or tell us?",
            ),
            t(
                "Hoe duidelijker u het beschrijft, hoe beter we u kunnen helpen.",
                "The more clearly you describe it, the better we can help.",
            ),
            required=True,
        ),
        Question(
            "place",
            "short_text",
            t(
                "Over welke plek gaat uw verzoek?",
                "Which place is your request about?",
            ),
            t(
                "Vul dit alleen in als het over een plek gaat, zoals een straat "
                "of een gebouw. Dan weten we waar we moeten kijken.",
                "Only fill this in if it's about a place, such as a street or a "
                "building. Then we know where to look.",
            ),
        ),
        Question(
            "name",
            "short_text",
            t("Wat is uw naam?", "What is your name?"),
            t(
                "Zo weten we met wie we contact hebben.",
                "So we know who we are in touch with.",
            ),
            required=True,
        ),
        Question(
            "call_me",
            "yes_no",
            t(
                "Mogen we u bellen in plaats van te mailen?",
                "May we phone you instead of emailing you?",
            ),
            t(
                "Daarna vragen we alleen naar het telefoonnummer of het "
                "e-mailadres dat we nodig hebben.",
                "Next we only ask for the phone number or the email address we need.",
            ),
            jumps=(Jump("call_me", YES, "phone"),),
        ),
        Question(
            "email",
            "email",
            t("Wat is uw e-mailadres?", "What is your email address?"),
            t(
                "We gebruiken het alleen om u te antwoorden.",
                "We only use it to reply to you.",
            ),
            required=True,
            jumps=(skip_unless_yes("call_me", SUBMIT),),
        ),
        Question(
            "phone",
            "phone_number",
            t(
                "Op welk telefoonnummer kunnen we u bellen?",
                "Which phone number can we call you on?",
            ),
            t(
                "We gebruiken het alleen om u te antwoorden.",
                "We only use it to reply to you.",
            ),
            required=True,
        ),
    ),
)


NEW_COLLEAGUE = BilingualTemplate(
    key="new_colleague",
    retention_days=90,
    title=t("Welkom als nieuwe collega", "Welcome, new colleague"),
    description=t(
        "Geef je gegevens door voor je eerste werkdag. Het invullen duurt "
        "ongeveer 5 minuten.",
        "Share your details before your first working day. It takes about 5 minutes.",
    ),
    welcome=t(
        "Fijn dat je bij ons komt werken! Met dit formulier geef je door wat we "
        "nodig hebben voor je contract, je salaris en je eerste werkdag. Het "
        "invullen duurt ongeveer 5 minuten. Je identiteitsbewijs regelen we "
        "niet via dit formulier, maar persoonlijk met je.",
        "Great that you're joining us! Use this form to share what we need for "
        "your contract, your pay and your first working day. It takes about 5 "
        "minutes. We don't handle your identity document through this form; "
        "we'll arrange that with you in person.",
    ),
    ending_title=t("Bedankt, en alvast welkom!", "Thank you, and welcome!"),
    ending_message=t(
        "We hebben je gegevens ontvangen. Je hoort van ons voor je eerste werkdag.",
        "We have received your details. You'll hear from us before your first "
        "working day.",
    ),
    questions=(
        Question(
            "call_name",
            "short_text",
            t("Hoe wil je dat we je noemen?", "What would you like us to call you?"),
            t(
                "Zo spreken we je aan zoals jij dat wilt, bijvoorbeeld in e-mails "
                "en op je eerste dag.",
                "So we address you the way you like, for example in emails and on "
                "your first day.",
            ),
        ),
        Question(
            "legal_name",
            "short_text",
            t(
                "Wat is je volledige naam, zoals op je identiteitsbewijs?",
                "What is your full name, as shown on your identity document?",
            ),
            t(
                "Die naam hebben we nodig voor je contract en je salaris.",
                "We need this name for your contract and your pay.",
            ),
            required=True,
        ),
        Question(
            "email",
            "email",
            t(
                "Op welk e-mailadres kunnen we je bereiken tot je begint?",
                "Which email address can we reach you at until you start?",
            ),
            t(
                "Hier sturen we informatie over je eerste werkdag naartoe, tot je "
                "een e-mailadres van het werk hebt.",
                "We'll send information about your first day there, until you "
                "have a work email address.",
            ),
            required=True,
        ),
        Question(
            "phone",
            "phone_number",
            t("Wat is je telefoonnummer?", "What is your phone number?"),
            t(
                "Zo kan je leidinggevende je bellen als er voor je eerste dag "
                "iets verandert.",
                "So your manager can call you if something changes before your "
                "first day.",
            ),
        ),
        Question(
            "birth_date",
            "date",
            t("Wat is je geboortedatum?", "What is your date of birth?"),
            t(
                "Die hebben we nodig voor de salarisadministratie.",
                "We need it for payroll.",
            ),
            required=True,
            date_rules=BEFORE_TODAY,
        ),
        Question(
            "address",
            "short_text",
            t("Wat is je woonadres?", "What is your home address?"),
            t(
                "Dit adres komt op je contract en op je loonstrook.",
                "This address goes on your contract and your payslip.",
            ),
            required=True,
        ),
        Question(
            "iban",
            "short_text",
            t(
                "Op welk rekeningnummer (IBAN) wil je je salaris ontvangen?",
                "Which bank account (IBAN) should we pay your salary into?",
            ),
            t(
                "Op dit rekeningnummer maken we je salaris over.",
                "That's the account we transfer your pay to.",
            ),
            required=True,
        ),
        Question(
            "emergency_contact",
            "yes_no",
            t(
                "Wil je iemand opgeven die we kunnen bellen in een noodgeval?",
                "Would you like to give us someone to call in an emergency?",
            ),
            t(
                "Dit is niet verplicht. Vraag die persoon eerst of dat goed is.",
                "This is optional. Ask that person first if that's OK.",
            ),
            jumps=(skip_unless_yes("emergency_contact", "work_needs"),),
        ),
        Question(
            "emergency_name",
            "short_text",
            t("Wat is de naam van die persoon?", "What is that person's name?"),
            t(
                "Zo weten we naar wie we vragen als we bellen.",
                "So we know who to ask for when we call.",
            ),
        ),
        Question(
            "emergency_phone",
            "phone_number",
            t(
                "Op welk telefoonnummer is die persoon bereikbaar?",
                "Which phone number can we reach that person on?",
            ),
            t(
                "We bellen dit nummer alleen in een noodgeval.",
                "We only call this number in an emergency.",
            ),
        ),
        Question(
            "work_needs",
            "long_text",
            t(
                "Heb je iets nodig om goed te kunnen werken?",
                "Is there anything you need to work well?",
            ),
            t(
                "Bijvoorbeeld een aangepaste werkplek of een hulpmiddel. Dan "
                "kunnen we het op tijd regelen.",
                "For example an adapted workspace or an aid. Then we can arrange "
                "it in time.",
            ),
        ),
        Question(
            "first_day_questions",
            "long_text",
            t(
                "Heb je nog vragen over je eerste werkdag?",
                "Do you have any questions about your first working day?",
            ),
            t(
                "Dan zorgen we dat je antwoord hebt voordat je begint.",
                "Then we'll make sure you have an answer before you start.",
            ),
        ),
    ),
)


EVENT_REGISTRATION = BilingualTemplate(
    key="event_registration",
    retention_days=180,
    title=t("Aanmelden voor een evenement", "Event registration"),
    description=t(
        "Meld je aan voor ons evenement. Het invullen duurt ongeveer 2 minuten.",
        "Sign up for our event. It takes about 2 minutes.",
    ),
    welcome=t(
        "Leuk dat je erbij wilt zijn! Met dit formulier meld je je aan. Het "
        "invullen duurt ongeveer 2 minuten.",
        "Great that you'd like to come! Use this form to sign up. It takes "
        "about 2 minutes.",
    ),
    ending_title=t("Bedankt voor je aanmelding", "Thank you for signing up"),
    ending_message=t(
        "We hebben je aanmelding ontvangen. Voor het evenement sturen we je "
        "praktische informatie per e-mail.",
        "We have received your registration. Before the event we'll email you "
        "practical information.",
    ),
    questions=(
        Question(
            "name",
            "short_text",
            t("Wat is je naam?", "What is your name?"),
            t("Zo weten we wie er komt.", "So we know who is coming."),
            required=True,
        ),
        Question(
            "email",
            "email",
            t("Wat is je e-mailadres?", "What is your email address?"),
            t(
                "Hier sturen we praktische informatie over het evenement naartoe.",
                "We'll send practical information about the event here.",
            ),
            required=True,
        ),
        Question(
            "party_size",
            "number",
            t(
                "Met hoeveel personen kom je? Tel jezelf ook mee.",
                "How many people are coming, including you?",
            ),
            t(
                "Zo weten we hoeveel plekken we moeten regelen.",
                "So we know how many places to arrange.",
            ),
            required=True,
            validations={"min_value": 1, "max_value": 10},
        ),
        Question(
            "food",
            "yes_no",
            t(
                "Heb je wensen voor eten of drinken?",
                "Do you have any food or drink requirements?",
            ),
            t(
                "Bijvoorbeeld als je vegetarisch eet of een allergie hebt.",
                "For example if you're vegetarian or have an allergy.",
            ),
            jumps=(skip_unless_yes("food", "access"),),
        ),
        Question(
            "food_details",
            "long_text",
            t(
                "Waar moeten we rekening mee houden bij eten en drinken?",
                "What should we keep in mind for food and drink?",
            ),
            t(
                "We geven dit alleen door aan wie het eten verzorgt.",
                "We only share this with whoever provides the food.",
            ),
        ),
        Question(
            "access",
            "yes_no",
            t(
                "Heb je iets nodig om goed mee te kunnen doen?",
                "Do you need anything to take part fully?",
            ),
            t(
                "Bijvoorbeeld een plek voor een rolstoel, een tolk of een rustige ruimte.",
                "For example space for a wheelchair, an interpreter or a quiet room.",
            ),
            jumps=(skip_unless_yes("access", "photos"),),
        ),
        Question(
            "access_details",
            "long_text",
            t("Wat kunnen we voor je regelen?", "What can we arrange for you?"),
            t(
                "Dan kunnen we het van tevoren regelen.",
                "Then we can arrange it beforehand.",
            ),
        ),
        Question(
            "photos",
            "yes_no",
            t(
                "Mogen we foto's gebruiken waarop jij goed te zien bent?",
                "May we use photos in which you can be clearly recognised?",
            ),
            t(
                "Je aanmelding hangt hier niet van af. Zeg je geen ja, dan "
                "gebruiken we geen foto's waarop jij goed te zien bent.",
                "Your registration doesn't depend on this. Unless you say yes, we "
                "won't use photos in which you can be clearly recognised.",
            ),
        ),
    ),
)


BILINGUAL_TEMPLATES = (
    HOUSING_APPLICATION,
    SCHOOL_ENROLMENT,
    ORGANISATION_REQUEST,
    NEW_COLLEAGUE,
    EVENT_REGISTRATION,
)


def _id() -> str:
    return str(uuid.uuid4())


def build_template(template: BilingualTemplate, lang: str) -> dict:
    """``template`` in ``lang`` as the seed's payload: one page per question,
    fresh ids, and the page jumps pointing at the pages they name."""
    by_key = {q.key: q for q in template.questions}
    for question in template.questions:
        for jump in question.jumps:
            if by_key[jump.source].type != "yes_no" or jump.value not in (YES, NO):
                raise ValueError(f"{template.key}.{question.key}: jumps on yes/no only")
    field_ids = {q.key: _id() for q in template.questions}
    page_ids = {q.key: _id() for q in template.questions}
    pages = []
    for question in template.questions:
        props: dict = {"why_we_ask": question.why[lang]}
        if question.type == "yes_no":
            # Same choices the builder creates; shown in the form's language.
            props["choices"] = [{"id": _id(), "value": YES}, {"id": _id(), "value": NO}]
        elif question.choices:
            props["choices"] = [
                {"id": _id(), "value": c[lang]} for c in question.choices
            ]
        if question.date_rules:
            props["date_rules"] = [dict(rule) for rule in question.date_rules]
        field_ = {
            "id": field_ids[question.key],
            "index": 0,
            "type": question.type,
            "title": question.title[lang],
            "properties": props,
        }
        validations = dict(question.validations)
        if question.required:
            validations["required"] = True
        if validations:
            field_["validations"] = validations
        page = {
            "id": page_ids[question.key],
            "index": 0,
            "type": "slide",
            "properties": {"layout": LAYOUT, "fields": [field_]},
        }
        if question.jumps:
            page["properties"]["jumps"] = [
                {
                    "operator": "AND",
                    "conditions": [
                        {
                            "field_id": field_ids[jump.source],
                            "field_type": "yes_no",
                            "comparison": "IS_EQUAL" if jump.equal else "IS_NOT_EQUAL",
                            "value": jump.value,
                        }
                    ],
                    "target": SUBMIT if jump.to == SUBMIT else page_ids[jump.to],
                }
                for jump in question.jumps
            ]
        pages.append(page)
    return {
        "title": template.title[lang],
        "description": template.description[lang],
        "category": None,
        "language": lang,
        "response_expiration_type": "days",
        "response_expiration": str(template.retention_days),
        "fields": pages,
        "welcome_page": {
            "title": template.title[lang],
            "description": template.welcome[lang],
            "layout": LAYOUT,
            "buttonText": template.start[lang],
        },
        "thankyou_page": [
            {
                "layout": LAYOUT,
                "title": template.ending_title[lang],
                "message": template.ending_message[lang],
            }
        ],
    }


def _builder(template: BilingualTemplate, lang: str):
    def build() -> dict:
        return build_template(template, lang)

    build.__name__ = f"{template.key}_{lang}"
    build.__qualname__ = build.__name__
    return build


# Zero-arg builders, as TEMPLATE_BUILDERS expects. The gallery lists the
# newest template first, so each English twin is seeded just before its
# Dutch original: on a fresh install the Dutch one comes first.
BILINGUAL_BUILDERS: Tuple = tuple(
    _builder(template, lang)
    for template in BILINGUAL_TEMPLATES
    for lang in ("en", "nl")
)
