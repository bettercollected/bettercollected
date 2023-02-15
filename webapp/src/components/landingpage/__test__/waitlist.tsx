import { render } from '@testing-library/react';

import WaitList from '@app/components/landingpage/waitList';

describe('renders WaitList Section', () => {
    it('should render component', function () {
        render(<WaitList />);
    });
});
