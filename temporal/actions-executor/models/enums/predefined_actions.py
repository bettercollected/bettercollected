import enum


class PredefinedActions(str, enum.Enum):
    WEBHOOK = "send_webhook"
    RESPONDER_COPY = "responder_copy_mail"
    CREATOR_COPY = "creator_copy_mail"
    DISCORD="send_to_discord"
