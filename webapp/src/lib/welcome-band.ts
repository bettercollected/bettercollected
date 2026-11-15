/**
 * What the forms dashboard's welcome band says and offers, decided from what the
 * dashboard already has (the forms list and the workspace's pending deletion
 * requests): no new request. Pure, so the choice is tested without a screen.
 */

export type GreetingPeriod = 'morning' | 'afternoon' | 'evening';

/** Morning until 12:00, afternoon until 18:00, evening after. */
export function greetingPeriod(hour: number): GreetingPeriod {
    if (hour < 12) return 'morning';
    if (hour < 18) return 'afternoon';
    return 'evening';
}

export interface WelcomeInput {
    /** Forms in the workspace (the list's total); undefined while it loads. */
    formsTotal: number | undefined;
    /** Drafts among the forms the list has loaded, most recent first. */
    drafts: Array<{ formId: string; title?: string | null }>;
    /** Deletion requests still waiting for a decision; undefined when unknown or not the member's to see. */
    pendingRequests: number | undefined;
    canCreateForms: boolean;
    canReviewRequests: boolean;
}

export type WelcomeState = { kind: 'loading' } | { kind: 'no-forms' } | { kind: 'requests'; count: number } | { kind: 'draft'; formId: string; title: string; count: number } | { kind: 'ready' };

/**
 * One next step, in this order: the first form (nothing exists yet), what is waiting for the
 * person (deletion requests), a draft to finish, else nothing in particular. A step the
 * member's role cannot take is skipped, never offered as a dead end.
 */
export function welcomeState({ formsTotal, drafts, pendingRequests, canCreateForms, canReviewRequests }: WelcomeInput): WelcomeState {
    if (formsTotal === undefined) return { kind: 'loading' };
    if (formsTotal === 0 && canCreateForms) return { kind: 'no-forms' };
    if (canReviewRequests && (pendingRequests ?? 0) > 0) return { kind: 'requests', count: pendingRequests as number };
    if (drafts.length > 0) return { kind: 'draft', formId: drafts[0].formId, title: (drafts[0].title ?? '').trim(), count: drafts.length };
    return { kind: 'ready' };
}
