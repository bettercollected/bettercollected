import React, { useState } from 'react';

import _ from 'lodash';

import { FieldRequired } from '@Components/UI/FieldRequired';
import { Star, StarBorder } from '@mui/icons-material';

interface IRatingFieldProps {
    field: any;
    id: any;
}

export default function RatingField({ field, id }: IRatingFieldProps) {
    const [hovered, setHovered] = useState(-1);

    return (
        <div
            tabIndex={0}
            id={id}
            className="flex relative gap-3 w-fit flex-wrap outline-none"
            onMouseLeave={() => {
                setHovered(-1);
            }}
        >
            {field?.validations?.required && <FieldRequired className="top-2 -right-5" />}{' '}
            {_.range(field.properties?.steps || 5).map((index) => {
                const Component = index <= hovered ? Star : StarBorder;
                return (
                    <Component
                        fontSize="large"
                        key={index}
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
