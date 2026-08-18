import React, { forwardRef } from 'react';

interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
    /** Optional class name for the scroll container */
    className?: string;
    /** Children to be rendered inside the scrollable area */
    children: React.ReactNode;
}

/**
 * Simple scrollable container component.
 * Uses Tailwind utilities to provide a smooth scrollbar that works well in dark mode.
 * The component forwards its ref to the underlying div for flexibility.
 */
export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
    ({ className = '', children, ...rest }, ref) => {
        return (
            <div
                ref={ref}
                className={`overflow-auto rounded-md ${className}`}
                {...rest}
            >
                {children}
            </div>
        );
    }
);

ScrollArea.displayName = 'ScrollArea';

export default ScrollArea;
