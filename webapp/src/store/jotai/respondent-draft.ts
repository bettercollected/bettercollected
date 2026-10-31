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

const respondentDraftAtom = atom<RespondentDraft>({ status: 'none' });

export const useRespondentDraft = () => {
    const [draft, setDraft] = useAtom(respondentDraftAtom);
    return { draft, setDraft, resetDraft: () => setDraft({ status: 'none' }) };
};
