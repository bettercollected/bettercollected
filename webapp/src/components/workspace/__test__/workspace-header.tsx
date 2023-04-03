import { render } from '@testing-library/react';

import WorkspaceHeader from '@app/components/workspace/workspace-header';

describe('Render Workspace Header', () => {
    it('should render component', function () {
        render(<WorkspaceHeader isFormCreator={true} />);
    });
});
