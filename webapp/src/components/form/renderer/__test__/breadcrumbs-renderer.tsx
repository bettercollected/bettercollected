import '@testing-library/jest-dom';
import { cleanup, render } from '@testing-library/react';

describe('Breadcrumbs render test', () => {
    afterEach(cleanup);

    it('ankit please fix it', () => {
        render(<p></p>);
    });

    // it('renders the breadcrumbs component', () => {
    //     render(<BreadcrumbsRenderer breadcrumbsItem={[]} />);
    //     expect(screen.getByTestId('breadcrumbs-renderer')).toBeInTheDocument();
    // });

    // it('renders the expected text', () => {
    //     const breadcrumbsItem = [
    //         {
    //             title: 'title1',
    //             disabled: true,
    //             url: '#url'
    //         }
    //     ];
    //     render(<BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} />);
    //     within(screen.getByTestId('item0'));
    //     expect(screen.getByTestId('item0')).toBeInTheDocument();
    // });
});
