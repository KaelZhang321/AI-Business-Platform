import React from 'react'
import { motion, type Variants } from 'framer-motion'
import RegistrationSection from '../components/sections/RegistrationSection'
import CustomerProfileSection from '../components/sections/CustomerProfileSection'
import CustomerSourceSection from '../components/sections/CustomerSourceSection'
import { legacyEase } from '../utils/motion'

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: legacyEase },
  }),
}

const PageCustomer: React.FC = () => (
  <div>
    <motion.div custom={0} initial="hidden" animate="visible" variants={fadeUp} style={{ marginBottom: 28 }}>
      <RegistrationSection />
    </motion.div>
    <motion.div custom={1} initial="hidden" animate="visible" variants={fadeUp} style={{ marginBottom: 28 }}>
      <CustomerProfileSection />
    </motion.div>
    <motion.div custom={2} initial="hidden" animate="visible" variants={fadeUp}>
      <CustomerSourceSection />
    </motion.div>
  </div>
)

export default PageCustomer
