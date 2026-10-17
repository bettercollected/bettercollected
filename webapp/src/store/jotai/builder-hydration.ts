import { atom, useAtom } from 'jotai';

/**
 * The form whose loaded data the builder state now holds. Set by the editor
 * page once it has copied the loaded form into the builder atoms; until then
 * AutoSaveForm treats state changes as loading, not as edits.
 */
const builderHydratedFormIdAtom = atom<string | null>(null);

export function useBuilderHydration() {
    const [hydratedFormId, setHydratedFormId] = useAtom(builderHydratedFormIdAtom);
    return { hydratedFormId, setHydratedFormId };
}
