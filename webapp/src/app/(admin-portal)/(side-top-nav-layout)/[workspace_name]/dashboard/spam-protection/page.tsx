'use client';

import SpamCheckSettings from '@app/components/captcha/spam-check-settings';

/** Workspace settings, "Spam protection": whether the workspace's forms ask for the automatic spam check by default (docs/captcha.md). */
export default function SpamProtectionPage() {
    return <SpamCheckSettings />;
}
