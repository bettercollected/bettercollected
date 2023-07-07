import { useState } from 'react';

import _ from 'lodash';

import { Star, StarBorder } from '@mui/icons-material';

import { StandardFormQuestionDto } from '@app/models/dtos/form';

export default function RatingField({ field }: { field: StandardFormQuestionDto }) {
    const [hovered, setHovered] = useState(-1);

    const [answer, setAnswer] = useState(-1);

    return (
        <div
            onMouseLeave={() => {
                setHovered(answer);
            }}
        >
            {_.range(field.properties?.steps || 5).map((index) => {
                const Component = index <= hovered ? Star : StarBorder;

                return (
                    <Component
                        fontSize="large"
                        key={index}
                        onClick={() => {
                            setAnswer(index);
                        }}
                        onMouseEnter={() => {
                            setHovered(index);
                        }}
                        className={`${index <= hovered ? 'cursor-pointer text-yellow-500' : 'text-gray-400'} `}
                    />
                );
            })}
        </div>
    );
}
