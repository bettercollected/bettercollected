"use client";

import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { Sheet, SheetContent, SheetTitle } from '@app/shadcn/components/ui/sheet';
import { cn } from '@app/shadcn/util/lib';
import { usePathname } from 'next/navigation';
import { useEffect } from 'react';

interface IMuiDrawerProps {
    drawerWidth?: number;
    mobileOpen?: boolean;
    handleDrawerToggle: () => void;
    anchor?: 'left' | 'top' | 'right' | 'bottom';
    mobileDrawerDisplayProps?: any; // kept for compatibility signature
    desktopDrawerDisplayProps?: any; // kept for compatibility signature
    children?: any;
}

export default function MuiDrawer({ drawerWidth = 289, mobileOpen, children, handleDrawerToggle, anchor = 'left' }: IMuiDrawerProps) {

    const isMobile = useIsMobile()
    const pathname = usePathname();

    useEffect(() => {
        if (isMobile && mobileOpen) {
            handleDrawerToggle();
        }
    }, [pathname])

    return (
        <>
            <div className="lg:hidden">
                <Sheet open={mobileOpen} onOpenChange={(open) => !open && handleDrawerToggle()} >
                    <SheetContent hideCloseIcon side={anchor === 'right' ? 'right' : 'left'} className="p-0 bg-white border-r border-r-black-200 z-[9999]" style={{ width: drawerWidth, maxWidth: '100vw' }}>
                        <SheetTitle className="sr-only">Menu</SheetTitle>
                        {children}
                    </SheetContent>
                </Sheet>
            </div>

            <div
                className={cn(
                    // No py here — the drawer content owns its own top band
                    // (aligned to the navbar) and bottom padding.
                    "hidden lg:block fixed top-0 h-full bg-white shrink-0 scrollbar-hide",
                    anchor === 'right' ? 'right-0 border-l' : 'left-0 border-r border-r-black-200'
                )}
                style={{ width: drawerWidth }}
            >
                {children}
            </div>
        </>
    );
}

// Keep defaultProps for compatibility if needed, though simpler now
MuiDrawer.defaultProps = {
    drawerWidth: 289,
    mobileOpen: false,
};
