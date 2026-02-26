'use client';

import { ThemeProvider as NextThemeProvider } from 'next-themes';

import React from 'react';

export default function ThemeProvider({
    children,
}: Readonly<{
    children: React.ReactNode | React.ReactNode[];
}>) {
    return (
        <NextThemeProvider attribute="class" enableSystem={true} forcedTheme="light" defaultTheme="light">
            {children}
        </NextThemeProvider>
    );
}
