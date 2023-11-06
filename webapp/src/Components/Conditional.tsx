import React, { useState } from 'react';

import _ from 'lodash';

import { FieldRequired } from '@Components/UI/FieldRequired';
import { Star, StarBorder } from '@mui/icons-material';

interface IRatingFieldProps {
    field: any;
    id: any;
    position: any;
}

export default function Conditional({ field, id, position }: IRatingFieldProps) {
    const [hovered, setHovered] = useState(-1);

    return (
        <div
            tabIndex={0}
            id={id}
            className="flex w-[800px] p-4 border-2 border-dashed border-black-300 rounded-lg"
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
