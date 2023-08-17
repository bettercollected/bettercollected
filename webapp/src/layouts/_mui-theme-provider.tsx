/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-11
 * Time: 13:49
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { ReactNode, useEffect, useState } from 'react';

import { useTheme } from 'next-themes';

import { ThemeProvider } from '@mui/material';

import { darkTheme, lightTheme } from '@app/configs/muiTheme';

interface MuiThemeProviderProps {
    children: ReactNode;
}

const MuiThemeProvider = ({ children }: MuiThemeProviderProps) => {
    const { resolvedTheme } = useTheme();
    const [currentTheme, setCurrentTheme] = useState(darkTheme);

    useEffect(() => {
        resolvedTheme === 'light' ? setCurrentTheme(lightTheme) : setCurrentTheme(darkTheme);
    }, [resolvedTheme]);

    return <ThemeProvider theme={currentTheme}>{children}</ThemeProvider>;
};

export default MuiThemeProvider;
