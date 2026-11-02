import i18n, { TFunction } from 'i18next';

import { Action } from '@app/models/dtos/actions';

/**
 * What an integration does, in the dashboard's language. The action catalog's own text is English, so the
 * integrations we know by name have a translated line; any other (and any not yet translated) keeps the catalog's.
 */
export function actionDescription(t: TFunction, integration: Pick<Action, 'name' | 'description'>): string | undefined {
    const key = `STAFF.FORM_SETTINGS.ACTION_DESCRIPTIONS.${integration.name}`;
    return /^[a-z0-9_]+$/.test(integration.name ?? '') && i18n.exists(key) ? t(key) : integration.description;
}
