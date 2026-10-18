import { ReactNode } from 'react';

/**
 * The landmarks of a published form's page: the form is the page's main
 * content and the privacy strip its footer, so screen-reader users can jump
 * between the two and nothing sits outside a landmark.
 *
 * `data-fit-area` marks the space the form gets (utils/panel-fit.ts).
 */
export default function RespondentPageShell({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
    return (
        <div className="relative flex h-dvh w-screen flex-col">
            <main className="relative min-h-0 flex-1" data-fit-area>
                {children}
            </main>
            {footer && <footer className="relative z-40 shrink-0">{footer}</footer>}
        </div>
    );
}
