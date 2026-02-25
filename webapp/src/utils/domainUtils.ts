"use client";

export const isAdminDomain = () => {
    if (typeof window !== 'undefined') return window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN === window.location.host;
    return false;
};