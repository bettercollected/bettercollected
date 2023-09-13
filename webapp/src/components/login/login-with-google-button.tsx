import ProviderLoginButton from './provider-login-btn';

interface ConnectWithProviderButtonProps {
    text: string;
    url: string;
    type?: 'light' | 'dark' | 'typeform';
    creator?: boolean;
    disabled?: boolean;
    prospectiveProUser?: string | string[] | undefined;
}

ConnectWithProviderButton.defaultProps = {
    creator: false,
    type: 'dark',
    disabled: false
};

export default function ConnectWithProviderButton(props: ConnectWithProviderButtonProps) {
    const { url, text, type, creator, disabled, prospectiveProUser } = props;

    if (disabled)
        return (
            <div className="mx-auto w-full flex items-center justify-center">
                <ProviderLoginButton disabled={disabled} label={text} type={type} onClick={() => {}} />
            </div>
        );

    return (
        <a href={`${url}${creator ? '?creator=true' : ''}${prospectiveProUser ? '&prospective_pro_user=true' : ''}`} referrerPolicy="unsafe-url" className={`w-full flex items-center justify-start`}>
            <ProviderLoginButton className={'!w-full !rounded !gap-2 !flex !justify-start'} disabled={disabled} label={text} type={type} onClick={() => {}} />
        </a>
    );
}
