import { DeclineReason } from '@app/models/enums/deletion-request';

// Staff closing a deletion request: mark as deleted, or decline with a reason.
export const deletionRequestLocale = {
    markDeleted: 'DELETION_REQUEST.MARK_DELETED',
    decline: 'DELETION_REQUEST.DECLINE',
    markDeletedTitle: 'DELETION_REQUEST.MARK_DELETED_TITLE',
    markDeletedDescription: 'DELETION_REQUEST.MARK_DELETED_DESCRIPTION',
    declineTitle: 'DELETION_REQUEST.DECLINE_TITLE',
    declineDescription: 'DELETION_REQUEST.DECLINE_DESCRIPTION',
    reasonLabel: 'DELETION_REQUEST.REASON_LABEL',
    reasonRequired: 'DELETION_REQUEST.REASON_REQUIRED',
    reason: (code: DeclineReason) => `DELETION_REQUEST.REASON.${code.toUpperCase()}`,
    notDeleted: 'DELETION_REQUEST.NOT_DELETED',
    markedDeleted: 'DELETION_REQUEST.MARKED_DELETED',
    declined: 'DELETION_REQUEST.DECLINED',
    alreadyClosed: 'DELETION_REQUEST.ALREADY_CLOSED',
    copyUnresolved: 'DELETION_REQUEST.COPY_UNRESOLVED',
    failed: 'DELETION_REQUEST.FAILED'
};
