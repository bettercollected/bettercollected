// The organisation logo strip on respondent pages (DESIGN.md §9).
import React from 'react';

import { render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { logoFileProblem, logoUploadError, resolveFormLogo } from '@app/utils/form-logo';
import FormLogoStrip from '@app/views/molecules/form/form-logo-strip';

import Form from './form';
import FormSlide from './form-slide';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const LOGO = 'https://storage.example.test/bettercollected/public/form-logos/f1/logo.png';
const WORKSPACE_LOGO = 'https://storage.example.test/bettercollected/workspace.png';
const DEFAULT = { title: 'Default', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB', style: 'classic' as const };
const LEAFLET = { title: 'Leaflet', primary: '#1A1A1A', secondary: '#0B3D91', tertiary: '#6B7A99', accent: '#FFFFFF', style: 'leaflet' as const };
const slide = (id: string, index: number, fields: StandardFormFieldDto[], layout?: FormSlideLayout): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields, layout } });

const loadForm = (extra: Record<string, unknown> = {}, theme: any = DEFAULT) =>
    store.dispatch(
        setForm({
            formId: 'f1',
            title: 'Buurtonderzoek',
            theme,
            welcomePage: { description: 'Two short pages.' },
            fields: [slide('s1', 0, [{ id: 'name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name' }])],
            ...extra
        } as any)
    );

const Themed = ({ children }: { children: React.ReactNode }) => {
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme((store.getState() as any).form.theme);
    }, []);
    return <>{children}</>;
};

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Themed>{node}</Themed>
            </Provider>
        </ReduxProvider>
    );

describe('resolveFormLogo', () => {
    const workspace = { title: 'Wijkcentrum De Kroon', workspaceName: 'dekroon', profileImage: WORKSPACE_LOGO };

    it('shows the form logo on the left by default, named after the organisation', () => {
        expect(resolveFormLogo({ logo: LOGO }, workspace)).toEqual({ src: LOGO, alt: 'Wijkcentrum De Kroon', position: 'left', fromWorkspace: false });
    });

    it("uses the creator's alt text and position", () => {
        expect(resolveFormLogo({ logo: LOGO, logoAlt: '  De Kroon  ', logoPosition: 'center' }, workspace)).toMatchObject({ alt: 'De Kroon', position: 'center' });
    });

    it('falls back to the workspace handle when the workspace has no title', () => {
        expect(resolveFormLogo({ logo: LOGO }, { workspaceName: 'dekroon' })?.alt).toBe('dekroon');
    });

    it("shows the workspace's logo only when the creator turned that on and the form has none", () => {
        expect(resolveFormLogo({}, workspace)).toBeNull();
        expect(resolveFormLogo({ useWorkspaceLogo: false }, workspace)).toBeNull();
        expect(resolveFormLogo({ useWorkspaceLogo: true }, workspace)).toMatchObject({ src: WORKSPACE_LOGO, fromWorkspace: true });
        expect(resolveFormLogo({ logo: LOGO, useWorkspaceLogo: true }, workspace)?.src).toBe(LOGO);
        expect(resolveFormLogo({ useWorkspaceLogo: true }, { title: 'No image' })).toBeNull();
    });

    it('refuses SVG and large files before uploading, with a plain reason', () => {
        expect(logoFileProblem({ type: 'image/svg+xml', size: 10 })).toMatch(/SVG/);
        expect(logoFileProblem({ type: 'image/png', size: 2 * 1024 * 1024 })).toMatch(/1 MB/);
        expect(logoFileProblem({ type: 'image/webp', size: 2048 })).toBeNull();
        expect(logoUploadError(415)).toMatch(/PNG, JPEG or WebP/);
        expect(logoUploadError(500)).toMatch(/Try again/);
    });
});

