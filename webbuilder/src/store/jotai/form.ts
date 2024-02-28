import { atom, useAtom } from 'jotai';

import { ThemeColor } from '@app/constants/theme';

interface IFormState {
    title: string;
    description?: string;
    thankYouMessage?: string;
    thankYouButtonText?: string;
    buttonText?: string;
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

const initialFormState = atom<IFormState>({
    title: '',
    description: undefined,
    thankYouMessage: undefined,
    thankYouButtonText: '',
    buttonText: undefined,
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

    return {
        formState,
        setFormState,
        setFormDescription,
        setFormTitle,
        updateFormTheme,
        theme: formState.theme
    };
}
