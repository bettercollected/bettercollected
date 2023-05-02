import { Avatar } from '@mui/material';

interface IAuthAccountProfileImageProps {
    size?: number;
    image?: string;
    name: string;
}

AuthAccountProfileImage.defaultProps = {
    size: 36
};
export default function AuthAccountProfileImage({ size, image, name }: IAuthAccountProfileImageProps) {
    if (image) return <Avatar sx={{ width: size, height: size, borderRadius: 1 }} variant="rounded" src={image} className="rounded overflow-hidden" />;

    return (
        <Avatar sx={{ width: size, height: size, borderRadius: 1 }} variant="rounded" className="rounded sh1 !bg-brand-400 !text-white overflow-hidden">
            <span>{name[0]?.toUpperCase()}</span>
        </Avatar>
    );
}
