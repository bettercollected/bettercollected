import { StandardFormDto } from '@app/models/dtos/form';

type FormSettings = StandardFormDto['settings'];
type Translate = (key: string, options?: Record<string, unknown>) => string;

/** Upper bound of a "days" retention (backend services/retention.py). */
export const MAX_RETENTION_DAYS = 3650;

/** A valid number of retention days (1..MAX_RETENTION_DAYS), or null. */
export function retentionDays(value: unknown): number | null {
    const text = String(value ?? '').trim();
    if (!/^\d{1,4}$/.test(text)) return null;
    const days = Number(text);
    return days > 0 && days <= MAX_RETENTION_DAYS ? days : null;
}

/** The YYYY-MM-DD day a "date" retention ends on, or null. */
export function retentionDate(value: unknown): string | null {
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value ?? '').trim());
    if (!match) return null;
    const [year, month, day] = match.slice(1).map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
    return match[0];
}

/**
 * How long a form keeps answers, in plain words for respondents: always the
 * enforced period.
 *
 * It is read from the form's retention setting with the backend's rules
 * (services/retention.py, which applies that period to every submission), so
 * the stated period is the one that is applied. Without a readable period
 * nothing is invented: answers are kept until deleted. The creator's own
 * wording never replaces it (see `retentionExplanation`).
 */
export function describeRetention(settings: FormSettings | undefined, t: Translate, language: string): string {
    if (settings?.responseExpirationType === 'days') {
        const days = retentionDays(settings.responseExpiration);
        if (days) return t('RETENTION.DAYS', { count: days });
    }
    if (settings?.responseExpirationType === 'date') {
        const day = retentionDate(settings.responseExpiration);
        if (day) {
            const date = new Intl.DateTimeFormat(language === 'nl' ? 'nl-NL' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${day}T00:00:00Z`));
            return t('RETENTION.UNTIL_DATE', { date });
        }
    }
    return t('RETENTION.UNTIL_DELETED');
}

/**
 * The creator's explanation of the retention period (`retentionText`, e.g.
 * "until the project ends"), shown next to the enforced period and never
 * instead of it; null when there is none.
 */
export function retentionExplanation(settings: Partial<NonNullable<FormSettings>> | undefined): string | null {
    return settings?.retentionText?.trim() || null;
}
