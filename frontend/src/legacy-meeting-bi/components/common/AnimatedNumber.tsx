import { useEffect, type CSSProperties, type FC } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'

interface AnimatedNumberProps {
  value: number
  prefix?: string
  unit?: string
  duration?: number
  style?: CSSProperties
  unitStyle?: CSSProperties
}

const AnimatedNumber: FC<AnimatedNumberProps> = ({
  value,
  prefix = '',
  unit = '',
  duration = 1.5,
  style,
  unitStyle,
}) => {
  const spring = useSpring(0, { duration: duration * 1000 })
  const display = useTransform(spring, (v) => {
    if (value >= 10000) {
      return `${prefix}${(v / 10000).toFixed(2)}`
    }
    if (Number.isInteger(value)) {
      return `${prefix}${Math.round(v).toLocaleString()}`
    }
    return `${prefix}${v.toFixed(2)}`
  })

  const displayUnit = value >= 10000 ? `万${unit}` : unit

  useEffect(() => {
    spring.set(value)
  }, [value, spring])

  if (!unitStyle) {
    return (
      <span style={style}>
        <motion.span>{display}</motion.span>{displayUnit}
      </span>
    )
  }

  return (
    <span style={{ display: 'flex', alignItems: 'baseline' }}>
      <motion.span style={style}>{display}</motion.span>
      {displayUnit && <span style={unitStyle}>{displayUnit}</span>}
    </span>
  )
}

export default AnimatedNumber
