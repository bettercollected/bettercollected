
import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { UserStatus } from '@app/models/dtos/user-status';
import { getFullNameFromUser } from '@app/utils/user-utils';

interface IUserDetailsProps {
    user: UserStatus;
}

export default function UserDetails({ user }: IUserDetailsProps) {
    // A name-less account falls back to the email as its display name —
    // don't print the same email twice, stacked.
    const displayName = getFullNameFromUser(user);
    return (
        <div className="flex items-center space-x-3">
            <AuthAccountProfileImage image={user.profileImage} name={displayName} size={40} />
            <div className="flex flex-col">
                <div className="body3">{displayName}</div>
                {displayName !== user.email && <div className="body5 !text-black-600">{user.email}</div>}
            </div>
        </div>
    );
}