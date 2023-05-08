import { createSelector } from '@reduxjs/toolkit';

import { authApi } from './api';

const selectAuthStatusResult = authApi.endpoints.getStatus.select('status');

export const selectAuthStatus = createSelector(selectAuthStatusResult, (providersResult) => providersResult?.data?.user ?? null);
