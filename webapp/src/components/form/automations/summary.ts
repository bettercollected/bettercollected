/**
 * What an automation card says about itself, from data the page already loads.
 * Pure functions: the text comes from the card, which owns the translations.
 */

export type ChipKind = 'on' | 'off' | 'not-sent' | 'not-set-up' | 'unavailable' | 'reconnect';
export interface Chip {
    kind: ChipKind;
    /** Only for `not-sent`: how many deliveries did not go out. */
    count?: number;
}

export interface ListStats {
    total: number;
    on: number;
    /** Hosts or names of the entries that are on, in list order. */
    labels: string[];
}

export function listStats<T>(items: T[] | undefined, isOn: (item: T) => boolean, label: (item: T) => string | undefined): ListStats {
    const list = items ?? [];
    const on = list.filter(isOn);
    return { total: list.length, on: on.length, labels: on.map(label).filter((value): value is string => !!value) };
}

/** `a.example, b.example +2`: at most two names, the rest as a count. */
export function shortList(labels: string[], max = 2): string {
    const shown = labels.slice(0, max).join(', ');
    return labels.length > max ? `${shown} +${labels.length - max}` : shown;
}

/**
 * The chip of a card. Text always (never colour alone). Nothing set up reads
 * so; then a connection that must be renewed and deliveries that did not go
 * out (both need a person); then on/off.
 * `unavailable`: the server cannot send this kind at all (no mail server).
 */
export function chipFor({ configured, on, failed, unavailable = false, reconnect = false }: { configured: boolean; on: boolean; failed?: number; unavailable?: boolean; reconnect?: boolean }): Chip {
    if (!configured) return { kind: 'not-set-up' };
    if (reconnect) return { kind: 'reconnect' };
    if (failed && failed > 0) return { kind: 'not-sent', count: failed };
    if (unavailable) return { kind: 'unavailable' };
    return { kind: on ? 'on' : 'off' };
}

/** The number of failed deliveries, or undefined when it is unknown (loading, or the member may not read the log). */
export function failedCount(page: { total?: number } | undefined, error: unknown): number | undefined {
    if ((error as { status?: number } | undefined)?.status === 403) return undefined;
    return page?.total;
}
