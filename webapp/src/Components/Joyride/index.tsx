import React, { useEffect, useState } from 'react';

import JR, { ACTIONS, BeaconRenderProps, CallBackProps, EVENTS, Props as JoyRideState, STATUS, Step, Styles } from 'react-joyride';

import BeaconComponent from './JoyrideBeacon';

interface IJoyrideProps {
    steps: Array<Step>;
    id: string;
    scrollToFirstStep?: boolean;
    scrollOffset?: number;
    floaterProps?: any;
    styles?: Styles;
    continuous?: boolean;
    showProgress?: boolean;
    spotlightClicks?: boolean;
    showSkipButton?: boolean;
}

export default function Joyride({
    steps,
    id,
    continuous = true,
    showProgress = true,
    spotlightClicks = true,
    showSkipButton = true,
    scrollToFirstStep = false,
    scrollOffset = 68,
    floaterProps = { placement: 'bottom-end', showCloseButton: true, styles: { arrow: { length: 10, spread: 10 } } },
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
            beaconSize: 12,
            zIndex: 3100
        }
    }
}: IJoyrideProps) {
    const [state, setState] = useState<JoyRideState>({
        run: false,
        stepIndex: 0,
        steps: steps
    });

    const { run, stepIndex, steps: jrSteps } = state;

    useEffect(() => {
        // Fetch from localStorage and check if the tour should be displayed
        // set `run` to false if it has already been displayed
        setState({ ...state, run: true });
    }, [id]);

    const handleJoyrideCallback = (data: CallBackProps): void => {
        const { action, index, status, type } = data;

        const TARGET_NOT_FOUND = EVENTS.TARGET_NOT_FOUND;

        // @ts-ignore
        if ([EVENTS.STEP_AFTER, TARGET_NOT_FOUND].includes(type)) {
            // Update state to advance the tour
            setState({ ...state, stepIndex: index + (action === ACTIONS.PREV ? -1 : 1) });
        }
        // @ts-ignore
        else if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
            // Need to set our running state to false, so we can restart if we click start again.
            setState({ ...state, run: false });
        }

        console.groupCollapsed(type);
        console.log(data);
        console.groupEnd();
    };

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
