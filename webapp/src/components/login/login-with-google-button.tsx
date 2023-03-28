import ProviderLoginButton from './provider-login-btn';

interface ConnectWithProviderButtonProps {
    text: string;
    url: string;
    type?: 'light' | 'dark' | 'typeform';
    creator?: boolean;
    disabled?: boolean;
}

ConnectWithProviderButton.defaultProps = {
    creator: false,
    type: 'dark',
    disabled: false
};

export default function ConnectWithProviderButton(props: ConnectWithProviderButtonProps) {
    const { url, text, type, creator, disabled } = props;

    if (disabled)
        return (
            <div className="mx-auto w-fit flex items-center justify-center">
                <ProviderLoginButton disabled={disabled} label={text} type={type} onClick={() => {}} />
            </div>
        );

    return (
        <a href={`${url}${creator ? '?creator=true' : ''}`} referrerPolicy="unsafe-url" className={`mx-auto w-fit flex items-center justify-center`}>
            <ProviderLoginButton disabled={disabled} label={text} type={type} onClick={() => {}} />
        </a>
    );
}
