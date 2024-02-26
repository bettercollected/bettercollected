import { createSelector } from '@reduxjs/toolkit';

import { providerApi } from './api';


const selectEnabledProvidersResult = providerApi.endpoints.getEnabledProviders.select();

export const selectEnabledProviders = createSelector(selectEnabledProvidersResult, (providersResult) => providersResult?.data ?? []);