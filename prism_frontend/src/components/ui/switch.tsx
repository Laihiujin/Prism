import React, { forwardRef } from 'react';

interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {
    /** Whether the switch is on */
    checked?: boolean;
    /** Callback when toggled */
    onCheckedChange?: (checked: boolean) => void;
    /** Optional class name */
    className?: string;
}

/**
 * Simple toggle switch component.
 * Uses Tailwind CSS for a sleek appearance and works in dark mode.
 */
export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
    ({ checked, onCheckedChange, className = '', ...rest }, ref) => {
        const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            onCheckedChange?.(e.target.checked);
        };
        return (
            <label className={`inline-flex items-center cursor-pointer ${className}`}>
                <input
                    type="checkbox"
                    ref={ref}
                    className="sr-only"
                    checked={checked}
                    onChange={handleChange}
                    {...rest}
                />
                <span className="relative w-10 h-5 bg-gray-400 rounded-full transition-colors duration-200">
                    <span className="absolute left-0 top-0 w-5 h-5 bg-white rounded-full shadow transform transition-transform duration-200"
                        style={{ transform: checked ? 'translateX(20px)' : 'translateX(0)' }} />
                </span>
            </label>
        );
    }
);

Switch.displayName = 'Switch';

export default Switch;
