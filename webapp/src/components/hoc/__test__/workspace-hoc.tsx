import WorkspaceNStatusHoc from '@app/components/hoc/workspace-n-status-hoc';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

describe('Render Components with Wrapped Workspace-HOC component', () => {
    it('should render components when no workspace is passed', function () {
        renderWithProviders(
            <WorkspaceNStatusHoc>
                <div>Render Children</div>
            </WorkspaceNStatusHoc>
        );
    });

    it('should render childredn when workspace is passed', function () {
        renderWithProviders(
            <WorkspaceNStatusHoc workspace={initWorkspaceDto}>
                <div>Render Children</div>
            </WorkspaceNStatusHoc>
        );
    });
});
