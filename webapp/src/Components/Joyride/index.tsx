import React, { useEffect, useState } from 'react';

import JR, { ACTIONS, BeaconRenderProps, CallBackProps, EVENTS, Props as JoyRideState, STATUS, Step, Styles } from 'react-joyride';

import { useLocalStorage } from '@app/lib/hooks/use-local-storage';

import BeaconComponent from './JoyrideBeacon';

export interface JoyrideState extends JoyRideState {
    id: string;
    finished: boolean;
}

interface LocalStorageJoyrideState {
    id: string;
    run?: boolean;
    finished?: boolean;
    stepIndex?: number;
}

export interface IJoyrideProps {
    steps: Array<Step>;
    id: string;
    placement?: 'top' | 'top-start' | 'top-end' | 'bottom' | 'bottom-start' | 'bottom-end' | 'left' | 'left-start' | 'left-end' | 'right' | 'right-start' | 'right-end' | 'auto' | 'center';
    scrollToFirstStep?: boolean;
    saveToLocalStorage?: boolean;
    scrollOffset?: number;
    floaterProps?: any;
    styles?: Styles;
    continuous?: boolean;
    showProgress?: boolean;
    spotlightClicks?: boolean;
    showSkipButton?: boolean;
    showCloseButton?: boolean;
    hideBackButton?: boolean;
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
    saveToLocalStorage = false,
    showProgress = true,
    spotlightClicks = true,
    showSkipButton = true,
    showCloseButton = true,
    scrollToFirstStep = false,
    firstStepClicked = false,
    hideBackButton = false,
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
        options: {
            beaconSize: 20,
            zIndex: 3000
        }
    }
}: IJoyrideProps) {
    const [state, setState] = useState<JoyrideState>({
        id: id,
        run: false,
        finished: false,
        stepIndex: 0,
        steps: steps,
        hideBackButton: hideBackButton,
        disableCloseOnEsc: disableCloseOnEsc,
        disableOverlayClose: disableOverlayClose,
        hideCloseButton: hideCloseButton,
        showSkipButton: showSkipButton
    });

    const { run, stepIndex, steps: jrSteps } = state;
    const localStorageJoyrideId = `joyride:id:${id}`;

    const getFilteredState = ({ id, run, stepIndex, finished }: JoyrideState): LocalStorageJoyrideState => {
        return { id, run, stepIndex, finished };
    };

    const [localStorageJoyrideState, setLocalStorageJoyrideState] = useLocalStorage(localStorageJoyrideId, getFilteredState(state));

    useEffect(() => {
        if (saveToLocalStorage) setState({ ...state, ...localStorageJoyrideState, run: !localStorageJoyrideState?.finished });
        else setState({ ...state, run: true });
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
        const { action, index, status, type } = data;

        let newState = { ...state };
        // @ts-ignore
        if ([EVENTS.STEP_AFTER, EVENTS.TARGET_NOT_FOUND].includes(type)) {
            // Update state to advance the tour
            const nextStepIndex = index + (action === ACTIONS.PREV ? -1 : 1);
            newState = { ...newState, stepIndex: nextStepIndex };
            setState(newState);
        }
        // @ts-ignore
        else if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
            // Need to set our running state to false, so we can restart if we click start again.
            newState = { ...newState, run: false, stepIndex: 0, finished: true };
            setState(newState);
        }

        if (saveToLocalStorage) setLocalStorageJoyrideState(getFilteredState(newState));
    };

    if (placement) floaterProps.placement = placement;
    if (showCloseButton) floaterProps.showCloseButton = true;

    return (
        <JR
            run={run}
            scrollToFirstStep={scrollToFirstStep}
            scrollOffset={scrollOffset}
            // @ts-ignore
            beaconComponent={BeaconComponent as unknown as React.ReactElement<BeaconRenderProps>}
            continuous={continuous}
            showProgress={showProgress}
            spotlightClicks={spotlightClicks}
            showSkipButton={showSkipButton}
            floaterProps={floaterProps}
            callback={handleJoyrideCallback}
            stepIndex={stepIndex}
            steps={jrSteps}
            styles={styles}
        />
    );
}
