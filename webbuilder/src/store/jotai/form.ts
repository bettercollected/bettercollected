import { atom, useAtom } from 'jotai';

import { ThemeColor } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';

import { useActiveThankYouPageComponent } from './activeBuilderComponent';

export interface IFormState {
    title: string;
    // welcomeTitle?: string;
    description?: string;
    // thankYouMessage?: string;
    // thankYouButtonText?: string;
    // buttonText?: string;
    // buttonLink?: string;
    welcomePage?: {
        title?: string;
        description?: string;
        layout?: FormSlideLayout;
        imageUrl?: string;
        buttonText?: string;
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
    description: undefined,
    // welcomeTitle: '',
    // thankYouMessage: undefined,
    // thankYouButtonText: '',
    // buttonText: undefined,
    // buttonLink: undefined,
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
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();

    const setFormTitle = (title: string) => {
        setFormState({ ...formState, title: title });
    };

    const setWelcomeTitle = (welcomeTitle: string) => {
        setFormState({
            ...formState,
            welcomePage: { ...formState.welcomePage, title: welcomeTitle }
        });
    };

    const setFormDescription = (description?: string) => {
        formState.description = description;
        setFormState({
            ...formState
        });
    };

    const setThankYouPageDescription = (
        thankyouPageIndex: number,
        description?: string
    ) => {
        formState.thankyouPage &&
            (formState.thankyouPage[thankyouPageIndex].message = description);
        setFormState({ ...formState });
    };

    const setThankYouPageButtonText = (thankyouPageIndex: number, btnText?: string) => {
        formState.thankyouPage![thankyouPageIndex].buttonText = btnText;
        setFormState({ ...formState });
    };

    const setThankYouPageButtonLink = (thankyouPageIndex: number, btnLink?: string) => {
        formState.thankyouPage &&
            (formState.thankyouPage[thankyouPageIndex].buttonLink = btnLink);
        setFormState({ ...formState });
    };

    const setWelcomePageButtonText = (btnText: string) => {
        setFormState({
            ...formState,
            welcomePage: { ...formState.welcomePage, buttonText: btnText }
        });
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
        formState.welcomePage && (formState.welcomePage.imageUrl = imageUrl);
        setFormState({
            ...formState
        });
    };

    const updateWelcomePageLayout = (layout: FormSlideLayout) => {
        if (formState.welcomePage) {
            !formState.welcomePage.imageUrl &&
                (formState.welcomePage.imageUrl =
                    'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png');
            formState.welcomePage.layout = layout;
        }
        setFormState({
            ...formState
        });
    };

    const updateThankYouPageImage = (imageUrl: string) => {
        formState.thankyouPage &&
            (formState.thankyouPage![activeThankYouPageComponent?.index || 0].imageUrl =
                imageUrl);
        setFormState({ ...formState });
    };

    const updateThankYouPageLayout = (layout: FormSlideLayout) => {
        if (formState.thankyouPage) {
            !formState.thankyouPage![activeThankYouPageComponent?.index || 0]
                .imageUrl &&
                (formState.thankyouPage![
                    activeThankYouPageComponent?.index || 0
                ].imageUrl =
                    'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png');
            formState.thankyouPage![activeThankYouPageComponent?.index || 0].layout =
                layout;
        }
        setFormState({ ...formState });
    };

    return {
        formState,
        setFormState,
        setFormDescription,
        setWelcomeTitle,
        setWelcomePageButtonText,
        setThankYouPageDescription,
        setThankYouPageButtonText,
        setThankYouPageButtonLink,
        setFormTitle,
        updateFormTheme,
        theme: formState.theme,
        updateWelcomePageImage,
        updateThankYouPageImage,
        updateWelcomePageLayout,
        updateThankYouPageLayout
    };
}
