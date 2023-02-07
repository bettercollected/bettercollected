import '@testing-library/jest-dom';
import { cleanup, fireEvent, getByText, render, screen, within } from '@testing-library/react';

import BreadcrumbsRenderer from '../breadcrumbs-renderer';

describe('Breadcrumbs render test', () => {
    afterEach(cleanup);

    it('renders the breadcrumbs component', () => {
        render(<BreadcrumbsRenderer breadcrumbsItem={[]} />);
        expect(screen.getByTestId('breadcrumbs-renderer')).toBeInTheDocument();
    });

    it('renders the expected text', () => {
        const breadcrumbsItem = [
            {
                icon: 'icon',
                title: 'title1'
            }
        ];
        render(<BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} />);
        within(screen.getByTestId('item0'));
        expect(screen.getByTestId('item0')).toBeInTheDocument();
    });
});
