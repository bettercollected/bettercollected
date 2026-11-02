/**
 * The side sheets of the Automations cards, named in the URL (`?panel=webhooks`)
 * so the Back button closes one and a link can open one. The value is only
 * ever read through `parsePanel`, which accepts a fixed set of names and one
 * pattern (an integration action's id, looked up in the loaded list before
 * anything opens); every other value is treated as "no panel".
 */

export type CardKind = 'email' | 'webhooks' | 'case-system';
export type Panel = { kind: CardKind; view: 'manage' | 'deliveries' } | { kind: 'action'; actionId: string; view: 'manage' };

export const PANEL_PARAM = 'panel';

const FIXED: Record<string, Panel> = {
    email: { kind: 'email', view: 'manage' },
    'email-deliveries': { kind: 'email', view: 'deliveries' },
    webhooks: { kind: 'webhooks', view: 'manage' },
    'webhooks-deliveries': { kind: 'webhooks', view: 'deliveries' },
    'case-system': { kind: 'case-system', view: 'manage' },
    'case-system-deliveries': { kind: 'case-system', view: 'deliveries' }
};

const ACTION_PREFIX = 'action-';
// Ids of integration actions are UUIDs; anything else is not a panel name.
const ACTION_ID = /^[A-Za-z0-9_-]{1,64}$/;

export function parsePanel(value: string | null | undefined): Panel | null {
    if (!value) return null;
    if (Object.prototype.hasOwnProperty.call(FIXED, value)) return FIXED[value];
    if (value.startsWith(ACTION_PREFIX)) {
        const actionId = value.slice(ACTION_PREFIX.length);
        if (ACTION_ID.test(actionId)) return { kind: 'action', actionId, view: 'manage' };
    }
    return null;
}

export function panelName(panel: Panel): string {
    if (panel.kind === 'action') return `${ACTION_PREFIX}${panel.actionId}`;
    return panel.view === 'deliveries' ? `${panel.kind}-deliveries` : panel.kind;
}

/** The query string with the `panel` value set (or removed), every other parameter kept. */
export function withPanel(search: string, panel: Panel | null): string {
    const params = new URLSearchParams(search);
    if (panel) params.set(PANEL_PARAM, panelName(panel));
    else params.delete(PANEL_PARAM);
    const next = params.toString();
    return next ? `?${next}` : '';
}
