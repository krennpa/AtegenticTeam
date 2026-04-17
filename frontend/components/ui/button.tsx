import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'
import { Slot } from '@radix-ui/react-slot'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3a8aca] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-[#3a8aca] text-white hover:bg-[#3a8aca]/90 shadow',
        secondary: 'bg-slate-100 text-slate-900 hover:bg-slate-100/80 shadow-sm',
        outline: 'border border-slate-200 bg-transparent hover:bg-slate-50',
        ghost: 'hover:bg-slate-100 hover:text-slate-900',
        destructive: 'bg-red-600 text-white hover:bg-red-600/90',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-lg px-3',
        lg: 'h-11 rounded-lg px-6',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return <Comp className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
