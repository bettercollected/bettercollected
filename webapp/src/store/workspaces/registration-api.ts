import { workspacesApi } from '@app/store/workspaces/api';

// Sending a form's submissions to a case system (docs/open-formulieren-registration.md).
// Every call is `/workspaces/{id}/registration/...` or under a form. The
// service secret is write-only: no response carries one, only `hasSecret`.

export type RegistrationAuth = 'none' | 'header' | 'basic' | 'token';

/** What a service speaks: plain JSON to an address, or the Objects API. */
export type RegistrationKind = 'generic_json' | 'objects_api';

export interface RegistrationService {
    id: string;
    name: string;
    kind: RegistrationKind;
    /** For the Objects API: the address of the Objects API itself (`https://host/api/v2/`). */
    baseUrl: string;
    /** Objects API only: every form's object type address sits under this one. Never fetched. */
    objecttypesBaseUrl?: string | null;
    auth: RegistrationAuth;
    /** The header's name (auth "header") or the user name (auth "basic"). */
    authName?: string | null;
    hasSecret: boolean;
    secretSetAt?: string | null;
    organisationName: string;
    createdAt?: string | null;
    updatedAt?: string | null;
}

export interface RegistrationServiceInput {
    name?: string;
    /** Only when creating: a service's kind cannot be changed. */
    kind?: RegistrationKind;
    baseUrl?: string;
    objecttypesBaseUrl?: string;
    /** Generic JSON only: the Objects API sign-in is always its token. */
    auth?: RegistrationAuth;
    authName?: string | null;
    /** The password, header value or Objects API token. Leave out to keep the stored one. */
    secret?: string;
    organisationName?: string;
}

export interface RegistrationTestResult {
    ok: boolean;
    code?: string | null;
    httpStatus?: number | null;
}

export interface RegistrationVariableMapping {
    source: string;
    /** Generic JSON: the name in the sent body. */
    key?: string | null;
    /** Objects API: where the answer goes inside the object's data, one name per level. */
    targetPath?: string[] | null;
}

export interface FormRegistration {
    enabled: boolean;
    serviceId?: string | null;
    serviceName?: string | null;
    organisationName?: string | null;
    /** The chosen service's kind; null while none is chosen. */
    kind?: RegistrationKind | null;
    path: string;
    variables: RegistrationVariableMapping[];
    transformToList: string[];
    objectTypeUrl?: string | null;
    objectTypeVersion?: number | null;
    /** Where our delivery reference goes in the object's data. */
    referencePath?: string[] | null;
    updatedAt?: string | null;
}

export interface FormRegistrationInput {
    enabled: boolean;
    serviceId: string | null;
    path: string;
    variables: RegistrationVariableMapping[];
    transformToList: string[];
    objectTypeUrl?: string | null;
    objectTypeVersion?: number | null;
    referencePath?: string[];
}

export interface RegistrationVariable {
    source: string;
    label: string;
    type: string;
    supported: boolean;
    /** Why a variable is greyed out: `not_an_answer` or `type_not_supported`. */
    reason?: string | null;
}

export type DeliveryStatus = 'pending' | 'in_progress' | 'retrying' | 'delivered' | 'failed' | 'cancelled';

/** Ids and codes only: a delivery never carries answer content. */
export interface RegistrationDelivery {
    id: string;
    responseId: string;
    status: DeliveryStatus;
    serviceName?: string | null;
    attempts: number;
    manualAttempts: number;
    lastErrorCode?: string | null;
    lastHttpStatus?: number | null;
    lastAttemptAt?: string | null;
    nextAttemptAt?: string | null;
    deliveredAt?: string | null;
    createdAt?: string | null;
    /** Objects API: the id of the object that was created; none for Generic JSON. */
    remoteId?: string | null;
}

export interface RegistrationDeliveryPage {
    items: RegistrationDelivery[];
    total: number;
}

export interface DeliveriesQuery {
    workspaceId: string;
    formId: string;
    status?: DeliveryStatus[];
    limit?: number;
    offset?: number;
}

const SERVICES_TAG = 'REGISTRATION_SERVICES_TAG';
const FORM_TAG = 'REGISTRATION_FORM_TAG';
const DELIVERIES_TAG = 'REGISTRATION_DELIVERIES_TAG';

