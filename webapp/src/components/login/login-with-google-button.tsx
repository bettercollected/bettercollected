import { Google } from '@app/components/icons/brands/google';
import environments from '@app/configs/environments';

interface ConnectWithGoogleButtonProps {
    text: string;
    creator?: boolean;
    className?: string;
}

ConnectWithGoogleButton.defaultProps = {
    creator: false,
    className: ''
};

export default function ConnectWithGoogleButton(props: ConnectWithGoogleButtonProps) {
    const { text, creator } = props;

    return (
        <a
            href={`${environments.API_ENDPOINT_HOST}/auth/google/basicAuth${creator ? '?creator=true' : ''}`}
            referrerPolicy="unsafe-url"
            className={`bg-[#1a73e8] hover:bg-blue-600 max-w-[250px] mx-auto flex w-full items-center rounded-2xl p-[2px] ${props.className}`}
        >
            <div className="rounded-full bg-white p-2">
                <Google />
            </div>
            <div className="flex items-center w-full justify-center font-bold text-white text-[12px]">{text}</div>
        </a>
    );
}
