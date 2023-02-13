import WorkspaceHoc from '@app/components/hoc/workspace-hoc';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

describe('Render Components with Wrapped Workspace-HOC component', () => {
    it('should render components when no workspace is passed', function () {
        renderWithProviders(
            <WorkspaceHoc>
                <div>Render Children</div>
            </WorkspaceHoc>
        );
    });

    it('should render childredn when workspace is passed', function () {
        renderWithProviders(
            <WorkspaceHoc workspace={initWorkspaceDto}>
                <div>Render Children</div>
            </WorkspaceHoc>
        );
    });
});
