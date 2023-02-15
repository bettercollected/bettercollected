import { render } from '@testing-library/react';

import LandingPageSectionContainer from '@app/components/landingpage/LandingPageSectionContainer';
import Features from '@app/components/landingpage/features';

describe('renders Landing Page Section Container Section', () => {
    it('should render component', function () {
        render(
            <LandingPageSectionContainer sectionId="features">
                <Features />
            </LandingPageSectionContainer>
        );
    });
});
