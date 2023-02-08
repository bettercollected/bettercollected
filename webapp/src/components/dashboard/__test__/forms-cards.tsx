import React from 'react';

import { render, screen } from '@testing-library/react';

import FormCards from '@app/components/dashboard/form-cards';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import { formArray } from '@app/utils/__test_utils__/mock-form-data';
import mockUseBreakPoint from '@app/utils/__test_utils__/mock-use-breakpoint';

mockUseBreakPoint('lg');

global.window = Object.create(window);

jest.mock('next/router', () => ({
    useRouter: () => ({
        query: {},
        pathname: '/dashbaord',
        push: jest.fn()
    })
}));
jest.mock('@app/lib/hooks/use-copy-to-clipboard', () => ({
    useCopyToClipboard: () => [undefined, jest.fn()]
}));

describe('Render Forms Cards', () => {
    it('should not render form cards when array is empty', function () {
        render(<FormCards title="Forms" formsArray={[]} workspace={initWorkspaceDto} />);
        expect(screen.queryByTestId('form-cards-container')).toBe(null);
    });

    it('should render form cards when array is provided', function () {
        render(<FormCards title="Forms" formsArray={formArray} workspace={initWorkspaceDto} />);
        expect(screen.getByTestId('form-cards-container')).toBeInTheDocument();
    });
});
