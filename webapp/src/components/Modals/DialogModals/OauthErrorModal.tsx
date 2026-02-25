import ImportErrorView from '@app/Components/form-integrations/import-error-view';

export default function OauthErrorModal() {
    return <ImportErrorView provider="google" closable={false} />;
}