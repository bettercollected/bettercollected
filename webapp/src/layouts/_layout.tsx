import React from 'react';

import { Box } from '@mui/material';
import cn from 'classnames';
import { AnimatePresence, LazyMotion, domAnimation, motion } from 'framer-motion';

import AuthNavbar from '@app/components/auth/navbar';

interface LayoutProps {
    isCustomDomain?: boolean;
    isClientDomain?: boolean;
    showHamburgerIcon?: boolean;
    hideMenu?: boolean;
    className?: string;
    childClassName?: string;
    showAuthAccount?: boolean;
    hideSignIn?: boolean;
    showNavbar?: boolean;
    isFooter?: boolean;
}

export default function Layout({
    children,
    isCustomDomain = false,
    isClientDomain = false,
    hideMenu = false,
    showHamburgerIcon = false,
    className = '',
    childClassName = '',
    showNavbar = false,
    isFooter = false,
    showAuthAccount
}: React.PropsWithChildren<LayoutProps>) {
    return (
        <LazyMotion features={domAnimation}>
            <AnimatePresence mode="wait" initial={true} onExitComplete={() => window.scrollTo(0, 0)}>
                <motion.div
                    initial={{ x: 0, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    exit={{ x: 300, opacity: 0 }}
                    transition={{
                        ease: 'linear',
                        duration: 1,
                        x: { duration: 1 }
                    }}
                >
                    <div className="!min-h-screen !min-w-full bg-brand-100 dark:bg-dark z-20">
                        {showNavbar && <AuthNavbar isFooter={isFooter} isCustomDomain={isCustomDomain} isClientDomain={isClientDomain} showHamburgerIcon={showHamburgerIcon} hideMenu={hideMenu} showPlans={false} showAuthAccount={showAuthAccount} />}

                        <Box className={`float-none lg:float-right ${showNavbar ? 'mt-[68px] min-h-calc-68' : 'min-h-screen'} w-full px-5 lg:px-10 ${className}`} component="main" sx={{ display: 'flex', width: '100%' }}>
                            <div className={cn(`w-full h-full ${childClassName}`)}>{children}</div>
                        </Box>
                    </div>
                </motion.div>
            </AnimatePresence>
        </LazyMotion>
    );
}
