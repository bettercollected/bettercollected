import { useGetProvidersQuery } from '@app/store/redux/import-api';

import type { FormProviderDto } from './use-google-forms-import-mode';

export const OPEN_FORMULIEREN_PROVIDER = 'open_formulieren';

/**
 * Whether the instance offers the Open Formulieren import
 * (OPEN_FORMULIEREN_IMPORT=on): `GET /providers` then holds an entry
 * `{ providerName: "open_formulieren", importMode: "on" }`. No entry, an
 * unknown mode, or a list that could not be read all mean off: the import is
 * never offered on a guess.
 */
export function openFormulierenImportOn(providers: ReadonlyArray<FormProviderDto> | undefined | null): boolean {
    if (!Array.isArray(providers)) return false;
    return providers.some((provider) => provider?.providerName === OPEN_FORMULIEREN_PROVIDER && provider?.importMode === 'on');
}

export function useOpenFormulierenImportOn(): { on: boolean; isLoading: boolean } {
    const { data, isLoading } = useGetProvidersQuery();
    return { on: openFormulierenImportOn(data), isLoading };
}
