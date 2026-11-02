import { CalendarClock, LucideIcon, ShieldCheck, SlidersHorizontal, Sparkles, Workflow } from 'lucide-react';

import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

/** The pages of a form's Settings, in order. The key is also the address segment (`/settings/<key>`), English in every language. */
export const SETTINGS_PAGE_KEYS = ['access', 'availability', 'experience', 'automations', 'advanced'] as const;
export type SettingsPageKey = (typeof SETTINGS_PAGE_KEYS)[number];

export const SETTINGS_PAGE_LABELS: Record<SettingsPageKey, string> = {
    access: 'STAFF.FORM_SETTINGS.ACCESS',
    availability: 'STAFF.FORM_SETTINGS.AVAILABILITY',
    experience: 'STAFF.FORM_SETTINGS.EXPERIENCE',
    automations: 'STAFF.FORM_SETTINGS.AUTOMATIONS',
    advanced: 'STAFF.FORM_SETTINGS.ADVANCED'
};

export const SETTINGS_PAGE_ICONS: Record<SettingsPageKey, LucideIcon> = {
    access: ShieldCheck,
    availability: CalendarClock,
    experience: Sparkles,
    automations: Workflow,
    advanced: SlidersHorizontal
};

export const isSettingsPageKey = (value: unknown): value is SettingsPageKey => (SETTINGS_PAGE_KEYS as readonly unknown[]).includes(value);

/**
 * The Settings pages that have something to show for this form and this person. A page that would be empty is not
 * listed (a form imported from elsewhere has no Availability and no Automations: every setting there is for forms made
 * here), and a direct visit to one redirects to Access. Whether the person may open Settings at all (form.edit) is
 * decided by the caller.
 */
export function settingsPages(form: StandardFormDto | undefined, can: (permission: WorkspacePermission) => boolean): SettingsPageKey[] {
    const isSelf = form?.settings?.provider === 'self';
    // The builder is where purpose, retention and the privacy link are written (same rule as the header's Edit button).
    const canOpenBuilder = isSelf && form?.builderVersion === 'v2';
    const pages: SettingsPageKey[] = ['access'];
    if (isSelf) pages.push('availability');
    if (isSelf || form?.isPublished) pages.push('experience');
    if (isSelf) pages.push('automations');
    if (!!form?.importedFormId || canOpenBuilder || can(WorkspacePermission.FORM_DELETE)) pages.push('advanced');
    return pages;
}
