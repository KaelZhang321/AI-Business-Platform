import React from 'react'
import { motion, type Variants } from 'framer-motion'
import OperationsSection from '../components/sections/OperationsSection'
import { legacyEase } from '../utils/motion'

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: legacyEase } },
}

const PageOperations: React.FC = () => (
  <motion.div initial="hidden" animate="visible" variants={fadeUp}>
    <OperationsSection />
  </motion.div>
)

export default PageOperations
