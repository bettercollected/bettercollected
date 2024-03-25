import { atom, useAtom } from 'jotai';

import { ThemeColor } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';

export interface IFormState {
    title: string;
    welcomeTitle?: string;
    description?: string;
    thankYouMessage?: string;
    thankYouButtonText?: string;
    buttonText?: string;
    buttonLink?: string;
    welcomePage?: {
        title?: string;
        description?: string;
        layout?: FormSlideLayout;
        imageUrl?: string;
    };
    thankyouPage?: Array<{
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
}

export interface IThemeState {
    title: string;
    primary: string;
    secondary: string;
    tertiary: string;
    accent: string;
}

export const initialFormState = atom<IFormState>({
    title: '',
    welcomeTitle: '',
    description: undefined,
    thankYouMessage: undefined,
    thankYouButtonText: '',
    buttonText: undefined,
    buttonLink: undefined,
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
});

export function useFormState() {
    const [formState, setFormState] = useAtom(initialFormState);

    const setFormTitle = (title: string) => {
        setFormState({ ...formState, title });
    };

    const setWelcomeTitle = (welcomeTitle: string) => {
        setFormState({ ...formState, welcomeTitle });
    };

    const setFormDescription = (description: string) => {
        setFormState({ ...formState, description });
    };

    const updateFormTheme = (theme: {
        title: string;
        primary: string;
        secondary: string;
        tertiary: string;
        accent: string;
    }) => {
        setFormState({ ...formState, theme });
    };

    const updateWelcomePageImage = (imageUrl: string) => {
        setFormState({
            ...formState,
            welcomePage: { ...formState.welcomePage, imageUrl }
        });
    };

    const updateWelcomePageLayout = (layout: FormSlideLayout) => {
        setFormState({
            ...formState,
            welcomePage: {
                ...formState?.welcomePage,
                layout: layout
            }
        });
    };

    const updateThankYouPageImage = (imageUrl: string) => {
        formState.thankyouPage![0].imageUrl = imageUrl;
        setFormState({ ...formState });
    };

    const updateThankYouPageLayout = (layout: FormSlideLayout) => {
        formState.thankyouPage![0].layout = layout;
        setFormState({ ...formState });
    };

    return {
        formState,
        setFormState,
        setFormDescription,
        setFormTitle,
        updateFormTheme,
        theme: formState.theme,
        setWelcomeTitle,
        updateWelcomePageImage,
        updateThankYouPageImage,
        updateWelcomePageLayout,
        updateThankYouPageLayout
    };
}
