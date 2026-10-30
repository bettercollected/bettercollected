import { analyticsApi } from '@app/store/analytics/api';
import { apiActionsApi } from '@app/store/api-actions-api';
import { authApi } from '@app/store/auth/api';
import { couponCodeApi } from '@app/store/coupon-code/api';
import { integrationApi } from '@app/store/integration-apis';
import { mediaLibraryApi } from '@app/store/media-library/api';
import { plansApi } from '@app/store/plans/api';
import { priceSuggestionApi } from '@app/store/price-suggestion/api';
import { formsApi } from '@app/store/redux/form-api';
import { importApi } from '@app/store/redux/import-api';
import { openFormulierenImportApi } from '@app/store/redux/open-formulieren-import-api';
import { pdfImportApi } from '@app/store/redux/pdf-import-api';
import { templatesApi } from '@app/store/redux/template-api';
import { templateApi } from '@app/store/template/api';
import { workspacesApi } from '@app/store/workspaces/api';
import { membersNInvitationsApi } from '@app/store/workspaces/members-n-invitations-api';

/**
 * Every RTK Query API slice in the store, in one list. The store adds their
 * middleware from it, and the sign-out reset (actions/reset-after-sign-out)
 * empties all of them but `authApi`. A test compares this list with the
 * API slices the store holds, so a new slice cannot be left out of the reset.
 */
export const API_SLICES = [
    priceSuggestionApi,
    authApi,
    membersNInvitationsApi,
    plansApi,
    workspacesApi,
    templateApi,
    apiActionsApi,
    couponCodeApi,
    formsApi,
    templatesApi,
    importApi,
    pdfImportApi,
    openFormulierenImportApi,
    mediaLibraryApi,
    analyticsApi,
    integrationApi
] as const;
