import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('next/router', () => ({
    useRouter() {
        return {
            route: '/',
            pathname: '',
            query: null,
            asPath: '',
            push: jest.fn(),
            events: {
                on: jest.fn(),
                off: jest.fn()
            },
            beforePopState: jest.fn(() => null),
            prefetch: jest.fn(() => null)
        };
    }
}));

describe('reder Forms and submissions tab container', () => {
    it('should render Forms and Responses Tab Container', function () {
        renderWithProviders(<FormsAndSubmissionsTabContainer workspaceId={initWorkspaceDto.id} showResponseBar={true} workspace={initWorkspaceDto} />);
    });
});
