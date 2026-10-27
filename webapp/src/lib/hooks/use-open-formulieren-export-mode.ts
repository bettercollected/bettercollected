import { useGetProvidersQuery } from '@app/store/redux/import-api';

import type { FormProviderDto } from './use-google-forms-import-mode';

export const OPEN_FORMULIEREN_PROVIDER = 'open_formulieren';

/**
 * Whether the instance offers the Open Formulieren export
 * (OPEN_FORMULIEREN_EXPORT=on): `GET /providers` then holds an entry
 * `{ providerName: "open_formulieren", exportMode: "on" }` (beside an
 * `importMode` when the import is on too). No entry, an unknown mode, or a
 * list that could not be read all mean off: the download is never offered on
 * a guess.
 */
export function openFormulierenExportOn(providers: ReadonlyArray<(FormProviderDto & { exportMode?: string | null }) | undefined | null> | undefined | null): boolean {
    if (!Array.isArray(providers)) return false;
    return providers.some((provider) => provider?.providerName === OPEN_FORMULIEREN_PROVIDER && provider?.exportMode === 'on');
}

export function useOpenFormulierenExportOn(): { on: boolean; isLoading: boolean } {
    const { data, isLoading } = useGetProvidersQuery();
    return { on: openFormulierenExportOn(data), isLoading };
}
