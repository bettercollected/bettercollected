import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { store } from '@app/store/store';
import { unsplashRouteBase } from '@app/utils/first-party-image';
import ImageField from '@app/views/organism/form-builder/fields/image-field';
import { RenderImage } from '@app/views/organism/form-builder/fields/render-field';

import LayoutWrapper from './layout-wrapper';

/**
 * Forms store an Unsplash photo by its canonical images.unsplash.com address;
 * what a page renders must load it through our own API instead.
 */
const UNSPLASH = 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?ixid=abc&w=1080';

const wrap = (node: React.ReactNode) =>
    render(
        <ReduxProvider store={store}>
            <Provider>{node}</Provider>
        </ReduxProvider>
    );

const imageSources = (container: HTMLElement) => Array.from(container.querySelectorAll('img')).flatMap((img) => [img.getAttribute('src') ?? '', img.getAttribute('srcset') ?? '']);

const loadsOnlyThroughOurRoute = (container: HTMLElement) => {
    const sources = imageSources(container).filter(Boolean);
    expect(sources.length).toBeGreaterThan(0);
    for (const source of sources) {
        expect(source).not.toContain('images.unsplash.com');
        expect(source).toContain(`${unsplashRouteBase()}photo-1500530855697-b586d89ba3ee`);
    }
};

describe('Unsplash photos render through our route', () => {
    it('as a page layout image', () => {
        const { container } = wrap(
            <LayoutWrapper layout={FormSlideLayout.TWO_COLUMN_IMAGE_LEFT} imageUrl={UNSPLASH} disabled showDesktopLayout>
                <div />
            </LayoutWrapper>
        );
        loadsOnlyThroughOurRoute(container);
    });

    it('as a question image', () => {
        const { container } = wrap(<RenderImage field={{ id: 'q1', index: 0, type: FieldTypes.SHORT_TEXT, imageUrl: UNSPLASH } as any} />);
        loadsOnlyThroughOurRoute(container);
    });

    it('as an image block', () => {
        const { container } = wrap(<ImageField field={{ id: 'i1', index: 0, type: FieldTypes.IMAGE_CONTENT, attachment: { href: UNSPLASH } } as any} isBuilder />);
        loadsOnlyThroughOurRoute(container);
    });
});
