import { render } from '@testing-library/react';

import WorkspaceHeader from '@app/components/workspace/workspace-header';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';

describe('Render Workspace Header', () => {
    it('should render component', function () {
        render(<WorkspaceHeader workspace={initWorkspaceDto} />);
    });
});
