import ImportErrorView from '@app/components/form-integrations/import-error-view';

export default function OauthErrorModal() {
    return <ImportErrorView provider="google" closable={false} />;
}
