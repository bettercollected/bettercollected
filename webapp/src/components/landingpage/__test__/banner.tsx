import { render } from '@testing-library/react';

import Banner from '@app/components/landingpage/banner';

describe('renders Banner Section', () => {
    it('should render component', function () {
        render(<Banner />);
    });
});
