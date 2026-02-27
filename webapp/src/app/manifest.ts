import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
    return {
        name: 'BetterCollected',
        short_name: 'BetterCollected',
        description: 'Privacy-friendly form builder and data collection platform',
        start_url: '/',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#0764EB',
        orientation: 'portrait',
        icons: [
            {
                src: '/favicon.ico',
                sizes: 'any',
                type: 'image/x-icon'
            },
            {
                src: '/icons/icon-192x192.png',
                sizes: '192x192',
                type: 'image/png',
                purpose: 'maskable'
            },
            {
                src: '/icons/icon-512x512.png',
                sizes: '512x512',
                type: 'image/png',
                purpose: 'any'
            }
        ]
    };
}