export const registrationApi = workspacesApi.enhanceEndpoints({ addTagTypes: [SERVICES_TAG, FORM_TAG, DELIVERIES_TAG] }).injectEndpoints({
    endpoints: (builder) => ({
        // Any member may ask; false hides every registration screen.
        getRegistrationStatus: builder.query<{ enabled: boolean }, string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/registration/status`, method: 'GET' })
        }),
        getRegistrationServices: builder.query<RegistrationService[], string>({
            query: (workspaceId) => ({ url: `/workspaces/${workspaceId}/registration/services`, method: 'GET' }),
            providesTags: [SERVICES_TAG]
        }),
        createRegistrationService: builder.mutation<RegistrationService, { workspaceId: string; body: RegistrationServiceInput }>({
            query: ({ workspaceId, body }) => ({ url: `/workspaces/${workspaceId}/registration/services`, method: 'POST', body }),
            invalidatesTags: [SERVICES_TAG]
        }),
        updateRegistrationService: builder.mutation<RegistrationService, { workspaceId: string; serviceId: string; body: RegistrationServiceInput }>({
            query: ({ workspaceId, serviceId, body }) => ({ url: `/workspaces/${workspaceId}/registration/services/${serviceId}`, method: 'PATCH', body }),
            invalidatesTags: [SERVICES_TAG, FORM_TAG]
        }),
        deleteRegistrationService: builder.mutation<void, { workspaceId: string; serviceId: string }>({
            query: ({ workspaceId, serviceId }) => ({ url: `/workspaces/${workspaceId}/registration/services/${serviceId}`, method: 'DELETE' }),
            invalidatesTags: [SERVICES_TAG]
        }),
        testRegistrationService: builder.mutation<RegistrationTestResult, { workspaceId: string; serviceId: string }>({
            query: ({ workspaceId, serviceId }) => ({ url: `/workspaces/${workspaceId}/registration/services/${serviceId}/test`, method: 'POST' })
        }),
        getFormRegistration: builder.query<FormRegistration, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/registration`, method: 'GET' }),
            providesTags: [FORM_TAG]
        }),
        saveFormRegistration: builder.mutation<FormRegistration, { workspaceId: string; formId: string; body: FormRegistrationInput }>({
            query: ({ workspaceId, formId, body }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/registration`, method: 'PUT', body }),
            invalidatesTags: [FORM_TAG, DELIVERIES_TAG]
        }),
        // The Objects API check of a form's saved settings (workspace admins; 429 after 10 a minute).
        checkFormRegistration: builder.mutation<RegistrationTestResult, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/registration/test`, method: 'POST' })
        }),
        getRegistrationVariables: builder.query<RegistrationVariable[], { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/registration/variables`, method: 'GET' })
        }),
        getRegistrationDeliveries: builder.query<RegistrationDeliveryPage, DeliveriesQuery>({
            query: ({ workspaceId, formId, status = [], limit = 50, offset = 0 }) => {
                const params = new URLSearchParams();
                status.forEach((value) => params.append('status', value));
                params.set('limit', String(limit));
                params.set('offset', String(offset));
                return { url: `/workspaces/${workspaceId}/forms/${formId}/registration/deliveries?${params.toString()}`, method: 'GET' };
            },
            providesTags: [DELIVERIES_TAG]
        }),
        retryRegistrationDelivery: builder.mutation<RegistrationDelivery, { workspaceId: string; formId: string; deliveryId: string }>({
            query: ({ workspaceId, formId, deliveryId }) => ({ url: `/workspaces/${workspaceId}/forms/${formId}/registration/deliveries/${deliveryId}/retry`, method: 'POST' }),
            invalidatesTags: [DELIVERIES_TAG]
        })
    })
});

export const {
    useGetRegistrationStatusQuery,
    useGetRegistrationServicesQuery,
    useCreateRegistrationServiceMutation,
    useUpdateRegistrationServiceMutation,
    useDeleteRegistrationServiceMutation,
    useTestRegistrationServiceMutation,
    useGetFormRegistrationQuery,
    useSaveFormRegistrationMutation,
    useCheckFormRegistrationMutation,
    useGetRegistrationVariablesQuery,
    useGetRegistrationDeliveriesQuery,
    useRetryRegistrationDeliveryMutation
} = registrationApi;
