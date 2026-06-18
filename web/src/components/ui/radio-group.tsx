import * as React from 'react';
import { cn } from '@/lib/utils';

/* ------------------------------------------------------------------ */
/*  Lightweight RadioGroup — no radix dependency, uses native HTML    */
/* ------------------------------------------------------------------ */

const RadioGroupContext = React.createContext<{ value: string; onValueChange: (val: string) => void }>({
  value: '',
  onValueChange: () => {},
});

export interface RadioGroupProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onChange'> {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
}

const RadioGroup = React.forwardRef<HTMLDivElement, RadioGroupProps>(
  ({ className, value, defaultValue, onValueChange, ...props }, ref) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue || '');

    // Controlled or uncontrolled
    const currentValue = value !== undefined ? value : internalValue;

    const handleChange = (newValue: string) => {
      setInternalValue(newValue);
      onValueChange?.(newValue);
    };

    return (
      <RadioGroupContext.Provider value={{ value: currentValue, onValueChange: handleChange }}>
        <div role="radiogroup" ref={ref} className={cn('grid gap-2', className)} {...props} />
      </RadioGroupContext.Provider>
    );
  }
);
RadioGroup.displayName = 'RadioGroup';

interface RadioGroupItemProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value: string;
}

const RadioGroupItem = React.forwardRef<HTMLInputElement, RadioGroupItemProps>(
  ({ className, value, id, disabled, ...props }, ref) => {
    const context = React.useContext(RadioGroupContext);

    return (
      /* Native radio button visually hidden but accessible */
      <input
        type="radio"
        ref={ref}
        id={id}
        value={value}
        checked={context.value === value}
        disabled={disabled}
        onChange={() => context.onValueChange(value)}
        className={cn(
          'h-4 w-4 shrink-0 rounded-full border border-primary text-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        aria-checked={context.value === value}
        {...props}
      />
    );
  }
);
RadioGroupItem.displayName = 'RadioGroupItem';

export { RadioGroup, RadioGroupItem };
