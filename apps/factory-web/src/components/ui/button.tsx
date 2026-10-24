import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const buttonStyles = cva(
  'inline-flex items-center justify-center gap-2 rounded-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-forest disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-forest text-white hover:bg-[#2e5039]',
        outline: 'border border-[#dce3d9] bg-transparent text-[#657662] hover:bg-[#edf2eb]',
        ghost: 'bg-transparent text-[#657662] hover:bg-[#edf2eb]',
      },
      size: { default: 'h-10 px-4 text-xs', sm: 'h-8 px-3 text-[11px]' },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonStyles>

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, ...props },
  ref,
) {
  return <button ref={ref} className={cn(buttonStyles({ variant, size }), className)} {...props} />
})
