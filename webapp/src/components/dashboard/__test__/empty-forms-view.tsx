import { render, screen } from '@testing-library/react';

import EmptyFormsView from '@app/components/dashboard/empty-form';

describe('Renders Empty Form View', () => {
    it('Renders image correctly', () => {
        render(<EmptyFormsView />);
        expect(screen.getByTestId('empty-forms-view-image')).toBeInTheDocument();
    });
});
