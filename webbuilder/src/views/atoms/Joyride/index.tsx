import React, { useEffect, useState } from 'react';

import Jr, {
    ACTIONS,
    BeaconRenderProps,
    CallBackProps,
    EVENTS,
    LIFECYCLE,
    STATUS,
    Step,
    Styles
} from 'react-joyride';

import { JoyrideState } from '@app/models/dtos/joyride';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { setJoyrideState } from '@app/store/tours/slice';

import BeaconComponent from './JoyrideBeacon';

interface LocalStorageJoyrideState {
    id: string;
    run?: boolean;
    finished?: boolean;
    stepIndex?: number;
}

export interface IJoyrideProps {
    steps: Array<Step>;
    id: string;
    placement?:
        | 'top'
        | 'top-start'
        | 'top-end'
        | 'bottom'
        | 'bottom-start'
        | 'bottom-end'
        | 'left'
        | 'left-start'
        | 'left-end'
        | 'right'
        | 'right-start'
        | 'right-end'
        | 'auto'
        | 'center';
    scrollToFirstStep?: boolean;
    scrollOffset?: number;
    floaterProps?: any;
    styles?: Styles;
    continuous?: boolean;
    showProgress?: boolean;
    spotlightClicks?: boolean;
    showSkipButton?: boolean;
    showCloseButton?: boolean;
    hideBackButton?: boolean;
    disableOverlay?: boolean;
    disableOverlayClose?: boolean;
    hideCloseButton?: boolean;
    firstStepClicked?: boolean;
    disableCloseOnEsc?: boolean;
}

export default function Joyride({
    steps,
    id,
    placement = 'bottom-end',
    floaterProps = { styles: { arrow: { length: 10, spread: 10 } } },
    continuous = true,
    showProgress = true,
    spotlightClicks = true,
    showSkipButton = true,
    showCloseButton = true,
    scrollToFirstStep = false,
    firstStepClicked = false,
    hideBackButton = false,
    disableOverlay = false,
    disableCloseOnEsc = false,
    disableOverlayClose = false,
    hideCloseButton = false,
    scrollOffset = 68,
    styles = {
        tooltip: {
            borderRadius: 4,
            willChange: 'auto'
        },
        tooltipTitle: {
            textAlign: 'start'
        },
        tooltipContent: {
            padding: '16px 0 0 0',
            textAlign: 'start'
        },
        buttonSkip: {
            paddingLeft: 0,
            paddingRight: 0,
            borderRadius: 4
        },
        buttonBack: {
            color: '#495057',
            borderRadius: 4
        },
        buttonClose: {
            color: '#495057',
            borderRadius: 4
        },
        buttonNext: {
            backgroundColor: '#0764EB',
            borderRadius: 4
        },
        overlay: {
            backgroundColor: 'rgba(0, 0, 0, 0.3)'
        },
        beacon: {
            zIndex: 2100
        },
        options: {
            beaconSize: 20,
            zIndex: 2200
        },
        beaconInner: {}, // Add missing property
        beaconOuter: {}, // Add missing property
        overlayLegacy: {}, // Add missing property
        overlayLegacyCenter: {},
        spotlight: {},
        spotlightLegacy: {},
        tooltipContainer: {},
        tooltipFooter: {},
        tooltipFooterSpacer: {}
    }
}: Readonly<IJoyrideProps>) {
    //@ts-ignore
    const dispatch = useAppDispatch();
    const reduxState = useAppSelector((state) => state.joyride.joyrides[id]);

    const [state, setState] = useState<JoyrideState>({
        id: id,
        run: false,
        finished: false,
        stepIndex: 0,
        steps: steps,
        lifecycle: LIFECYCLE.INIT,
        hideBackButton: hideBackButton,
        disableCloseOnEsc: disableCloseOnEsc,
        disableOverlayClose: disableOverlayClose,
        hideCloseButton: hideCloseButton,
        showSkipButton: showSkipButton
    });

    const { run, stepIndex, steps: jrSteps } = state;

    const getFilteredState = ({ steps, ...rest }: JoyrideState) => rest;

    useEffect(() => {
        setState({
            ...state,
            ...reduxState,
            run: reduxState?.finished !== null ? reduxState?.finished : true
        });
        // dispatch(setJoyrideState(getFilteredState(state)));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (firstStepClicked) {
            setState({
                ...state,
                run: true,
                stepIndex: stepIndex === 0 ? 1 : stepIndex,
                disableOverlayClose: disableOverlayClose,
                hideCloseButton: hideCloseButton,
                disableCloseOnEsc: disableCloseOnEsc,
                showSkipButton: showSkipButton,
                hideBackButton: hideBackButton
            });
        }

        return () => {};
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [firstStepClicked]);

    const handleJoyrideCallback = (data: CallBackProps): void => {
        const { action, index, status, type, lifecycle } = data;

        let newState = { ...state, lifecycle };
        let skipStep = true;
        // @ts-ignore
        if ([EVENTS.STEP_AFTER, EVENTS.TARGET_NOT_FOUND].includes(type)) {
            skipStep = false;
            // Update state to advance the tour
            const nextStepIndex = index + (action === ACTIONS.PREV ? -1 : 1);
            newState = { ...newState, stepIndex: nextStepIndex };
        }
        // @ts-ignore
        else if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
            skipStep = false;
            // Need to set our running state to false, so we can restart if we click start again.
            newState = { ...newState, run: false, stepIndex: 0, finished: true };
        }

        if (skipStep) return;
        setState(newState);
        dispatch(setJoyrideState(getFilteredState(newState)));
    };

    if (placement) floaterProps.placement = placement;
    if (showCloseButton) floaterProps.showCloseButton = true;

    return (
        <Jr
            run={run}
            scrollToFirstStep={scrollToFirstStep}
            scrollOffset={scrollOffset}
            // @ts-ignore
            beaconComponent={
                BeaconComponent as unknown as React.ReactElement<BeaconRenderProps>
            }
            continuous={continuous}
            showProgress={showProgress}
            spotlightClicks={spotlightClicks}
            disableOverlay={disableOverlay}
            showSkipButton={showSkipButton}
            floaterProps={floaterProps}
            callback={handleJoyrideCallback}
            stepIndex={stepIndex}
            steps={jrSteps}
            styles={styles}
        />
    );
}
