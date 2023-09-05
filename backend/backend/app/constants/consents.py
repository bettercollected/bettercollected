from common.models.consent import Consent, ConsentType, ConsentCategory, ConsentResponse

default_consents = [Consent(consent_id='default_form_purpose', title='Data Collection',
                            description='We gather data from the responses you provide in our forms.',
                            required=True, type=ConsentType.CHECKBOX,
                            category=ConsentCategory.PURPOSE_OF_THE_FORM),
                    Consent(consent_id='responder_rights', title='Responder Right',
                            required=True, type=ConsentType.INFO,
                            category=ConsentCategory.RESPONDERS_RIGHTS)]

default_consent_responses = [
    ConsentResponse(consent_id='default_form_purpose', title='Data Collection',
                    description='We gather data from the responses you provide in our forms.',
                    required=True, type=ConsentType.CHECKBOX,
                    category=ConsentCategory.PURPOSE_OF_THE_FORM, accepted=True),
    ConsentResponse(consent_id='responder_rights', title='Responder Right',
                    required=True, type=ConsentType.INFO,
                    category=ConsentCategory.RESPONDERS_RIGHTS)
]
