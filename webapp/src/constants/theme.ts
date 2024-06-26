export const ThemeColor = {
    accent: '#F2F7FF',
    tertiary: '#A2C5F8',
    secondary: '#0764EB',
    primary: '#2E2E2E'
};

export interface FormTheme {
    title: string;
    primary: string;
    secondary: string;
    tertiary: string;
    accent: string;
}

export const ThemeColors: Array<FormTheme> = [
    {
        title: 'Default',
        primary: '#2E2E2E',
        secondary: '#0764EB',
        tertiary: '#A2C5F8',
        accent: '#F2F7FF'
    },
    {
        title: 'Blue',
        primary: '#2E2E2E',
        secondary: '#337FC2',
        tertiary: '#61A9E9',
        accent: '#B0DAFF'
    },
    {
        title: 'Green',
        primary: '#2E2E2E',
        secondary: '#459E73',
        tertiary: '#81D8AE',
        accent: '#D7F6E7'
    },
    {
        title: 'Red',
        primary: '#2E2E2E',
        secondary: '#BE3032',
        tertiary: '#E75759',
        accent: '#FFB2B3'
    },
    {
        title: 'Black',
        primary: '#2E2E2E',
        secondary: '#2E2E2E',
        tertiary: '#DBDBDB',
        accent: '#FFFFFF'
    },
    {
        title: 'Orange',
        primary: '#2E2E2E',
        secondary: '#DA8C0B',
        tertiary: '#F1B85A',
        accent: '#FFEFCC'
    },
    {
        title: 'Purple',
        primary: '#2E2E2E',
        secondary: '#533CAF',
        tertiary: '#846BEC',
        accent: '#CFC3FF'
    }
];
