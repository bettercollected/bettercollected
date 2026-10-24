import { atom, useAtom } from 'jotai';
import { selectAtom } from 'jotai/utils';

import { FormSlideLayout } from '@app/models/enums/form';
import { withEndingIds } from '@app/utils/endings';
import { deepCopy } from '@app/utils/object-utils';

import { useActiveThankYouPageComponent } from './active-builder-component';
import { IFormState, IThemeState } from './form-defaults';
import { CommitMeta, FORM_STATE_KEYS, FormDocument, FormStateKey, commitFormKeysAtom, formDocAtom } from './form-document';

export type { IFormState, IThemeState } from './form-defaults';
export { initialFormState } from './form-defaults';

type FormStateUpdate = IFormState | ((prev: IFormState) => IFormState);

const pickFormState = (doc: FormDocument): IFormState => {
    const state: Record<string, unknown> = {};
    for (const key of FORM_STATE_KEYS) if ((doc as unknown as Record<string, unknown>)[key] !== undefined) state[key] = (doc as unknown as Record<string, unknown>)[key];
    return state as unknown as IFormState;
};
const sameFormState = (a: IFormState, b: IFormState) => FORM_STATE_KEYS.every((key) => (a as unknown as Record<string, unknown>)[key] === (b as unknown as Record<string, unknown>)[key]);
const formSectionsAtom = selectAtom(formDocAtom, pickFormState, sameFormState);

/**
 * The form-level part of the builder's document (title, welcome and ending
 * pages, theme, hidden fields, logo settings): a view of the form document
 * (form-document.ts). A write becomes ops on the document — one undo step,
 * merged with the previous one while typing under the same coalesce key (or
 * none, with `{ undoable: false }`).
 * Keys the written state leaves out are removed, as before.
 */
export const formStateAtom = atom(
    (get) => get(formSectionsAtom),
    (get, set, update: FormStateUpdate, meta?: string | CommitMeta) => {
        const next = typeof update === 'function' ? update(get(formSectionsAtom)) : update;
        const values: Partial<Record<FormStateKey, unknown>> = {};
        for (const key of FORM_STATE_KEYS) values[key] = (next as unknown as Record<string, unknown>)?.[key];
        set(commitFormKeysAtom, values, typeof meta === 'string' ? { coalesceKey: meta } : (meta ?? {}));
    }
);

/**
 * The editor state with every form-level part of a server form copied in:
 * title, description, welcome and ending pages, theme, hidden fields and the
 * logo settings. Used when a whole form comes back from the server mid-edit
 * (an AI turn, a review fix), because autosave PATCHes the whole form from
 * this state — anything not copied here is written back over the server's
 * change. Parts the server form leaves out keep their current value; each
 * copy is deep, so the editor never shares objects with Redux or the response.
 */
export function formStateFromServerForm(prev: IFormState, form: any): IFormState {
    if (!form) return prev;
    const take = <K extends keyof IFormState>(key: K, value: any): IFormState[K] => (value === undefined || value === null ? prev[key] : deepCopy(value));
    return {
        ...prev,
        title: take('title', form.title),
        // null is a real value here: the AI may clear the description.
        description: form.description === undefined ? prev.description : form.description,
        welcomePage: take('welcomePage', form.welcomePage),
        thankyouPage: form.thankyouPage === undefined || form.thankyouPage === null ? prev.thankyouPage : withEndingIds(deepCopy(form.thankyouPage)),
        theme: take('theme', form.theme),
        hiddenFields: take('hiddenFields', form.hiddenFields),
        logoPosition: take('logoPosition', form.logoPosition),
        logoAlt: take('logoAlt', form.logoAlt),
        useWorkspaceLogo: take('useWorkspaceLogo', form.useWorkspaceLogo)
    };
}

/** Immutable update of one thank-you page entry against the CURRENT state. */
function patchThankYouPage(prev: IFormState, index: number, patch: Partial<NonNullable<IFormState['thankyouPage']>[number]>): IFormState {
    const thankyouPage = (prev.thankyouPage ?? []).map((page, i) => (i === index ? { ...page, ...patch } : page));
    return { ...prev, thankyouPage };
}

