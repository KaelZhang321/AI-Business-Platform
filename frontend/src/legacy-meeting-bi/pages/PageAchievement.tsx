import React from 'react'
import { motion, type Variants } from 'framer-motion'
import AchievementSection from '../components/sections/AchievementSection'
import ProgressSection from '../components/sections/ProgressSection'
import ProposalSection from '../components/sections/ProposalSection'
import { legacyEase } from '../utils/motion'

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: legacyEase },
  }),
}

const PageAchievement: React.FC = () => (
  <div className="goal-page">
    <motion.section className="goal-section goal-panel--top" custom={0} initial="hidden" animate="visible" variants={fadeUp}>
      <AchievementSection />
    </motion.section>

    <motion.section className="goal-section goal-panel--bottom" custom={1} initial="hidden" animate="visible" variants={fadeUp}>
      <div className="goal-panel-head">
        <div className="goal-section-heading">
          <div className="goal-section-heading-title">方案目标 VS 达成</div>
          <div className="goal-section-heading-subtitle">各成交方案目标与达成</div>
        </div>
      </div>

      <div className="goal-grid">
        <motion.div className="goal-grid-item" custom={2} initial="hidden" animate="visible" variants={fadeUp}>
          <ProgressSection fill />
        </motion.div>
        <motion.div className="goal-grid-item" custom={3} initial="hidden" animate="visible" variants={fadeUp}>
          <ProposalSection showOverview showCross={false} showSectionTitle={false} />
        </motion.div>
      </div>
    </motion.section>
  </div>
)

export default PageAchievement
