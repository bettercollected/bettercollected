import { act, renderHook, screen } from '@testing-library/react';

import DrawersContainer from '@app/components/drawer-views/container';
import { useDrawer } from '@app/components/drawer-views/context';
import ModalContainer from '@app/components/modal-views/container';
import { useModal } from '@app/components/modal-views/context';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

class IntersectionObserver {
    observe = jest.fn();
    disconnect = jest.fn();
    unobserve = jest.fn();
}

Object.defineProperty(window, 'IntersectionObserver', {
    writable: true,
    configurable: true,
    value: IntersectionObserver
});

Object.defineProperty(global, 'IntersectionObserver', {
    writable: true,
    configurable: true,
    value: IntersectionObserver
});

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

describe('render drawer view when open drawer modal is called', () => {
    it('should open drawer', function () {
        renderWithProviders(<ModalContainer />);
        const { result } = renderHook(() => useModal());

        act(() => {
            result.current.openModal('LOGIN_VIEW');
        });
        screen.debug();

        expect(screen.getByTestId('modal-view')).toBeInTheDocument();

        // TODO: fix multiple modal elements rendered
    });
});
