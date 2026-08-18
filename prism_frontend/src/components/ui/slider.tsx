import React, { useState, useEffect, forwardRef } from 'react';

interface SliderProps {
    /** Current value */
    value?: number;
    /** Minimum value */
    min?: number;
    /** Maximum value */
    max?: number;
    /** Step size */
    step?: number;
    /** Callback when value changes */
    onValueChange?: (value: number) => void;
    /** Optional className for styling */
    className?: string;
}

/**
 * Simple slider component using native `<input type="range">`.
 * Tailwind utilities give it a modern look that matches the rest of the UI.
 */
export const Slider = forwardRef<HTMLInputElement, SliderProps>(
    (
        {
            value = 0,
            min = 0,
            max = 100,
            step = 1,
            onValueChange,
            className = '',
            ...rest
        },
        ref
    ) => {
        const [internal, setInternal] = useState<number>(value);

        // sync external prop changes
        useEffect(() => {
            setInternal(value);
        }, [value]);

        const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            const newVal = Number(e.target.value);
            setInternal(newVal);
            onValueChange?.(newVal);
        };

        return (
            <input
                type="range"
                ref={ref}
                className={`w-full h-2 bg-gray-300 rounded-full appearance-none cursor-pointer ${className}`}
                min={min}
                max={max}
                step={step}
                value={internal}
                onChange={handleChange}
                {...rest}
            />
        );
    }
);

Slider.displayName = 'Slider';
export default Slider;
