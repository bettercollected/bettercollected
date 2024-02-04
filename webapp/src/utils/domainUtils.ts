import environments from '@app/configs/environments';

export const isAdminDomain = () => {
    if (!!window) return environments.ADMIN_DOMAIN === window.location.host;
    return false;
};