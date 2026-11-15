'use client';

import React from 'react';

import DaybreakArt from '@app/components/ui/daybreak-art';
import PigmentAppArt, { PigmentAppArtVariant } from '@app/components/ui/pigment-app-art';
import { AppTheme } from '@app/lib/app-theme';
import { useAppTheme } from '@app/lib/app-theme-context';

/**
 * The picture of the creator app's three moments (welcome band, empty states, publish dialog), drawn in the app theme
 * in scope: Pigment's flat shapes in a Pigment workspace, the Daybreak sun and hills everywhere else (Daybreak, and
 * any page without a scope), exactly as before. The scope is read from context, which `AppThemeScope` fills in the
 * server render, so there is no frame in the wrong picture.
 *
 * The publish dialog is portalled out of the workspace layout and cannot read the scope: it passes the workspace
 * theme it already holds in the store as `theme`.
 */
export default function AppArt({
    variant = 'panel',
    spark,
    theme
}: {
    variant?: PigmentAppArtVariant;
    /** Off where a control sits at the corner of the panel: Daybreak leaves the coral spark out, Pigment the ring. */ spark?: boolean;
    theme?: AppTheme | null;
}) {
    const inScope = useAppTheme();
    const resolved = theme ?? inScope;
    return resolved === 'pigment' ? <PigmentAppArt variant={variant} corner={spark !== false} /> : <DaybreakArt spark={spark} />;
}
