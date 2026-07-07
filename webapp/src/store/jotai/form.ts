import { atom, useAtom } from 'jotai';

import { ThemeColor } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';

import { useActiveThankYouPageComponent } from './active-builder-component';

export interface IFormState {
    title: string;
    description?: string | null;
    welcomePage?: {
        title?: string;
        description?: string;
        layout?: FormSlideLayout;
        imageUrl?: string;
        buttonText?: string;
    };
    thankyouPage?: Array<{
        title?: string;
        message?: string;
        buttonText?: string;
        buttonLink?: string;
        layout?: FormSlideLayout;
        imageUrl?: string;
    }>;
    theme?: {
        title: string;
        primary: string;
        secondary: string;
        tertiary: string;
        accent: string;
    };
    /**
     * Declared hidden-field (URL parameter) names, e.g. ['utm_source', 'name'].
     * Captured from the share link at fill time and stored with the response;
     * available to answer piping in question text.
     */
    hiddenFields?: string[];
}

export interface IThemeState {
    title: string;
    primary: string;
    secondary: string;
    tertiary: string;
    accent: string;
}


export const initialFormState: IFormState = {
    title: '',
    description: undefined,
    welcomePage: {
        title: '',
        layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
    },
    thankyouPage: [
        {
            layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
        }
    ],
    theme: {
        title: 'Default',
        primary: ThemeColor.primary,
        secondary: ThemeColor.secondary,
        tertiary: ThemeColor.tertiary,
        accent: ThemeColor.accent
    }
}
export const formStateAtom = atom<IFormState>(initialFormState);

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
    const [formState, setFormState] = useAtom(formStateAtom);
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();

    const setFormTitle = (title: string) => {
        setFormState((prev) => ({ ...prev, title }));
    };

    const setFormDescription = (description?: string) => {
        setFormState((prev) => ({
            ...prev,
            welcomePage: {
                ...(prev?.welcomePage || {}),
                description: description
            }
        }));
    };

    const setThankYouPageTitle = (thankyouPageIndex: number, title?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { title }));
    };

    const setThankYouPageDescription = (thankyouPageIndex: number, description?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { message: description }));
    };

    const setThankYouPageButtonText = (thankyouPageIndex: number, btnText?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { buttonText: btnText }));
    };

    const setThankYouPageButtonLink = (thankyouPageIndex: number, btnLink?: string) => {
        setFormState((prev) => patchThankYouPage(prev, thankyouPageIndex, { buttonLink: btnLink }));
    };

    const setWelcomePageButtonText = (btnText: string) => {
        setFormState((prev) => ({
            ...prev,
            welcomePage: { ...prev.welcomePage, buttonText: btnText }
        }));
    };

    const updateFormTheme = (theme: { title: string; primary: string; secondary: string; tertiary: string; accent: string }) => {
        setFormState((prev) => ({ ...prev, theme }));
    };

    const setHiddenFields = (hiddenFields: string[]) => {
        setFormState((prev) => ({ ...prev, hiddenFields }));
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
        theme: formState.theme,
        updateWelcomePageImage,
        updateThankYouPageImage,
        updateWelcomePageLayout,
        updateThankYouPageLayout
    };
}
