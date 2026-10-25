import { useGetProvidersQuery } from '@app/store/redux/import-api';

/**
 * What the instance's Google Forms import switch (GOOGLE_FORMS_IMPORT, see
 * docs/RUNNING_INTEGRATIONS.md) allows:
 * - `on`: imports, re-syncs and connecting a Google account work;
 * - `readonly`: forms and responses imported earlier stay, nothing new comes
 *   from Google Forms (the backend answers 403 `google_forms_readonly`);
 * - `off`: Google Forms is not offered at all (410 `google_forms_off`).
 */
export type GoogleFormsImportMode = 'on' | 'readonly' | 'off';

export interface FormProviderDto {
    providerName: string;
    importMode?: string | null;
}

/**
 * The mode `GET /providers` reports: Google with its `importMode`, or no
 * Google at all when it is off (or the provider is not enabled). Undefined
 * while unknown (loading, or the list could not be read): callers then
 * behave as before and handle the backend's refusal instead.
 */
export function googleFormsImportMode(providers: ReadonlyArray<FormProviderDto> | undefined | null): GoogleFormsImportMode | undefined {
    if (!Array.isArray(providers)) return undefined;
    const google = providers.find((provider) => provider?.providerName === 'google');
    if (!google) return 'off';
    // no mode (an older backend): imports are on
    if (google.importMode === 'readonly' || google.importMode === 'off') return google.importMode;
    return 'on';
}

/** Whether a failed request was refused by the switch, and in which mode. */
export function googleFormsRefusal(error: unknown): Exclude<GoogleFormsImportMode, 'on'> | null {
    const { status, data } = (error ?? {}) as { status?: number; data?: { code?: string } };
    if (status === 403 && data?.code === 'google_forms_readonly') return 'readonly';
    if (status === 410 && data?.code === 'google_forms_off') return 'off';
    return null;
}

export function useGoogleFormsImportMode(): { mode: GoogleFormsImportMode | undefined; isLoading: boolean } {
    const { data, isLoading } = useGetProvidersQuery();
    return { mode: googleFormsImportMode(data), isLoading };
}
