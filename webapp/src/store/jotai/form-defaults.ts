import { ThemeBackground, ThemeColor, ThemeStyle } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { v4 } from 'uuid';

/**
 * Starting values of the builder's document: the form-level part (title,
 * welcome and ending pages, theme, ...) and the pages. Kept apart from the
 * atoms so that the document store, the form state and the field selectors
 * can all use them without importing each other.
 */

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
    theme?: IThemeState;
    /**
     * Declared hidden-field (URL parameter) names, e.g. ['utm_source', 'name'].
     * Captured from the share link at fill time and stored with the response;
     * available to answer piping in question text.
     */
    hiddenFields?: string[];
    /** Organisation logo settings; the file itself is uploaded on its own (utils/form-logo.ts). */
    logoPosition?: 'left' | 'center' | 'auto';
    logoAlt?: string;
    useWorkspaceLogo?: boolean;
}

export interface IThemeState {
    title: string;
    primary: string;
    secondary: string;
    tertiary: string;
    accent: string;
    background?: ThemeBackground;
    style?: ThemeStyle;
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

export const initialFieldsState: StandardFormFieldDto[] = [
    {
        id: v4(),
        index: 0,
        type: FieldTypes.SLIDE,
        properties: {
            // Calm single-column default; decorative image/layout is opt-in.
            layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
            fields: [
                {
                    id: v4(),
                    index: 0,
                    type: FieldTypes.SHORT_TEXT,
                    value: 'Hi, what is your name?',
                    properties: {
                        placeholder: 'Answer'
                    }
                }
            ]
        }
    }
];
