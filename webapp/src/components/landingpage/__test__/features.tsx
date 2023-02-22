import { render } from '@testing-library/react';

import Features from '@app/components/landingpage/features';

describe('renders Features Section', () => {
    it('should render component', function () {
        render(<Features />);
    });
});
