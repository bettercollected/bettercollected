import { RootState } from '@app/store/store';

export const selectAuthStatus = (state: RootState) => state.authApi.queries['getStatus("status")'];
