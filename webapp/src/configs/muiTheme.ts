/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-11
 * Time: 13:56
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { PaletteOptions, createTheme, css } from '@mui/material/styles';

export type AllowedTheme = NonNullable<PaletteOptions['mode']>;

export const lightTheme = createTheme({
    typography: {
        fontFamily: `"Inter", "Roboto", "Helvetica", "Arial", sans-serif`
    },
    palette: {
        primary: { main: '#007AFF' },
        secondary: { main: '#f04444' },
        mode: 'light'
    },
    components: {
        MuiPaper: {
            styleOverrides: {
                root: {
                    borderRadius: '10px'
                }
            }
        }
    },
    breakpoints: {
        values: {
            xs: 0,
            sm: 640,
            md: 768,
            lg: 1024,
            xl: 1280
        }
    }
});

export const darkTheme = createTheme({
    typography: {
        fontFamily: `"Inter", "Roboto", "Helvetica", "Arial", sans-serif`
    },
    palette: {
        primary: { main: '#ffa500' },
        secondary: { main: '#f04444' },
        mode: 'dark'
    },
    components: {
        MuiPaper: {
            styleOverrides: {
                root: {
                    borderRadius: '10px'
                }
            }
        }
    },
    breakpoints: {
        values: {
            xs: 0,
            sm: 640,
            md: 768,
            lg: 1024,
            xl: 1280
        }
    }
});

export const globalStyles = css`
    :root {
        body {
            background-color: #fff;
            color: #121212;
        }
    }
    [data-theme='dark'] {
        body {
            background-color: #121212;
            color: #fff;
        }
    }
`;
