import { act, renderHook } from '@testing-library/react';

import { useModal } from '@app/components/modal-views/context';

describe('useDrawer hook', () => {
    it('should status of drawer to be closed when useModal', function () {
        const { result } = renderHook(() => useModal());
        expect(result.current.isOpen).toBe(false);
        expect(result.current.view).toBe('');

        act(() => {
            result.current.openModal('LOGIN_VIEW');
        });

        expect(result.current.isOpen).toBe(true);
        expect(result.current.view).toBe('LOGIN_VIEW');

        act(() => {
            result.current.closeModal();
        });

        expect(result.current.isOpen).toBe(false);
        expect(result.current.view).toBe('');
    });
});
