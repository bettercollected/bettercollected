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
    if (image) return <Avatar sx={{ width: size, height: size, borderRadius: 1 }} src={image} className="rounded-[4px] overflow-hidden !mr-0" />;

    return <Avatar sx={{ width: size, height: size, borderRadius: 1 }}>{name[0]?.toUpperCase()}</Avatar>;
}
