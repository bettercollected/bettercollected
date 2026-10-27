"""Registration of submissions in a workspace's case system (docs/open-formulieren-registration.md).

``mode``: the ``OPEN_FORMULIEREN_REGISTRATION`` switch. ``secrets``: the sealed
service secret. ``client``: the one outgoing call, through the safe-HTTP rules.
``body``: the Generic JSON body. ``service``: configuration, the hook on
submit and the delivery job's logic. Answers are decrypted only inside the
job and never reach job arguments, delivery records or logs.
"""
