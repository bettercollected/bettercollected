
import { Sheet, SheetContent } from '@app/shadcn/components/ui/sheet';
import { cn } from '@app/shadcn/util/lib';

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

    return (
        <>
            {/* Mobile drawer (Sheet) - Visible on small screens, hidden on large */}
            <div className="lg:hidden">
                <Sheet open={mobileOpen} onOpenChange={(open) => !open && handleDrawerToggle()}>
                    <SheetContent side={anchor === 'right' ? 'right' : 'left'} className="p-0 bg-white border-r border-r-black-200" style={{ width: drawerWidth, maxWidth: '100vw' }}>
                        {children}
                    </SheetContent>
                </Sheet>
            </div>

            {/* Desktop drawer (Permanent) - Hidden on small screens, visible on large */}
            <div
                className={cn(
                    "hidden lg:block fixed top-0 h-full bg-white shrink-0 scrollbar-hide py-3",
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
