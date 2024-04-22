import { createTheme, css } from '@mui/material/styles';

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
                    borderRadius: '4px'
                }
            }
        },
        MuiTooltip: {
            styleOverrides: {
                popper: {
                    zIndex: '3000 !important'
                }
            }
        },
        MuiMobileStepper: {
            styleOverrides: {
                progress: {
                    color: '#343A40',
                    width: '100%'
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
                    borderRadius: '4px'
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
            background: #ffffff;
            background-color: #ffffff;
            color: #121212;
        }
    }
    [data-theme='dark'] {
        body {
            background: #121212;
            background-color: #121212;
            color: #ffffff;
        }
    }
`;
