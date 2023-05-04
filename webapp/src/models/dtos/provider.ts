export interface IntegrationFormProviders {
    enabled: boolean;
    provider_name: string;
    provider_url: string;
    auth_callback_url: string;
    type: null | string;
    scope: null | string;
    client_id: null | string;
    client_secret: null | string;
    api_uri: null | string;
    auth_uri: null | string;
    token_uri: null | string;
    redirect_uri: null | string;
    revoke_uri: null | string;
}
