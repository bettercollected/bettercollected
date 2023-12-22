import ProviderLoginButton from './provider-login-btn';

interface ConnectWithProviderButtonProps {
    text: string;
    url: string;
    type?: 'light' | 'dark' | 'typeform';
    creator?: boolean;
    disabled?: boolean;
    fromProPlan?: string | string[] | undefined;
}

ConnectWithProviderButton.defaultProps = {
    creator: false,
    type: 'dark',
    disabled: false
};

export default function ConnectWithProviderButton(props: ConnectWithProviderButtonProps) {
    const { url, text, type, creator, disabled, fromProPlan } = props;

    if (disabled)
        return (
            <div className="!w-full rounded flex items-center justify-center">
                <ProviderLoginButton disabled={disabled} label={text} type={type} onClick={() => {}} className={'w-full rounded'} />
            </div>
        );

    return (
        <a href={`${url}${creator ? '?creator=true' : ''}${fromProPlan ? '&prospective_pro_user=true' : ''}`} referrerPolicy="unsafe-url" className={`w-full flex items-center justify-start `}>
            <ProviderLoginButton className="!w-full !rounded" disabled={disabled} label={text} type={type} onClick={() => {}} />
        </a>
    );
}