describe('FormLogoStrip', () => {
    const logo = { src: LOGO, alt: 'Wijkcentrum De Kroon', position: 'left' as const, fromWorkspace: false };

    it('sits on the form column, on the left or centred', () => {
        const { rerender } = render(<FormLogoStrip logo={logo} theme={DEFAULT} />);
        const strip = screen.getByTestId('form-logo-strip');
        expect(strip.getAttribute('data-logo-position')).toBe('left');
        expect(screen.getByTestId('form-logo').parentElement!.className).toContain('justify-start');
        expect(screen.getByTestId('form-logo').parentElement!.className).toContain('max-w-2xl');
        rerender(<FormLogoStrip logo={{ ...logo, position: 'center' }} theme={DEFAULT} />);
        expect(screen.getByTestId('form-logo').parentElement!.className).toContain('justify-center');
    });

    it('never draws the image larger than it is and keeps its proportions', () => {
        render(<FormLogoStrip logo={logo} theme={DEFAULT} />);
        const image = screen.getByRole('img', { name: 'Wijkcentrum De Kroon' });
        expect(image.className).toContain('h-auto');
        expect(image.className).toContain('w-auto');
        expect(image.className).toContain('object-contain');
        expect(image.className).toContain('max-h-10');
        expect(image.getAttribute('referrerpolicy')).toBe('no-referrer');
    });

    it('is larger on the cover', () => {
        render(<FormLogoStrip logo={logo} theme={DEFAULT} size="cover" />);
        expect(screen.getByTestId('form-logo').className).toContain('max-h-14');
        expect(screen.getByTestId('form-logo-strip').getAttribute('data-logo-size')).toBe('cover');
    });

    it('has the page colour and a rule in most styles, and is a white band without its own rule in Leaflet', () => {
        const { rerender } = render(<FormLogoStrip logo={logo} theme={DEFAULT} />);
        let strip = screen.getByTestId('form-logo-strip');
        expect(strip.className).toContain('border-b');
        expect(strip.style.background).toBe('rgb(245, 247, 251)');
        rerender(<FormLogoStrip logo={logo} theme={{ ...LEAFLET, accent: '#F2F2F2' }} />);
        strip = screen.getByTestId('form-logo-strip');
        expect(strip.className).not.toContain('border-b');
        expect(strip.style.background).toBe('rgb(255, 255, 255)');
    });

    it('is a band the privacy panel check takes off the room the page has', () => {
        render(<FormLogoStrip logo={logo} theme={DEFAULT} />);
        expect(screen.getByTestId('form-logo-strip').hasAttribute('data-fit-reserve')).toBe(true);
    });
});

describe('the logo on respondent pages', () => {
    beforeEach(() => {
        store.dispatch(setWorkspace({ id: 'ws-1', title: 'Wijkcentrum De Kroon', workspaceName: 'dekroon', profileImage: WORKSPACE_LOGO } as any));
    });

    it('opens the welcome page, larger, above the page', () => {
        loadForm({ logo: LOGO, logoPosition: 'center' });
        wrap(<Form isPreviewMode />);
        const strip = screen.getByTestId('form-logo-strip');
        expect(strip.getAttribute('data-logo-size')).toBe('cover');
        expect(strip.getAttribute('data-logo-position')).toBe('center');
        expect(within(strip).getByRole('img').getAttribute('alt')).toBe('Wijkcentrum De Kroon');
        // The strip comes before the page's own content.
        const title = screen.getByRole('heading', { level: 1 });
        expect(strip.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it('tops every question page, in every style', () => {
        for (const theme of [DEFAULT, { ...DEFAULT, style: 'sheet' }, { ...DEFAULT, style: 'studio' }, LEAFLET]) {
            loadForm({ logo: LOGO, logoAlt: 'De Kroon' }, theme);
            const { unmount } = wrap(<FormSlide index={0} isPreviewMode logo={resolveFormLogo({ logo: LOGO, logoAlt: 'De Kroon' }, null)} />);
            const strip = screen.getByTestId('form-logo-strip');
            expect(strip.getAttribute('data-logo-size')).toBe('page');
            expect(within(strip).getByRole('img', { name: 'De Kroon' })).toBeTruthy();
            // above the page header (Back and the page count)
            const back = screen.getByRole('button', { name: /back/i });
            expect(strip.compareDocumentPosition(back) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
            unmount();
        }
    });

    it("shows the workspace's logo when the form has none and the creator chose that", () => {
        loadForm({ useWorkspaceLogo: true });
        wrap(<Form isPreviewMode />);
        expect(screen.getByTestId('form-logo').getAttribute('src')).toBe(WORKSPACE_LOGO);
    });

    it('draws no strip without a logo', () => {
        loadForm({});
        wrap(<Form isPreviewMode />);
        expect(screen.queryByTestId('form-logo-strip')).toBeNull();
    });
});
