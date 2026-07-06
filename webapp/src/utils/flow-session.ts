import { v4 } from 'uuid';

/**
 * Anonymous flow-analytics session ids: one random uuid per form per page
 * load. Nothing about the responder is stored or derivable from it — it only
 * lets the backend group navigation steps into "one attempt" for drop-off
 * aggregation. Not persisted anywhere client-side either: a reload is simply
 * a new attempt.
 */
const sessions = new Map<string, string>();

export function getFlowSessionId(formId: string): string {
    let id = sessions.get(formId);
    if (!id) {
        id = v4();
        sessions.set(formId, id);
    }
    return id;
}

/** Test hook / future "restart" support. */
export function resetFlowSession(formId: string): void {
    sessions.delete(formId);
}
