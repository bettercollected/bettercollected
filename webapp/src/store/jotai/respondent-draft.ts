import { atom, useAtom } from 'jotai';

/**
 * What this browser knows about the respondent's saved draft (utils/form-drafts.ts,
 * components/drafts). Kept in memory only: the edit key is a credential and
 * the address is not kept anywhere once the link is sent.
 */
export interface RespondentDraft {
    /** An anonymous draft's edit key (the page saves with it, and sends it with the submit). */
    editKey?: string;
    /** The address the link went to, for the status line only. */
    email?: string;
    expiresAt?: string;
    /** What the status line says. */
    status: 'none' | 'saved_account' | 'link_sent' | 'resumed' | 'changes_saved' | 'deleted';
}

const NONE: RespondentDraft = { status: 'none' };

// The form the state belongs to: one respondent session can move from one form
// to another without a reload, and form B must never see form A's key or note.
const respondentDraftAtom = atom<RespondentDraft & { formId?: string }>(NONE);

/**
 * The draft state of `formId`. Another form's state reads as none, and what is
 * set is stamped with `formId`, so a key never crosses from one form to another.
 */
export const useRespondentDraft = (formId?: string) => {
    const [stored, setStored] = useAtom(respondentDraftAtom);
    const draft: RespondentDraft = !formId || stored.formId === formId ? stored : NONE;
    return {
        draft,
        setDraft: (next: RespondentDraft) => setStored({ ...next, formId }),
        resetDraft: () => setStored(NONE)
    };
};
