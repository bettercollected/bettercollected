import {ReactNode, useEffect, useState} from 'react';

import {useTheme} from 'next-themes';
import {AppRouterCacheProvider} from '@mui/material-nextjs/v13-appRouter'
import {ThemeProvider} from '@mui/material';
import {darkTheme, lightTheme} from '@app/configs/muiTheme';

interface MuiThemeProviderProps {
    children: ReactNode;
}

const MuiThemeProvider = ({children}: MuiThemeProviderProps) => {
    const {resolvedTheme} = useTheme();
    const [currentTheme, setCurrentTheme] = useState(darkTheme);

    useEffect(() => {
        resolvedTheme === 'light'
            ? setCurrentTheme(lightTheme)
            : setCurrentTheme(darkTheme);
    }, [resolvedTheme]);

    return (
        <AppRouterCacheProvider>
            <ThemeProvider theme={currentTheme}>
                <>{children}</>
            </ThemeProvider>
        </AppRouterCacheProvider>
    );
};

export default MuiThemeProvider;