export function useFormState() {
    // Every setter below uses the FUNCTIONAL form. Several components fire
    // these from mount effects (FormDispatcher sets the theme, WelcomeSlide
    // the description, the editor page seeds the loaded form) — spreading the
    // render-time `formState` closure instead of `prev` let whichever effect
    // ran last resurrect stale state and silently drop the others' writes.
    // The second argument names the text being typed, so that typing is one
    // undo step.
    const [formState, setFormState] = useAtom(formStateAtom);
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();

    // The welcome page shows the form's title: renaming the form titles it
    // too (as update_form_info does), in the same undo step.
    const setFormTitle = (title: string) => {
        setFormState((prev) => ({ ...prev, title, ...(prev?.welcomePage ? { welcomePage: { ...prev.welcomePage, title } } : {}) }), 'form:title');
    };

    /** `options.undoable` false: a default written on mount, not an edit (no undo step). */
    const setFormDescription = (description?: string, options: { undoable?: boolean } = {}) => {
        setFormState(
            (prev) => ({
                ...prev,
                welcomePage: {
                    ...(prev?.welcomePage || {}),
                    description: description
                }
            }),
            { coalesceKey: 'welcome:description', undoable: options.undoable }
        );
    };

    const setThankYouPageTitle = (thankyouPageIndex: number, title?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { title }), `ending:${thankyouPageIndex}:title`);
    };

    const setThankYouPageDescription = (thankyouPageIndex: number, description?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { message: description }), `ending:${thankyouPageIndex}:message`);
    };

    const setThankYouPageButtonText = (thankyouPageIndex: number, btnText?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { buttonText: btnText }), `ending:${thankyouPageIndex}:buttonText`);
    };

    const setThankYouPageButtonLink = (thankyouPageIndex: number, btnLink?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { buttonLink: btnLink }), `ending:${thankyouPageIndex}:buttonLink`);
    };

    const setWelcomePageButtonText = (btnText: string) => {
        setFormState(
            (prev) => ({
                ...prev,
                welcomePage: { ...prev.welcomePage, buttonText: btnText }
            }),
            'welcome:buttonText'
        );
    };

    /** `options.undoable` false: the loaded form's theme put in place, not an edit (no undo step). */
    const updateFormTheme = (theme: IThemeState, options: { undoable?: boolean } = {}) => {
        setFormState((prev) => ({ ...prev, theme }), { coalesceKey: 'form:theme', undoable: options.undoable });
    };

    const setHiddenFields = (hiddenFields: string[]) => {
        setFormState((prev) => ({ ...prev, hiddenFields }));
    };

    const setLogoSettings = (settings: Pick<IFormState, 'logoPosition' | 'logoAlt' | 'useWorkspaceLogo'>) => {
        setFormState((prev) => ({ ...prev, ...settings }), 'form:logo');
    };

    const updateWelcomePageImage = (imageUrl: string) => {
        setFormState((prev) => ({
            ...prev,
            welcomePage: { ...(prev.welcomePage || {}), imageUrl }
        }));
    };

    const updateWelcomePageLayout = (layout: FormSlideLayout) => {
        setFormState((prev) => ({
            ...prev,
            welcomePage: { ...(prev.welcomePage || {}), layout }
        }));
    };

    const updateThankYouPageImage = (imageUrl: string) => {
        setFormState((prev) => patchThankYouPage(prev, activeThankYouPageComponent?.index || 0, { imageUrl }));
    };

    const updateThankYouPageLayout = (layout: FormSlideLayout) => {
        setFormState((prev) => patchThankYouPage(prev, activeThankYouPageComponent?.index || 0, { layout }));
    };

    return {
        formState,
        setFormState,
        setFormDescription,
        setWelcomePageButtonText,
        setThankYouPageTitle,
        setThankYouPageDescription,
        setThankYouPageButtonText,
        setThankYouPageButtonLink,
        setFormTitle,
        updateFormTheme,
        setHiddenFields,
        setLogoSettings,
        theme: formState.theme,
        updateWelcomePageImage,
        updateThankYouPageImage,
        updateWelcomePageLayout,
        updateThankYouPageLayout
    };
}
