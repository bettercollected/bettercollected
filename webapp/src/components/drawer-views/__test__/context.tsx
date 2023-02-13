import { act, renderHook } from '@testing-library/react';

import { useDrawer } from '@app/components/drawer-views/context';

describe('useDrawer hook', () => {
    it('should status of drawer to be closed when useModal', function () {
        const { result } = renderHook(() => useDrawer());
        expect(result.current.isOpen).toBe(false);
        expect(result.current.view).toBe('');
        act(() => {
            result.current.openDrawer('DASHBOARD_SIDEBAR');
        });
        expect(result.current.isOpen).toBe(true);
        expect(result.current.view).toBe('DASHBOARD_SIDEBAR');

        act(() => {
            result.current.closeDrawer();
        });

        expect(result.current.isOpen).toBe(false);
        expect(result.current.view).toBe('');
    });
});
